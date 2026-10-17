"""Execution orchestration for synthesized tests."""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

from pydantic import BaseModel, Field

from c4.config import TargetAppConfig
from c4.execution.appium_runner import AppiumRunner
from c4.execution.models import (
    ExecutionAttempt,
    ExecutionResult,
    ExecutionStatus,
    FailureInfo,
    FailureKind,
)
from c4.execution.retry import ExecutionRetryConfig
from c4.execution.shared_adb import SharedAdb, SharedAdbUnavailable
from c4.synthesis.service import SynthesisResult


class PreflightReport(BaseModel):
    """Device and Appium readiness checks."""

    adb_available: bool
    device_ready: bool
    appium_reachable: bool
    package_installed: bool
    problems: list[str] = Field(default_factory=list)


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
Probe = Callable[[TargetAppConfig], bool]
LocatorFailureHook = Callable[[ExecutionResult], None]


class ExecutionService:
    """Persist and execute generated tests with classified retries."""

    def __init__(
        self,
        runner: AppiumRunner | None = None,
        retry_config: ExecutionRetryConfig | None = None,
        target: TargetAppConfig | None = None,
        command_runner: CommandRunner | None = None,
        adb_probe: Probe | None = None,
        device_probe: Probe | None = None,
        appium_probe: Probe | None = None,
        package_probe: Probe | None = None,
        on_locator_failure: LocatorFailureHook | None = None,
        adb_device: SharedAdb | None = None,
    ) -> None:
        self.runner = runner or AppiumRunner()
        self.retry_config = retry_config or ExecutionRetryConfig()
        self.target = target
        self.command_runner = command_runner or _default_command_runner
        self._probes = (adb_probe, device_probe, appium_probe, package_probe)
        self.on_locator_failure = on_locator_failure
        self._adb_device = adb_device

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
            result = ExecutionResult(
                run_id=run_name,
                journey_id=synthesis.journey_id,
                status=ExecutionStatus.SKIPPED,
                started_at=started_at,
                elapsed_seconds=time.perf_counter() - started,
                error_type="SynthesisNotExecutable",
                error_message=synthesis.reason or f"synthesis status: {synthesis.status}",
            )
            self._write_result(run_dir, result)
            return result

        script_path = run_dir / "synthesized_test.py"
        script_path.write_text(synthesis.script, encoding="utf-8")
        attempts: list[ExecutionAttempt] = []
        for attempt_number in range(1, self.retry_config.max_attempts + 1):
            setup_failure = self._run_setup(attempt_number)
            if setup_failure is not None:
                attempt = setup_failure
            else:
                attempt = self.runner.run(
                    script_path,
                    attempt=attempt_number,
                    timeout_seconds=self.retry_config.timeout_seconds,
                    run_dir=run_dir,
                    stdout_path=run_dir / f"attempt-{attempt_number}.stdout.log",
                    stderr_path=run_dir / f"attempt-{attempt_number}.stderr.log",
                )
            attempts.append(attempt)
            if attempt.status is ExecutionStatus.PASSED:
                break
            if attempt.failure is None or attempt.failure.kind not in self.retry_config.retry_kinds:
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
            failure=final_attempt.failure,
        )
        self._write_result(run_dir, result)
        if (
            result.failure is not None
            and result.failure.kind is FailureKind.LOCATOR_NOT_FOUND
            and self.on_locator_failure is not None
        ):
            self.on_locator_failure(result)
        return result

    def preflight(self, target: TargetAppConfig | None = None) -> PreflightReport:
        """Check ADB, device, Appium, and package readiness."""
        config = target or self.target
        if config is None:
            raise ValueError("target is required for preflight")
        try:
            device = self._adb_device or SharedAdb(config)
        except SharedAdbUnavailable as error:
            return PreflightReport(
                adb_available=False,
                device_ready=False,
                appium_reachable=False,
                package_installed=False,
                problems=[str(error)],
            )
        defaults: tuple[Probe, ...] = (
            lambda current: _probe_adb(current, device),
            lambda current: _probe_device(current, device),
            _probe_appium,
            lambda current: _probe_package(current, device),
        )
        values = [
            (probe or default)(config)
            for probe, default in zip(self._probes, defaults)
        ]
        names = ("adb", "device", "Appium", f"package {config.package}")
        problems = [
            f"{name} is not ready" for name, ready in zip(names, values) if not ready
        ]
        return PreflightReport(
            adb_available=values[0],
            device_ready=values[1],
            appium_reachable=values[2],
            package_installed=values[3],
            problems=problems,
        )

    def _run_setup(self, attempt_number: int) -> ExecutionAttempt | None:
        if self.target is None:
            return None
        try:
            device = self._adb_device or SharedAdb(self.target)
        except SharedAdbUnavailable as error:
            return _setup_failure(
                attempt_number, type(error).__name__, str(error)
            )
        for command in self.target.setup_commands:
            args = [self.target.adb_path]
            if self.target.udid:
                args.extend(["-s", self.target.udid])
            args.extend(command)
            try:
                completed = (
                    self.command_runner(args)
                    if self.command_runner is not _default_command_runner
                    else device.run(command)
                )
            except OSError as error:
                return _setup_failure(attempt_number, type(error).__name__, str(error))
            if completed.returncode != 0:
                return _setup_failure(
                    attempt_number,
                    "SetupCommandError",
                    completed.stderr or f"setup command failed: {' '.join(args)}",
                )
        return None

    @staticmethod
    def _write_result(run_dir: Path, result: ExecutionResult) -> None:
        (run_dir / "execution_result.json").write_text(
            json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )


def _setup_failure(attempt: int, error_type: str, message: str) -> ExecutionAttempt:
    now = datetime.now(timezone.utc)
    failure = FailureInfo(
        exception_type=error_type,
        message=message,
        kind=FailureKind.INFRASTRUCTURE,
    )
    return ExecutionAttempt(
        attempt=attempt,
        status=ExecutionStatus.ERROR,
        started_at=now,
        elapsed_seconds=0.0,
        error_type=error_type,
        error_message=message,
        failure=failure,
    )


def _default_command_runner(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), capture_output=True, text=True, check=False, shell=False
    )


def _probe_adb(target: TargetAppConfig, device: SharedAdb) -> bool:
    try:
        return device.run(["version"]).returncode == 0
    except (OSError, SharedAdbUnavailable):
        return False


def _probe_device(target: TargetAppConfig, device: SharedAdb) -> bool:
    try:
        result = device.run(["get-state"])
        return result.returncode == 0 and result.stdout.strip() == "device"
    except (OSError, SharedAdbUnavailable):
        return False


def _probe_appium(target: TargetAppConfig) -> bool:
    try:
        with urlopen(f"{target.appium_url.rstrip('/')}/status", timeout=3):
            return True
    except OSError:
        return False


def _probe_package(target: TargetAppConfig, device: SharedAdb) -> bool:
    try:
        result = device.run(["shell", "pm", "list", "packages"])
        return result.returncode == 0 and f"package:{target.package}" in result.stdout
    except (OSError, SharedAdbUnavailable):
        return False
