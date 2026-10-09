"""Interfaces shared by telemetry ingestion adapters."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from c4.schemas import NormalizedEvent


class TelemetryAdapter(Protocol):
    """Convert one provider payload into normalized events."""

    def parse(self, payload: Mapping[str, Any]) -> list[NormalizedEvent]:
        """Parse a provider payload."""


def string_value(value: Any) -> str | None:
    """Return a non-empty string representation or ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def first_string(values: Iterable[Any]) -> str | None:
    """Return the first non-empty string from an iterable."""
    for value in values:
        result = string_value(value)
        if result is not None:
            return result
    return None
