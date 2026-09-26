"""
Component 2 async capture trigger routes.
"""

from fastapi import APIRouter, BackgroundTasks
from vision_oracle.api.schemas import C2TriggerPayload

router = APIRouter(prefix="/api/oracle", tags=["Trigger"])


@router.post("/trigger", status_code=202)
def trigger_action_capture(payload: C2TriggerPayload, background_tasks: BackgroundTasks):
    """
    Non-blocking async capture trigger from Component 2 (FR6, IF-C2-to-C3).
    Enqueues background capture and returns 202 Accepted in <10ms.
    """
    from vision_oracle.services.trigger_queue import process_c2_trigger_task
    background_tasks.add_task(process_c2_trigger_task, payload)
    return {
        "status": "enqueued",
        "action_id": payload.action_id,
        "session_id": payload.session_id,
        "non_blocking": True,
    }
