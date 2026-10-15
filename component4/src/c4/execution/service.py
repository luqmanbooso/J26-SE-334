"""Execution orchestration for synthesized tests."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from c4.execution.appium_runner import AppiumRunner
from c4.execution.models import ExecutionAttempt, ExecutionResult, ExecutionStatus
from c4.execution.retry import ExecutionRetryConfig
from c4.synthesis.service import SynthesisResult


class ExecutionService:
    """Persist and execute generated scripts with bounded retries."""

    def __init__(
        self,
        runner: AppiumRunner | None = None,
        retry_config: ExecutionRetryConfig | None = None,
    ) -> None:
        self.runner = runner or AppiumRunner()
        self.retry_config = retry_config or ExecutionRetryConfig()

    def execute(
        self,
        synthesis: SynthesisResult,
        *,
        runs_dir: str | Path = "runs",
        run_id: str | None = None,
    ) -> ExecutionResult:
        """Execute a generated synthesis result and persist run artifacts."""
        started_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        run_name = run_id or uuid4().hex
        run_dir = Path(runs_dir) / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        if synthesis.status != "generated" or synthesis.script is None:
            status = ExecutionStatus.SKIPPED
            reason = synthesis.reason or f"synthesis status: {synthesis.status}"
            result = ExecutionResult(
                run_id=run_name,
                journey_id=synthesis.journey_id,
                status=status,
                started_at=started_at,
                elapsed_seconds=time.perf_counter() - started,
                error_type="SynthesisNotExecutable",
                error_message=reason,
            )
            self._write_result(run_dir, result)
            return result

        script_path = run_dir / "synthesized_test.py"
        script_path.write_text(synthesis.script, encoding="utf-8")
        attempts: list[ExecutionAttempt] = []
        for attempt_number in range(1, self.retry_config.max_attempts + 1):
            attempt = self.runner.run(
                script_path,
                attempt=attempt_number,
                timeout_seconds=self.retry_config.timeout_seconds,
                stdout_path=run_dir / f"attempt-{attempt_number}.stdout.log",
                stderr_path=run_dir / f"attempt-{attempt_number}.stderr.log",
            )
            attempts.append(attempt)
            if attempt.status is ExecutionStatus.PASSED:
                break

        final_attempt = attempts[-1]
        result = ExecutionResult(
            run_id=run_name,
            journey_id=synthesis.journey_id,
            status=final_attempt.status,
            started_at=started_at,
            elapsed_seconds=time.perf_counter() - started,
            attempts=attempts,
            script_path=str(script_path),
            error_type=final_attempt.error_type,
            error_message=final_attempt.error_message,
        )
        self._write_result(run_dir, result)
        return result

    @staticmethod
    def _write_result(run_dir: Path, result: ExecutionResult) -> None:
        (run_dir / "execution_result.json").write_text(
            json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
