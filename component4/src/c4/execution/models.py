"""Execution result models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ExecutionStatus(str, Enum):
    """Possible outcomes of a generated test execution."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class FailureKind(str, Enum):
    """Classification used to decide whether execution is retryable."""

    LOCATOR_NOT_FOUND = "locator_not_found"
    ELEMENT_STATE = "element_state"
    INFRASTRUCTURE = "infrastructure"
    SCRIPT_ERROR = "script_error"
    UNKNOWN = "unknown"


class FailureInfo(BaseModel):
    """Structured failure details captured from a generated script."""

    model_config = ConfigDict(extra="forbid")

    step_index: int | None = None
    action: str | None = None
    exception_type: str | None = None
    message: str | None = None
    kind: FailureKind
    page_source_path: str | None = None
    screenshot_path: str | None = None


class ExecutionAttempt(BaseModel):
    """Result captured for one subprocess attempt."""

    model_config = ConfigDict(extra="forbid")

    attempt: int = Field(ge=1)
    status: ExecutionStatus
    started_at: datetime
    elapsed_seconds: float = Field(ge=0.0)
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    failure: FailureInfo | None = None


class ExecutionResult(BaseModel):
    """Final execution result and all attempts."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    journey_id: str
    status: ExecutionStatus
    started_at: datetime
    elapsed_seconds: float = Field(ge=0.0)
    attempts: list[ExecutionAttempt] = Field(default_factory=list)
    script_path: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    failure: FailureInfo | None = None
