"""Thread-friendly orchestration for the Component 4 desktop demo."""

from __future__ import annotations

import difflib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from c4.config import load_target_config
from c4.c3_interface.mock_client import MockC3Client
from c4.execution.models import ExecutionResult
from c4.execution.service import ExecutionService
from c4.healing.engine import HealingEngine
from c4.healing.models import HealingConfig
from c4.healing.semantic import Embedder, LexicalEmbedder, SentenceBertEmbedder
from c4.ingestion import TelemetryIngestionService
from c4.journeys.export import journey_to_document, load_journeys, write_journeys
from c4.schemas import EventSource, FailureJourney
from c4.sessionization import SessionizationService
from c4.synthesis.qwen_client import OllamaQwenClient
from c4.synthesis.service import SynthesisResult, SynthesisService


@dataclass
class PreflightView:
    adb: bool = False
    device: bool = False
    appium: bool = False
    package: bool = False
    ollama: bool = False
    c3: bool = False
    problems: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class StepView:
    index: int
    action: str
    name: str
    screen: str | None
    locator: dict[str, str]


@dataclass
class JourneyView:
    id: str = ""
    failing_screen: str | None = None
    steps: int = 0
    reproducible: bool = False
    hints: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class TestView:
    status: str
    script: str = ""
    attempts: int = 0
    c3_status: str = "not_requested"
    error: str | None = None


@dataclass
class RunView:
    status: str
    failing_step: int | None = None
    failure_kind: str | None = None
    run_folder: str | None = None
    artifact_paths: list[str] = field(default_factory=list)
    error: str | None = None
    execution_result: ExecutionResult | None = field(default=None, repr=False)
    synthesis_result: SynthesisResult | None = field(default=None, repr=False)


@dataclass
class HealView:
    status: str
    original_locator: dict[str, str] = field(default_factory=dict)
    healed_locator: dict[str, str] | None = None
    confidence: float | None = None
    margin: float | None = None
    threshold: float = 0.0
    candidates_total: int = 0
    candidates_after_narrowing: int = 0
    rule_counts: dict[str, int] = field(default_factory=dict)
    top_candidates: list[dict[str, Any]] = field(default_factory=list)
    healed_script_diff: str = ""
    rerun_status: str | None = None
    versions: list[int] = field(default_factory=list)
    error: str | None = None


