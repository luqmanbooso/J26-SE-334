"""Time one screenshot through the base model and through a fine-tuned adapter, arm by arm.

Three arms, so the panel can see what comes from where:

* ``A  base, default path``  the base model as a plain user would run it: the screen is shrunk to fit 720x1280 and
  the answer is decoded freely (up to 256 tokens).
* ``B  base, contract path`` the same base weights, but fed the way the adapter is: the screen is resized to the
  contract's pixel budget, the verdict is read from one token, and decoding stops after the box. Any speed gain A -> B
  comes from the inference design, not from training.
* ``C  fine-tuned``          the adapter on the contract path. The gap B -> C is what fine-tuning adds (it makes the
  verdict usable and the answer format reliable); it is not a speed claim.

Nothing here loads a model by itself: callers pass in backends, so the helpers are testable without a GPU.
"""

from __future__ import annotations

import statistics
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from PIL import Image

DEFAULT_THUMBNAIL = (720, 1280)  # what TransformersInferenceBackend uses when an adapter ships no contract


def eval_image(image: Image.Image, max_pixels: Optional[int] = None, thumbnail: Tuple[int, int] = DEFAULT_THUMBNAIL) -> Image.Image:
    """The image the model really sees: the contract's pixel budget if there is one, else the default thumbnail."""
    if max_pixels:
        from local_vision_oracle.engine import resize_to_max_pixels
        return resize_to_max_pixels(image, max_pixels)
    out = image.copy()
    out.thumbnail(thumbnail, Image.Resampling.LANCZOS)
    return out


def visual_tokens(processor: Any, image: Image.Image, text_prompt: str) -> int:
    """How many image tokens the language model must attend to (Qwen2-VL merges 2x2 patches into one token)."""
    inputs = processor(text=[text_prompt], images=[image], padding=True, return_tensors="pt")
    return int(inputs["image_grid_thw"].prod(dim=-1).sum().item() // 4)


def measure(backend: Any, image: Image.Image, messages: List[Dict[str, Any]], repeats: int = 3,
            clock: Callable[[], float] = time.perf_counter) -> Dict[str, Any]:
    """Run one screen through ``backend.generate`` and report timing, tokens and the answer.

    One untimed warm-up call first (the first CUDA call pays kernel start-up), then ``repeats`` timed calls; the
    median is reported so a single slow call does not decide the result.
    """
    peak = _reset_peak()
    contract = getattr(backend, "inference_contract", None)
    backend.generate(messages=messages, image=image)
    totals, verdicts, locs, output = [], [], [], ""
    for _ in range(max(1, repeats)):
        tick = clock()
        output = backend.generate(messages=messages, image=image)
        totals.append((clock() - tick) * 1000.0)
        call = getattr(backend, "last_call", None) or {}
        verdicts.append(call.get("verdict_ms"))
        locs.append(call.get("localization_ms"))
    seen = eval_image(image, (contract or {}).get("image_max_pixels"))
    text_prompt = backend.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    return {
        "total_ms": round(statistics.median(totals), 1),
        "verdict_ms": _median(verdicts),
        "box_ms": _median(locs),
        "image_px": seen.width * seen.height,
        "image_size": seen.size,
        "visual_tokens": visual_tokens(backend.processor, seen, text_prompt),
        "defect_probability": (getattr(backend, "last_call", None) or {}).get("defect_probability"),
        "output": output,
        "peak_vram_mib": peak(),
    }


def speedup(slow_ms: float, fast_ms: float) -> float:
    """How many times faster ``fast_ms`` is than ``slow_ms``."""
    return round(slow_ms / fast_ms, 1) if fast_ms else float("inf")


def _median(values: List[Optional[float]]) -> Optional[float]:
    real = [v for v in values if v is not None]
    return round(statistics.median(real), 1) if real else None


def _reset_peak() -> Callable[[], Optional[float]]:
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            return lambda: round(torch.cuda.max_memory_allocated() / 2**20, 0)
    except Exception:
        pass
    return lambda: None
