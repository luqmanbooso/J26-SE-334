"""Common normalization helpers for telemetry adapters."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_timestamp(value: Any) -> datetime:
    """Parse an ISO timestamp and return a timezone-aware UTC datetime."""
    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, (int, float)):
        if value > 100_000_000_000:
            value /= 1_000
        timestamp = datetime.fromtimestamp(value, tz=timezone.utc)
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        timestamp = datetime.fromisoformat(text)
    else:
        raise ValueError(f"Unsupported telemetry timestamp: {value!r}")

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def attributes_without_keys(
    payload: dict[str, Any],
    excluded: set[str],
) -> dict[str, Any]:
    """Keep provider fields not represented by normalized top-level fields."""
    return {key: value for key, value in payload.items() if key not in excluded}