class C4DemoController:
    """Stateful adapter that keeps UI concerns out of the C4 services."""

    def __init__(
        self,
        *,
        llm: Any | None = None,
        execution_service: ExecutionService | None = None,
        embedder: Embedder | None = None,
        c3_client: Any | None = None,
    ) -> None:
        self.llm = llm
        self.execution_service = execution_service
        self.embedder = embedder
        self.c3_client = c3_client
        self.journeys: dict[str, FailureJourney] = {}
        self.syntheses: dict[str, SynthesisResult] = {}

    def preflight(self, config_path: str) -> PreflightView:
        try:
            target = load_target_config(config_path)
            service = self.execution_service or ExecutionService(target=target)
            report = service.preflight(target)
            ollama_url = getattr(self.llm, "base_url", "http://127.0.0.1:11434")
            ollama = self._probe_ollama(ollama_url)
            problems = list(report.problems)
            if not ollama:
                problems.append("Ollama is not reachable")
            return PreflightView(
                adb=report.adb_available,
                device=report.device_ready,
                appium=report.appium_reachable,
                package=report.package_installed,
                ollama=ollama,
                c3=self.c3_client is not None,
                problems=problems,
            )
        except Exception as error:
            return PreflightView(error=str(error), problems=[str(error)])

    def create_journeys(self, telemetry_path: str, source: str, out_dir: str) -> list[JourneyView]:
        try:
            events = TelemetryIngestionService().parse_file(telemetry_path, EventSource(source))
            journeys = SessionizationService().process(events)
            write_journeys(journeys, out_dir)
            self.journeys = {journey.journey_id: journey for journey in journeys}
            return [self._journey_view(journey) for journey in journeys]
        except Exception as error:
            return [JourneyView(error=str(error))]

    def journey_steps(self, journey_id: str) -> list[StepView]:
        try:
            journey = self._journey(journey_id)
            return [
                StepView(index=index, action=event.action or "unknown", name=event.name,
                         screen=event.screen, locator=dict(event.locator))
                for index, event in enumerate(journey.events)
            ]
        except Exception as error:
            return [StepView(index=-1, action="error", name=str(error), screen=None, locator={})]

    def export_seed(self, journey_id: str, out_path: str) -> str:
        try:
            journey = self._journey(journey_id)
            target = Path(out_path)
            if target.suffix.lower() == ".json":
                target.parent.mkdir(parents=True, exist_ok=True)
                document = journey_to_document(journey)
                target.write_text(json.dumps(document.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
                return str(target)
            written = write_journeys([journey], target)
            return str(next(written.glob("*.json")))
        except Exception as error:
            return f"ERROR: {error}"

    def generate_test(
        self, journey_id: str, model: str, ollama_url: str, use_c3: bool, config_path: str
    ) -> TestView:
        try:
            journey = self._journey(journey_id)
            target = load_target_config(config_path)
            llm = self.llm or OllamaQwenClient(base_url=ollama_url, model=model)
            service = SynthesisService(
                llm, target=target, use_c3=use_c3,
                c3_client=self.c3_client if use_c3 else None,
            )
            result = service.synthesize(journey)
            self.syntheses[journey_id] = result
            return TestView(result.status, result.script or "", len(result.attempts), result.c3_status, result.reason)
        except Exception as error:
            return TestView("error", error=str(error))

    def run_test(self, journey_id: str, config_path: str, runs_dir: str = "runs", **_: Any) -> RunView:
        try:
            synthesis = self.syntheses.get(journey_id)
            if synthesis is None:
                generated = self.generate_test(journey_id, "qwen3:8b", "http://127.0.0.1:11434", False, config_path)
                if generated.error:
                    return RunView("error", error=generated.error)
                synthesis = self.syntheses[journey_id]
            target = load_target_config(config_path)
            service = self.execution_service or ExecutionService(target=target)
            result = service.execute(synthesis, runs_dir=runs_dir)
            folder = str(Path(runs_dir) / result.run_id)
            artifacts = [str(path) for path in Path(folder).glob("*")] if Path(folder).exists() else []
            return RunView(
                result.status.value,
                result.failure.step_index if result.failure else None,
                result.failure.kind.value if result.failure else None,
                folder, artifacts, execution_result=result, synthesis_result=synthesis,
            )
        except Exception as error:
            return RunView("error", error=str(error))

    def heal_last_failure(self, run_view: RunView, embedder: Embedder | str | None = None, threshold: float = 0.5) -> HealView:
        try:
            result = run_view.execution_result
            synthesis = run_view.synthesis_result
            if result is None or synthesis is None or result.failure is None:
                return HealView("not_applicable", error="No failed execution is available")
            failure = result.failure
            if not failure.page_source_path or not Path(failure.page_source_path).exists():
                return HealView("not_applicable", error="The failure has no page source artifact")
            selected = self._embedder(embedder)
            decision = HealingEngine(HealingConfig(embedder=selected.name, confidence_threshold=threshold), selected).heal(
                synthesis.script or "", failure.step_index or 0,
                Path(failure.page_source_path).read_text(encoding="utf-8"),
            )
            return self._heal_view(decision, synthesis.script or "")
        except Exception as error:
            return HealView("error", error=str(error))

    def offline_heal(
        self, script_path: str, step_index: int, new_hierarchy_path: str,
        baseline_hierarchy_path: str | None = None, embedder: Embedder | str | None = None,
    ) -> HealView:
        try:
            script = Path(script_path).read_text(encoding="utf-8")
            selected = self._embedder(embedder)
            config = HealingConfig(embedder=selected.name)
            decision = HealingEngine(config, selected).heal(
                script, step_index, Path(new_hierarchy_path).read_text(encoding="utf-8"),
                baseline_hierarchy_xml=(
                    Path(baseline_hierarchy_path).read_text(encoding="utf-8")
                    if baseline_hierarchy_path else None
                ),
            )
            return self._heal_view(decision, script)
        except Exception as error:
            return HealView("error", error=str(error))

    def _journey(self, journey_id: str) -> FailureJourney:
        if journey_id not in self.journeys:
            raise ValueError(f"Unknown journey: {journey_id}")
        return self.journeys[journey_id]

    @staticmethod
    def _journey_view(journey: FailureJourney) -> JourneyView:
        return JourneyView(
            journey.journey_id, journey.metadata.get("failing_screen") or journey.failure.screen,
            len(journey.events), bool(journey.metadata.get("reproducible")),
            [hint.reason for hint in journey_to_document(journey).seed.perturbation_hints],
        )

    def _embedder(self, value: Embedder | str | None) -> Embedder:
        selected = value or self.embedder or "lexical"
        if isinstance(selected, str):
            return LexicalEmbedder() if selected == "lexical" else SentenceBertEmbedder(
                "sentence-transformers/all-MiniLM-L6-v2"
            )
        return selected

    @staticmethod
    def _probe_ollama(url: str) -> bool:
        try:
            with urlopen(f"{url.rstrip('/')}/api/tags", timeout=0.5):
                return True
        except Exception:
            return False

    @staticmethod
    def _heal_view(decision: Any, original: str) -> HealView:
        healed = decision.healed_script or ""
        top = [
            {"node_index": item.node_index, "score": item.score,
             "locator": item.locator_preview, "text": item.descriptor.text}
            for item in decision.top_candidates
        ]
        return HealView(
            decision.status.value, decision.original_locator, decision.healed_locator,
            decision.confidence, decision.margin, decision.threshold,
            decision.candidates_total, decision.candidates_after_narrowing,
            dict(decision.rule_counts), top,
            "".join(difflib.unified_diff(original.splitlines(True), healed.splitlines(True),
                                         fromfile="original", tofile="healed")),
        )
