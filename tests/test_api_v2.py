"""
Integration tests for Component 3 V2 REST API (Phase H of Implementation Plan).
Verifies:
- GET /health/live: Immediate liveness check without loading model
- GET /health/ready: Truthful operational readiness check
- POST /v2/captures: Immutable capture registration with SHA-256
- POST /v2/jobs: Asynchronous job submission and non-blocking 202 response
- GET /v2/jobs/{job_id}: Progress polling and terminal state transition
- POST /v2/jobs/{job_id}/cancel: Job cancellation
- GET /v2/results/{verdict_id}: Retrieval of canonical VerdictEnvelopeV2
- GET /v2/sessions/{session_id}/results: Session results query
- POST /v2/reviews: Human QA review feedback
"""

import io
import time
import base64
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from vision_oracle.server import app, set_engine
from local_vision_oracle.engine import OracleEngine, MockInferenceBackend
from vision_oracle.services.oracle_service import get_oracle_service, OracleService
from vision_oracle.persistence.db import DatabaseManager
from vision_oracle.persistence.repository import OracleRepository


def _make_base64_image(color=(255, 255, 255), size=(1080, 2400)) -> str:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


@pytest.fixture
def test_client(tmp_path):
    # Setup isolated test repository with in-memory / temp SQLite
    db_file = tmp_path / "v2_test.db"
    artifacts_dir = tmp_path / "artifacts"
    db_manager = DatabaseManager(db_path=db_file)
    repo = OracleRepository(db_manager=db_manager, artifacts_dir=artifacts_dir)

    engine = OracleEngine(backend=MockInferenceBackend())
    service = OracleService(engine=engine, repository=repo)
    from vision_oracle.services.oracle_service import set_oracle_service
    set_oracle_service(service)

    return TestClient(app)


def test_health_live_endpoint(test_client):
    resp = test_client.get("/health/live")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "live"
    assert data["service"] == "vision_oracle"


def test_health_ready_endpoint(test_client):
    resp = test_client.get("/health/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["model_ready"] is True
    assert data["db_ready"] is True


def test_v2_capture_and_async_job_flow(test_client):
    b64_img = _make_base64_image()
    capture_payload = {
        "session_id": "session_api_v2_test",
        "app_package": "com.solvance.android",
        "image_base64": b64_img,
        "raw_hierarchy": '<hierarchy><node bounds="[0,0][100,50]"/></hierarchy>',
    }

    # 1. Register Capture
    cap_resp = test_client.post("/v2/captures", json=capture_payload)
    assert cap_resp.status_code == 201
    cap_data = cap_resp.json()
    capture_id = cap_data["capture_id"]
    assert capture_id.startswith("cap_")
    assert cap_data["width"] == 1080
    assert cap_data["height"] == 2400

    # 2. Submit Async Job
    job_payload = {
        "capture_id": capture_id,
        "session_id": "session_api_v2_test",
        "policy": "global_plus_tiles_v1",
    }
    job_resp = test_client.post("/v2/jobs", json=job_payload)
    assert job_resp.status_code == 202
    job_data = job_resp.json()
    job_id = job_data["job_id"]
    assert job_id.startswith("job_")
    assert job_data["state"] in ("queued", "running", "completed")

    # 3. Poll Job until terminal state
    completed = False
    for _ in range(50):
        poll_resp = test_client.get(f"/v2/jobs/{job_id}")
        assert poll_resp.status_code == 200
        status_data = poll_resp.json()
        if status_data["state"] == "completed":
            completed = True
            assert "verdict_id" in status_data
            verdict_id = status_data["verdict_id"]
            break
        elif status_data["state"] in ("failed", "cancelled"):
            pytest.fail(f"Job terminated unexpectedly with state: {status_data['state']}")
        time.sleep(0.1)

    assert completed, "Job did not complete within timeout"

    # 4. Fetch Result
    res_resp = test_client.get(f"/v2/results/{verdict_id}")
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert res_data["schema_version"] == "2.0"
    assert res_data["decision"] in ("defect_detected", "no_defect_detected", "inconclusive")
    assert res_data["screenshot"]["width"] == 1080
    assert res_data["screenshot"]["height"] == 2400

    # 5. Fetch Session Results
    sess_resp = test_client.get("/v2/sessions/session_api_v2_test/results")
    assert sess_resp.status_code == 200
    sess_verdicts = sess_resp.json()
    assert len(sess_verdicts) >= 1
    assert sess_verdicts[0]["verdict_id"] == verdict_id

    # 6. Submit Human QA Review
    rev_payload = {
        "verdict_id": verdict_id,
        "review_status": "accepted",
        "reviewer_notes": "Clean screen verified by test client",
    }
    rev_resp = test_client.post("/v2/reviews", json=rev_payload)
    assert rev_resp.status_code == 201
    assert rev_resp.json()["status"] == "persisted"


def test_v2_job_cancellation(test_client):
    b64_img = _make_base64_image()
    cap_resp = test_client.post("/v2/captures", json={"image_base64": b64_img})
    capture_id = cap_resp.json()["capture_id"]

    job_resp = test_client.post("/v2/jobs", json={"capture_id": capture_id})
    job_id = job_resp.json()["job_id"]

    cancel_resp = test_client.post(f"/v2/jobs/{job_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancellation_requested"


def test_v2_capture_with_image_path(test_client, tmp_path):
    img_file = tmp_path / "sample_screen.png"
    img = Image.new("RGB", (1080, 2400), (200, 200, 200))
    img.save(img_file)

    payload = {
        "session_id": "session_image_path_test",
        "image_path": str(img_file),
        "raw_hierarchy": "<hierarchy/>",
    }
    resp = test_client.post("/v2/captures", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["capture_id"].startswith("cap_")
    assert data["width"] == 1080
    assert data["height"] == 2400

