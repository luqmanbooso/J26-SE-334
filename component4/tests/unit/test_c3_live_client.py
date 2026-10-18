"""
Unit tests for C3LiveClient (IF-C3-to-C4, FR7).
Verifies in-process evaluation, HTTP fallback, and contract compliance.
"""

from __future__ import annotations

import pytest
pytest.importorskip("PIL")
pytest.importorskip("local_vision_oracle")

import io
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
import pytest

from c4.c3_interface import C3Client, C3LiveClient, C3Verdict
from c4.schemas import EventKind, EventSource, NormalizedEvent
from local_vision_oracle.engine import OracleEngine, MockInferenceBackend


def _create_sample_failure(screenshot_path: str | None = None) -> NormalizedEvent:
    attrs = {}
    if screenshot_path:
        attrs["screenshot_path"] = screenshot_path
    return NormalizedEvent(
        event_id="evt-failure-123",
        session_id="session-live-01",
        source=EventSource.SENTRY,
        kind=EventKind.ERROR,
        timestamp=datetime.now(timezone.utc),
        name="NullPointerException",
        screen="CheckoutActivity",
        attributes=attrs,
    )


def _create_test_image_file(tmp_path: Path) -> Path:
    img = Image.new("RGB", (360, 640), (255, 255, 255))
    path = tmp_path / "test_screenshot.png"
    img.save(path)
    return path


def test_c3_live_client_implements_protocol():
    client = C3LiveClient()
    assert isinstance(client, C3Client)


def test_c3_live_client_in_process_evaluation(tmp_path: Path):
    img_path = _create_test_image_file(tmp_path)
    failure = _create_sample_failure(screenshot_path=str(img_path))

    engine = OracleEngine(backend=MockInferenceBackend())
    client = C3LiveClient(mode="in_process", engine=engine)

    verdict = client.get_verdict("session-live-01", failure)
    assert isinstance(verdict, C3Verdict)
    assert verdict.schema_version == "1.0.0"
    assert verdict.session_id == "session-live-01"
    assert verdict.has_gui_defect is False


def test_c3_live_client_fallback_when_no_screenshot():
    failure = _create_sample_failure(screenshot_path=None)
    client = C3LiveClient(mode="in_process")

    verdict = client.get_verdict("session-no-img", failure)
    assert isinstance(verdict, C3Verdict)
    assert verdict.has_gui_defect is False
    assert verdict.confidence == 0.0
    assert verdict.evidence["note"] == "no_screenshot_attached_or_oracle_offline"


def test_c3_live_client_http_evaluation(tmp_path: Path):
    img_path = _create_test_image_file(tmp_path)
    failure = _create_sample_failure(screenshot_path=str(img_path))

    mock_response_data = {
        "oracle_result": {"status": "ok"},
        "c4_verdict": {
            "schema_version": "1.0.0",
            "verdict_id": "c4-verdict-http-999",
            "session_id": "session-http-01",
            "has_gui_defect": True,
            "defect_type": "component_overlap",
            "confidence": 0.95,
            "screenshot": {"path": str(img_path), "width": 360, "height": 640},
            "regions": [{"x": 10, "y": 20, "width": 100, "height": 50, "label": "overlap"}],
            "evidence": {"iou": 0.45},
            "metadata": {},
        },
    }

    client = C3LiveClient(mode="http", base_url="http://127.0.0.1:8003")

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_response_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        verdict = client.get_verdict("session-http-01", failure)
        assert isinstance(verdict, C3Verdict)
        assert verdict.has_gui_defect is True
        assert verdict.defect_type == "component_overlap"
        assert verdict.confidence == 0.95
        assert len(verdict.regions) == 1
        assert verdict.regions[0].label == "overlap"


def test_c3_live_client_handles_unreachable_server_gracefully():
    failure = _create_sample_failure(screenshot_path="dummy.png")
    client = C3LiveClient(
        mode="http",
        base_url="http://127.0.0.1:9999",
        fallback_on_error=True,
    )

    verdict = client.get_verdict("session-offline", failure)
    assert isinstance(verdict, C3Verdict)
    assert verdict.has_gui_defect is False
    assert verdict.confidence == 0.0
