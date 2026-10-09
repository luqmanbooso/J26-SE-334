from datetime import timezone
import json

import pytest

from c4.ingestion import (
    SentryAdapter,
    TelemetryIngestionError,
    TelemetryIngestionService,
)
from c4.ingestion.crashlytics import CrashlyticsAdapter
from c4.ingestion.normalizer import parse_timestamp
from c4.schemas import EventKind, EventSource


def test_parse_timestamp_normalizes_iso_and_milliseconds() -> None:
    iso_timestamp = parse_timestamp("2026-01-01T05:30:00+05:30")
    millisecond_timestamp = parse_timestamp(1767225600000)

    assert iso_timestamp.tzinfo == timezone.utc
    assert iso_timestamp.isoformat() == "2026-01-01T00:00:00+00:00"
    assert millisecond_timestamp.isoformat() == "2026-01-01T00:00:00+00:00"


def test_sentry_adapter_extracts_actions_and_error_in_time_order() -> None:
    payload = {
        "event_id": "evt-1",
        "contexts": {"session": {"id": "sess-1"}},
        "timestamp": "2026-01-01T00:00:03Z",
        "breadcrumbs": {
            "values": [
                {
                    "timestamp": "2026-01-01T00:00:02Z",
                    "category": "ui.click",
                    "message": "Submit",
                    "data": {"text": "SUBMIT", "screen": "Login"},
                },
                {
                    "timestamp": "2026-01-01T00:00:01Z",
                    "category": "navigation",
                    "message": "Open login",
                },
            ]
        },
        "exception": {"values": [{"type": "ValueError"}]},
    }

    events = SentryAdapter().parse(payload)

    assert [event.kind for event in events] == [
        EventKind.ACTION,
        EventKind.ACTION,
        EventKind.ERROR,
    ]
    assert events[0].name == "Open login"
    assert events[1].locator == {"text": "SUBMIT"}
    assert all(event.session_id == "sess-1" for event in events)


def test_crashlytics_adapter_creates_failure_event() -> None:
    payload = {
        "crash_id": "crash-1",
        "user_session_id": "sess-2",
        "timestamp": 1767225600000,
        "exception_type": "NullPointerException",
        "logs": [
            {
                "time": 1767225599000,
                "action": "tap",
                "name": "Submit",
                "resource_id": "login_submit",
            }
        ],
    }

    events = CrashlyticsAdapter().parse(payload)

    assert events[0].kind == EventKind.ACTION
    assert events[0].locator == {"resource_id": "login_submit"}
    assert events[-1].kind == EventKind.ERROR
    assert events[-1].name == "NullPointerException"


def test_ingestion_service_dispatches_and_loads_json(tmp_path) -> None:
    path = tmp_path / "sentry.json"
    path.write_text(
        json.dumps(
            {
                "event_id": "evt-2",
                "breadcrumbs": [
                    {
                        "timestamp": "2026-01-01T00:00:00Z",
                        "category": "user",
                        "message": "Tap",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    events = TelemetryIngestionService().parse_file(path, EventSource.SENTRY)

    assert len(events) == 1
    assert events[0].source == EventSource.SENTRY


def test_ingestion_service_reports_unknown_source() -> None:
    with pytest.raises(TelemetryIngestionError, match="Unsupported telemetry source"):
        TelemetryIngestionService().parse({}, "unknown")
