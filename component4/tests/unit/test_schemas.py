from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from c4.schemas import (
    EventKind,
    EventSource,
    FailureJourney,
    HealResult,
    HealingDecision,
    NormalizedEvent,
    Session,
    TestStep as SynthesizedTestStep,
)


def make_event(event_id: str = "event-1") -> NormalizedEvent:
    return NormalizedEvent(
        event_id=event_id,
        session_id="session-1",
        source=EventSource.SENTRY,
        kind=EventKind.ACTION,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        name="Tap submit",
    )


def test_normalized_event_defaults_are_independent() -> None:
    first = make_event("first")
    second = make_event("second")

    first.attributes["screen"] = "login"

    assert second.attributes == {}


def test_session_and_failure_journey_accept_normalized_events() -> None:
    event = make_event()
    session = Session(
        session_id="session-1",
        started_at=event.timestamp,
        events=[event],
    )
    journey = FailureJourney(
        journey_id="journey-1",
        session_id=session.session_id,
        events=[event],
        failure=event,
    )

    assert session.events[0].event_id == journey.failure.event_id


def test_test_step_rejects_negative_index() -> None:
    with pytest.raises(ValidationError):
        SynthesizedTestStep(index=-1, action="tap")


def test_heal_result_rejects_confidence_outside_range() -> None:
    with pytest.raises(ValidationError):
        HealResult(
            decision=HealingDecision.HEALED,
            confidence=1.1,
        )
