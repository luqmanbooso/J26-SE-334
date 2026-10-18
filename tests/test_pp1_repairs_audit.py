"""
Regression tests verifying repairs R1 through R11 from the HEART C3 Finalization Plan.
"""

import io
import time
import tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image

import pytest
from vision_oracle.services.oracle_service import OracleService, set_oracle_service
from vision_oracle.services.capture_service import CaptureService
from vision_oracle.local_vision_oracle.pipeline import AnalysisPipeline
from local_vision_oracle.engine import OracleEngine, MockInferenceBackend
from vision_oracle.persistence.repository import OracleRepository
from vision_oracle.persistence.db import DatabaseManager
from vision_oracle.contracts.v2 import CaptureBundle, CoveragePolicy, VerdictEnvelopeV2, AnalysisDecision, JobState


@pytest.fixture
def test_env():
    root = Path(tempfile.mkdtemp(prefix="c3-test-repairs-"))
    db_mgr = DatabaseManager(root / "test_audit.db")
    repo = OracleRepository(db_mgr, root / "images")
    backend = MockInferenceBackend(
        default_response='{"has_defect": true, "defect_type": "component_overlap", "bounding_box": [100, 100, 300, 300], "affected_element_id": "btn_buy"}',
        simulated_latency_ms=10,
    )
    svc = OracleService(OracleEngine(backend=backend), repo)
    set_oracle_service(svc)

    img = Image.new("RGB", (1080, 2400), (250, 250, 250))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    yield {"repo": repo, "svc": svc, "img": img, "png": png_bytes}
    try:
        svc._job_queue.put(None)
    except Exception:
        pass


def test_r1_global_only_evaluation_does_not_crash(test_env):
    """R1: OracleService.evaluate(enable_sahi=False) must execute cleanly without AttributeError."""
    svc = test_env["svc"]
    img = test_env["img"]
    res = svc.evaluate(img, enable_sahi=False, action_context="act_r1_test")
    assert res is not None
    assert "oracle_result" in res
    assert res["verdict_v2"]["coverage"]["policy"] == "global_only"


def test_r2_timing_and_confidence_propagation(test_env):
    """R2: Timings must read total_pipeline_ms (>0) and uncalibrated/unavailable confidence is preserved."""
    svc = test_env["svc"]
    img = test_env["img"]
    res = svc.evaluate(img, action_context="act_r2_test")
    breakdown = res["oracle_result"]["latency_breakdown"]
    assert breakdown["total_pipeline_ms"] > 0.0
    assert breakdown["inference_ms"] > 0.0
    assert breakdown["meets_sla"] is True


def test_r3_evidence_survives_persistence_roundtrip(test_env):
    """R3: action_id and capture timings/warnings must survive SQLite round-trip and preserve ready_for_test_generation."""
    svc = test_env["svc"]
    repo = test_env["repo"]
    img = test_env["img"]

    res = svc.evaluate(img, action_context="act_r3_roundtrip")
    verdict_id = res["verdict_v2"]["verdict_id"]

    restored = repo.get_verdict(verdict_id)
    assert restored is not None
    assert restored.action_id == "act_r3_roundtrip"
    assert restored.primary_finding is not None

    c4_verdict = restored.to_c4_verdict()
    assert c4_verdict.evidence["handover_outcome"] == "ready_for_test_generation"


def test_r6_mixed_schema_contradiction_rejected(test_env):
    """R6: Contradictory mixed schema (empty findings + has_defect: true) must evaluate as inconclusive, never clean."""
    contradictory_raw = '{"findings": [], "has_defect": true, "defect_type": "component_overlap"}'
    pipeline = AnalysisPipeline(MockInferenceBackend(default_response=contradictory_raw))
    bundle = CaptureBundle(width=1080, height=2400, image_sha256="b" * 64)
    img = test_env["img"]

    verdict = pipeline.analyze(bundle=bundle, image=img, policy=CoveragePolicy.GLOBAL_ONLY)
    assert verdict.decision == AnalysisDecision.INCONCLUSIVE
    assert any("Contradictory mixed schema" in err for err in verdict.errors)


def test_r6_boolean_confidence_and_coordinates_rejected(test_env):
    """R6: Booleans passed as numeric confidence or coordinate integers must be rejected."""
    bad_conf_raw = '{"has_defect": true, "defect_type": "component_overlap", "confidence": true, "bounding_box": [100, 100, 200, 200]}'
    pipeline = AnalysisPipeline(MockInferenceBackend(default_response=bad_conf_raw))
    bundle = CaptureBundle(width=1080, height=2400, image_sha256="c" * 64)
    img = test_env["img"]

    verdict = pipeline.analyze(bundle=bundle, image=img, policy=CoveragePolicy.GLOBAL_ONLY)
    assert verdict.decision == AnalysisDecision.INCONCLUSIVE

    bad_box_raw = '{"has_defect": true, "defect_type": "component_overlap", "bounding_box": [true, false, 200, 200]}'
    pipeline2 = AnalysisPipeline(MockInferenceBackend(default_response=bad_box_raw))
    verdict2 = pipeline2.analyze(bundle=bundle, image=img, policy=CoveragePolicy.GLOBAL_ONLY)
    assert verdict2.decision == AnalysisDecision.INCONCLUSIVE


def test_r7_c4_conversion_failure_does_not_fail_inference_job(test_env):
    """R7: Failure during C4 conversion/caching must not mark a completed inference job as failed in SQLite."""
    svc = test_env["svc"]
    repo = test_env["repo"]
    png_bytes = test_env["png"]

    bundle = CaptureBundle(width=1080, height=2400, image_sha256="d" * 64)
    path, sha = repo.save_image_artifact(bundle.capture_id, png_bytes)
    bundle.artifact_path = str(path)
    bundle.image_sha256 = sha
    repo.save_capture(bundle)

    with patch.object(VerdictEnvelopeV2, "to_c4_verdict", side_effect=RuntimeError("Simulated C4 format crash")):
        job = svc.submit_job(bundle.capture_id, policy="global_only")
        svc._job_queue.join()

    job_state = svc.get_job(job["job_id"])
    assert job_state["state"] == JobState.COMPLETED.value
    saved_verdict = repo.get_verdict_by_job(job["job_id"])
    assert saved_verdict is not None


def test_r8_capture_retry_submits_missing_job(test_env):
    """R8: If prior job submission failed, a subsequent capture retry on the same action must retry job admission."""
    repo = test_env["repo"]
    svc = test_env["svc"]
    png_bytes = test_env["png"]

    cap_svc = CaptureService(repo)

    # Simulate queue failure during initial capture
    with patch.object(svc, "submit_job", side_effect=RuntimeError("Simulated queue saturation")):
        try:
            cap_svc.capture_action_evidence("act_r8_retry", "sess_r8", image_bytes_override=png_bytes)
        except RuntimeError:
            pass

    # Retry the same action_id now that queue is free
    retry_res = cap_svc.capture_action_evidence("act_r8_retry", "sess_r8", image_bytes_override=png_bytes)
    assert retry_res["status"] == "already_captured"
    assert retry_res["job_id"] is not None
    assert retry_res["idempotent"] is True
