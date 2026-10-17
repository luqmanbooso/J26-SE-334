"""Orchestration for prompt, model, parsing, grounding, and script generation."""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, Field

from c4.c3_interface.client import C3Client
from c4.c3_interface.contract import C3Verdict
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


class SynthesisResult(BaseModel):
    """Final synthesis status and generated artifacts."""

    journey_id: str
    status: Literal["generated", "skipped_not_reproducible", "failed"]
    steps: list[SynthStep]
    script: str | None
    attempts: list[SynthesisAttempt]
    c3_used: bool
    prompt_version: str
    model: str | None
    elapsed_seconds: float = Field(ge=0.0)
    reason: str | None = None


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
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        self.llm = llm
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.parser = parser or StepParser()
        self.generator = generator or AppiumScriptGenerator()
        self.c3_client = c3_client
        self.use_c3 = use_c3
        self.max_attempts = max_attempts
        self.target = target

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
        if self.use_c3 and self.c3_client is not None:
            verdict = self.c3_client.get_verdict(
                journey.session_id, journey.failure, journey
            )
        base_prompt = self.prompt_builder.build(journey, verdict)
        attempts: list[SynthesisAttempt] = []
        previous_response = ""
        last_error: str | None = None
        for attempt_number in range(1, self.max_attempts + 1):
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
                steps = self.parser.validate_grounding(steps, journey)
                script = self.generator.generate(
                    steps,
                    appium_url=self.target.appium_url if self.target else "http://127.0.0.1:4723",
                    capabilities=self.target.capabilities() if self.target else None,
                )
                compile(script, "<generated_appium_test>", "exec")
            except (QwenClientError, StepParsingError, ValueError, SyntaxError) as error:
                last_error = str(error)
                attempts.append(
                    SynthesisAttempt(
                        attempt=attempt_number,
                        error=last_error,
                        response_chars=len(response),
                    )
                )
                continue
            attempts.append(
                SynthesisAttempt(
                    attempt=attempt_number,
                    response_chars=len(response),
                )
            )
            return self._result(
                journey,
                "generated",
                steps,
                attempts,
                verdict is not None,
                started,
                script=script,
                model=model,
            )
        return self._result(
            journey,
            "failed",
            [],
            attempts,
            verdict is not None,
            started,
            model=model,
            reason=last_error,
        )

    def synthesize_many(self, journeys: list[FailureJourney]) -> list[SynthesisResult]:
        """Synthesize journeys in input order."""
        return [self.synthesize(journey) for journey in journeys]

    def _result(
        self,
        journey: FailureJourney,
        status: Literal["generated", "skipped_not_reproducible", "failed"],
        steps: list[SynthStep],
        attempts: list[SynthesisAttempt],
        c3_used: bool,
        started: float,
        *,
        script: str | None = None,
        model: str | None = None,
        reason: str | None = None,
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
        )
