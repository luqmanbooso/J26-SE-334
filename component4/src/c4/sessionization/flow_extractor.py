"""Rule-based extraction of ordered failure journeys."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from c4.schemas import EventKind, FailureJourney, NormalizedEvent, Session
from c4.sessionization.actions import (
    REPRODUCIBLE_ACTIONS,
    canonicalize_action,
)
from c4.sessionization.config import SessionizationConfig


def extract_journeys(
    session: Session,
    config: SessionizationConfig,
) -> list[FailureJourney]:
    """Extract one non-overlapping journey for every error in a session."""
    journeys: list[FailureJourney] = []
    previous_error_index = -1
    for error_index, event in enumerate(session.events):
        if event.kind is not EventKind.ERROR:
            continue
        window = session.events[previous_error_index + 1 : error_index]
        journeys.append(_build_journey(session, event, window, config))
        previous_error_index = error_index
    return journeys


def _build_journey(
    session: Session,
    failure: NormalizedEvent,
    window: list[NormalizedEvent],
    config: SessionizationConfig,
) -> FailureJourney:
    candidate_events = [
        event
        for event in window
        if event.kind in {EventKind.ACTION, EventKind.SCREEN}
        or (config.keep_unknown and event.kind in {EventKind.UNKNOWN, EventKind.LIFECYCLE})
    ]
    if config.collapse_duplicates:
        candidate_events = _collapse_consecutive(candidate_events)

    action_indexes = [
        index for index, event in enumerate(candidate_events)
        if event.kind is EventKind.ACTION
    ]
    truncated = len(action_indexes) > config.max_actions
    if truncated:
        first_kept_action = action_indexes[-config.max_actions]
        candidate_events = [
            event
            for index, event in enumerate(candidate_events)
            if event.kind is EventKind.ACTION and index >= first_kept_action
            or event.kind is EventKind.SCREEN and index > first_kept_action
            or event.kind not in {EventKind.ACTION, EventKind.SCREEN}
        ]

    processed = [_copy_event(event) for event in candidate_events]
    reproducible_count = sum(
        1
        for event in processed
        if event.kind is EventKind.ACTION
        and canonicalize_action(event.action) in REPRODUCIBLE_ACTIONS
    )
    reproducible = reproducible_count >= config.min_actions_for_reproducible
    reason = None if reproducible else "no reproducible actions before failure"
    failing_screen = next(
        (event.screen for event in reversed(window) if event.screen is not None),
        failure.screen,
    )
    action_count = sum(event.kind is EventKind.ACTION for event in processed)
    metadata = {
        "failing_screen": failing_screen,
        "exception_type": _exception_type(failure),
        "action_count": action_count,
        "reproducible": reproducible,
        "not_reproducible_reason": reason,
        "truncated": truncated,
        "max_actions": config.max_actions,
        "grouping": session.metadata.get("grouping"),
        "source": failure.source.value,
    }
    return FailureJourney(
        journey_id=f"{session.session_id}:{failure.event_id}",
        session_id=session.session_id,
        events=processed,
        failure=failure,
        metadata=metadata,
    )


def _collapse_consecutive(events: list[NormalizedEvent]) -> list[NormalizedEvent]:
    collapsed: list[NormalizedEvent] = []
    previous_key: tuple[Any, ...] | None = None
    for event in events:
        key = (
            canonicalize_action(event.action),
            event.screen,
            tuple(sorted(event.locator.items())),
            event.name,
        )
        if key != previous_key:
            collapsed.append(event)
            previous_key = key
    return collapsed


def _copy_event(event: NormalizedEvent) -> NormalizedEvent:
    copied = event.model_copy(deep=True)
    if copied.action is not None:
        original_action = copied.attributes.get("original_action", copied.action)
        copied.attributes["original_action"] = original_action
        copied.action = canonicalize_action(copied.action).value
    return copied


def _exception_type(event: NormalizedEvent) -> str:
    if event.error is not None:
        direct_type = event.error.get("type")
        if direct_type is not None:
            return str(direct_type)
        values = event.error.get("values")
        if isinstance(values, list) and values:
            last = values[-1]
            if isinstance(last, dict) and last.get("type") is not None:
                return str(last["type"])
    return event.name
