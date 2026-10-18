"""Execution-only retry configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from c4.execution.models import FailureKind


@dataclass(frozen=True)
class ExecutionRetryConfig:
    """Controls subprocess timeout and execution retry count."""

    max_attempts: int = 2
    timeout_seconds: float = 120.0
    retry_kinds: frozenset[FailureKind] = field(
        default_factory=lambda: frozenset({FailureKind.INFRASTRUCTURE})
    )

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
