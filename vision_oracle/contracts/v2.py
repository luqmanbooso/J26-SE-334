"""
Canonical Contract v2 for Component 3 (Local Vision Oracle).
Compliant with HEART C3 Full Implementation Plan (v1.0, 18 Oct 2026).
Enforces:
- Strict typed schemas separating job state from scientific assessment
- Invariant: no_defect_detected requires complete status and zero accepted findings
- Invariant: partial analysis with zero findings is strictly inconclusive
- Invariant: errors never convert to clean verdicts
- Invariant: physical pixel coordinates [x1, y1, x2, y2] strictly bounded by original screen resolution
- Bi-directional adapters for legacy C3OracleResult and C4 C3Verdict envelopes
"""

from __future__ import annotations

import uuid
import time
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator


class JobState(str, Enum):
    """Lifecycle states of an evaluation job."""
    QUEUED = "queued"
    CAPTURING = "capturing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class AnalysisStatus(str, Enum):
    """Execution completeness of the scientific visual analysis."""
    COMPLETE = "complete"
    PARTIAL = "partial"
    ERROR = "error"


class AnalysisDecision(str, Enum):
    """Definitive analytical conclusion of the oracle."""
    DEFECT_DETECTED = "defect_detected"
    NO_DEFECT_DETECTED = "no_defect_detected"
    INCONCLUSIVE = "inconclusive"


class FindingType(str, Enum):
    """Supported 6-class academic non-crash defect taxonomy."""
    COMPONENT_OVERLAP = "component_overlap"
    TEXT_TRUNCATION = "text_truncation"
    UNRENDERED_ASSET = "unrendered_asset"
    BROKEN_LAYOUT = "broken_layout"
    MISSING_COMPONENT = "missing_component"
    SUSPECTED_UNRESPONSIVE = "suspected_unresponsive"


class ReviewStatus(str, Enum):
    """Human QA review status."""
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EDITED = "edited"


class CoveragePolicy(str, Enum):
    """Scanning and view coverage policy."""
    GLOBAL_ONLY = "global_only"
    GLOBAL_ONLY_V1 = "global_only"
    GLOBAL_PLUS_TILES_V1 = "global_plus_tiles_v1"


class Coverage(BaseModel):
    """Inspection coverage metadata."""
    policy: str = Field(default=CoveragePolicy.GLOBAL_PLUS_TILES_V1.value)
    planned_views: int = Field(default=1, ge=1)
    completed_views: int = Field(default=1, ge=0)
    warnings: List[str] = Field(default_factory=list)


class ScreenshotRef(BaseModel):
    """Original screenshot metadata and physical coordinate space."""
    artifact_id: str = Field(default_factory=lambda: f"art_{uuid.uuid4().hex[:12]}")
    width: int = Field(..., gt=0, description="Original screenshot width in physical pixels")
    height: int = Field(..., gt=0, description="Original screenshot height in physical pixels")
    coordinate_space: str = Field(default="original_pixels_xyxy")
    sha256: Optional[str] = Field(default=None, description="SHA256 hex digest of raw image bytes")
    storage_path: Optional[str] = Field(default=None, description="Local disk path to immutable artifact")


class Finding(BaseModel):
    """An individual localized visual defect finding."""
    finding_id: str = Field(default_factory=lambda: f"find_{uuid.uuid4().hex[:12]}")
    type: str = Field(..., description="Taxonomy type string (e.g. component_overlap)")
    bbox_xyxy: Optional[List[int]] = Field(
        default=None,
        description="Physical pixel bounding box [x1, y1, x2, y2] strictly within screen dimensions"
    )
    element_ref: Optional[str] = Field(
        default=None,
        description="Resource-ID or accessibility identifier mapped from hierarchy, or null if ambiguous"
    )
    explanation: str = Field(
        ...,
        description="Traceable explanation grounded in observable visual or temporal evidence"
    )
    source: str = Field(default="vlm", description="vlm, geometric_rule, temporal_rule, or human_review")
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Calibrated probability if method supplied, else null"
    )
    confidence_method: str = Field(
        default="unavailable",
        description="Method: calibrated_platt_v1, raw_heuristic, or unavailable"
    )
    view_ids: List[str] = Field(
        default_factory=lambda: ["global"],
        description="IDs of views/slices where this defect was observed"
    )
    review_status: ReviewStatus = Field(default=ReviewStatus.UNREVIEWED)

    @model_validator(mode="after")
    def validate_box_order(self) -> Finding:
        if self.bbox_xyxy is not None:
            if len(self.bbox_xyxy) != 4:
                raise ValueError("bbox_xyxy must contain exactly 4 integers: [x1, y1, x2, y2]")
            x1, y1, x2, y2 = self.bbox_xyxy
            if x1 >= x2:
                raise ValueError(f"Invalid horizontal box bounds: x1={x1} >= x2={x2}")
            if y1 >= y2:
                raise ValueError(f"Invalid vertical box bounds: y1={y1} >= y2={y2}")
            if x1 < 0 or y1 < 0:
                raise ValueError(f"Negative coordinates are invalid: x1={x1}, y1={y1}")
        return self


