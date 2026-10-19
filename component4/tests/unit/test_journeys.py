from datetime import datetime, timezone

from c4.journeys.export import load_hint_rules, load_journeys, write_journeys
from c4.schemas import (
    EventKind,
    EventSource,
    FailureJourney,
    NormalizedEvent,
    document_to_journey,
    journey_to_document,
)


def _journey() -> FailureJourney:
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    action = NormalizedEvent(
        event_id="tap-1",
        session_id="s1",
        source=EventSource.SENTRY,
        kind=EventKind.ACTION,
        timestamp=timestamp,
        name="Open settings",
        action="tap",
        screen="Home",
        locator={"text": "Settings"},
    )
    failure = NormalizedEvent(
        event_id="error-1",
        session_id="s1",
        source=EventSource.SENTRY,
        kind=EventKind.ERROR,
        timestamp=timestamp,
        name="Crash",
        error={"type": "SocketTimeoutException", "message": "timeout"},
        screen="Settings",
    )
    return FailureJourney(
        journey_id="s1:error/1",
        session_id="s1",
        events=[action],
        failure=failure,
        metadata={
            "reproducible": True,
            "action_count": 1,
            "failing_screen": "Settings",
            "exception_type": "SocketTimeoutException",
            "truncated": False,
        },
    )


def test_journey_document_round_trip_preserves_synthesis_fields() -> None:
    original = _journey()
    document = journey_to_document(original, load_hint_rules())
    restored = document_to_journey(document)

    assert restored.events == original.events
    assert restored.failure.name == original.failure.name
    assert restored.failure.screen == original.failure.screen
    assert restored.events[0].locator == original.events[0].locator
    assert document.seed.targets[0].label == "Settings"
    assert document.seed.failing_step_index == 0
    assert document.seed.perturbation_hints[0].stressor == "network"


def test_journey_export_is_deterministic_and_sanitizes_ids(tmp_path) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    write_journeys([_journey()], first, load_hint_rules())
    write_journeys([_journey()], second, load_hint_rules())

    assert (first / "journeys_index.json").read_bytes() == (
        second / "journeys_index.json"
    ).read_bytes()
    first_file = next(path for path in first.glob("*.json") if path.name != "journeys_index.json")
    second_file = second / first_file.name
    assert first_file.read_bytes() == second_file.read_bytes()
    assert "/" not in first_file.name
    assert load_journeys(first)[0].journey_id == "s1:error/1"


def test_unknown_exception_has_no_perturbation_hint() -> None:
    journey = _journey()
    journey.failure.error = {"type": "UnexpectedFailure", "message": "unknown"}
    journey.metadata["exception_type"] = "UnexpectedFailure"
    document = journey_to_document(journey, load_hint_rules())
    assert document.seed.perturbation_hints == []
