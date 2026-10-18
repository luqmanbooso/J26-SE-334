"""
Capture Service for Component 3 (Local Vision Oracle).
Compliant with PP1 Section 4 (Action-Linked Capture and Handover Schema).

Guarantees:
1. Strict Action-to-Capture Link: Captures evidence immediately when requested by C2
   before C2 continues, ensuring verdict references the exact post-action screen state.
2. Synchronous Capture Acknowledgement: C2 waits only for fast screenshot capture (<150ms),
   never for slow multi-view VLM inference.
3. Foreground Package Policy: Validates that foreground package matches target app
   or allowed system dialogs, rejecting/warning if a launcher is captured.
4. Multimodal Skew Tracking: Measures monotonic difference between screenshot and hierarchy,
   marking hierarchy stale when skew > 1000ms.
5. Idempotent C2 Handover: Re-submitting the same action_id returns the existing capture
   and job without duplicate device actuation or queue pollution.
"""

from __future__ import annotations

import io
import time
import uuid
import logging
from typing import Optional, Dict, Any, List, Union
from pathlib import Path
from PIL import Image

from common.adb import AdbDevice, NoDeviceError
from vision_oracle.contracts.v2 import CaptureBundle, JobState
from vision_oracle.persistence.repository import OracleRepository, get_repository

logger = logging.getLogger("vision_oracle.capture_service")

ALLOWED_SYSTEM_PACKAGES = {
    "com.android.systemui",
    "android",
    "com.google.android.permissioncontroller",
    "com.android.packageinstaller",
}


def extract_foreground_package(device: AdbDevice) -> Optional[str]:
    """Retrieves current foreground package name via dumpsys window or activity."""
    import re
    try:
        out = device.shell("dumpsys", "window", "windows")
        for line in out.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                m = re.search(r"([a-zA-Z0-9._]+)/", line)
                if m:
                    return m.group(1)
        # Fallback to activity top
        out_act = device.shell("dumpsys", "activity", "top")
        for line in out_act.splitlines():
            if "ACTIVITY" in line:
                m = re.search(r"([a-zA-Z0-9._]+)/", line)
                if m:
                    return m.group(1)
    except Exception as exc:
        logger.debug("Failed extracting foreground package: %s", exc)
    return None


