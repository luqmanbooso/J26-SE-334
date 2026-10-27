"""The neutral trace format feeds datasets through the same ingestion and journey path."""

import json

import pytest

from c4.cli import main as cli_main
from c4.ingestion import TelemetryIngestionError, TelemetryIngestionService
from c4.schemas import EventSource
from c4.sessionization import SessionizationService
from evaluation.run_synthesis_eval import collect_journeys


def _trace(trace_id="t1", **overrides):
    trace = {
        "trace_id": trace_id,
        "app_version": "2.1.0",
        "device": "Pixel 7",
        "steps": [
            {"timestamp": "2026-01-01T00:00:01Z", "action": "tap", "text": "Network and internet", "screen": "Home"},
            {"timestamp": "2026-01-01T00:00:02Z", "action": "input", "resource_id": "com.app:id/search",
             "value": "wifi", "screen": "Search"},
            {"timestamp": "2026-01-01T00:00:03Z", "action": "scroll", "screen": "Results"},
            {"timestamp": "2026-01-01T00:00:04Z", "action": "back"},
            {"timestamp": "2026-01-01T00:00:05Z", "action": "navigate", "name": "open details", "screen": "Details"},
        ],
        "failure": {"type": "IllegalStateException", "message": "boom"},
    }
    trace.update(overrides)
    return trace


def _journey(trace):
    events = TelemetryIngestionService().parse(trace, EventSource.TRACE)
    return SessionizationService().process(events)[0]


def test_trace_becomes_an_ordered_journey_with_every_action_kind() -> None:
    journey = _journey(_trace())

    assert [event.action for event in journey.events] == ["tap", "input", "scroll", "back", "navigate"]
    assert journey.events[0].locator == {"text": "Network and internet"}
    assert journey.events[1].attributes["value"] == "wifi"
    assert journey.events[1].locator == {"resource_id": "com.app:id/search"}
    assert journey.session_id == "t1" and journey.metadata["source"] == "trace"
    assert journey.metadata["reproducible"] is True and journey.metadata["failing_screen"] == "Details"
    assert journey.failure.name == "IllegalStateException"
    assert journey.failure.app_version == "2.1.0" and journey.failure.device == "Pixel 7"


def test_trace_journey_reaches_the_seed_document_with_its_origin() -> None:
    from c4.schemas import journey_to_document

    document = journey_to_document(_journey(_trace()), [])
    assert document.source == "trace" and document.app_version == "2.1.0"
    assert [target.action for target in document.seed.targets] == ["tap", "input", "navigate"]


def test_trace_without_a_failure_gives_events_but_no_journey() -> None:
    events = TelemetryIngestionService().parse(_trace(failure=None), EventSource.TRACE)
    assert len(events) == 5 and SessionizationService().process(events) == []


def test_bad_steps_are_quarantined_and_no_timestamp_is_invented() -> None:
    trace = _trace()
    trace["steps"].insert(1, {"action": "tap", "text": "no time"})
    trace["steps"].insert(2, {"timestamp": "2026-01-01T00:00:01Z", "text": "no action"})
    trace["steps"].insert(3, "not an object")

    report = TelemetryIngestionService().parse_report(trace, EventSource.TRACE)

    assert len(report.events) == 6
    assert sorted(item.reason for item in report.quarantined) == [
        "missing step action", "missing step timestamp", "step must be an object",
    ]


def test_trace_without_a_steps_list_is_quarantined() -> None:
    report = TelemetryIngestionService().parse_report({"trace_id": "x"}, EventSource.TRACE)
    assert report.events == [] and "steps" in report.quarantined[0].reason


def test_trace_failure_needs_a_type() -> None:
    report = TelemetryIngestionService().parse_report(_trace(failure={"message": "x"}), EventSource.TRACE)
    assert len(report.events) == 5 and report.quarantined[0].reason == "failure needs a type"


def test_trace_values_are_redacted_during_ingestion() -> None:
    trace = _trace(failure={"type": "Crash", "message": "failed for jane@example.com"})
    trace["steps"][1]["value"] = "password=hunter2"
    events = TelemetryIngestionService().parse(trace, EventSource.TRACE)
    dump = json.dumps([event.model_dump(mode="json") for event in events])
    assert "jane@example.com" not in dump and "hunter2" not in dump


def test_traces_load_from_json_arrays_and_jsonl(tmp_path) -> None:
    (tmp_path / "a.json").write_text(json.dumps([_trace("t1"), _trace("t2")]), encoding="utf-8")
    (tmp_path / "b.jsonl").write_text(json.dumps(_trace("t3")) + "\n" + json.dumps(_trace("t4")) + "\n", encoding="utf-8")

    journeys = collect_journeys(tmp_path, source="trace")

    assert sorted(journey.session_id for journey in journeys) == ["t1", "t2", "t3", "t4"]
    assert len(collect_journeys(tmp_path, source="trace", limit=2)) == 2


def test_cli_exports_trace_journeys_with_trace_origin(tmp_path) -> None:
    source = tmp_path / "traces.json"
    source.write_text(json.dumps([_trace("t1")]), encoding="utf-8")
    out = tmp_path / "journeys"

    code = cli_main(["journeys", "--telemetry", str(source), "--source", "trace", "--out", str(out)])

    assert code == 0
    document = json.loads(next(out.glob("t1*.json")).read_text(encoding="utf-8"))
    assert document["source"] == "trace" and document["seed"]["targets"][0]["label"] == "Network and internet"


def test_unknown_source_is_still_rejected() -> None:
    with pytest.raises(TelemetryIngestionError):
        TelemetryIngestionService().parse({}, "carrier-pigeon")
