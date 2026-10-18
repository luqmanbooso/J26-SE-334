"""Deterministic event deduplication."""

from __future__ import annotations

from c4.schemas import NormalizedEvent


def event_dedupe_key(event: NormalizedEvent) -> tuple[object, ...]:
    """Build the FR1 identity key for duplicate breadcrumbs."""
    return (
        event.session_id,
        event.timestamp,
        event.action,
        event.name,
        tuple(sorted(event.locator.items())),
    )


def deduplicate(events: list[NormalizedEvent]) -> tuple[list[NormalizedEvent], int]:
    """Keep first occurrences while preserving chronological order."""
    unique: list[NormalizedEvent] = []
    seen: set[tuple[object, ...]] = set()
    duplicates = 0
    for event in sorted(events, key=lambda item: item.timestamp):
        key = event_dedupe_key(event)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(event)
    return unique, duplicates