class CaptureService:
    """Service responsible for acquiring, validating, and persisting immutable evidence captures."""

    def __init__(self, repository: Optional[OracleRepository] = None):
        if repository is not None:
            self._repo = repository
        else:
            try:
                from vision_oracle.services.oracle_service import get_oracle_service
                svc = get_oracle_service()
                self._repo = svc.repository if (svc and hasattr(svc, "repository")) else get_repository()
            except Exception:
                self._repo = get_repository()

    def capture_action_evidence(
        self,
        action_id: str,
        session_id: str = "live_session",
        device_serial: Optional[str] = None,
        app_package: Optional[str] = None,
        action_started_epoch_ms: Optional[int] = None,
        action_completed_epoch_ms: Optional[int] = None,
        observation: Optional[Dict[str, Any]] = None,
        perturbation_event_ids: Optional[List[str]] = None,
        device: Optional[Any] = None,
        image_bytes_override: Optional[bytes] = None,
        hierarchy_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes immediate immutable evidence capture corresponding to a completed C2 action.
        Returns capture metadata and enqueued job ID for async processing.
        """
        # 1. Idempotency check: Return existing capture if already registered for action_id
        existing_captures = self._repo.list_session_captures(session_id)
        for cap in existing_captures:
            if cap.action_id == action_id:
                logger.info("Idempotent hit: action_id '%s' already captured in capture '%s'", action_id, cap.capture_id)
                existing_job = self._repo.get_job_by_capture(cap.capture_id)
                return {
                    "status": "already_captured",
                    "capture_id": cap.capture_id,
                    "job_id": existing_job["job_id"] if existing_job else None,
                    "action_id": action_id,
                    "session_id": session_id,
                    "idempotent": True,
                }

        t_start_mono = time.monotonic()
        capture_started_epoch_ms = int(time.time() * 1000)
        capture_id = f"cap_{uuid.uuid4().hex[:12]}"
        warnings: List[str] = []

        # 2. Acquire screenshot bytes
        if image_bytes_override:
            image_bytes = image_bytes_override
            fg_pkg = app_package or "com.test.mock"
            t_cap_end_mono = time.monotonic()
            raw_hierarchy = hierarchy_override
            skew_ms = 0.0
        else:
            if device is None:
                target_serial = AdbDevice.resolve_serial(device_serial)
                device = AdbDevice(serial=target_serial, verify=True)

            image_bytes = device.screencap(as_pil=False)
            t_cap_end_mono = time.monotonic()

            fg_pkg = extract_foreground_package(device)
            # Hierarchy capture with skew measurement
            try:
                t_hier_mono = time.monotonic()
                raw_hierarchy = device.dump_hierarchy(max_age_s=0.5)
                skew_ms = abs(t_hier_mono - t_cap_end_mono) * 1000.0
            except Exception as err:
                raw_hierarchy = None
                skew_ms = 0.0
                warnings.append(f"Hierarchy capture skipped: {err}")

        capture_completed_epoch_ms = int(time.time() * 1000)
        capture_duration_ms = (t_cap_end_mono - t_start_mono) * 1000.0

        # 3. Foreground Package Validation Policy
        if app_package and fg_pkg:
            if fg_pkg != app_package and fg_pkg not in ALLOWED_SYSTEM_PACKAGES:
                warn_msg = (
                    f"Foreground package policy warning: focus is '{fg_pkg}', expected target app '{app_package}'"
                )
                logger.warning(warn_msg)
                warnings.append(warn_msg)

        # 4. Hierarchy Status & Skew Evaluation
        if not raw_hierarchy:
            hierarchy_status = "missing"
        elif skew_ms > 1000.0:
            hierarchy_status = "stale"
            warnings.append(f"Inter-modality skew is {skew_ms:.1f}ms (>1000ms threshold); hierarchy marked stale")
        else:
            hierarchy_status = "available"

        # 5. Image verification and dimensions
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.load()
            width, height = img.size
        except Exception as exc:
            raise ValueError(f"Captured screenshot bytes are invalid or corrupted: {exc}")

        # 6. Atomic artifact write with SHA-256
        artifact_path, sha256_hex = self._repo.save_image_artifact(capture_id, image_bytes)

        # 7. Persist immutable CaptureBundle
        bundle = CaptureBundle(
            capture_id=capture_id,
            session_id=session_id,
            action_id=action_id,
            device_serial=device_serial or (getattr(device, "serial", None) if device else None),
            app_package=fg_pkg or app_package,
            width=width,
            height=height,
            image_sha256=sha256_hex,
            artifact_path=str(artifact_path),
            raw_hierarchy=raw_hierarchy if hierarchy_status == "available" else None,
            hierarchy_status=hierarchy_status,
            inter_modality_skew_ms=round(skew_ms, 2),
            capture_started_epoch_ms=capture_started_epoch_ms,
            capture_completed_epoch_ms=capture_completed_epoch_ms,
            warnings=warnings,
        )
        self._repo.save_capture(bundle)

        # 8. Submit asynchronous analysis job
        from vision_oracle.services.oracle_service import get_oracle_service
        service = get_oracle_service()
        job_record = service.submit_job(capture_id=capture_id, session_id=session_id)

        return {
            "status": "captured",
            "capture_id": capture_id,
            "job_id": job_record["job_id"],
            "action_id": action_id,
            "session_id": session_id,
            "foreground_package": fg_pkg,
            "capture_duration_ms": round(capture_duration_ms, 2),
            "capture_started_epoch_ms": capture_started_epoch_ms,
            "capture_completed_epoch_ms": capture_completed_epoch_ms,
            "inter_modality_skew_ms": round(skew_ms, 2),
            "warnings": warnings,
            "non_blocking_inference": True,
        }
