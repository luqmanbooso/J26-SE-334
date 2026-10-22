"""Build the C3 v2 fine-tuning manifests (compact target, visible mutations only).

Why v2 exists (see evidence/MODEL_V2_DECISIONS.md):
* v1 targets carried a constant ``confidence: 1.0``, free-text explanations and
  resource ids. Those tokens dominate the loss but carry no visual signal.
* 27% of Rico synthetic mutations change < 0.2% of pixels at the training
  resolution (262,144 px), so they are effectively clean screens labelled as
  defects. They are dropped from train/val (kept in test, reported separately).
* The prompt used for training is exported as ``TRAINING_PROMPT`` so inference
  can use the identical string (v1 inference used a different system prompt
  and ~3.5x more pixels than training).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

TRAINING_MAX_PIXELS = 262_144
VISIBILITY_THRESHOLD = 0.002  # fraction of pixels changed by > 30 grey levels
DEFECT_TYPES = ("none", "component_overlap", "text_truncation",
                "missing_component", "data_binding_null")

TRAINING_PROMPT = (
    "Inspect this Android screen for non-crash UI defects. "
    "Answer with JSON only: {\"has_defect\": true|false, \"defect_type\": "
    "\"none|component_overlap|text_truncation|missing_component|data_binding_null\", "
    "\"bounding_box\": [ymin, xmin, ymax, xmax] in 0-1000 or null}."
)


def compact_target(verdict: Dict) -> str:
    """Reduce a v1 verdict to the three fields that carry visual signal."""
    defect_type = verdict.get("defect_type", "none")
    if defect_type not in DEFECT_TYPES:
        raise ValueError(f"Unknown defect_type {defect_type!r}")
    has_defect = defect_type != "none"
    box = verdict.get("bounding_box") if has_defect else None
    if box is not None:
        if len(box) != 4:
            raise ValueError(f"Bad bounding box {box!r}")
        box = [int(max(0, min(1000, v))) for v in box]
    return json.dumps({"has_defect": has_defect, "defect_type": defect_type,
                       "bounding_box": box})


def resize_to_training(img, max_pixels: int = TRAINING_MAX_PIXELS):
    """Same down-scaling rule LLaMA-Factory applies with image_max_pixels."""
    w, h = img.size
    if w * h > max_pixels:
        f = math.sqrt(max_pixels / (w * h))
        img = img.resize((int(w * f), int(h * f)))
    return img


def mutation_visibility(mutated: str, clean_dir: str) -> Optional[float]:
    """Fraction of pixels a Rico mutation visibly changes at training scale."""
    import numpy as np
    from PIL import Image

    match = re.match(r"(\d+)_mut", os.path.basename(mutated))
    if not match:
        return None
    source = Path(clean_dir) / f"{match.group(1)}.jpg"
    if not source.exists():
        return None
    a = np.asarray(resize_to_training(Image.open(mutated).convert("L")), dtype=np.int16)
    b = np.asarray(resize_to_training(Image.open(source).convert("L")), dtype=np.int16)
    if a.shape != b.shape:
        return None
    return float((np.abs(a - b) > 30).mean())


def convert(samples: Iterable[Dict], clean_dir: str, drop_invisible: bool) -> List[Dict]:
    out = []
    for s in samples:
        image = s["images"][0]
        verdict = json.loads(s["messages"][-1]["content"])
        if drop_invisible and "mutated" in image.replace("\\", "/"):
            vis = mutation_visibility(image, clean_dir)
            if vis is None or vis < VISIBILITY_THRESHOLD:
                continue
        out.append({
            "messages": [
                {"role": "user", "content": "<image>" + TRAINING_PROMPT},
                {"role": "assistant", "content": compact_target(verdict)},
            ],
            "images": [image],
        })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", required=True, help="LLaMA-Factory data dir with v1 manifests")
    ap.add_argument("--clean-dir", required=True, help="Rico clean screens (mutation sources)")
    a = ap.parse_args(argv)
    data_dir = Path(a.data_dir)
    plan = {"train.json": ("c3v2_train.json", True),
            "val.json": ("c3v2_val.json", True),
            "test.json": ("c3v2_test.json", False)}
    for src, (dst, drop) in plan.items():
        rows = json.loads((data_dir / src).read_text(encoding="utf-8"))
        new = convert(rows, a.clean_dir, drop)
        (data_dir / dst).write_text(json.dumps(new, indent=1), encoding="utf-8")
        print(f"{src}: {len(rows)} -> {dst}: {len(new)}")
    info_path = data_dir / "dataset_info.json"
    info = json.loads(info_path.read_text(encoding="utf-8"))
    for dst, _ in plan.values():
        info[dst[:-5]] = {"file_name": dst, "formatting": "sharegpt",
                          "columns": {"messages": "messages", "images": "images"},
                          "tags": {"role_tag": "role", "content_tag": "content",
                                   "user_tag": "user", "assistant_tag": "assistant"}}
    info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
