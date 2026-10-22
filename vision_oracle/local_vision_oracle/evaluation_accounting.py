"""Strict single-verdict benchmark validation and failure-aware metrics."""

import hashlib
import json
import math
from pathlib import Path
from statistics import mean

from local_vision_oracle.prompt import VerdictParser
from local_vision_oracle.schemas import DefectType
from local_vision_oracle.evaluation import compute_bbox_iou


def parse_prediction(text):
    """Validate without the legacy parser's clean fallback or type coercions."""
    data = json.loads(VerdictParser.extract_json_block(text))
    if not isinstance(data, dict) or type(data.get("has_defect")) is not bool:
        raise ValueError("has_defect must be a JSON boolean")
    kind = data.get("defect_type")
    if not isinstance(kind, str) or kind not in {item.value for item in DefectType}:
        raise ValueError("Unknown or missing defect_type")
    if data["has_defect"] == (kind == "none"):
        raise ValueError("Contradictory has_defect and defect_type")
    box = data.get("bounding_box")
    if box is not None:
        if not data["has_defect"]:
            raise ValueError("Clean verdict contains a box")
        if (
            not isinstance(box, list) or len(box) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1000 for v in box)
            or box[0] >= box[2] or box[1] >= box[3]
        ):
            raise ValueError("Invalid normalized yxyx bounding box")
    confidence = data.get("confidence")
    if confidence is not None and (
        type(confidence) not in (int, float)
        or not math.isfinite(confidence) or not 0 <= confidence <= 1
    ):
        raise ValueError("Invalid confidence")
    return data


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize_records(records):
    """Confusion matrix excludes abstentions; end-to-end recall includes them."""
    valid = [r for r in records if r["status"] == "valid"]
    tp = sum(r["true_has_defect"] and r["pred_has_defect"] for r in valid)
    tn = sum(not r["true_has_defect"] and not r["pred_has_defect"] for r in valid)
    fp = sum(not r["true_has_defect"] and r["pred_has_defect"] for r in valid)
    fn = sum(r["true_has_defect"] and not r["pred_has_defect"] for r in valid)
    total = len(records)
    positives = sum(r["true_has_defect"] for r in records)
    failed_positive = sum(r["true_has_defect"] for r in records if r["status"] != "valid")
    failed_clean = total - len(valid) - failed_positive

    def pct(n, d):
        return round(100 * n / d, 2) if d else None

    positive_f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    clean_f1 = 2 * tn / (2 * tn + fp + fn) if 2 * tn + fp + fn else 0.0
    # Localization is evaluated only where a ground-truth box exists; absent
    # predictions/boxes and failed inference score zero on those targets.
    localized = [r for r in records if r["true_has_defect"] and r.get("true_bbox") is not None]
    ious = [
        compute_bbox_iou(r["pred_bbox"], r["true_bbox"])
        if r["status"] == "valid" and r["pred_has_defect"] and r.get("pred_bbox") else 0.0
        for r in localized
    ]
    latencies = sorted(r["latency_ms"] for r in records)
    typed = [r for r in valid if "true_defect_type" in r and "pred_defect_type" in r]
    labels = sorted({r["true_defect_type"] for r in typed} | {r["pred_defect_type"] for r in typed})
    per_class = {}
    for label in labels:
        class_tp = sum(r["true_defect_type"] == label == r["pred_defect_type"] for r in typed)
        class_fp = sum(r["true_defect_type"] != label and r["pred_defect_type"] == label for r in typed)
        class_fn = sum(r["true_defect_type"] == label and r["pred_defect_type"] != label for r in typed)
        per_class[label] = {
            "support": class_tp + class_fn,
            "precision_pct": pct(class_tp, class_tp + class_fp),
            "recall_pct": pct(class_tp, class_tp + class_fn),
            "f1_pct": 200 * class_tp / (2 * class_tp + class_fp + class_fn),
        }

    def percentile(p):
        if not latencies:
            return None
        pos = (len(latencies) - 1) * p
        lo, hi = math.floor(pos), math.ceil(pos)
        return round(latencies[lo] + (latencies[hi] - latencies[lo]) * (pos - lo), 2)

    return {
        "total_samples": total,
        "valid_samples": len(valid),
        "invalid_samples": total - len(valid),
        "clean_samples": total - positives,
        "defect_samples": positives,
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "abstentions": {"actual_defect": failed_positive, "actual_clean": failed_clean},
        "status_counts": {s: sum(r["status"] == s for r in records)
                          for s in ("valid", "invalid_output", "inference_error", "input_error")},
        "localization_targets": len(localized),
        "valid_per_class": per_class,
        "metrics": {
            "valid_coverage_pct": pct(len(valid), total),
            "invalid_rate_pct": pct(total - len(valid), total),
            "valid_accuracy_pct": pct(tp + tn, len(valid)),
            "valid_precision_pct": pct(tp, tp + fp),
            "valid_recall_pct": pct(tp, tp + fn),
            "valid_binary_f1_pct": round(positive_f1 * 100, 2) if valid else None,
            # Fixed clean/defect label set, zero division -> 0 for absent classes.
            "valid_binary_macro_f1_pct": round((positive_f1 + clean_f1) * 50, 2) if valid else None,
            "valid_multiclass_macro_f1_pct": round(mean(c["f1_pct"] for c in per_class.values()), 2) if per_class else None,
            "end_to_end_accuracy_pct": pct(tp + tn, total),
            "end_to_end_defect_recall_pct": pct(tp, positives),
            "mean_bbox_iou_all_localization_targets": round(mean(ious), 4) if ious else None,
            "localization_recall_iou50_pct": pct(sum(iou >= 0.5 for iou in ious), len(ious)),
            "missing_predicted_boxes": sum(r["pred_has_defect"] and r.get("pred_bbox") is None for r in valid),
            "mean_latency_ms": round(mean(latencies), 2) if latencies else None,
            "p50_latency_ms": percentile(0.5),
            "p95_latency_ms": percentile(0.95),
        },
    }


def restore_records(checkpoint, identity, total):
    if checkpoint.get("run_identity") != identity:
        raise ValueError("Checkpoint is stale or incompatible; use a new output directory or --no-resume")
    records = checkpoint.get("detailed_records")
    if not isinstance(records, list) or len(records) > total:
        raise ValueError("Invalid checkpoint records")
    for index, record in enumerate(records):
        if record.get("index") != index or record.get("status") not in {
            "valid", "invalid_output", "inference_error", "input_error",
        }:
            raise ValueError("Checkpoint records are not a contiguous evaluated prefix")
    # Recalculate aggregates; never trust stored counters.
    summarize_records(records)
    return records
