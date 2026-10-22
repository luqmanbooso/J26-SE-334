"""
Temporal sequence evaluation routes (FR3 freeze detection).
"""

import os
import io
import gc
import base64
from typing import List, Union
from PIL import Image
import torch
from fastapi import APIRouter, HTTPException

from vision_oracle.api.schemas import SequenceEvaluateRequest
from vision_oracle.core.config import resolve_path
from vision_oracle.services.oracle_service import get_oracle_service

router = APIRouter(prefix="/api/oracle", tags=["Temporal Sequence"])


@router.post("/sequence")
def evaluate_sequence(req: SequenceEvaluateRequest):
    """
    Evaluates multi-frame sequence to detect temporal freezes or verify UI progression (FR3).
    """
    frames: List[Union[Image.Image, str]] = []
    if req.image_base64_list:
        for b64 in req.image_base64_list:
            try:
                raw_bytes = base64.b64decode(b64)
                frames.append(Image.open(io.BytesIO(raw_bytes)))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Corrupt frame in image_base64_list: {exc}")
    elif req.image_paths:
        for p in req.image_paths:
            resolved = resolve_path(p)
            if not resolved or not resolved.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"Sequence image file not found: '{p}'. Checked workspace and notebook directories.",
                )
            frames.append(str(resolved))
    else:
        raise HTTPException(status_code=400, detail="Either image_paths or image_base64_list must be provided.")

    if len(frames) < 2:
        raise HTTPException(status_code=400, detail="Temporal sequence requires at least 2 frames.")

    service = get_oracle_service()
    try:
        return service.evaluate_sequence(
            screens=frames,
            hierarchies=req.hierarchies,
            time_delta_s=req.time_delta_s,
            action_dispatched=req.action_dispatched,
            action_context=req.action_context,
            session_id=req.session_id,
        )
    except Exception as exc:
        if exc.__class__.__name__ == "OutOfMemoryError" or "out of memory" in str(exc).lower():
            gc.collect()
            if hasattr(torch, "cuda") and torch.cuda.is_available():
                torch.cuda.empty_cache()
            raise HTTPException(
                status_code=503,
                detail=f"GPU VRAM exhausted / GPU out of memory during sequence evaluation: {exc}. Allocator cache cleared, please retry with backoff.",
            )
        raise HTTPException(status_code=500, detail=f"Sequence evaluation failed: {exc}")
