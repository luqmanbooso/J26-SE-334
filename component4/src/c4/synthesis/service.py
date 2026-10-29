"""Orchestration for prompt, model, parsing, grounding, and script generation."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field

from c4.c3_interface.client import C3Client
from c4.c3_interface.contract import C3Verdict
from c4.c3_interface.normalize import normalize_verdict
from c4.config import TargetAppConfig
from c4.schemas import FailureJourney, SynthStep
from c4.synthesis.appium_generator import AppiumScriptGenerator
from c4.synthesis.llm_client import LLMClient
from c4.synthesis.prompt_builder import PromptBuilder
from c4.synthesis.qwen_client import QwenClientError
from c4.synthesis.step_parser import StepParser, StepParsingError


class SynthesisAttempt(BaseModel):
    """Outcome summary for one synthesis model attempt."""

    attempt: int
    error: str | None = None
    response_chars: int = Field(ge=0)
    part: str | None = None


class SynthesisResult(BaseModel):
    """Final synthesis status and generated artifacts."""

    journey_id: str
    status: Literal["generated", "skipped_not_reproducible", "failed", "error"]
    steps: list[SynthStep]
    script: str | None
    attempts: list[SynthesisAttempt]
    c3_used: bool
    prompt_version: str
    model: str | None
    elapsed_seconds: float = Field(ge=0.0)
    reason: str | None = None
    c3_status: Literal[
        "not_requested", "used", "unavailable", "invalid", "no_evidence"
    ] = "not_requested"
    c3_verdict: C3Verdict | None = None


class SynthesisService:
    """Run deterministic synthesis with output-validity retries."""

    def __init__(
        self,
        llm: LLMClient,
        prompt_builder: PromptBuilder | None = None,
        parser: StepParser | None = None,
        generator: AppiumScriptGenerator | None = None,
        c3_client: C3Client | None = None,
        use_c3: bool = True,
        max_attempts: int = 3,
        target: TargetAppConfig | None = None,
        c3_strict: bool = False,
        chunk_size: int | None = 8,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if chunk_size is not None and chunk_size < 1:
            raise ValueError("chunk_size must be at least one")
        self.llm = llm
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.parser = parser or StepParser()
        self.generator = generator or AppiumScriptGenerator()
        self.c3_client = c3_client
        self.use_c3 = use_c3
        self.max_attempts = max_attempts
        self.target = target
        self.c3_strict = c3_strict
        self.chunk_size = chunk_size
        self.progress = progress
        self.last_c3_verdict: C3Verdict | None = None
        self.last_c3_status = "not_requested"

    def synthesize(self, journey: FailureJourney) -> SynthesisResult:
        """Synthesize one journey, skipping journeys known to be unreproducible."""
        started = time.perf_counter()
        model = getattr(self.llm, "model", None)
        if journey.metadata.get("reproducible") is False:
            return self._result(
                journey,
                "skipped_not_reproducible",
                [],
                [],
                False,
                started,
                reason=journey.metadata.get(
                    "not_reproducible_reason", "journey is not reproducible"
                ),
                model=model,
            )
        verdict: C3Verdict | None = None
        c3_status = "not_requested"
        if self.use_c3 and self.c3_client is not None:
            try:
                verdict = self.c3_client.get_verdict(
                journey.session_id, journey.failure, journey
                )
            except Exception as error:
                c3_status = "invalid"
                if self.c3_strict:
                    return self._result(
                        journey, "error", [], [], False, started,
                        model=model, reason=f"C3 invalid response: {error}",
                        c3_status=c3_status,
                    )
            else:
                c3_status = getattr(self.c3_client, "last_status", "used")
                verdict = normalize_verdict(verdict)
                if self.c3_strict and c3_status in {"unavailable", "invalid"}:
                    return self._result(
                        journey, "error", [], [], False, started,
                        model=model,
                        reason=getattr(self.c3_client, "last_error", None)
                        or f"C3 {c3_status}",
                        c3_status=c3_status,
                        c3_verdict=verdict,
                    )
        self.last_c3_verdict = verdict
        self.last_c3_status = c3_status
        # Only real evidence enters the prompt; a placeholder no-evidence verdict must not.
        prompt_verdict = verdict if c3_status == "used" else None
        parts = self._parts(journey)
        attempts: list[SynthesisAttempt] = []
        steps: list[SynthStep] = []
        for number, part in enumerate(parts, start=1):
            label = f"part {number} of {len(parts)}" if len(parts) > 1 else None
            part_steps, error = self._generate(part, prompt_verdict, attempts, label)
            if part_steps is None:
                return self._result(
                    journey, "failed", [], attempts, c3_status == "used", started,
                    model=model, reason=f"{label}: {error}" if label else error,
                    c3_status=c3_status, c3_verdict=verdict,
                )
            steps.extend(part_steps)
        steps = [step.model_copy(update={"index": index}) for index, step in enumerate(steps)]
        try:
            script = self._script(steps)
        except (ValueError, SyntaxError) as error:
            return self._result(
                journey, "failed", [], attempts, c3_status == "used", started,
                model=model, reason=str(error), c3_status=c3_status, c3_verdict=verdict,
            )
        return self._result(
            journey, "generated", steps, attempts, c3_status == "used", started,
            script=script, c3_status=c3_status, c3_verdict=verdict, model=model,
        )

    def _parts(self, journey: FailureJourney) -> list[FailureJourney]:
        """Split a long journey into ordered parts so no single request grows with its length."""
        size = self.chunk_size
        if not size or len(journey.events) <= size:
            return [journey]
        return [
            journey.model_copy(update={"events": journey.events[start:start + size]})
            for start in range(0, len(journey.events), size)
        ]

    def _generate(
        self,
        part: FailureJourney,
        verdict: C3Verdict | None,
        attempts: list[SynthesisAttempt],
        label: str | None,
    ) -> tuple[list[SynthStep] | None, str | None]:
        """Ask the model for one part until its steps pass every check, or attempts run out."""
        base_prompt = self.prompt_builder.build(part, verdict)
        previous_response = ""
        last_error: str | None = None
        name = label or "test steps"
        for attempt_number in range(1, self.max_attempts + 1):
            self._report(f"Generating {name}, attempt {attempt_number} of {self.max_attempts}")
            prompt = (
                base_prompt
                if attempt_number == 1
                else self.prompt_builder.build_retry(
                    base_prompt, last_error or "invalid output", previous_response
                )
            )
            response = ""
            try:
                response = self.llm.generate(prompt)
                previous_response = response
                steps = self.parser.parse(response)
                steps = self.parser.validate_grounding(steps, part)
                steps = self.parser.validate_coverage(steps, part)
                self._script(steps)
            except (QwenClientError, StepParsingError, ValueError, SyntaxError) as error:
                last_error = str(error)
                self._report(f"{name}: attempt {attempt_number} rejected, {last_error[:90]}")
                attempts.append(SynthesisAttempt(
                    attempt=attempt_number, error=last_error,
                    response_chars=len(response), part=label,
                ))
                continue
            attempts.append(SynthesisAttempt(
                attempt=attempt_number, response_chars=len(response), part=label,
            ))
            return steps, None
        return None, last_error

    def _report(self, message: str) -> None:
        """Tell the caller what is running; a failing callback never affects synthesis."""
        if self.progress is not None:
            try:
                self.progress(message)
            except Exception:
                pass

    def _script(self, steps: list[SynthStep]) -> str:
        script = self.generator.generate(
            steps,
            appium_url=self.target.appium_url if self.target else "http://127.0.0.1:4723",
            capabilities=self.target.capabilities() if self.target else None,
        )
        compile(script, "<generated_appium_test>", "exec")
        return script

    def synthesize_many(self, journeys: list[FailureJourney]) -> list[SynthesisResult]:
        """Synthesize journeys in input order."""
        return [self.synthesize(journey) for journey in journeys]

    def _result(
        self,
        journey: FailureJourney,
        status: Literal["generated", "skipped_not_reproducible", "failed", "error"],
        steps: list[SynthStep],
        attempts: list[SynthesisAttempt],
        c3_used: bool,
        started: float,
        *,
        script: str | None = None,
        model: str | None = None,
        reason: str | None = None,
        c3_status: str = "not_requested",
        c3_verdict: C3Verdict | None = None,
    ) -> SynthesisResult:
        return SynthesisResult(
            journey_id=journey.journey_id,
            status=status,
            steps=steps,
            script=script,
            attempts=attempts,
            c3_used=c3_used,
            prompt_version=self.prompt_builder.prompt_version,
            model=model,
            elapsed_seconds=time.perf_counter() - started,
            reason=reason,
            c3_status=c3_status,
            c3_verdict=c3_verdict,
        )
