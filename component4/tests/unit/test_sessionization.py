from datetime import datetime, timedelta, timezone

from c4.schemas import EventKind, EventSource, NormalizedEvent
from c4.sessionization import (
    CanonicalAction,
    SessionizationConfig,
    SessionizationService,
    canonicalize_action,
)


BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def event(
    event_id: str,
    minutes: int,
    *,
    kind: EventKind = EventKind.ACTION,
    session_id: str | None = "session-1",
    action: str | None = "tap",
    screen: str | None = None,
    name: str = "action",
    source: EventSource = EventSource.SENTRY,
    error: dict | None = None,
    raw: dict | None = None,
) -> NormalizedEvent:
    return NormalizedEvent(
        event_id=event_id,
        session_id=session_id,
        source=source,
        kind=kind,
        timestamp=BASE + timedelta(minutes=minutes),
        name=name,
        action=action,
        screen=screen,
        error=error,
        raw=raw or {},
    )


def error_event(
    event_id: str,
    minutes: int,
    *,
    session_id: str | None = "session-1",
    source: EventSource = EventSource.SENTRY,
    error: dict | None = None,
) -> NormalizedEvent:
    return event(
        event_id,
        minutes,
        kind=EventKind.ERROR,
        session_id=session_id,
        action=None,
        name="Crash",
        source=source,
        error=error,
    )


def test_explicit_sessions_are_grouped_and_sorted() -> None:
    events = [event("late", 2), event("early", 1), event("other", 3, session_id="other")]

    sessions = SessionizationService().group_sessions(events)

    assert [session.session_id for session in sessions] == ["session-1", "other"]
    assert [item.event_id for item in sessions[0].events] == ["early", "late"]
    assert sessions[0].metadata["grouping"] == "session_id"


def test_equal_timestamps_keep_original_input_order() -> None:
    events = [event("second", 1), event("first", 1)]

    session = SessionizationService().group_sessions(events)[0]

    assert [item.event_id for item in session.events] == ["second", "first"]


def test_anonymous_events_split_by_gap_with_deterministic_ids() -> None:
    events = [
        event("payload:one", 0, session_id=None),
        event("payload:two", 1, session_id=None),
        event("payload:three", 32, session_id=None),
    ]

    sessions = SessionizationService(
        SessionizationConfig(gap_minutes=30)
    ).group_sessions(events)

    assert [session.session_id for session in sessions] == [
        "auto-sentry-payload-0",
        "auto-sentry-payload-1",
    ]
    assert [len(session.events) for session in sessions] == [2, 1]


def test_two_errors_create_non_overlapping_journeys() -> None:
    events = [
        event("a", 1),
        error_event("failure-1", 2),
        event("b", 3),
        error_event("failure-2", 4),
    ]

    journeys = SessionizationService().process(events)

    assert [[item.event_id for item in journey.events] for journey in journeys] == [
        ["a"],
        ["b"],
    ]


def test_failure_without_actions_is_returned_as_not_reproducible() -> None:
    journey = SessionizationService().process([error_event("failure", 1)])[0]

    assert journey.events == []
    assert journey.metadata["reproducible"] is False
    assert journey.metadata["not_reproducible_reason"] == (
        "no reproducible actions before failure"
    )


def test_max_actions_keeps_last_actions_and_sets_truncation() -> None:
    events = [
        event(f"a-{index}", index, name=f"Action {index}")
        for index in range(4)
    ]
    events.append(event("screen", 4, kind=EventKind.SCREEN, action=None, screen="Details"))
    events.append(error_event("failure", 5))

    journey = SessionizationService(
        SessionizationConfig(max_actions=2)
    ).process(events)[0]

    assert [item.event_id for item in journey.events] == ["a-2", "a-3", "screen"]
    assert journey.metadata["truncated"] is True
    assert journey.metadata["action_count"] == 2


def test_unknown_and_lifecycle_policy() -> None:
    events = [
        event("unknown", 1, kind=EventKind.UNKNOWN, action="tap", name="Unknown"),
        event("lifecycle", 2, kind=EventKind.LIFECYCLE, action="tap", name="Lifecycle"),
        error_event("failure", 3),
    ]

    default = SessionizationService().process(events)[0]
    kept = SessionizationService(
        SessionizationConfig(keep_unknown=True)
    ).process(events)[0]

    assert default.events == []
    assert [item.event_id for item in kept.events] == ["unknown", "lifecycle"]


def test_consecutive_duplicate_policy() -> None:
    events = [
        event("one", 1, name="Submit"),
        event("two", 2, name="Submit"),
        error_event("failure", 3),
    ]

    collapsed = SessionizationService().process(events)[0]
    preserved = SessionizationService(
        SessionizationConfig(collapse_duplicates=False)
    ).process(events)[0]

    assert [item.event_id for item in collapsed.events] == ["one"]
    assert [item.event_id for item in preserved.events] == ["one", "two"]


def test_canonicalize_action_aliases() -> None:
    assert canonicalize_action(" ui.click ") is CanonicalAction.TAP
    assert canonicalize_action("tap") is CanonicalAction.TAP
    assert canonicalize_action("navigation") is CanonicalAction.NAVIGATE
    assert canonicalize_action(None) is CanonicalAction.UNKNOWN
    assert canonicalize_action("something-new") is CanonicalAction.UNKNOWN


def test_sentry_and_crashlytics_shapes_have_same_canonical_flow() -> None:
    sentry = [
        event("s1", 1, action="ui.click"),
        event("s2", 2, action="navigation"),
        error_event("s-error", 3),
    ]
    crashlytics = [
        event("c1", 1, action="tap", source=EventSource.CRASHLYTICS),
        event("c2", 2, action="open_screen", source=EventSource.CRASHLYTICS),
        error_event("c-error", 3, source=EventSource.CRASHLYTICS),
    ]

    sentry_actions = [
        item.action for item in SessionizationService().process(sentry)[0].events
    ]
    crashlytics_actions = [
        item.action for item in SessionizationService().process(crashlytics)[0].events
    ]

    assert sentry_actions == crashlytics_actions == ["tap", "navigate"]


def test_events_are_not_mutated_and_processing_is_deterministic() -> None:
    events = [
        event("action", 1, action="ui.click"),
        error_event("failure", 2),
    ]
    before = [item.model_dump() for item in events]
    service = SessionizationService()

    first = service.process(events)
    second = service.process(events)

    assert [item.model_dump() for item in events] == before
    assert first == second
    assert first[0].events[0].attributes["original_action"] == "ui.click"


def test_metadata_contains_screen_exception_type_and_action_count() -> None:
    events = [
        event("tap", 1, screen="Login"),
        error_event(
            "failure",
            2,
            error={"values": [{"type": "Outer"}, {"type": "NullPointerException"}]},
        ),
    ]

    metadata = SessionizationService().process(events)[0].metadata

    assert metadata["failing_screen"] == "Login"
    assert metadata["exception_type"] == "NullPointerException"
    assert metadata["action_count"] == 1
