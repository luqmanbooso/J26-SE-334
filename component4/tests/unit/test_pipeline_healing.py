from __future__ import annotations

from types import SimpleNamespace

from c4.config import TargetAppConfig
from c4.execution.models import ExecutionResult, ExecutionStatus, FailureInfo, FailureKind
from c4.healing.service import HealingOutcome
from c4.pipeline import Pipeline
from c4.synthesis.service import SynthesisResult
from c4.schemas import EventSource


class FakeIngestion:
    def __init__(self):
        self.source = None

    def parse_file(self, path, source):
        self.source = source
        return ["event"]


class FakeSessionization:
    def process(self, events):
        return [SimpleNamespace(journey_id="journey")]


class FakeSynthesis:
    def synthesize(self, journey):
        return SynthesisResult(
            journey_id="journey",
            status="generated",
            steps=[],
            script="def step_0(driver):\n    driver.back()\n",
            attempts=[],
            c3_used=False,
            prompt_version="test",
            model=None,
            elapsed_seconds=0.0,
        )


def _execution(kind: FailureKind | None) -> ExecutionResult:
    return ExecutionResult(
        run_id="journey",
        journey_id="journey",
        status=ExecutionStatus.FAILED if kind else ExecutionStatus.PASSED,
        started_at="2026-01-01T00:00:00Z",
        elapsed_seconds=0.0,
        failure=FailureInfo(kind=kind) if kind else None,
    )


class FakeExecution:
    def __init__(self, kind: FailureKind | None):
        self.kind = kind

    def execute(self, *args, **kwargs):
        return _execution(self.kind)


class FakeHealer:
    def __init__(self, status: str):
        self.status = status

    def heal_and_rerun(self, *args, **kwargs):
        return HealingOutcome(final_status=self.status)


def _pipeline(execution, healer, ingestion=None):
    return Pipeline(
        object(),
        TargetAppConfig(package="com.example", activity="MainActivity"),
        ingestion=ingestion or FakeIngestion(),
        sessionization=FakeSessionization(),
        synthesis=FakeSynthesis(),
        execution=execution,
        healer=healer,
        use_c3=False,
    )


def test_pipeline_records_healed_and_refused_outcomes(tmp_path) -> None:
    healed = _pipeline(
        FakeExecution(FailureKind.LOCATOR_NOT_FOUND),
        FakeHealer("passed_after_healing"),
    ).run("telemetry.json", tmp_path / "healed")
    refused = _pipeline(
        FakeExecution(FailureKind.LOCATOR_NOT_FOUND),
        FakeHealer("refused"),
    ).run("telemetry.json", tmp_path / "refused")

    assert healed[0].status == "healed"
    assert refused[0].status == "heal_refused"


def test_pipeline_does_not_heal_non_locator_failures(tmp_path) -> None:
    records = _pipeline(
        FakeExecution(FailureKind.SCRIPT_ERROR),
        FakeHealer("passed_after_healing"),
    ).run("telemetry.json", tmp_path / "runs")

    assert records[0].status == "executed"
    assert records[0].healing is None


def test_pipeline_dispatches_selected_telemetry_source(tmp_path) -> None:
    ingestion = FakeIngestion()
    _pipeline(FakeExecution(None), None, ingestion=ingestion).run(
        "telemetry.json", tmp_path / "sentry", source=EventSource.SENTRY
    )
    assert ingestion.source is EventSource.SENTRY

    _pipeline(FakeExecution(None), None, ingestion=ingestion).run(
        "telemetry.json", tmp_path / "crashlytics", source=EventSource.CRASHLYTICS
    )
    assert ingestion.source is EventSource.CRASHLYTICS
