"""
Synchronous evaluation routes.
"""

import os
import io
import gc
import base64
from typing import Optional, Union
from PIL import Image
import torch
from fastapi import APIRouter, HTTPException

from vision_oracle.api.schemas import EvaluateRequest
from vision_oracle.core.config import resolve_path
from vision_oracle.services.oracle_service import get_oracle_service
from common.adb import NoDeviceError

router = APIRouter(prefix="/api/oracle", tags=["Evaluation"])


@router.post("/evaluate")
def evaluate_screen(req: EvaluateRequest):
    """
    Synchronous multimodal evaluation of screenshot and accessibility hierarchy.
    Returns C3OracleResult and C4 C3Verdict envelope.
    """
    img_input: Optional[Union[Image.Image, str]] = None
    if req.image_base64:
        try:
            raw_bytes = base64.b64decode(req.image_base64)
            img_input = Image.open(io.BytesIO(raw_bytes))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid image_base64 payload: {exc}")
    elif req.image_path:
        resolved = resolve_path(req.image_path)
        if not resolved or not resolved.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Image file not found: '{req.image_path}'. Checked workspace and notebook directories.",
            )
        img_input = str(resolved)
    else:
        raise HTTPException(status_code=400, detail="Either image_base64 or image_path must be provided.")

    service = get_oracle_service()
    try:
        return service.evaluate(
            image_input=img_input,
            raw_hierarchy=req.hierarchy_xml,
            screen_id=req.screen_id,
            action_context=req.action_context,
            enable_sahi=req.enable_sahi,
            session_id=req.session_id,
        )
    except NoDeviceError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "device_unavailable",
                "message": str(exc),
                "resolution": "Check ADB connection or ensure device is attached with USB debugging enabled.",
            },
        )
    except Exception as exc:
        if exc.__class__.__name__ == "OutOfMemoryError" or "out of memory" in str(exc).lower():
            gc.collect()
            if hasattr(torch, "cuda") and torch.cuda.is_available():
                torch.cuda.empty_cache()
            raise HTTPException(
                status_code=503,
                detail=f"GPU VRAM exhausted / GPU out of memory during evaluation: {exc}. Allocator cache cleared, please retry with backoff.",
            )
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {exc}")


@router.post("/evaluate_device")
def evaluate_device(serial: Optional[str] = None, action_context: Optional[str] = None):
    """Captures and evaluates screen directly from attached Android device via common.adb."""
    service = get_oracle_service()
    try:
        return service.evaluate_device(serial=serial, action_context=action_context)
    except NoDeviceError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "device_unavailable",
                "message": str(exc),
                "resolution": "Check ADB connection or ensure device is attached with USB debugging enabled.",
            },
        )
    except Exception as exc:
        if exc.__class__.__name__ == "OutOfMemoryError" or "out of memory" in str(exc).lower():
            gc.collect()
            if hasattr(torch, "cuda") and torch.cuda.is_available():
                torch.cuda.empty_cache()
            raise HTTPException(
                status_code=503,
                detail=f"GPU VRAM exhausted / GPU out of memory during device evaluation: {exc}. Allocator cache cleared, please retry with backoff.",
            )
        raise HTTPException(status_code=500, detail=f"Device evaluation failed: {exc}")
