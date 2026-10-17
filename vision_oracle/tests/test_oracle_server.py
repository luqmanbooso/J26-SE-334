"""
Unit tests for Component 3 FastAPI Backend Service (vision_oracle/server.py).
Tests synchronous evaluation, non-blocking C2 trigger queue, and C4 verdict publishing.
"""

import io
import base64
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from vision_oracle.server import app, get_engine, set_engine
from local_vision_oracle.engine import OracleEngine, MockInferenceBackend
from local_vision_oracle.schemas import DefectType


@pytest.fixture
def client():
    # Force Mock backend for fast deterministic test execution
    engine = OracleEngine(backend=MockInferenceBackend())
    set_engine(engine)
    return TestClient(app)


def _create_base64_image(color=(255, 255, 255), size=(360, 640)) -> str:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def test_server_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["zero_cloud_egress"] is True


def test_server_status_endpoint(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "nominal"
    assert data["zero_cloud_egress"] is True
    assert "compute_device" in data
    assert "cuda_available" in data


def test_server_evaluate_endpoint_clean_screen(client):
    b64_img = _create_base64_image()
    payload = {
        "image_base64": b64_img,
        "hierarchy_xml": '<hierarchy><node class="android.widget.TextView" text="Hello" bounds="[0,0][100,50]"/></hierarchy>',
        "screen_id": "test_clean_01",
        "session_id": "session_unit_test",
    }
    response = client.post("/api/oracle/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert "oracle_result" in data
    assert "c4_verdict" in data
    c4 = data["c4_verdict"]
    assert c4["schema_version"] == "1.0.0"
    assert c4["session_id"] == "session_unit_test"
    assert c4["has_gui_defect"] is False


def test_server_evaluate_missing_payload_returns_400(client):
    response = client.post("/api/oracle/evaluate", json={})
    assert response.status_code == 400
    assert "Either image_base64 or image_path" in response.json()["detail"]


def test_server_c2_trigger_async_queue(client):
    """C2 trigger endpoint must return 202 Accepted in <10ms without blocking runner."""
    payload = {
        "action_id": "act_rage_tap_42",
        "session_id": "session_c2_stress",
        "target_element_id": "com.example:id/checkout_btn",
        "stress_level": 0.85,
        "delay_ms": 150.0,
    }
    response = client.post("/api/oracle/trigger", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "enqueued"
    assert data["action_id"] == "act_rage_tap_42"
    assert data["non_blocking"] is True


def test_server_sequence_freeze_detection(client):
    b64_1 = _create_base64_image(color=(200, 200, 200))
    b64_2 = _create_base64_image(color=(200, 200, 200))  # Identical
    
    payload = {
        "image_base64_list": [b64_1, b64_2],
        "time_delta_s": 3.0,
        "action_dispatched": True,
        "action_context": "Tap Refresh",
    }
    response = client.post("/api/oracle/sequence", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    c4 = data["c4_verdict"]
    assert c4["has_gui_defect"] is True
    assert c4["defect_type"] == "frozen_state"


def test_server_verdict_history_and_retrieval(client):
    b64_img = _create_base64_image()
    eval_resp = client.post(
        "/api/oracle/evaluate",
        json={"image_base64": b64_img, "screen_id": "history_screen_01"}
    )
    assert eval_resp.status_code == 200
    verdict_id = eval_resp.json()["c4_verdict"]["verdict_id"]
    
    # List verdicts
    list_resp = client.get("/api/oracle/verdicts")
    assert list_resp.status_code == 200
    verdicts = list_resp.json()
    assert any(v["verdict_id"] == verdict_id for v in verdicts)
    
    # Get specific verdict
    get_resp = client.get(f"/api/oracle/verdicts/{verdict_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["verdict_id"] == verdict_id
