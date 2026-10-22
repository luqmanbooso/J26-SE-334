"""Small helpers the presentation notebooks share: load a model, run one screen, read the answer, draw the box."""
import gc
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

ADAPTERS = {
    "v1 (first model)": "c3_qwen2vl_2b_lora_step246",
    "v3 vision": "c3_v3_vision_1ep",
    "v3 fusion": "c3_v3_fusion_1ep",
}
# Screens in demo_inputs with the true defect type and region [ymin, xmin, ymax, xmax] in 0-1000.
SCREENS = {
    "01_overlap_team_names.jpg": ("component_overlap", [200, 0, 340, 1000]),
    "03_null_text.jpg": ("data_binding_null", [262, 450, 295, 560]),
    "04_missing_icons.jpg": ("missing_component", [294, 80, 380, 250]),
    "07_clean_owleye.jpg": ("none", None),
}


def parse_answer(text: str) -> Dict[str, Any]:
    """Read the model's JSON answer. An unreadable answer counts as 'no verdict' rather than an error."""
    try:
        obj = json.loads(text[text.index("{"): text.rindex("}") + 1])
    except (ValueError, TypeError):
        return {"type": "unreadable", "has_defect": None, "box": None}
    box = obj.get("bounding_box")
    ok = isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box)
    return {"type": obj.get("defect_type", "none"), "has_defect": obj.get("has_defect"), "box": box if ok else None}


def run_once(backend: Any, image: Image.Image, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """One screen through ``backend.generate``; returns the readable answer plus seconds and defect score."""
    tick = time.perf_counter()
    raw = backend.generate(messages=messages, image=image)
    seconds = time.perf_counter() - tick
    out = parse_answer(raw)
    call = getattr(backend, "last_call", None) or {}
    out.update(seconds=round(seconds, 2), score=call.get("defect_probability"), raw=raw)
    return out


def box_to_pixels(box: Optional[List[float]], width: int, height: int) -> Optional[tuple]:
    """[ymin, xmin, ymax, xmax] in 0-1000 -> (x, y, w, h) in pixels for a matplotlib Rectangle."""
    if not box:
        return None
    y1, x1, y2, x2 = box
    return (x1 * width / 1000, y1 * height / 1000, (x2 - x1) * width / 1000, (y2 - y1) * height / 1000)


def iou(a: Optional[List[float]], b: Optional[List[float]]) -> float:
    """Overlap of two boxes in the same coordinates, 0 (apart) to 1 (identical)."""
    if not a or not b:
        return 0.0
    ay1, ax1, ay2, ax2 = a
    by1, bx1, by2, bx2 = b
    iy = max(0.0, min(ay2, by2) - max(ay1, by1))
    ix = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter = iy * ix
    union = (ay2 - ay1) * (ax2 - ax1) + (by2 - by1) * (bx2 - bx1) - inter
    return inter / union if union > 0 else 0.0


def load_backend(models_dir: Path, adapter: Optional[str]) -> Any:
    """Base Qwen2-VL-2B in 4-bit, with the named adapter folder on top (or none for the plain base model)."""
    from local_vision_oracle.engine import TransformersInferenceBackend
    return TransformersInferenceBackend(
        model_name_or_path=str(models_dir / "Qwen2-VL-2B-Instruct"),
        adapter_dir=str(models_dir / adapter) if adapter else None,
        quantization_bit=4, device="cuda", lazy_load=False,
    )


def free_backend(backend: Any) -> None:
    """Release the GPU so the next model fits in 4 GB."""
    import torch
    backend.unload()
    del backend
    gc.collect()
    torch.cuda.empty_cache()
