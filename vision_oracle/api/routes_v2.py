"""
V2 REST Endpoints for Component 3.
Compliant with Phase H and Section 10.1 of HEART C3 Full Implementation Plan.
"""

import os
import io
import time
import base64
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status, Query
from PIL import Image

from vision_oracle.core.config import resolve_path
from vision_oracle.contracts.v2 import (
    JobState,
    CoveragePolicy,
    CaptureBundle,
    VerdictEnvelopeV2,
    ReviewStatus,
)
from vision_oracle.services.oracle_service import get_oracle_service

router = APIRouter(tags=["v2"])


class CaptureRegisterRequest(BaseModel):
    """Payload to register a screenshot capture for analysis."""
    session_id: Optional[str] = Field(default="live_session")
    action_id: Optional[str] = Field(default=None)
    device_serial: Optional[str] = Field(default=None)
    app_package: Optional[str] = Field(default=None)
    image_base64: Optional[str] = Field(default=None, description="Base64 encoded PNG/JPEG screenshot")
    image_path: Optional[str] = Field(default=None, description="Path to local image on disk")
    raw_hierarchy: Optional[str] = Field(default=None, description="Accessibility view hierarchy XML")
    hierarchy_status: str = Field(default="available")
    inter_modality_skew_ms: Optional[float] = Field(default=0.0)


class JobSubmitRequest(BaseModel):
    """Payload to submit an asynchronous analysis job."""
    capture_id: str = Field(..., description="ID of previously registered capture")
    session_id: Optional[str] = Field(default=None)
    policy: CoveragePolicy = Field(default=CoveragePolicy.GLOBAL_PLUS_TILES_V1)


class ReviewSubmitRequest(BaseModel):
    """Payload to record human QA review feedback."""
    verdict_id: str = Field(...)
    finding_id: Optional[str] = Field(default=None)
    review_status: Literal["accepted", "rejected", "edited"] = Field(...)
    reviewer_notes: Optional[str] = Field(default=None)


# --- 1. Liveness & Readiness Endpoints ---

@router.get("/health/live", status_code=status.HTTP_200_OK)
def get_liveness():
    """Fast process liveness check. Zero GPU trigger, returns immediately."""
    return {
        "status": "live",
        "service": "vision_oracle",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


@router.get("/health/ready")
def get_readiness():
    """Truthful operational readiness check. Probes model worker, database, and ADB state."""
    try:
        service = get_oracle_service()
        report = service.check_readiness()
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "ready": False, "model_error": str(exc)}) from exc
    if not report["ready"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", **report},
        )
    return {"status": "ready", **report}


# --- 2. Captures ---

@router.post("/v2/captures", status_code=status.HTTP_201_CREATED)
def register_capture(payload: CaptureRegisterRequest):
    """Registers and persists screenshot capture and hierarchy metadata with SHA-256 verification."""
    service = get_oracle_service()
    repo = service.repository

    if not payload.image_base64 and not payload.image_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either image_base64 or image_path must be provided to register a capture.",
        )

    if payload.image_base64:
        try:
            image_bytes = base64.b64decode(payload.image_base64, validate=True)
            img = Image.open(io.BytesIO(image_bytes))
            img.load()
            width, height = img.size
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base64 screenshot payload: {exc}",
            )
    else:
        raw_path = payload.image_path
        resolved = resolve_path(raw_path) if raw_path else None
        if not resolved or not resolved.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Specified image_path does not exist: {raw_path}",
            )
        try:
            image_bytes = resolved.read_bytes()
            img = Image.open(resolved)
            img.load()
            width, height = img.size
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read image from path {raw_path}: {exc}",
            )

    capture_id = f"cap_{uuid.uuid4().hex[:12]}"
    artifact_path, sha256_hex = repo.save_image_artifact(capture_id, image_bytes)

    bundle = CaptureBundle(
        capture_id=capture_id,
        session_id=payload.session_id,
        action_id=payload.action_id,
        device_serial=payload.device_serial,
        app_package=payload.app_package,
        width=width,
        height=height,
        image_sha256=sha256_hex,
        artifact_path=str(artifact_path),
        raw_hierarchy=payload.raw_hierarchy,
        hierarchy_status=payload.hierarchy_status if payload.raw_hierarchy else "missing",
        inter_modality_skew_ms=payload.inter_modality_skew_ms,
    )
    repo.save_capture(bundle)

    return bundle.model_dump()


# --- 3. Asynchronous Jobs ---

@router.post("/v2/jobs", status_code=status.HTTP_202_ACCEPTED)
def submit_job(payload: JobSubmitRequest):
    """Submits a capture for asynchronous multi-view analysis."""
    service = get_oracle_service()
    try:
        job = service.submit_job(
            capture_id=payload.capture_id,
            session_id=payload.session_id,
            policy=payload.policy,
        )
        return job
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/v2/jobs/{job_id}")
def get_job_status(job_id: str):
    """Polls job progress, status, coverage, and terminal verdict link."""
    service = get_oracle_service()
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found.")

    response_data = dict(job)
    if job["state"] == JobState.COMPLETED.value:
        verdict = service.repository.get_verdict_by_job(job_id)
        if verdict:
            response_data["verdict_id"] = verdict.verdict_id
            response_data["decision"] = verdict.decision.value

    return response_data


@router.post("/v2/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    """Requests cancellation of a queued or running job."""
    service = get_oracle_service()
    cancelled = service.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found.")
    return {"job_id": job_id, "status": "cancellation_requested"}


# --- 4. Results & Sessions ---

@router.get("/v2/results/{verdict_id}")
def get_result(verdict_id: str):
    """Retrieves persisted versioned VerdictEnvelopeV2."""
    service = get_oracle_service()
    verdict = service.repository.get_verdict(verdict_id)
    if not verdict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Verdict '{verdict_id}' not found.")
    return verdict.model_dump()


@router.get("/v2/sessions/{session_id}/results")
def list_session_results(session_id: str):
    """Retrieves all verdicts associated with a given testing session."""
    service = get_oracle_service()
    verdicts = service.repository.list_session_verdicts(session_id)
    return [v.model_dump() for v in verdicts]


# --- 5. Human QA Reviews ---

@router.post("/v2/reviews", status_code=status.HTTP_201_CREATED)
def submit_review(payload: ReviewSubmitRequest):
    """Appends human review record without altering original scientific verdict."""
    service = get_oracle_service()
    verdict = service.repository.get_verdict(payload.verdict_id)
    if not verdict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verdict '{payload.verdict_id}' not found.",
        )

    review_id = service.repository.add_review(
        verdict_id=payload.verdict_id,
        finding_id=payload.finding_id,
        review_status=payload.review_status,
        notes=payload.reviewer_notes,
    )
    return {
        "review_id": review_id,
        "verdict_id": payload.verdict_id,
        "finding_id": payload.finding_id,
        "review_status": payload.review_status,
        "status": "persisted",
    }
