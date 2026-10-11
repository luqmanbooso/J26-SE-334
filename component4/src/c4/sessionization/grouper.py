"""Deterministic grouping of normalized events into sessions."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import timedelta
from typing import NamedTuple

from c4.schemas import EventSource, EventKind, NormalizedEvent, Session
from c4.sessionization.config import SessionizationConfig


class _IndexedEvent(NamedTuple):
    """An event paired with its original input position."""

    event: NormalizedEvent
    index: int


def group_sessions(
    events: Iterable[NormalizedEvent],
    config: SessionizationConfig,
) -> list[Session]:
    """Group events by explicit session or deterministic payload time gaps."""
    indexed = sorted(
        (_IndexedEvent(event, index) for index, event in enumerate(events)),
        key=lambda item: (item.event.timestamp, item.index),
    )
    explicit: dict[str, list[NormalizedEvent]] = defaultdict(list)
    anonymous: dict[tuple[EventSource, str], list[NormalizedEvent]] = defaultdict(list)

    for item in indexed:
        event = item.event
        if event.session_id is not None:
            explicit[event.session_id].append(event)
        else:
            payload_key = event.event_id.split(":", 1)[0]
            anonymous[(event.source, payload_key)].append(event)

    sessions: list[Session] = []
    for session_id, session_events in explicit.items():
        sessions.append(_build_session(session_id, session_events, "session_id"))

    gap = timedelta(minutes=config.gap_minutes)
    for (source, payload_key), payload_events in anonymous.items():
        chunks: list[list[NormalizedEvent]] = []
        for event in payload_events:
            if not chunks or event.timestamp - chunks[-1][-1].timestamp > gap:
                chunks.append([])
            chunks[-1].append(event)
        for number, chunk in enumerate(chunks):
            grouping = "payload" if len(chunks) == 1 else "time_gap"
            session_id = f"auto-{source.value}-{payload_key}-{number}"
            sessions.append(_build_session(session_id, chunk, grouping))

    return sorted(sessions, key=lambda session: (session.started_at, session.session_id))


def _build_session(
    session_id: str,
    events: list[NormalizedEvent],
    grouping: str,
) -> Session:
    ordered = sorted(events, key=lambda event: event.timestamp)
    sources = {event.source.value for event in ordered}
    source = next(iter(sources)) if len(sources) == 1 else "mixed"
    failure = next(
        (event for event in reversed(ordered) if event.kind is EventKind.ERROR),
        None,
    )
    app_version = _error_context(failure, "release", "app_version")
    if app_version is None and failure is not None:
        app_version = failure.app_version
    return Session(
        session_id=session_id,
        started_at=ordered[0].timestamp,
        ended_at=ordered[-1].timestamp,
        events=ordered,
        app_version=app_version,
        device=failure.device if failure is not None else None,
        os_version=failure.os_version if failure is not None else None,
        metadata={
            "source": source,
            "event_count": len(ordered),
            "grouping": grouping,
            "app_version": app_version,
        },
    )


def _error_context(event: NormalizedEvent | None, *keys: str) -> str | None:
    if event is None:
        return None
    for key in keys:
        value = event.raw.get(key)
        if value is not None:
            return str(value)
    return None
