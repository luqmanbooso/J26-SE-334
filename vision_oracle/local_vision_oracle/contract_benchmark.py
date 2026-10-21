"""Benchmark a C3 adapter through the production backend and its inference contract.

Every prediction goes through ``TransformersInferenceBackend.generate``, the same
call the HEART desktop app makes, so the measured prompt, resolution and 4-bit
loading are the deployed ones. Results are checkpointed after every screen.

Usage:
    python -m local_vision_oracle.contract_benchmark --manifest <llamafactory json>
        --adapter models/c3_qwen2vl_2b_lora_v2 --output results/bench.json [--limit 60 --seed 7]
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image

BASE_MODEL = Path(__file__).resolve().parents[1] / "models" / "Qwen2-VL-2B-Instruct"


def parse_output(raw: str) -> Optional[Dict]:
    """Strict parse: a JSON object with boolean has_defect, else None (abstention)."""
    try:
        obj = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(obj, dict) or not isinstance(obj.get("has_defect"), bool):
        return None
    return obj


def box_iou(a: List[float], b: List[float]) -> float:
    ya, xa, yb, xb = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, yb - ya) * max(0.0, xb - xa)

    def area(r):
        return max(0.0, r[2] - r[0]) * max(0.0, r[3] - r[1])

    union = area(a) + area(b) - inter
    return inter / union if union else 0.0


def summarize(records: List[Dict]) -> Dict:
    """Binary detection metrics; invalid outputs count as 'no defect' (end-to-end)."""
    n = len(records)
    tp = sum(r["gold_has"] and r["pred_has"] is True for r in records)
    fp = sum((not r["gold_has"]) and r["pred_has"] is True for r in records)
    fn = sum(r["gold_has"] and r["pred_has"] is not True for r in records)
    tn = n - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    positives = [r for r in records if r["gold_has"]]
    type_hits = sum(r["pred_type"] == r["gold_type"] for r in positives)
    ious = [r["iou"] for r in positives if r.get("iou") is not None]
    lat = sorted(r["latency_ms"] for r in records)
    per_class = {}
    for cls in sorted({r["gold_type"] for r in records}):
        rows = [r for r in records if r["gold_type"] == cls]
        per_class[cls] = {
            "n": len(rows),
            "binary_correct": sum((r["pred_has"] is True) == r["gold_has"] for r in rows),
            "type_correct": sum(r["pred_type"] == cls for r in rows),
        }
    return {
        "n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": round((tp + tn) / n, 4) if n else 0.0,
        "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
        "type_accuracy_on_defects": round(type_hits / len(positives), 4) if positives else None,
        "iou_at_0_5_on_defects": round(sum(i >= 0.5 for i in ious) / len(positives), 4) if positives else None,
        "invalid_outputs": sum(r["pred_has"] is None for r in records),
        "median_latency_ms": lat[n // 2] if n else None,
        "p95_latency_ms": lat[min(n - 1, int(n * 0.95))] if n else None,
        "per_class": per_class,
    }


def run(manifest: str, adapter: Optional[str], output: str, limit: Optional[int], seed: int,
        contract_file: Optional[str] = None) -> Dict:
    import torch
    from local_vision_oracle.engine import TransformersInferenceBackend

    rows = json.loads(Path(manifest).read_text(encoding="utf-8"))
    random.Random(seed).shuffle(rows)
    if limit:
        rows = rows[:limit]
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    backend = TransformersInferenceBackend(model_name_or_path=str(BASE_MODEL), adapter_dir=adapter,
                                           quantization_bit=4, device="cuda")
    if contract_file:
        # Base-model ablation: same prompt and resolution as an adapter, no LoRA weights.
        from local_vision_oracle.engine import load_inference_contract
        backend.inference_contract = load_inference_contract(str(Path(contract_file).parent))
    tick = time.perf_counter()
    backend._load_model()
    meta = {"manifest": str(manifest), "adapter": adapter, "seed": seed, "limit": limit,
            "load_seconds": round(time.perf_counter() - tick, 1),
            "contract": backend.inference_contract, "gpu": torch.cuda.get_device_name(0)}
    records: List[Dict] = []
    torch.cuda.reset_peak_memory_stats()
    for row in rows:
        gold = json.loads(row["messages"][-1]["content"])
        image_path = row["images"][0]
        with Image.open(image_path) as src:
            image = src.convert("RGB")
        # With a contract the backend replaces these messages with the trained prompt.
        tick = time.perf_counter()
        raw = backend.generate([{"role": "user", "content": [{"type": "image"}]}], image, max_new_tokens=160)
        latency = round((time.perf_counter() - tick) * 1000, 1)
        pred = parse_output(raw)
        rec = {"image": image_path, "gold_has": bool(gold["has_defect"]), "gold_type": gold["defect_type"],
               "gold_box": gold.get("bounding_box"), "pred_has": None, "pred_type": "INVALID",
               "pred_box": None, "iou": None, "raw": raw, "latency_ms": latency}
        if pred is not None:
            rec["pred_has"] = pred["has_defect"]
            rec["pred_type"] = pred.get("defect_type") if pred["has_defect"] else "none"
            box = pred.get("bounding_box")
            if isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box):
                rec["pred_box"] = box
                if rec["gold_box"]:
                    rec["iou"] = round(box_iou(box, rec["gold_box"]), 4)
        records.append(rec)
        result = {"meta": meta, "summary": summarize(records),
                  "peak_vram_bytes": torch.cuda.max_memory_allocated(), "records": records}
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, indent=1), encoding="utf-8")
        tmp.replace(out)
        print(f"{len(records)}/{len(rows)} gold={rec['gold_type']} pred={rec['pred_type']} {latency}ms", flush=True)
    return result


def roc_auc(scores: List[float], labels: List[bool]) -> Optional[float]:
    """Probability a random defective screen scores above a random clean one (ties count half)."""
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def best_threshold(scores: List[float], labels: List[bool]) -> Dict:
    """Threshold maximising binary F1 (ties broken towards higher precision)."""
    best = {"threshold": 0.5, "f1": -1.0, "precision": 0.0, "recall": 0.0}
    for t in sorted(set(scores)):
        tp = sum(s >= t and y for s, y in zip(scores, labels))
        fp = sum(s >= t and not y for s, y in zip(scores, labels))
        fn = sum(s < t and y for s, y in zip(scores, labels))
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        if f > best["f1"] or (f == best["f1"] and p > best["precision"]):
            best = {"threshold": t, "f1": round(f, 4), "precision": round(p, 4), "recall": round(r, 4)}
    return best


def metrics_at(scores: List[float], labels: List[bool], t: float) -> Dict:
    """Binary metrics when screens with score >= t are flagged as defective."""
    tp = sum(s >= t and y for s, y in zip(scores, labels))
    fp = sum(s >= t and not y for s, y in zip(scores, labels))
    fn = sum(s < t and y for s, y in zip(scores, labels))
    tn = len(scores) - tp - fp - fn
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"threshold": t, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(p, 4),
            "recall": round(r, 4), "f1": round(f, 4), "accuracy": round((tp + tn) / len(scores), 4)}


def bootstrap_auc_ci(scores: List[float], labels: List[bool], n: int = 1000, seed: int = 0) -> List[float]:
    """95% percentile bootstrap interval for AUC."""
    rng = random.Random(seed)
    idx = list(range(len(scores)))
    vals = []
    for _ in range(n):
        pick = [rng.choice(idx) for _ in idx]
        a = roc_auc([scores[i] for i in pick], [labels[i] for i in pick])
        if a is not None:
            vals.append(a)
    vals.sort()
    return [round(vals[int(0.025 * len(vals))], 4), round(vals[int(0.975 * len(vals)) - 1], 4)]


def score_run(manifest: str, adapter: Optional[str], output: str, limit: Optional[int], seed: int,
              contract_file: Optional[str] = None) -> Dict:
    """One forward pass per screen: P(has_defect=true), AUC, and the F1-optimal threshold."""
    import torch
    from local_vision_oracle.engine import TransformersInferenceBackend, load_inference_contract

    rows = json.loads(Path(manifest).read_text(encoding="utf-8"))
    random.Random(seed).shuffle(rows)
    if limit:
        rows = rows[:limit]
    backend = TransformersInferenceBackend(model_name_or_path=str(BASE_MODEL), adapter_dir=adapter,
                                           quantization_bit=4, device="cuda")
    if contract_file:
        backend.inference_contract = load_inference_contract(str(Path(contract_file).parent))
    backend._load_model()
    records = []
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    for row in rows:
        gold = json.loads(row["messages"][-1]["content"])
        with Image.open(row["images"][0]) as src:
            image = src.convert("RGB")
        tick = time.perf_counter()
        p = backend.defect_probability(image)
        records.append({"image": row["images"][0], "gold_has": bool(gold["has_defect"]),
                        "gold_type": gold["defect_type"], "p_defect": round(p, 5),
                        "latency_ms": round((time.perf_counter() - tick) * 1000, 1)})
        print(f"{len(records)}/{len(rows)} {gold['defect_type']} p={p:.3f}", flush=True)
    scores = [r["p_defect"] for r in records]
    labels = [r["gold_has"] for r in records]
    result = {"meta": {"manifest": manifest, "adapter": adapter, "contract_file": contract_file,
                       "seed": seed, "limit": limit, "contract": backend.inference_contract},
              "auc": round(roc_auc(scores, labels), 4) if roc_auc(scores, labels) is not None else None,
              "best_threshold": best_threshold(scores, labels),
              "auc_95ci": bootstrap_auc_ci(scores, labels),
              "at_0_5": metrics_at(scores, labels, 0.5),
              "records": records}
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--output", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--contract", default=None, help="inference_contract.json to apply (for the base model)")
    ap.add_argument("--score", action="store_true", help="probability scoring (AUC, best threshold) instead of generation")
    a = ap.parse_args()
    if a.score:
        res = score_run(a.manifest, a.adapter, a.output, a.limit, a.seed, a.contract)
        print(json.dumps({k: res[k] for k in ("auc", "auc_95ci", "best_threshold", "at_0_5")}, indent=1))
    else:
        res = run(a.manifest, a.adapter, a.output, a.limit, a.seed, a.contract)
        print(json.dumps(res["summary"], indent=1))
