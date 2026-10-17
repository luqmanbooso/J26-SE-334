"""Generated-test execution and retry support."""

from c4.execution.appium_runner import AppiumRunner
from c4.execution.classifier import classify_failure
from c4.execution.models import (
    ExecutionAttempt,
    ExecutionResult,
    ExecutionStatus,
    FailureInfo,
    FailureKind,
)
from c4.execution.retry import ExecutionRetryConfig
from c4.execution.service import ExecutionService, PreflightReport
from c4.execution.shared_adb import SharedAdb, SharedAdbUnavailable

__all__ = [
    "AppiumRunner",
    "ExecutionAttempt",
    "ExecutionResult",
    "ExecutionRetryConfig",
    "ExecutionService",
    "ExecutionStatus",
    "FailureInfo",
    "FailureKind",
    "PreflightReport",
    "classify_failure",
    "SharedAdb",
    "SharedAdbUnavailable",
]
