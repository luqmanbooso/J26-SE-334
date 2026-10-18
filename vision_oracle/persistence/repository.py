"""
Repository layer providing durable SQLite persistence, atomic artifact writes,
and scientific integrity for Component 3.
"""

import json
import os
import time
import uuid
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any

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
from vision_oracle.persistence.db import DatabaseManager, get_database

ARTIFACTS_DIR = Path("results/artifacts")


class OracleRepository:
    """Handles ACID data access for captures, jobs, verdicts, and findings."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None, artifacts_dir: Optional[Path] = None):
        self.db = db_manager or get_database()
        self.artifacts_dir = artifacts_dir or ARTIFACTS_DIR
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def save_image_artifact(self, capture_id: str, image_bytes: bytes) -> tuple[Path, str]:
        """
        Atomically saves screenshot bytes to disk with SHA-256 integrity verification.
        Uses temporary file write followed by atomic rename.
        """
        hasher = hashlib.sha256(image_bytes)
        sha256_hex = hasher.hexdigest()

        final_path = self.artifacts_dir / f"{capture_id}.png"
        temp_path = self.artifacts_dir / f"{capture_id}.tmp_{uuid.uuid4().hex[:8]}"

        try:
            with open(temp_path, "wb") as f:
                f.write(image_bytes)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, final_path)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

        return final_path, sha256_hex

    def save_capture(self, bundle: CaptureBundle) -> None:
        """Persists capture bundle metadata to SQLite."""
        conn = self.db.get_connection()
        with conn:
            # Ensure session exists
            if bundle.session_id:
                conn.execute(
                    "INSERT OR IGNORE INTO sessions (session_id, created_at) VALUES (?, ?);",
                    (bundle.session_id, bundle.timestamp_utc),
                )
            conn.execute(
                """
                INSERT OR REPLACE INTO captures (
                    capture_id, session_id, action_id, app_package, device_serial,
                    image_path, image_sha256, width, height,
                    hierarchy_xml, hierarchy_status, inter_modality_skew_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    bundle.capture_id,
                    bundle.session_id,
                    bundle.action_id,
                    bundle.app_package,
                    bundle.device_serial,
                    bundle.artifact_path or "",
                    bundle.image_sha256,
                    bundle.width,
                    bundle.height,
                    bundle.raw_hierarchy,
                    bundle.hierarchy_status,
                    bundle.inter_modality_skew_ms,
                    bundle.timestamp_utc,
                ),
            )

    @staticmethod
    def _row_to_capture_bundle(row: Any) -> CaptureBundle:
        return CaptureBundle(
            capture_id=row["capture_id"],
            session_id=row["session_id"],
            action_id=row["action_id"] if "action_id" in row.keys() else None,
            app_package=row["app_package"],
            device_serial=row["device_serial"],
            timestamp_utc=row["created_at"],
            width=row["width"],
            height=row["height"],
            image_sha256=row["image_sha256"],
            artifact_path=row["image_path"],
            raw_hierarchy=row["hierarchy_xml"],
            hierarchy_status=row["hierarchy_status"],
            inter_modality_skew_ms=row["inter_modality_skew_ms"],
        )

    def get_capture(self, capture_id: str) -> Optional[CaptureBundle]:
        """Loads capture bundle by ID."""
        conn = self.db.get_connection()
        cur = conn.execute("SELECT * FROM captures WHERE capture_id = ?;", (capture_id,))
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_capture_bundle(row)

    def list_session_captures(self, session_id: str) -> List[CaptureBundle]:
        """Retrieves all captures belonging to a session in chronological order."""
        conn = self.db.get_connection()
        cur = conn.execute(
            "SELECT * FROM captures WHERE session_id = ? ORDER BY created_at ASC;",
            (session_id,),
        )
        rows = cur.fetchall()
        return [self._row_to_capture_bundle(r) for r in rows]

    def get_capture_by_action(self, action_id: str, session_id: Optional[str] = None) -> Optional[CaptureBundle]:
        """Retrieves capture associated with a specific C2 action ID."""
        conn = self.db.get_connection()
        if session_id:
            cur = conn.execute(
                "SELECT * FROM captures WHERE action_id = ? AND session_id = ? ORDER BY created_at DESC LIMIT 1;",
                (action_id, session_id),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM captures WHERE action_id = ? ORDER BY created_at DESC LIMIT 1;",
                (action_id,),
            )
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_capture_bundle(row)

    def create_job(
        self,
        capture_id: str,
        session_id: Optional[str] = None,
        policy: str = "global_plus_tiles_v1",
        planned_views: int = 4,
    ) -> Dict[str, Any]:
        """Creates a new durable job record in QUEUED state."""
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self.db.get_connection()
        with conn:
            # Ensure session and capture exist to satisfy foreign keys
            if session_id:
                conn.execute(
                    "INSERT OR IGNORE INTO sessions (session_id, created_at) VALUES (?, ?);",
                    (session_id, now),
                )
            conn.execute(
                """
                INSERT OR IGNORE INTO captures (
                    capture_id, session_id, app_package, device_serial,
                    image_path, image_sha256, width, height,
                    hierarchy_xml, hierarchy_status, inter_modality_skew_ms, created_at
                ) VALUES (?, ?, '', '', '', '', 1080, 2400, '', 'missing', 0.0, ?);
                """,
                (capture_id, session_id, now),
            )
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, capture_id, session_id, state, policy,
                    planned_views, completed_views, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?);
                """,
                (job_id, capture_id, session_id, JobState.QUEUED.value, policy, planned_views, now),
            )
        return {
            "job_id": job_id,
            "capture_id": capture_id,
            "session_id": session_id,
            "state": JobState.QUEUED.value,
            "policy": policy,
            "planned_views": planned_views,
            "completed_views": 0,
            "created_at": now,
        }

    def update_job(
        self,
        job_id: str,
        state: JobState,
        completed_views: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Updates job state transition and progress timestamps."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self.db.get_connection()
        with conn:
            if state in (JobState.RUNNING, JobState.CAPTURING):
                conn.execute(
                    "UPDATE jobs SET state = ?, started_at = COALESCE(started_at, ?) WHERE job_id = ?;",
                    (state.value, now, job_id),
                )
            elif state in (JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED, JobState.INTERRUPTED):
                if completed_views is not None:
                    conn.execute(
                        """
                        UPDATE jobs SET state = ?, completed_views = ?, completed_at = ?, error_message = ?
                        WHERE job_id = ?;
                        """,
                        (state.value, completed_views, now, error_message, job_id),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE jobs SET state = ?, completed_at = ?, error_message = ?
                        WHERE job_id = ?;
                        """,
                        (state.value, now, error_message, job_id),
                    )
            else:
                conn.execute("UPDATE jobs SET state = ? WHERE job_id = ?;", (state.value, job_id))

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves job record by ID."""
        conn = self.db.get_connection()
        cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?;", (job_id,))
        row = cur.fetchone()
        if not row:
            return None
        return dict(row)

    def get_job_by_capture(self, capture_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves most recent job associated with a capture ID."""
        conn = self.db.get_connection()
        cur = conn.execute("SELECT * FROM jobs WHERE capture_id = ? ORDER BY created_at DESC LIMIT 1;", (capture_id,))
        row = cur.fetchone()
        if not row:
            return None
        return dict(row)

    def list_capture_jobs(self, capture_id: str) -> List[Dict[str, Any]]:
        """Retrieves all jobs associated with a capture ID."""
        conn = self.db.get_connection()
        cur = conn.execute("SELECT * FROM jobs WHERE capture_id = ? ORDER BY created_at ASC;", (capture_id,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    def update_job_c4_delivery(self, job_id: str, status: str) -> None:
        """Updates C4 delivery dispatch status for a job."""
        conn = self.db.get_connection()
        with conn:
            conn.execute("UPDATE jobs SET c4_delivery_status = ? WHERE job_id = ?;", (status, job_id))

    def save_verdict(self, verdict: VerdictEnvelopeV2) -> None:
        """Atomically saves verdict and all associated findings."""
        conn = self.db.get_connection()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with conn:
            # Ensure session, capture, and job exist to satisfy foreign keys
            if verdict.session_id:
                conn.execute(
                    "INSERT OR IGNORE INTO sessions (session_id, created_at) VALUES (?, ?);",
                    (verdict.session_id, now),
                )
            conn.execute(
                """
                INSERT OR IGNORE INTO captures (
                    capture_id, session_id, app_package, device_serial,
                    image_path, image_sha256, width, height,
                    hierarchy_xml, hierarchy_status, inter_modality_skew_ms, created_at
                ) VALUES (?, ?, '', '', ?, ?, ?, ?, '', 'missing', 0.0, ?);
                """,
                (
                    verdict.capture_id,
                    verdict.session_id,
                    verdict.screenshot.storage_path or "",
                    verdict.screenshot.sha256 or "",
                    verdict.screenshot.width,
                    verdict.screenshot.height,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO jobs (
                    job_id, capture_id, session_id, state, policy,
                    planned_views, completed_views, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    verdict.job_id,
                    verdict.capture_id,
                    verdict.session_id,
                    JobState.COMPLETED.value,
                    verdict.coverage.policy,
                    verdict.coverage.planned_views,
                    verdict.coverage.completed_views,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO verdicts (
                    verdict_id, job_id, session_id, capture_id, schema_version,
                    decision, analysis_status, model_run_id, coverage_json,
                    screenshot_json, timings_json, errors_json, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    verdict.verdict_id,
                    verdict.job_id,
                    verdict.session_id,
                    verdict.capture_id,
                    verdict.schema_version,
                    verdict.decision.value,
                    verdict.analysis_status.value,
                    verdict.model_run_id,
                    verdict.coverage.model_dump_json(),
                    verdict.screenshot.model_dump_json(),
                    json.dumps(verdict.timings_ms),
                    json.dumps(verdict.errors),
                    json.dumps(verdict.metadata),
                    now,
                ),
            )

            # Persist findings
            for f in verdict.findings:
                x1, y1, x2, y2 = (f.bbox_xyxy[0], f.bbox_xyxy[1], f.bbox_xyxy[2], f.bbox_xyxy[3]) if f.bbox_xyxy else (None, None, None, None)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO findings (
                        finding_id, verdict_id, defect_type, x1, y1, x2, y2,
                        element_ref, explanation, source, confidence,
                        confidence_method, view_ids_json, review_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        f.finding_id,
                        verdict.verdict_id,
                        f.type,
                        x1,
                        y1,
                        x2,
                        y2,
                        f.element_ref,
                        f.explanation,
                        f.source,
                        f.confidence,
                        f.confidence_method,
                        json.dumps(f.view_ids),
                        f.review_status.value if hasattr(f.review_status, "value") else str(f.review_status),
                    ),
                )

    def get_verdict(self, verdict_id: str) -> Optional[VerdictEnvelopeV2]:
        """Loads verdict envelope and reconstructed findings by verdict_id."""
        conn = self.db.get_connection()
        cur = conn.execute("SELECT * FROM verdicts WHERE verdict_id = ?;", (verdict_id,))
        vrow = cur.fetchone()
        if not vrow:
            return None

        # Fetch findings
        f_cur = conn.execute("SELECT * FROM findings WHERE verdict_id = ?;", (verdict_id,))
        frows = f_cur.fetchall()
        findings: List[Finding] = []
        for r in frows:
            bbox = None
            if r["x1"] is not None and r["y1"] is not None and r["x2"] is not None and r["y2"] is not None:
                bbox = [int(r["x1"]), int(r["y1"]), int(r["x2"]), int(r["y2"])]

            findings.append(
                Finding(
                    finding_id=r["finding_id"],
                    type=r["defect_type"],
                    bbox_xyxy=bbox,
                    element_ref=r["element_ref"],
                    explanation=r["explanation"],
                    source=r["source"],
                    confidence=r["confidence"],
                    confidence_method=r["confidence_method"],
                    view_ids=json.loads(r["view_ids_json"] or "[]"),
                    review_status=ReviewStatus(r["review_status"]),
                )
            )

        coverage_dict = json.loads(vrow["coverage_json"])
        screenshot_dict = json.loads(vrow["screenshot_json"])

        return VerdictEnvelopeV2(
            schema_version=vrow["schema_version"],
            job_id=vrow["job_id"],
            verdict_id=vrow["verdict_id"],
            session_id=vrow["session_id"],
            capture_id=vrow["capture_id"],
            analysis_status=AnalysisStatus(vrow["analysis_status"]),
            decision=AnalysisDecision(vrow["decision"]),
            coverage=Coverage(**coverage_dict),
            screenshot=ScreenshotRef(**screenshot_dict),
            findings=findings,
            model_run_id=vrow["model_run_id"],
            timings_ms=json.loads(vrow["timings_json"] or "{}"),
            errors=json.loads(vrow["errors_json"] or "[]"),
            metadata=json.loads(vrow["metadata_json"] or "{}"),
        )

    def get_verdict_by_job(self, job_id: str) -> Optional[VerdictEnvelopeV2]:
        """Loads verdict envelope by job_id."""
        conn = self.db.get_connection()
        cur = conn.execute("SELECT verdict_id FROM verdicts WHERE job_id = ?;", (job_id,))
        row = cur.fetchone()
        if not row:
            return None
        return self.get_verdict(row["verdict_id"])

    def list_session_verdicts(self, session_id: str) -> List[VerdictEnvelopeV2]:
        """Retrieves all verdicts belonging to a testing session in reverse chronological order."""
        conn = self.db.get_connection()
        cur = conn.execute(
            "SELECT verdict_id FROM verdicts WHERE session_id = ? ORDER BY created_at DESC;",
            (session_id,),
        )
        rows = cur.fetchall()
        results: List[VerdictEnvelopeV2] = []
        for r in rows:
            v = self.get_verdict(r["verdict_id"])
            if v:
                results.append(v)
        return results

    def list_recent_verdicts(self, limit: int = 50) -> List[VerdictEnvelopeV2]:
        """Retrieves most recent verdicts across all sessions."""
        conn = self.db.get_connection()
        cur = conn.execute("SELECT verdict_id FROM verdicts ORDER BY created_at DESC LIMIT ?;", (limit,))
        rows = cur.fetchall()
        results: List[VerdictEnvelopeV2] = []
        for r in rows:
            v = self.get_verdict(r["verdict_id"])
            if v:
                results.append(v)
        return results

    def add_review(
        self,
        verdict_id: str,
        review_status: str,
        finding_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> str:
        """Appends human review record without modifying original scientific verdict."""
        review_id = f"rev_{uuid.uuid4().hex[:12]}"
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO reviews (review_id, verdict_id, finding_id, review_status, reviewer_notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (review_id, verdict_id, finding_id, review_status, notes or "", now),
            )
            # Update finding review_status if finding_id provided
            if finding_id:
                conn.execute(
                    "UPDATE findings SET review_status = ? WHERE finding_id = ?;",
                    (review_status, finding_id),
                )
        return review_id

    def reconcile_interrupted_jobs(self) -> int:
        """Startup reconciliation: Marks any hanging running/capturing jobs as interrupted."""
        conn = self.db.get_connection()
        with conn:
            cur = conn.execute(
                """
                UPDATE jobs
                SET state = ?, error_message = 'Process interrupted during execution (server restart)'
                WHERE state IN (?, ?);
                """,
                (JobState.INTERRUPTED.value, JobState.RUNNING.value, JobState.CAPTURING.value),
            )
            return cur.rowcount


_REPO_INSTANCE: Optional[OracleRepository] = None


def get_repository() -> OracleRepository:
    """Returns singleton OracleRepository instance."""
    global _REPO_INSTANCE
    if _REPO_INSTANCE is None:
        _REPO_INSTANCE = OracleRepository()
    return _REPO_INSTANCE
