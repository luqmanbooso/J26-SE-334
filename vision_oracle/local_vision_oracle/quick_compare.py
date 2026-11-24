"""Quick live comparison of C3 adapters and inference settings on 10-20 screens.

Each CONFIG is (label, adapter folder, image_max_pixels or None to keep the adapter's own). The same screens
are scored by every config, so differences come from the adapter or the setting, never from the screens.
It prints one row per screen with P(defect) for every config, then a summary per config: AUC, flags at the
config's own threshold, and the average score on defect vs clean screens (a config that scores everything near
0.5, or everything near 0 or 1, is not separating the two).

Run from the repository root (PowerShell):
    python -m vision_oracle.local_vision_oracle.quick_compare --n 16 --seed 1
Close the HEART app and any notebook that holds the model first (4 GB GPU). About 40 s to load each config.
"""

from __future__ import annotations

import argparse
import gc
import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import vision_oracle.services.oracle_service  # noqa: F401  (must come first: path guard for the local package)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "D:/university/Resesarch/RD/LLaMA-Factory/data/c3v3_vision_test.json"
V3 = str(ROOT / "models" / "c3_v3_vision_1ep")
V1 = str(ROOT / "models" / "c3_qwen2vl_2b_lora_step246")
CKPT = "D:/university/Resesarch/results/c3_lora_v3_vision_1ep"

# (label, adapter folder, image_max_pixels override or None). Edit freely.
CONFIGS: List[Tuple[str, str, Optional[int]]] = [
    ("v1 shipped", V1, None),
    ("v3 final (434)", V3, None),
    ("v3 ckpt-300", f"{CKPT}/checkpoint-300", None),
    ("v3 ckpt-100", f"{CKPT}/checkpoint-100", None),
    ("v3 final, 150k px", V3, 150_000),
    ("v3 final, 400k px", V3, 400_000),
]


def pick_screens(manifest: str, n: int, seed: int) -> List[Dict]:
    rows = json.loads(Path(manifest).read_text(encoding="utf-8"))
    for r in rows:
        r["gold"] = bool(json.loads(r["messages"][-1]["content"])["has_defect"])
    rng = random.Random(seed)
    pos, neg = [r for r in rows if r["gold"]], [r for r in rows if not r["gold"]]
    rng.shuffle(pos), rng.shuffle(neg)
    return pos[: n // 2] + neg[: n - n // 2]


def auc(labels: List[bool], scores: List[float]) -> float:
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return float("nan")
    return sum((p > q) + 0.5 * (p == q) for p in pos for q in neg) / (len(pos) * len(neg))


def score_config(label: str, adapter: str, pixels: Optional[int], rows: List[Dict]) -> Dict:
    import torch
    from PIL import Image
    from local_vision_oracle.engine import TransformersInferenceBackend, load_inference_contract

    base = ROOT / "models" / "Qwen2-VL-2B-Instruct"
    backend = TransformersInferenceBackend(model_name_or_path=str(base), adapter_dir=adapter,
                                           quantization_bit=4, device="cuda")
    # Checkpoint folders have no contract of their own; borrow the v3 one (same prompt and resolution).
    contract = dict(backend.inference_contract or load_inference_contract(V3))
    if pixels:
        contract["image_max_pixels"] = pixels
    backend.inference_contract = contract
    backend._load_model()
    scores = []
    for r in rows:
        with Image.open(r["images"][0]) as im:
            scores.append(float(backend.defect_probability(im.convert("RGB"))))
    threshold = contract.get("decision_threshold", 0.5)
    del backend
    gc.collect()
    torch.cuda.empty_cache()
    return {"label": label, "scores": scores, "threshold": threshold}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=MANIFEST)
    ap.add_argument("--n", type=int, default=16, help="screens, half defect and half clean")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--only", default=None, help="comma-separated config labels to run (substring match)")
    a = ap.parse_args(argv)
    rows = pick_screens(a.manifest, a.n, a.seed)
    labels = [r["gold"] for r in rows]
    configs = [c for c in CONFIGS if not a.only or any(k.strip() in c[0] for k in a.only.split(","))]
    results = []
    for label, adapter, pixels in configs:
        print(f"... scoring {label}", flush=True)
        results.append(score_config(label, adapter, pixels, rows))

    names = [r["label"] for r in results]
    print("\n" + " " * 34 + "".join(f"{n[:14]:>15}" for n in names))
    for i, row in enumerate(rows):
        tag = "DEFECT" if row["gold"] else "clean "
        print(f"{tag} {Path(row['images'][0]).name[:26]:<26}" + "".join(f"{res['scores'][i]:>15.2f}" for res in results))
    print("\nSummary (AUC needs several screens of each kind; with 16 screens treat it as a rough signal)")
    for res in results:
        s, t = res["scores"], res["threshold"]
        d = [x for x, y in zip(s, labels) if y]
        c = [x for x, y in zip(s, labels) if not y]
        flagged_d = sum(x >= t for x in d)
        flagged_c = sum(x >= t for x in c)
        print(f"{res['label']:<22} AUC {auc(labels, s):.2f} | threshold {t:.2f} | defects flagged {flagged_d}/{len(d)}"
              f" | clean flagged {flagged_c}/{len(c)} | mean p defect {sum(d)/len(d):.2f} vs clean {sum(c)/len(c):.2f}")


if __name__ == "__main__":
    main()
