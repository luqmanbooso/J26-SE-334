"""
Background trigger queue processor for Component 2 (IF-C2-to-C3, FR6).
Executes screen capture and evaluation asynchronously without blocking the test runner.
"""

import logging
from vision_oracle.api.schemas import C2TriggerPayload
from vision_oracle.services.oracle_service import get_oracle_service
from common.adb import AdbDevice

logger = logging.getLogger("vision_oracle.trigger_queue")


def process_c2_trigger_task(payload: C2TriggerPayload) -> None:
    """
    Background worker invoked asynchronously upon receiving POST /api/oracle/trigger.
    Executes live capture and oracle evaluation without blocking C2 caller.
    """
    try:
        service = get_oracle_service()
        device = AdbDevice(serial=payload.device_serial, verify=True)
        result = service.engine.evaluate_device(
            device=device,
            enable_sahi=True,
            action_context=f"C2 Action: {payload.action_id} (Target: {payload.target_element_id})",
        )
        service.save_verdict_to_ledger(result, session_id=payload.session_id)
        logger.info("Successfully processed C2 trigger action: %s", payload.action_id)
    except Exception as exc:
        logger.warning("Failed processing C2 trigger action %s: %s", payload.action_id, exc)
