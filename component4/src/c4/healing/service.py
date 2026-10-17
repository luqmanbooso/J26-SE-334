"""Heal-and-rerun orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from c4.execution.models import ExecutionResult, FailureKind
from c4.execution.service import ExecutionService
from c4.healing.baseline import BaselineStore
from c4.healing.engine import HealingEngine
from c4.healing.models import HealingConfig, HealingDecision, HealingStatus
from c4.store.repository import TestRepository
from c4.synthesis.service import SynthesisResult


class HealingRound(BaseModel):
    """One healing decision and its optional rerun."""

    decision: HealingDecision
    execution: ExecutionResult | None = None


class HealingOutcome(BaseModel):
    """Final outcome of a bounded healing loop."""

    final_status: Literal[
        "not_needed",
        "passed_after_healing",
        "refused",
        "failed_after_healing",
        "not_applicable",
    ]
    rounds: list[HealingRound] = Field(default_factory=list)
    final_script_path: str | None = None
    versions: list[int] = Field(default_factory=list)


class HealingService:
    """Connect pure healing decisions to execution reruns and storage."""

    def __init__(
        self,
        engine: HealingEngine,
        execution_service: ExecutionService,
        baseline_store: BaselineStore | None = None,
        repository: TestRepository | None = None,
        config: HealingConfig | None = None,
    ) -> None:
        self.engine = engine
        self.execution_service = execution_service
        self.baseline_store = baseline_store
        self.repository = repository
        self.config = config or engine.config

    def heal_and_rerun(
        self,
        synthesis_result: SynthesisResult,
        execution_result: ExecutionResult,
        run_dir: Path,
        test_id: str,
    ) -> HealingOutcome:
        """Heal locator failures and rerun each accepted replacement."""
        rounds: list[HealingRound] = []
        versions: list[int] = []
        healed_path: Path | None = None
        current_script = synthesis_result.script
        if current_script is None or execution_result.failure is None:
            return self._write(
                run_dir,
                HealingOutcome(final_status="not_needed", rounds=[], versions=[]),
            )
        if execution_result.failure.kind is not FailureKind.LOCATOR_NOT_FOUND:
            return self._write(
                run_dir,
                HealingOutcome(final_status="not_applicable", rounds=[], versions=[]),
            )
        if self.repository and not self.repository.history(test_id):
            versions.append(
                self.repository.add_version(test_id, current_script, "synthesized", None, None)
            )
        current_execution = execution_result
        for round_number in range(1, self.config.max_heal_rounds + 1):
            failure = current_execution.failure
            if (
                failure is None
                or failure.kind is not FailureKind.LOCATOR_NOT_FOUND
                or not failure.page_source_path
            ):
                status = "passed_after_healing" if current_execution.status.value == "passed" else "not_applicable"
                if current_execution.status.value == "passed":
                    status = "passed_after_healing"
                elif rounds:
                    status = "failed_after_healing"
                else:
                    status = "not_applicable"
                return self._write(
                    run_dir,
                    HealingOutcome(
                        final_status=status,
                        rounds=rounds,
                        final_script_path=str(healed_path) if healed_path else None,
                        versions=versions,
                    ),
                )
            page_source = Path(failure.page_source_path)
            if not page_source.exists():
                return self._write(
                    run_dir,
                    HealingOutcome(
                        final_status="not_applicable" if not rounds else "failed_after_healing",
                        rounds=rounds,
                        final_script_path=str(healed_path) if healed_path else None,
                        versions=versions,
                    ),
                )
            new_xml = page_source.read_text(encoding="utf-8")
            baseline_xml = (
                self.baseline_store.load(test_id, failure.step_index)
                if self.baseline_store and failure.step_index is not None
                else None
            )
            decision = self.engine.heal(
                current_script,
                failure.step_index or 0,
                new_xml,
                baseline_hierarchy_xml=baseline_xml,
            )
            if decision.status is not HealingStatus.HEALED or not decision.healed_script:
                rounds.append(HealingRound(decision=decision))
                return self._write(
                    run_dir,
                    HealingOutcome(
                        final_status="refused",
                        rounds=rounds,
                        final_script_path=str(healed_path) if healed_path else None,
                        versions=versions,
                    ),
                )
            healed_path = run_dir / f"healed_test_v{round_number}.py"
            run_dir.mkdir(parents=True, exist_ok=True)
            healed_path.write_text(decision.healed_script, encoding="utf-8")
            if self.repository:
                parent = versions[-1] if versions else None
                versions.append(
                    self.repository.add_version(
                        test_id,
                        decision.healed_script,
                        f"healing round {round_number}",
                        parent,
                        decision,
                    )
                )
            rerun_synthesis = synthesis_result.model_copy(
                update={"script": decision.healed_script}
            )
            current_execution = self.execution_service.execute(
                rerun_synthesis,
                runs_dir=run_dir.parent,
                run_id=f"{execution_result.run_id}-heal{round_number}",
            )
            rounds.append(HealingRound(decision=decision, execution=current_execution))
            current_script = decision.healed_script
            if current_execution.status.value == "passed":
                return self._write(
                    run_dir,
                    HealingOutcome(
                        final_status="passed_after_healing",
                        rounds=rounds,
                        final_script_path=str(healed_path),
                        versions=versions,
                    ),
                )
        return self._write(
            run_dir,
            HealingOutcome(
                final_status="failed_after_healing",
                rounds=rounds,
                final_script_path=str(healed_path) if healed_path else None,
                versions=versions,
            ),
        )

    @staticmethod
    def _write(run_dir: Path, outcome: HealingOutcome) -> HealingOutcome:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "healing_report.json").write_text(
            json.dumps(outcome.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return outcome
