"""
Unit tests for SQLite Durable Persistence & Repository (Phase H & Section 10.2).
Verifies:
- Schema initialization with WAL mode and foreign keys
- Atomic image artifact writes with SHA-256 verification
- ACID capture, job, verdict, and finding persistence
- Crash recovery: automatic reconciliation of interrupted jobs on startup
- Human QA review records
"""

import tempfile
import pytest
from pathlib import Path

from vision_oracle.persistence.db import DatabaseManager
from vision_oracle.persistence.repository import OracleRepository
from vision_oracle.contracts.v2 import (
    JobState,
    AnalysisStatus,
    AnalysisDecision,
    Coverage,
    ScreenshotRef,
    Finding,
    CaptureBundle,
    VerdictEnvelopeV2,
    ReviewStatus,
)


@pytest.fixture
def repo(tmp_path):
    db_file = tmp_path / "test_oracle.db"
    artifacts_dir = tmp_path / "artifacts"
    db_manager = DatabaseManager(db_path=db_file)
    return OracleRepository(db_manager=db_manager, artifacts_dir=artifacts_dir)


def test_sqlite_wal_mode_enabled(repo):
    conn = repo.db.get_connection()
    cur = conn.execute("PRAGMA journal_mode;")
    mode = cur.fetchone()[0]
    assert mode.lower() == "wal"


def test_atomic_image_artifact_write(repo):
    test_bytes = b"\x89PNG\r\n\x1a\nTestImageDataPayload12345"
    capture_id = "cap_atomic_01"

    path, sha256 = repo.save_image_artifact(capture_id, test_bytes)
    assert path.exists()
    assert path.name == "cap_atomic_01.png"
    assert path.read_bytes() == test_bytes
    assert len(sha256) == 64


def test_capture_and_job_lifecycle(repo):
    bundle = CaptureBundle(
        capture_id="cap_life_01",
        session_id="session_alpha",
        app_package="com.example.app",
        device_serial="device_usb_1",
        width=1080,
        height=2400,
        image_sha256="abc123456",
        artifact_path="/tmp/screen.png",
        raw_hierarchy="<hierarchy/>",
    )
    repo.save_capture(bundle)

    loaded = repo.get_capture("cap_life_01")
    assert loaded is not None
    assert loaded.capture_id == "cap_life_01"
    assert loaded.session_id == "session_alpha"
    assert loaded.width == 1080

    # Create Job
    job = repo.create_job(capture_id="cap_life_01", session_id="session_alpha")
    job_id = job["job_id"]
    assert job["state"] == JobState.QUEUED.value

    # Update Job to Running then Completed
    repo.update_job(job_id, JobState.RUNNING)
    assert repo.get_job(job_id)["state"] == JobState.RUNNING.value

    repo.update_job(job_id, JobState.COMPLETED, completed_views=4)
    completed_job = repo.get_job(job_id)
    assert completed_job["state"] == JobState.COMPLETED.value
    assert completed_job["completed_views"] == 4


def test_verdict_and_finding_persistence(repo):
    screenshot = ScreenshotRef(width=1080, height=2400, storage_path="/path/test.png")
    verdict = VerdictEnvelopeV2(
        capture_id="cap_persist_01",
        session_id="session_beta",
        analysis_status=AnalysisStatus.COMPLETE,
        decision=AnalysisDecision.DEFECT_DETECTED,
        screenshot=screenshot,
        findings=[
            Finding(
                finding_id="find_01",
                type="component_overlap",
                bbox_xyxy=[100, 200, 400, 500],
                explanation="Button overlap",
                confidence=0.88,
                view_ids=["global", "tile_1"],
            ),
            Finding(
                finding_id="find_02",
                type="text_truncation",
                bbox_xyxy=[50, 600, 300, 700],
                explanation="Title truncated",
                confidence=0.91,
                view_ids=["tile_2"],
            ),
        ],
    )

    repo.save_verdict(verdict)
    loaded_verdict = repo.get_verdict(verdict.verdict_id)
    assert loaded_verdict is not None
    assert loaded_verdict.decision == AnalysisDecision.DEFECT_DETECTED
    assert len(loaded_verdict.findings) == 2

    # Check finding details
    f1 = next(f for f in loaded_verdict.findings if f.finding_id == "find_01")
    assert f1.type == "component_overlap"
    assert f1.bbox_xyxy == [100, 200, 400, 500]
    assert "tile_1" in f1.view_ids


def test_reconcile_interrupted_jobs(repo):
    # Setup two running jobs and one queued job
    j1 = repo.create_job("cap_dummy_1")
    j2 = repo.create_job("cap_dummy_2")
    j3 = repo.create_job("cap_dummy_3")

    repo.update_job(j1["job_id"], JobState.RUNNING)
    repo.update_job(j2["job_id"], JobState.CAPTURING)
    # j3 remains QUEUED

    count = repo.reconcile_interrupted_jobs()
    assert count == 2

    assert repo.get_job(j1["job_id"])["state"] == JobState.INTERRUPTED.value
    assert repo.get_job(j2["job_id"])["state"] == JobState.INTERRUPTED.value
    assert repo.get_job(j3["job_id"])["state"] == JobState.QUEUED.value


def test_human_review_addition(repo):
    screenshot = ScreenshotRef(width=1080, height=2400)
    verdict = VerdictEnvelopeV2(
        capture_id="cap_rev_01",
        analysis_status=AnalysisStatus.COMPLETE,
        decision=AnalysisDecision.DEFECT_DETECTED,
        screenshot=screenshot,
        findings=[
            Finding(
                finding_id="find_rev_1",
                type="broken_layout",
                bbox_xyxy=[50, 50, 300, 300],
                explanation="Misaligned grid",
            )
        ],
    )
    repo.save_verdict(verdict)

    rev_id = repo.add_review(
        verdict_id=verdict.verdict_id,
        finding_id="find_rev_1",
        review_status="accepted",
        notes="Confirmed by QA engineer in oral review",
    )
    assert rev_id.startswith("rev_")

    loaded_v = repo.get_verdict(verdict.verdict_id)
    assert loaded_v.findings[0].review_status == ReviewStatus.ACCEPTED
