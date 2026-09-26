"""
Status and health check routes.
"""

from fastapi import APIRouter
from common.adb import AdbDevice
from vision_oracle.core.config import ZERO_CLOUD_EGRESS
from vision_oracle.services.oracle_service import get_oracle_service

router = APIRouter(tags=["Status"])


@router.get("/")
def root():
    service = get_oracle_service()
    return {
        "service": "HEART Component 3: Localized Multimodal Vision-Semantic Oracle",
        "description": "Offline edge oracle for non-crash Android UI defect detection, multi-slice SAHI tiling, and self-healing test synthesis telemetry.",
        "status": "online",
        "student_author": "M. L. Booso (IT23452916)",
        "project": "HEART Framework (J26-SE-334)",
        "zero_cloud_egress": ZERO_CLOUD_EGRESS,
        "engine_descriptor": service.engine.engine_descriptor,
        "capabilities": {
            "tier_1_ast_fast_path": "Deterministic view hierarchy bounding-box collision detection (<5ms CPU, 0 VRAM)",
            "tier_2_vlm_sahi": "Edge VLM core with SAHI 720x720 dynamic tiling for high-aspect-ratio screens",
            "tier_3_freeze_detector": "Multi-frame perceptual dHash and DOM stability freeze detection (FR3)",
            "async_c2_trigger": "Non-blocking background capture queue for Component 2 stress runner (FR6)",
            "c4_verdict_ledger": "Normalized C3Verdict publishing for Component 4 self-healing synthesis (FR7)",
        },
        "endpoints": {
            "health_status": "GET /api/status",
            "sync_evaluate": "POST /api/oracle/evaluate",
            "device_evaluate": "POST /api/oracle/evaluate_device",
            "c2_async_trigger": "POST /api/oracle/trigger",
            "freeze_sequence": "POST /api/oracle/sequence",
            "verdict_ledger": "GET /api/oracle/verdicts",
        },
    }


@router.get("/api/status")
def get_status():
    """Returns engine health, hardware telemetry, and active attached devices."""
    service = get_oracle_service()

    attached_devices = []
    try:
        attached_devices = AdbDevice.list_devices()
    except Exception:
        pass

    cuda_available = False
    compute_device = "CPU"
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            compute_device = f"CUDA (device 0: {torch.cuda.get_device_name(0)})"
    except Exception:
        pass

    return {
        "status": "nominal",
        "engine_descriptor": service.engine.engine_descriptor,
        "compute_device": compute_device,
        "cuda_available": cuda_available,
        "attached_devices": attached_devices,
        "attached_devices_count": len(attached_devices),
        "recent_verdicts_count": len(service.list_verdicts()),
        "zero_cloud_egress": ZERO_CLOUD_EGRESS,
        "device_sync_layer": "common.adb.AdbDevice with cross-process DeviceLock",
        "supported_taxonomies": [
            "component_overlap",
            "text_truncation",
            "missing_component",
            "unrendered_asset",
            "functional_incongruence",
            "frozen_state",
            "other_defect",
        ],
    }

