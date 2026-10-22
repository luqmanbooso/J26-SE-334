"""Staged C3 evaluation: smoke -> screen -> full, metrics recomputed from saved predictions.

Stages use FIXED, stratified validation subsets (same screens for every candidate):
    smoke   24 screens   ~1 min score mode   reject broken runs
    screen  96 screens   ~2 min score mode   compare candidates
    full    all val      ~5 min score mode   finalists
    final   the test split, once per frozen model (logged; repeated use is refused unless --force)

Modes:
    score   one forward pass per screen: P(defect). Gives AUC, thresholded P/R/F1, latency.
    e2e     full production answer (decision + type + box). Adds type accuracy, IoU, invalid rate.

Every run saves raw records. `recompute` rebuilds every metric from a saved run without the model;
`rank` compares saved runs on the same stage.

Usage (from vision_oracle/):
    python -m local_vision_oracle.eval_stages run --stage smoke --adapter models/c3_qwen2vl_2b_lora_step246
    python -m local_vision_oracle.eval_stages run --stage screen --mode e2e --adapter <dir>
    python -m local_vision_oracle.eval_stages run --stage full --base-only --contract models/c3_qwen2vl_2b_lora_step246/inference_contract.json
    python -m local_vision_oracle.eval_stages recompute evaluation_runs/<run>.json
    python -m local_vision_oracle.eval_stages rank --stage screen
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from local_vision_oracle.contract_benchmark import (
    best_threshold, bootstrap_auc_ci, box_iou, metrics_at, parse_output, roc_auc,
)

DATA = Path("D:/university/Resesarch/RD/LLaMA-Factory/data")
RUNS = Path(__file__).resolve().parents[1] / "evaluation_runs"
STAGE_SIZE = {"smoke": 24, "screen": 96, "full": None, "final": None}
GATES = {"max_invalid_rate": 0.05, "min_auc": 0.55}
CLASSES = ("component_overlap", "text_truncation", "missing_component", "data_binding_null")


def _source(image: str) -> str:
    i = image.replace("\\", "/")
    if "bug-aug" in i:
        return "owleye_bug"
    if "normal-aug" in i:
        return "owleye_normal"
    return "rico_mutated" if ("_v3_" in i or "_mut_" in i) else "rico_clean"


def load_subset(stage: str, manifest: Optional[str] = None, seed: int = 2026) -> List[Dict]:
    """Fixed subset, stratified by (source, defect type) so small stages still cover every class."""
    split = "test" if stage == "final" else "val"
    path = Path(manifest) if manifest else DATA / f"c3v3_vision_{split}.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for r in rows:
        gold = json.loads(r["messages"][-1]["content"])
        items.append({"image": r["images"][0], "gold_has": bool(gold["has_defect"]),
                      "gold_type": gold["defect_type"], "gold_box": gold.get("bounding_box"),
                      "source": _source(r["images"][0])})
    n = STAGE_SIZE[stage]
    if not n or n >= len(items):
        return items
    strata = defaultdict(list)
    for it in sorted(items, key=lambda x: x["image"]):
        strata[(it["source"], it["gold_type"])].append(it)
    rng = random.Random(seed)
    for v in strata.values():
        rng.shuffle(v)
    picked, keys = [], sorted(strata)
    while len(picked) < n and any(strata[k] for k in keys):  # round-robin across strata
        for k in keys:
            if strata[k] and len(picked) < n:
                picked.append(strata[k].pop())
    return picked


def _digest(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def compute_metrics(records: List[Dict], mode: str, threshold: Optional[float]) -> Dict:
    """Every metric from saved records; no model needed."""
    out: Dict = {"n": len(records), "by_source": dict(Counter(r["source"] for r in records))}
    lat = sorted(r["latency_ms"] for r in records)
    out["latency_ms"] = {"p50": lat[len(lat) // 2], "p95": lat[min(len(lat) - 1, int(len(lat) * 0.95))]} if lat else {}
    labels = [r["gold_has"] for r in records]
    if mode == "score":
        scores = [r["p_defect"] for r in records]
        auc = roc_auc(scores, labels)
        out["auc"] = round(auc, 4) if auc is not None else None
        out["auc_95ci"] = bootstrap_auc_ci(scores, labels) if auc is not None else None
        out["best_threshold_on_this_set"] = best_threshold(scores, labels)
        if threshold is not None:
            out["at_contract_threshold"] = metrics_at(scores, labels, threshold)
        for src in sorted(set(r["source"] for r in records)):
            sub = [r for r in records if r["source"] == src]
            if threshold is not None:
                hit = sum((r["p_defect"] >= threshold) == r["gold_has"] for r in sub)
                out.setdefault("decision_accuracy_by_source", {})[src] = round(hit / len(sub), 4)
        return out
    # e2e
    preds = [r["pred_has"] is True for r in records]
    tp = sum(p and g for p, g in zip(preds, labels)); fp = sum(p and not g for p, g in zip(preds, labels))
    fn = sum((not p) and g for p, g in zip(preds, labels)); tn = len(records) - tp - fp - fn
    P = tp / (tp + fp) if tp + fp else 0.0; R = tp / (tp + fn) if tp + fn else 0.0
    out["binary"] = {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(P, 4), "recall": round(R, 4),
                     "f1": round(2 * P * R / (P + R), 4) if P + R else 0.0, "accuracy": round((tp + tn) / len(records), 4)}
    out["invalid_rate"] = round(sum(r["pred_has"] is None for r in records) / len(records), 4)
    names = ("none",) + CLASSES
    cm = {g: {p: 0 for p in names + ("invalid",)} for g in names}
    for r in records:
        cm[r["gold_type"]][r["pred_type"] if r["pred_type"] in names else "invalid"] += 1
    out["confusion_matrix"] = cm
    per, f1s = {}, []
    for c in names:
        tp_c = cm[c][c]; fp_c = sum(cm[g][c] for g in names if g != c); fn_c = sum(cm[c].values()) - tp_c
        p = tp_c / (tp_c + fp_c) if tp_c + fp_c else 0.0; rc = tp_c / (tp_c + fn_c) if tp_c + fn_c else 0.0
        f = 2 * p * rc / (p + rc) if p + rc else 0.0
        per[c] = {"precision": round(p, 4), "recall": round(rc, 4), "f1": round(f, 4), "support": sum(cm[c].values())}
        if per[c]["support"]:
            f1s.append(f)
    out["per_class"] = per
    out["macro_f1"] = round(sum(f1s) / len(f1s), 4) if f1s else 0.0
    pos = [r for r in records if r["gold_has"] and r.get("gold_box")]
    ious = [box_iou(r["pred_box"], r["gold_box"]) if r.get("pred_box") else 0.0 for r in pos]
    out["localization"] = {"n_with_box": len(pos), "mean_iou": round(sum(ious) / len(ious), 4) if ious else None,
                           "recall_at_iou_0.5": round(sum(i >= 0.5 for i in ious) / len(ious), 4) if ious else None,
                           "recall_at_iou_0.3": round(sum(i >= 0.3 for i in ious) / len(ious), 4) if ious else None}
    return out


def gate(metrics: Dict, mode: str) -> Dict:
    """Early rejection of clearly broken runs before spending time on larger stages."""
    reasons = []
    if mode == "score":
        if metrics.get("auc") is None or metrics["auc"] < GATES["min_auc"]:
            reasons.append(f"AUC {metrics.get('auc')} < {GATES['min_auc']}")
    else:
        if metrics["invalid_rate"] > GATES["max_invalid_rate"]:
            reasons.append(f"invalid outputs {metrics['invalid_rate']:.0%} > {GATES['max_invalid_rate']:.0%}")
        b = metrics["binary"]
        if b["tp"] + b["fp"] in (0, metrics["n"]):
            reasons.append("predicts a single class for every screen")
    return {"passed": not reasons, "reasons": reasons}


def run(stage: str, mode: str, adapter: Optional[str], contract_file: Optional[str], name: Optional[str],
        manifest: Optional[str], force: bool) -> Path:
    import torch
    from PIL import Image
    from local_vision_oracle.engine import TransformersInferenceBackend, load_inference_contract

    base = Path(__file__).resolve().parents[1] / "models" / "Qwen2-VL-2B-Instruct"
    items = load_subset(stage, manifest)
    model_id = (Path(adapter).name if adapter else "base") + ("" if not contract_file else "+contract")
    RUNS.mkdir(exist_ok=True)
    if stage == "final":
        log = RUNS / "final_test_log.json"
        done = json.loads(log.read_text()) if log.exists() else []
        key = f"{model_id}|{_digest(Path(adapter) / 'adapter_model.safetensors') if adapter else 'base'}|{mode}"
        if key in [d["key"] for d in done] and not force:
            raise SystemExit(f"Final test already run for {key}. Test data must not drive decisions; use --force only to reproduce.")
    backend = TransformersInferenceBackend(model_name_or_path=str(base), adapter_dir=adapter, quantization_bit=4, device="cuda")
    if contract_file:
        backend.inference_contract = load_inference_contract(str(Path(contract_file).parent))
    tick = time.perf_counter(); backend._load_model(); load_s = time.perf_counter() - tick
    if mode == "e2e" and not (backend.inference_contract or {}).get("decision_threshold"):
        raise SystemExit("e2e mode needs a contract with decision_threshold (choose it on validation first).")
    threshold = (backend.inference_contract or {}).get("decision_threshold")
    records = []
    torch.cuda.reset_peak_memory_stats()
    for it in items:
        with Image.open(it["image"]) as src:
            img = src.convert("RGB")
        t = time.perf_counter()
        rec = dict(it)
        if mode == "score":
            rec["p_defect"] = round(backend.defect_probability(img, messages=[{"role": "user", "content": [{"type": "image"}]}]), 5)
        else:
            raw = backend.generate([{"role": "user", "content": [{"type": "image"}]}], img, max_new_tokens=160)
            pred = parse_output(raw)
            rec.update(raw=raw, pred_has=None, pred_type="invalid", pred_box=None)
            if pred is not None:
                rec["pred_has"] = pred["has_defect"]
                rec["pred_type"] = pred.get("defect_type") if pred["has_defect"] else "none"
                b = pred.get("bounding_box")
                rec["pred_box"] = b if isinstance(b, list) and len(b) == 4 else None
        rec["latency_ms"] = round((time.perf_counter() - t) * 1000, 1)
        records.append(rec)
    metrics = compute_metrics(records, mode, threshold)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_name = name or f"{stage}_{mode}_{model_id}_{stamp}"
    doc = {"identity": {"stage": stage, "mode": mode, "model": model_id, "adapter": adapter,
                        "adapter_sha16": _digest(Path(adapter) / "adapter_model.safetensors") if adapter else None,
                        "contract": backend.inference_contract, "subset_size": len(items),
                        "subset_sha16": hashlib.sha256("\n".join(i["image"] for i in items).encode()).hexdigest()[:16],
                        "load_seconds": round(load_s, 1), "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
                        "gpu": torch.cuda.get_device_name(0), "utc": stamp},
           "metrics": metrics, "gate": gate(metrics, mode), "records": records}
    out = RUNS / f"{run_name}.json"
    out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    if stage == "final":
        done.append({"key": key, "run": out.name, "utc": stamp})
        (RUNS / "final_test_log.json").write_text(json.dumps(done, indent=1))
    return out


def recompute(path: str) -> Dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    ident = doc["identity"]
    thr = (ident.get("contract") or {}).get("decision_threshold")
    return compute_metrics(doc["records"], ident["mode"], thr)


def rank(stage: str) -> List[Dict]:
    rows = []
    for p in sorted(RUNS.glob("*.json")):
        if p.name == "final_test_log.json":
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        i, m = d["identity"], d["metrics"]
        if i["stage"] != stage:
            continue
        key = m.get("auc") if i["mode"] == "score" else m["binary"]["f1"]
        rows.append({"run": p.name, "model": i["model"], "mode": i["mode"], "subset": i["subset_sha16"],
                     "key_metric": key, "gate": d["gate"]["passed"]})
    return sorted(rows, key=lambda r: (r["subset"], r["mode"], -(r["key_metric"] or 0)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--stage", choices=list(STAGE_SIZE), required=True)
    r.add_argument("--mode", choices=["score", "e2e"], default="score")
    r.add_argument("--adapter", default=None)
    r.add_argument("--base-only", action="store_true", help="no adapter (baseline)")
    r.add_argument("--contract", default=None, help="contract to apply (needed for the base model)")
    r.add_argument("--manifest", default=None, help="override the validation/test manifest")
    r.add_argument("--name", default=None)
    r.add_argument("--force", action="store_true")
    c = sub.add_parser("recompute"); c.add_argument("path")
    k = sub.add_parser("rank"); k.add_argument("--stage", choices=list(STAGE_SIZE), default="screen")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        if not a.adapter and not a.base_only:
            raise SystemExit("Pass --adapter <dir> or --base-only")
        out = run(a.stage, a.mode, None if a.base_only else a.adapter, a.contract, a.name, a.manifest, a.force)
        d = json.loads(out.read_text(encoding="utf-8"))
        print(out); print(json.dumps({"gate": d["gate"], **{k: v for k, v in d["metrics"].items() if k not in ("records", "confusion_matrix")}}, indent=1))
    elif a.cmd == "recompute":
        print(json.dumps(recompute(a.path), indent=1))
    else:
        for row in rank(a.stage):
            print(row)


if __name__ == "__main__":
    main()
