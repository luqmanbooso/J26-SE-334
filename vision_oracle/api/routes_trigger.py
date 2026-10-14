import logging
from fastapi import APIRouter, HTTPException
from vision_oracle.api.schemas import C2TriggerPayload
from vision_oracle.services.capture_service import CaptureService
from common.adb import NoDeviceError

logger = logging.getLogger("vision_oracle.api.trigger")
router = APIRouter(prefix="/api/oracle", tags=["Trigger"])


@router.post("/trigger", status_code=202)
def trigger_action_capture(payload: C2TriggerPayload):
    """
    Action-linked evidence capture trigger from Component 2 (PP1 Section 4).
    Synchronously captures immutable screen evidence and returns capture_id and job_id in <150ms.
    Analysis runs asynchronously via the bounded job worker.
    """
    try:
        capture_svc = CaptureService()
        result = capture_svc.capture_action_evidence(
            action_id=payload.action_id,
            session_id=payload.session_id,
            device_serial=getattr(payload, "device_serial", None),
            app_package=getattr(payload, "app_package", None),
            action_started_epoch_ms=getattr(payload, "action_started_epoch_ms", None),
            action_completed_epoch_ms=getattr(payload, "action_completed_epoch_ms", None),
            observation=getattr(payload, "observation", None),
            perturbation_event_ids=getattr(payload, "perturbation_event_ids", None),
        )
        return {
            **result,
            "status": "enqueued",
            "action_id": payload.action_id,
            "session_id": payload.session_id,
            "capture_id": result.get("capture_id"),
            "job_id": result.get("job_id"),
            "non_blocking": True,
        }
    except NoDeviceError as exc:
        logger.warning("Device unavailable on capture trigger for action %s: %s", payload.action_id, exc)
        raise HTTPException(status_code=503, detail=f"Device unavailable: {exc}")
    except RuntimeError as exc:
        if "queue is full" in str(exc).lower() or "backpressure" in str(exc).lower():
            logger.warning("Queue full on capture trigger for action %s: %s", payload.action_id, exc)
            raise HTTPException(status_code=503, detail=str(exc))
        raise HTTPException(status_code=500, detail=f"Capture trigger failed: {exc}")
    except Exception as exc:
        logger.error("Capture trigger failure for action %s: %s", payload.action_id, exc)
        raise HTTPException(status_code=500, detail=f"Capture trigger failed: {exc}")