class CaptureBundle(BaseModel):
    """Complete multimodal input bundle captured from device or test harness."""
    capture_id: str = Field(default_factory=lambda: f"cap_{uuid.uuid4().hex[:12]}")
    session_id: Optional[str] = Field(default="live_session")
    action_id: Optional[str] = Field(default=None)
    device_serial: Optional[str] = Field(default=None)
    app_package: Optional[str] = Field(default=None)
    timestamp_utc: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    timestamp_mono: float = Field(default_factory=time.monotonic)
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)
    image_sha256: str = Field(..., description="SHA-256 digest of image bytes")
    artifact_path: Optional[str] = Field(default=None)
    raw_hierarchy: Optional[str] = Field(default=None)
    hierarchy_status: str = Field(default="available", description="available, stale, missing, malformed")
    inter_modality_skew_ms: Optional[float] = Field(
        default=0.0,
        description="Time difference between screenshot capture and hierarchy capture"
    )
    capture_started_epoch_ms: Optional[int] = Field(default=None)
    capture_completed_epoch_ms: Optional[int] = Field(default=None)
    warnings: List[str] = Field(default_factory=list)


class VerdictEnvelopeV2(BaseModel):
    """Canonical internal scientific result envelope (schema 2.0)."""
    schema_version: str = Field(default="2.0")
    job_id: str = Field(default_factory=lambda: f"job_{uuid.uuid4().hex[:12]}")
    verdict_id: str = Field(default_factory=lambda: f"verdict_{uuid.uuid4().hex[:12]}")
    session_id: Optional[str] = Field(default=None)
    action_id: Optional[str] = Field(default=None)
    capture_id: str = Field(...)
    analysis_status: AnalysisStatus = Field(...)
    decision: AnalysisDecision = Field(...)
    coverage: Coverage = Field(default_factory=Coverage)
    screenshot: ScreenshotRef = Field(...)
    scope: Dict[str, Any] = Field(
        default_factory=lambda: {"mode": "single_primary_visual_finding", "exhaustive": False}
    )
    primary_finding: Optional[Finding] = Field(
        default=None,
        description="Supported single primary visual finding for PP1, or null if clean"
    )
    findings: List[Finding] = Field(default_factory=list)
    model_run_id: str = Field(default="qwen2-vl-2b-instruct-local")
    timings_ms: Dict[str, float] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_scientific_invariants(self) -> VerdictEnvelopeV2:
        """
        Enforce strict scientific truthfulness rules:
        - Populate primary_finding from findings if present
        - no_defect_detected requires complete status and zero findings.
        - partial analysis with zero findings must be inconclusive.
        - error status must never be reported as no_defect_detected.
        - bounding boxes must remain strictly within screenshot physical pixel bounds.
        """
        if self.primary_finding is None and len(self.findings) > 0:
            self.primary_finding = self.findings[0]
        elif self.primary_finding is not None and len(self.findings) == 0:
            self.findings = [self.primary_finding]

        # Rule 1: Clean verdict requires complete coverage
        if self.decision == AnalysisDecision.NO_DEFECT_DETECTED:
            if self.analysis_status != AnalysisStatus.COMPLETE:
                raise ValueError(
                    f"Invalid verdict: decision cannot be 'no_defect_detected' when "
                    f"analysis_status is '{self.analysis_status.value}'"
                )
            if len(self.findings) > 0:
                raise ValueError(
                    f"Invalid verdict: decision cannot be 'no_defect_detected' when "
                    f"{len(self.findings)} findings are present"
                )

        # Rule 2: Partial scan with zero findings is inconclusive
        if self.analysis_status == AnalysisStatus.PARTIAL and len(self.findings) == 0:
            if self.decision != AnalysisDecision.INCONCLUSIVE:
                raise ValueError(
                    "Invalid verdict: partial analysis with zero findings must produce decision='inconclusive'"
                )

        # Rule 3: Error analysis can never certify defect-free state
        if self.analysis_status == AnalysisStatus.ERROR:
            if self.decision == AnalysisDecision.NO_DEFECT_DETECTED:
                raise ValueError("Invalid verdict: error status cannot produce 'no_defect_detected'")

        # Rule 4: Defect detected requires at least one finding
        if self.decision == AnalysisDecision.DEFECT_DETECTED and len(self.findings) == 0:
            raise ValueError("Invalid verdict: decision='defect_detected' requires at least one finding")

        # Rule 5: Check physical pixel bounds for all findings
        width = self.screenshot.width
        height = self.screenshot.height
        for f in self.findings:
            if f.bbox_xyxy is not None:
                x1, y1, x2, y2 = f.bbox_xyxy
                if x2 > width or y2 > height:
                    raise ValueError(
                        f"Finding {f.finding_id} bounds [{x1}, {y1}, {x2}, {y2}] "
                        f"exceed screenshot dimensions [{width}, {height}]"
                    )

        return self

    def to_c4_verdict(self, schema_version: str = "2.0.0") -> Any:
        """Bi-directional adapter: Converts V2 envelope to Component 4 C3Verdict contract."""
        try:
            from c4.c3_interface.contract import C3Verdict, ScreenshotEvidence, DefectRegion
        except ImportError:
            import sys
            from pathlib import Path
            repo_candidates = [
                Path(__file__).resolve().parent.parent,
                Path(__file__).resolve().parent.parent.parent,
                Path.cwd(),
                Path.cwd() / "J26-SE-334",
            ]
            for r in repo_candidates:
                p = r / "component4" / "src"
                if p.exists() and str(p) not in sys.path:
                    sys.path.insert(0, str(p))
            from c4.c3_interface.contract import C3Verdict, ScreenshotEvidence, DefectRegion

        screenshot_evidence = ScreenshotEvidence(
            path=self.screenshot.storage_path,
            width=self.screenshot.width,
            height=self.screenshot.height,
        )

        regions: List[DefectRegion] = []
        for f in self.findings:
            if f.bbox_xyxy is not None:
                x1, y1, x2, y2 = f.bbox_xyxy
                w = max(1, x2 - x1)
                h = max(1, y2 - y1)
                # Ensure clamped to screenshot boundary for C4 validator
                if x1 + w > self.screenshot.width:
                    w = self.screenshot.width - x1
                if y1 + h > self.screenshot.height:
                    h = self.screenshot.height - y1

                regions.append(
                    DefectRegion(
                        x=x1,
                        y=y1,
                        width=w,
                        height=h,
                        label=f.type,
                    )
                )

        primary = self.primary_finding or (self.findings[0] if self.findings else None)
        primary_defect = primary.type if primary else None

        # Status-aware mapping: do not reduce inconclusive to has_gui_defect=False!
        if self.decision == AnalysisDecision.DEFECT_DETECTED:
            has_defect: Optional[bool] = True
        elif self.decision == AnalysisDecision.NO_DEFECT_DETECTED:
            has_defect = False
        else:
            # INCONCLUSIVE (analysis_status is PARTIAL or ERROR)
            has_defect = None

        primary_confidence = float(primary.confidence) if (primary and primary.confidence is not None) else 0.0

        # Handover outcome (PP1 Section 7):
        # - Ready for test generation: enough action and target information exists.
        # - Evidence only: finding is preserved, but reproduction context is insufficient.
        if has_defect is True:
            action_ctx = self.action_id or self.metadata.get("action_id")
            target_elem = (primary.element_ref if primary else None) or self.metadata.get("target_element_id")
            if action_ctx and target_elem:
                handover_outcome = "ready_for_test_generation"
            else:
                handover_outcome = "evidence_only"
        elif has_defect is False:
            handover_outcome = "evidence_only"
        else:
            handover_outcome = "unsupported_inconclusive"

        evidence_payload = {
            "decision": self.decision.value,
            "analysis_status": self.analysis_status.value,
            "handover_outcome": handover_outcome,
            "capture_id": self.capture_id,
            "model_run_id": self.model_run_id,
            "coverage": self.coverage.model_dump(),
            "findings": [f.model_dump() for f in self.findings],
            "timings_ms": self.timings_ms,
            "errors": self.errors,
        }
        if self.action_id:
            evidence_payload["action_id"] = self.action_id

        meta = dict(self.metadata)
        meta["model_run_id"] = self.model_run_id
        meta["capture_id"] = self.capture_id
        if self.action_id:
            meta["action_id"] = self.action_id

        return C3Verdict(
            schema_version=schema_version,
            verdict_id=self.verdict_id,
            session_id=self.session_id,
            has_gui_defect=has_defect,
            defect_type=primary_defect if has_defect else None,
            confidence=primary_confidence,
            screenshot=screenshot_evidence,
            regions=regions,
            evidence=evidence_payload,
            metadata=meta,
        )
