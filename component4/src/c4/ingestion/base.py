"""Interfaces shared by telemetry ingestion adapters."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from c4.schemas import IngestionReport, NormalizedEvent, QuarantinedRecord


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


def first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    """Return the first value present, including valid zero timestamps."""
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def locator_from_mapping(item: Mapping[str, Any]) -> dict[str, str]:
    """Extract common locator fields, including observed Sentry ``view.*`` keys."""
    view = item.get("view")
    view_mapping = view if isinstance(view, Mapping) else {}
    aliases = {
        "text": ("text", "view.text"),
        "resource_id": ("resource_id", "resource-id", "view.id", "view.resource_id"),
        "content_desc": ("content_desc", "content-desc", "view.content_desc"),
        "xpath": ("xpath",),
        "accessibility_id": ("accessibility_id", "view.accessibility_id"),
    }
    result: dict[str, str] = {}
    for name, keys in aliases.items():
        value = first_string(
            [item.get(key) for key in keys]
            + [view_mapping.get(key.removeprefix("view.")) for key in keys]
        )
        if value is not None:
            result[name] = value
    return result


def make_report(
    events: list[NormalizedEvent],
    quarantined: list[QuarantinedRecord],
):
    """Deduplicate accepted events and return an ingestion report."""
    from c4.ingestion.dedupe import deduplicate

    unique, deduped_count = deduplicate(events)
    return IngestionReport(
        events=unique,
        quarantined=quarantined,
        deduped_count=deduped_count,
    )
