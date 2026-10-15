"""Subprocess runner for generated Appium scripts."""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from c4.execution.models import ExecutionAttempt, ExecutionStatus


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
        stdout_path: str | Path | None = None,
        stderr_path: str | Path | None = None,
    ) -> ExecutionAttempt:
        """Run a script and capture process output, timeout, and exit status."""
        path = Path(script_path)
        started_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        if not path.is_file():
            return ExecutionAttempt(
                attempt=attempt,
                status=ExecutionStatus.ERROR,
                started_at=started_at,
                elapsed_seconds=time.perf_counter() - started,
                error_type="FileNotFoundError",
                error_message=f"Generated script does not exist: {path}",
            )
        try:
            completed = subprocess.run(
                [self.python_executable, str(path)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as error:
            stdout = _text(error.stdout)
            stderr = _text(error.stderr)
            result = ExecutionAttempt(
                attempt=attempt,
                status=ExecutionStatus.ERROR,
                started_at=started_at,
                elapsed_seconds=time.perf_counter() - started,
                stdout=stdout,
                stderr=stderr,
                error_type="TimeoutExpired",
                error_message=f"Script exceeded {timeout_seconds} seconds",
            )
            _write_logs(stdout_path, stderr_path, stdout, stderr)
            return result
        except OSError as error:
            return ExecutionAttempt(
                attempt=attempt,
                status=ExecutionStatus.ERROR,
                started_at=started_at,
                elapsed_seconds=time.perf_counter() - started,
                error_type=type(error).__name__,
                error_message=str(error),
            )

        status = (
            ExecutionStatus.PASSED
            if completed.returncode == 0
            else ExecutionStatus.FAILED
        )
        result = ExecutionAttempt(
            attempt=attempt,
            status=status,
            started_at=started_at,
            elapsed_seconds=time.perf_counter() - started,
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
            error_type=None if status is ExecutionStatus.PASSED else "ProcessError",
            error_message=None
            if status is ExecutionStatus.PASSED
            else f"Script exited with code {completed.returncode}",
        )
        _write_logs(stdout_path, stderr_path, completed.stdout, completed.stderr)
        return result


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
