import json

from c4.ingestion import TelemetryIngestionService
from c4.ingestion.redaction import redact_text, redact_value
from c4.sessionization import SessionizationService


def test_redact_text_masks_pii_and_credentials() -> None:
    text = (
        "mail jane.doe@example.com call +94 77 123 4567 or (415) 555-2671 "
        "card 4111 1111 1111 1111 Authorization: Bearer abcdefghijklmnop "
        "password=hunter2 jwt eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0.SflKxwRJSMeKKF2QT4"
    )
    result = redact_text(text)
    for leaked in ("jane.doe@example.com", "123 4567", "555-2671", "4111", "abcdefghijklmnop", "hunter2", "eyJzdWI"):
        assert leaked not in result
    for marker in ("EMAIL", "PHONE", "CARD", "TOKEN", "SECRET"):
        assert f"[REDACTED:{marker}]" in result


def test_redact_text_keeps_non_sensitive_values() -> None:
    text = "2026-01-01T00:01:00Z 1700000000000 Network and internet v1.2.3.4 order 1234567812345678"
    assert redact_text(text) == text


def test_redact_value_masks_sensitive_keys_and_nested_strings() -> None:
    value = {"user": {"email": "a@b.co", "note": "write to c@d.org"}, "items": ["x@y.io", 7]}
    result = redact_value(value)
    assert result["user"]["email"] == "[REDACTED:SECRET]"
    assert result["user"]["note"] == "write to [REDACTED:EMAIL]"
    assert result["items"] == ["[REDACTED:EMAIL]", 7]


def test_ingestion_redacts_events_and_journeys_keep_order_and_ids(tmp_path) -> None:
    payload = {
        "event_id": "e1",
        "timestamp": "2026-01-01T00:01:00Z",
        "release": "1.2.3",
        "user": {"email": "jane@example.com"},
        "exception": {"values": [{"type": "IllegalStateException", "value": "failed for jane@example.com"}]},
        "breadcrumbs": [
            {"timestamp": "2026-01-01T00:00:01Z", "category": "ui.click", "data": {"text": "Network and internet"}},
            {"timestamp": "2026-01-01T00:00:02Z", "category": "ui.click",
             "message": "token=abcd1234efgh5678", "data": {"text": "Pay"}},
        ],
    }
    path = tmp_path / "e.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    events = TelemetryIngestionService().parse_file(path, "sentry")

    assert "jane@example.com" not in json.dumps([e.model_dump(mode="json") for e in events])
    assert "abcd1234efgh5678" not in json.dumps([e.model_dump(mode="json") for e in events])
    journey = SessionizationService().process(events)[0]
    assert [e.locator.get("text") for e in journey.events] == ["Network and internet", "Pay"]
    assert journey.session_id and journey.metadata["source"] == "sentry"
    assert "[REDACTED:EMAIL]" in json.dumps(journey.failure.model_dump(mode="json"))
