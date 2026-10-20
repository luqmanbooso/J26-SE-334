import json

from c4.ui.controller import C4DemoController


def _sentry(tmp_path, exc_type):
    payload = {
        "event_id": "e1",
        "timestamp": "2026-01-01T00:01:00Z",
        "exception": {"values": [{"type": exc_type, "value": "boom"}]},
        "breadcrumbs": [
            {"timestamp": "2026-01-01T00:00:01Z", "category": "ui.click", "data": {"text": "Pay"}}
        ],
    }
    path = tmp_path / "e.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_ui_journeys_show_and_export_hints(tmp_path) -> None:
    controller = C4DemoController()
    views = controller.create_journeys(
        str(_sentry(tmp_path, "java.net.SocketTimeoutException")), "sentry", str(tmp_path / "out")
    )
    assert views[0].error is None and views[0].hints
    seed = next(
        json.loads(f.read_text())["seed"]
        for f in (tmp_path / "out").glob("*error.json")
    )
    assert seed["perturbation_hints"][0]["stressor"] == "network"


def test_ui_unknown_exception_has_no_hint(tmp_path) -> None:
    views = C4DemoController().create_journeys(
        str(_sentry(tmp_path, "NullPointerException")), "sentry", str(tmp_path / "out")
    )
    assert views[0].hints == []
