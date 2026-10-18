from __future__ import annotations

import json
from pathlib import Path

from c4.execution.models import (
    ExecutionResult,
    ExecutionStatus,
    FailureInfo,
    FailureKind,
)
from c4.healing.models import HealingConfig, HealingDecision, HealingStatus
from c4.healing.service import HealingService
from c4.synthesis.service import SynthesisResult


SCRIPT = "def step_0(driver):\n    driver.back()\n"


def _synthesis() -> SynthesisResult:
    return SynthesisResult(
        journey_id="journey",
        status="generated",
        steps=[],
        script=SCRIPT,
        attempts=[],
        c3_used=False,
        prompt_version="test",
        model=None,
        elapsed_seconds=0.0,
    )


def _execution(
    run_id: str,
    kind: FailureKind | None,
    page_source_path: str | None = None,
    status: ExecutionStatus = ExecutionStatus.FAILED,
) -> ExecutionResult:
    failure = (
        FailureInfo(
            step_index=0,
            action="tap",
            kind=kind,
            page_source_path=page_source_path,
        )
        if kind is not None
        else None
    )
    return ExecutionResult(
        run_id=run_id,
        journey_id="journey",
        status=status,
        started_at="2026-01-01T00:00:00Z",
        elapsed_seconds=0.0,
        failure=failure,
    )


class FakeEngine:
    config = HealingConfig(embedder="lexical", max_heal_rounds=2)

    def __init__(self, decisions: list[HealingDecision]) -> None:
        self.decisions = iter(decisions)

    def heal(self, *args, **kwargs) -> HealingDecision:
        return next(self.decisions)


class FakeExecutionService:
    def __init__(self, results: list[ExecutionResult]) -> None:
        self.results = iter(results)

    def execute(self, *args, **kwargs) -> ExecutionResult:
        return next(self.results)


def _decision(status: HealingStatus, script: str | None = None) -> HealingDecision:
    return HealingDecision(
        status=status,
        step_index=0,
        action="tap",
        original_locator={"by": "ID", "value": "old"},
        healed_locator={"by": "ID", "value": "new"} if script else None,
        healed_script=script,
        embedder="lexical",
        threshold=0.5,
        latency_ms=0.0,
    )


def test_service_handles_missing_page_source_and_writes_keyword_outcome(tmp_path) -> None:
    outcome = HealingService(
        FakeEngine([]), FakeExecutionService([]), config=HealingConfig(embedder="lexical")
    ).heal_and_rerun(
        _synthesis(),
        _execution("run", FailureKind.LOCATOR_NOT_FOUND, str(tmp_path / "missing.xml")),
        tmp_path / "run",
        "journey",
    )

    assert outcome.final_status == "not_applicable"
    report = json.loads((tmp_path / "run" / "healing_report.json").read_text())
    assert report["final_status"] == "not_applicable"


def test_service_passed_healing_tracks_script_and_round(tmp_path) -> None:
    page = tmp_path / "page.xml"
    page.write_text("<hierarchy />")
    healed = "def step_0(driver):\n    driver.back()\n# healed\n"
    outcome = HealingService(
        FakeEngine([_decision(HealingStatus.HEALED, healed)]),
        FakeExecutionService([_execution("run-heal1", None, status=ExecutionStatus.PASSED)]),
        config=HealingConfig(embedder="lexical"),
    ).heal_and_rerun(
        _synthesis(),
        _execution("run", FailureKind.LOCATOR_NOT_FOUND, str(page)),
        tmp_path / "run",
        "journey",
    )

    assert outcome.final_status == "passed_after_healing"
    assert outcome.final_script_path is not None
    assert Path(outcome.final_script_path).is_file()
    assert len(outcome.rounds) == 1


def test_service_not_needed_and_non_locator_outcomes(tmp_path) -> None:
    service = HealingService(
        FakeEngine([]),
        FakeExecutionService([]),
        config=HealingConfig(embedder="lexical"),
    )
    not_needed = service.heal_and_rerun(
        _synthesis(),
        _execution("run", None, status=ExecutionStatus.FAILED),
        tmp_path / "not-needed",
        "journey",
    )
    not_applicable = service.heal_and_rerun(
        _synthesis(),
        _execution("run", FailureKind.SCRIPT_ERROR),
        tmp_path / "not-applicable",
        "journey",
    )

    assert not_needed.final_status == "not_needed"
    assert not_applicable.final_status == "not_applicable"


def test_service_refusal_and_exhaustion_keep_last_healed_path(tmp_path) -> None:
    page = tmp_path / "page.xml"
    page.write_text("<hierarchy />")
    healed = "def step_0(driver):\n    driver.back()\n"
    refused = HealingService(
        FakeEngine([_decision(HealingStatus.REFUSED_LOW_CONFIDENCE)]),
        FakeExecutionService([]),
        config=HealingConfig(embedder="lexical"),
    ).heal_and_rerun(
        _synthesis(),
        _execution("run", FailureKind.LOCATOR_NOT_FOUND, str(page)),
        tmp_path / "refused",
        "journey",
    )
    exhausted = HealingService(
        FakeEngine(
            [
                _decision(HealingStatus.HEALED, healed),
                _decision(HealingStatus.HEALED, healed + "#2\n"),
            ]
        ),
        FakeExecutionService(
            [
                _execution("run-heal1", FailureKind.LOCATOR_NOT_FOUND, str(page)),
                _execution("run-heal2", FailureKind.LOCATOR_NOT_FOUND, str(page)),
            ]
        ),
        config=HealingConfig(embedder="lexical", max_heal_rounds=2),
    ).heal_and_rerun(
        _synthesis(),
        _execution("run", FailureKind.LOCATOR_NOT_FOUND, str(page)),
        tmp_path / "exhausted",
        "journey",
    )

    assert refused.final_status == "refused"
    assert exhausted.final_status == "failed_after_healing"
    assert exhausted.final_script_path is not None
    assert Path(exhausted.final_script_path).name == "healed_test_v2.py"
