from datetime import datetime, timezone

from c4.execution import (
    AppiumRunner,
    ExecutionRetryConfig,
    ExecutionService,
    ExecutionStatus,
)
from c4.synthesis.service import SynthesisResult


def synthesis(script: str, status: str = "generated") -> SynthesisResult:
    return SynthesisResult(
        journey_id="journey-1",
        status=status,
        steps=[],
        script=script if status == "generated" else None,
        attempts=[],
        c3_used=False,
        prompt_version="synthesis_v1",
        model="test-model",
        elapsed_seconds=0.01,
    )


def test_runner_executes_passing_script(tmp_path) -> None:
    script = tmp_path / "pass.py"
    script.write_text("print('ok')", encoding="utf-8")

    result = AppiumRunner().run(
        script,
        attempt=1,
        timeout_seconds=5,
    )

    assert result.status is ExecutionStatus.PASSED
    assert result.exit_code == 0
    assert result.stdout.strip() == "ok"


def test_runner_captures_failed_script(tmp_path) -> None:
    script = tmp_path / "fail.py"
    script.write_text("raise RuntimeError('boom')", encoding="utf-8")

    result = AppiumRunner().run(script, attempt=1, timeout_seconds=5)

    assert result.status is ExecutionStatus.FAILED
    assert result.exit_code != 0
    assert "boom" in result.stderr


def test_runner_reports_missing_script(tmp_path) -> None:
    result = AppiumRunner().run(
        tmp_path / "missing.py",
        attempt=1,
        timeout_seconds=5,
    )

    assert result.status is ExecutionStatus.ERROR
    assert result.error_type == "FileNotFoundError"


def test_execution_service_persists_artifacts(tmp_path) -> None:
    result = ExecutionService().execute(
        synthesis("print('passed')"),
        runs_dir=tmp_path,
        run_id="run-1",
    )

    run_dir = tmp_path / "run-1"
    assert result.status is ExecutionStatus.PASSED
    assert (run_dir / "synthesized_test.py").is_file()
    assert (run_dir / "attempt-1.stdout.log").read_text(encoding="utf-8").strip() == "passed"
    assert (run_dir / "execution_result.json").is_file()


def test_execution_service_retries_failed_execution(tmp_path) -> None:
    result = ExecutionService(
        retry_config=ExecutionRetryConfig(max_attempts=2, timeout_seconds=5)
    ).execute(
        synthesis("raise ConnectionRefusedError('failed')"),
        runs_dir=tmp_path,
        run_id="run-2",
    )

    assert result.status is ExecutionStatus.FAILED
    assert len(result.attempts) == 2


def test_execution_service_skips_non_generated_synthesis(tmp_path) -> None:
    result = ExecutionService().execute(
        synthesis("", status="skipped_not_reproducible"),
        runs_dir=tmp_path,
        run_id="run-3",
    )

    assert result.status is ExecutionStatus.SKIPPED
    assert result.attempts == []
    assert not (tmp_path / "run-3" / "synthesized_test.py").exists()


def test_default_timeout_outlasts_server_launch_wait() -> None:
    from c4.config import TargetAppConfig

    target = TargetAppConfig(package="p", activity=".A", server_launch_timeout_ms=90000)
    assert ExecutionService(target=target).retry_config.timeout_seconds == 210.0
    assert target.capabilities()["uiautomator2ServerLaunchTimeout"] == 90000
    assert target.capabilities()["forceAppLaunch"] and target.capabilities()["shouldTerminateApp"]
