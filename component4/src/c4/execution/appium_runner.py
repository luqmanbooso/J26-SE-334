"""Subprocess runner for generated Appium scripts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from c4.execution.classifier import classify_failure
from c4.execution.models import ExecutionAttempt, ExecutionStatus, FailureInfo


class AppiumRunner:
    """Execute one generated script without invoking a shell."""

    def __init__(self, python_executable: str | Path | None = None) -> None:
        self.python_executable = str(python_executable or sys.executable)

    def run(
        self,
        script_path: str | Path,
        *,
        attempt: int,
        timeout_seconds: float,
        run_dir: str | Path | None = None,
        extra_env: Mapping[str, str] | None = None,
        stdout_path: str | Path | None = None,
        stderr_path: str | Path | None = None,
    ) -> ExecutionAttempt:
        """Run a script and capture process output, timeout, and failure artifacts."""
        path = Path(script_path)
        artifact_dir = Path(run_dir) if run_dir is not None else path.parent
        started_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        if not path.is_file():
            return _error_attempt(
                attempt,
                started_at,
                started,
                "FileNotFoundError",
                f"Generated script does not exist: {path}",
            )
        environment = os.environ.copy()
        if run_dir is not None:
            environment["C4_RUN_DIR"] = str(artifact_dir)
        if extra_env:
            environment.update(extra_env)
        try:
            completed = subprocess.run(
                [self.python_executable, str(path)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                shell=False,
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            stdout = _text(error.stdout)
            stderr = _text(error.stderr)
            _write_logs(stdout_path, stderr_path, stdout, stderr)
            failure = _failure_info(
                artifact_dir, None, stderr, timed_out=True
            )
            return ExecutionAttempt(
                attempt=attempt,
                status=ExecutionStatus.ERROR,
                started_at=started_at,
                elapsed_seconds=time.perf_counter() - started,
                stdout=stdout,
                stderr=stderr,
                error_type="TimeoutExpired",
                error_message=f"Script exceeded {timeout_seconds} seconds",
                failure=failure,
            )
        except OSError as error:
            return _error_attempt(
                attempt, started_at, started, type(error).__name__, str(error)
            )

        _write_logs(stdout_path, stderr_path, completed.stdout, completed.stderr)
        if completed.returncode == 0:
            status = ExecutionStatus.PASSED
            failure = None
        else:
            status = ExecutionStatus.FAILED
            failure = _failure_info(
                artifact_dir, completed.stderr, completed.stderr, timed_out=False
            )
        return ExecutionAttempt(
            attempt=attempt,
            status=status,
            started_at=started_at,
            elapsed_seconds=time.perf_counter() - started,
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
            error_type=None if failure is None else "ProcessError",
            error_message=None
            if failure is None
            else f"Script exited with code {completed.returncode}",
            failure=failure,
        )


def _failure_info(
    artifact_dir: Path,
    failure_stderr: str | None,
    stderr: str,
    *,
    timed_out: bool,
) -> FailureInfo:
    failure_path = artifact_dir / "failure.json"
    payload: dict[str, object] | None = None
    try:
        loaded = json.loads(failure_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            payload = loaded
    except (OSError, json.JSONDecodeError):
        payload = None
    kind = classify_failure(payload, stderr, timed_out)
    return FailureInfo(
        step_index=_optional_int(payload, "step_index"),
        action=_optional_str(payload, "action"),
        exception_type=_optional_str(payload, "exception_type"),
        message=(_optional_str(payload, "message") or failure_stderr or "")[:500],
        kind=kind,
        page_source_path=str(artifact_dir / "page_source.xml")
        if (artifact_dir / "page_source.xml").exists()
        else None,
        screenshot_path=str(artifact_dir / "screenshot.png")
        if (artifact_dir / "screenshot.png").exists()
        else None,
    )


def _optional_str(payload: dict[str, object] | None, key: str) -> str | None:
    value = (payload or {}).get(key)
    return value if isinstance(value, str) else None


def _optional_int(payload: dict[str, object] | None, key: str) -> int | None:
    value = (payload or {}).get(key)
    return value if isinstance(value, int) else None


def _error_attempt(
    attempt: int,
    started_at: datetime,
    started: float,
    error_type: str,
    error_message: str,
) -> ExecutionAttempt:
    return ExecutionAttempt(
        attempt=attempt,
        status=ExecutionStatus.ERROR,
        started_at=started_at,
        elapsed_seconds=time.perf_counter() - started,
        error_type=error_type,
        error_message=error_message,
        failure=FailureInfo(kind=classify_failure(None, error_message, False)),
    )


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def _write_logs(
    stdout_path: str | Path | None,
    stderr_path: str | Path | None,
    stdout: str,
    stderr: str,
) -> None:
    if stdout_path is not None:
        Path(stdout_path).write_text(stdout, encoding="utf-8")
    if stderr_path is not None:
        Path(stderr_path).write_text(stderr, encoding="utf-8")
