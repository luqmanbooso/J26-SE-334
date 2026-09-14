"""
Empirical Benchmark Evaluator & Statistical Significance Suite.
Grounded in METHOD-Empirical-Evaluation-and-McNemar, EXP-01, and EXP-03.
Implements precision, recall, macro-F1, normalized bbox IoU, and McNemar's test.
"""

import os
import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from pydantic import BaseModel, Field

from local_vision_oracle.schemas import DefectType, Verdict, C3OracleResult
from local_vision_oracle.engine import OracleEngine


class EvaluationItem(BaseModel):
    """
    Ground-truth test sample item from benchmark corpus (OwlEye, Rico, AndroR2).
    """
    screen_id: str
    image_path: str
    hierarchy_path: Optional[str] = None
    expected_has_defect: bool
    expected_defect_type: DefectType = DefectType.NONE
    expected_bounding_box: Optional[List[int]] = None  # [ymin, xmin, ymax, xmax] in [0, 1000]
    expected_element_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


def compute_bbox_iou(box_a: Optional[List[int]], box_b: Optional[List[int]]) -> float:
    """
    Computes Intersection-over-Union (IoU) for normalized bounding boxes [ymin, xmin, ymax, xmax].
    """
    if not box_a or not box_b or len(box_a) != 4 or len(box_b) != 4:
        return 0.0

    y_top = max(box_a[0], box_b[0])
    x_left = max(box_a[1], box_b[1])
    y_bottom = min(box_a[2], box_b[2])
    x_right = min(box_a[3], box_b[3])

    if y_bottom <= y_top or x_right <= x_left:
        return 0.0

    intersection_area = (y_bottom - y_top) * (x_right - x_left)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union_area = float(area_a + area_b - intersection_area)

    if union_area <= 0.0:
        return 0.0
    return round(intersection_area / union_area, 4)


def mcnemar_test(b: int, c: int) -> Dict[str, float]:
    """
    Computes McNemar's paired nominal test statistic with Edwards continuity correction.
    Grounded in METHOD-Empirical-Evaluation-and-McNemar (EXP-03).
    
    b: Model A correct, Model B incorrect (Model A wins)
    c: Model A incorrect, Model B correct (Model B wins)
    """
    if (b + c) == 0:
        return {"chi2": 0.0, "p_value": 1.0, "significant": False}

    diff = abs(b - c)
    if diff <= 1:
        return {"chi2": 0.0, "p_value": 1.0, "significant": False}

    chi2_stat = ((diff - 1.0) ** 2) / float(b + c)

    try:
        from scipy.stats import chi2
        p_val = float(chi2.sf(chi2_stat, df=1))
    except ImportError:
        # Fallback approximation for 1-DOF chi2 survival function
        import math
        p_val = math.erfc(math.sqrt(chi2_stat) / math.sqrt(2.0))

    return {
        "chi2": round(chi2_stat, 4),
        "p_value": round(p_val, 6),
        "significant": p_val < 0.05,
    }



class EvaluationMetrics(BaseModel):
    """
    Telemetry and classification benchmark report for empirical evaluation.
    """
    total_samples: int
    tp: int
    fp: int
    fn: int
    tn: int
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    fpr: float
    fnr: float
    macro_f1: float
    per_class_f1: Dict[str, Dict[str, float]]
    mean_iou: float
    localization_accuracy_iou50: float
    mean_latency_ms: float
    p95_latency_ms: float
    sla_compliance_rate: float


class Evaluator:
    """
    Runs benchmark dataset evaluation and generates empirical result matrices.
    """

    def __init__(self, engine: OracleEngine):
        self.engine = engine

    def evaluate_dataset(
        self,
        dataset: List[EvaluationItem],
        iou_threshold: float = 0.50,
    ) -> Tuple[EvaluationMetrics, List[Dict[str, Any]]]:
        """
        Executes end-to-end inference over dataset and computes all empirical metrics.
        """
        tp = fp = fn = tn = 0
        ious: List[float] = []
        latencies: List[float] = []
        sla_pass = 0

        # Multi-class tracking: defect_type -> {tp, fp, fn}
        classes = [d.value for d in DefectType if d != DefectType.NONE]
        class_stats = {c: {"tp": 0, "fp": 0, "fn": 0, "support": 0} for c in classes}

        detailed_results: List[Dict[str, Any]] = []

        for item in dataset:
            # Hierarchy loading
            raw_h = None
            if item.hierarchy_path and os.path.exists(item.hierarchy_path):
                if item.hierarchy_path.endswith(".json"):
                    with open(item.hierarchy_path, "r", encoding="utf-8") as f:
                        raw_h = json.load(f)
                else:
                    with open(item.hierarchy_path, "r", encoding="utf-8") as f:
                        raw_h = f.read()

            result: C3OracleResult = self.engine.evaluate(
                image_input=item.image_path,
                raw_hierarchy=raw_h,
                screen_id=item.screen_id,
                metadata=item.metadata,
            )

            pred_defect = result.verdict.has_defect
            true_defect = item.expected_has_defect
            pred_type = result.verdict.defect_type.value
            true_type = item.expected_defect_type.value

            latencies.append(result.latency_breakdown.total_pipeline_ms)
            if result.latency_breakdown.meets_sla:
                sla_pass += 1

            # Binary classification counters
            if true_defect and pred_defect:
                tp += 1
            elif not true_defect and pred_defect:
                fp += 1
            elif true_defect and not pred_defect:
                fn += 1
            else:
                tn += 1

            # Multi-class stats
            if true_type in class_stats:
                class_stats[true_type]["support"] += 1
            if pred_defect and true_defect and pred_type == true_type:
                if true_type in class_stats:
                    class_stats[true_type]["tp"] += 1
            elif pred_defect and pred_type in class_stats:
                class_stats[pred_type]["fp"] += 1
            elif true_defect and not pred_defect and true_type in class_stats:
                class_stats[true_type]["fn"] += 1

            # Spatial IoU
            iou = 0.0
            if true_defect and pred_defect and item.expected_bounding_box and result.verdict.bounding_box:
                iou = compute_bbox_iou(result.verdict.bounding_box, item.expected_bounding_box)
                ious.append(iou)

            detailed_results.append({
                "screen_id": item.screen_id,
                "true_defect": true_defect,
                "pred_defect": pred_defect,
                "true_type": true_type,
                "pred_type": pred_type,
                "confidence": result.verdict.confidence,
                "iou": iou,
                "latency_ms": result.latency_breakdown.total_pipeline_ms,
                "meets_sla": result.latency_breakdown.meets_sla,
            })

        total = len(dataset)
        precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        f1 = round(2 * (precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0
        accuracy = round((tp + tn) / total, 4) if total > 0 else 0.0
        fpr = round(fp / (fp + tn), 4) if (fp + tn) > 0 else 0.0
        fnr = round(fn / (fn + tp), 4) if (fn + tp) > 0 else 0.0

        # Multi-class Per-class F1 and Macro-F1
        per_class_f1: Dict[str, Dict[str, float]] = {}
        valid_f1s: List[float] = []
        for c, s in class_stats.items():
            c_tp, c_fp, c_fn, supp = s["tp"], s["fp"], s["fn"], s["support"]
            c_p = round(c_tp / (c_tp + c_fp), 4) if (c_tp + c_fp) > 0 else 0.0
            c_r = round(c_tp / (c_tp + c_fn), 4) if (c_tp + c_fn) > 0 else 0.0
            c_f1 = round(2 * (c_p * c_r) / (c_p + c_r), 4) if (c_p + c_r) > 0 else 0.0
            per_class_f1[c] = {"precision": c_p, "recall": c_r, "f1": c_f1, "support": supp}
            if supp > 0:
                valid_f1s.append(c_f1)

        macro_f1 = round(sum(valid_f1s) / len(valid_f1s), 4) if valid_f1s else 0.0

        # Localization metrics
        mean_iou = round(sum(ious) / len(ious), 4) if ious else 0.0
        iou50_count = sum(1 for v in ious if v >= iou_threshold)
        loc_acc = round(iou50_count / len(ious), 4) if ious else 0.0

        # Latencies
        sorted_lats = sorted(latencies) if latencies else [0.0]
        mean_lat = round(sum(sorted_lats) / len(sorted_lats), 2)
        p95_idx = int(0.95 * len(sorted_lats))
        p95_lat = round(sorted_lats[min(p95_idx, len(sorted_lats) - 1)], 2)
        sla_rate = round(sla_pass / total, 4) if total > 0 else 1.0

        metrics = EvaluationMetrics(
            total_samples=total,
            tp=tp,
            fp=fp,
            fn=fn,
            tn=tn,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1,
            fpr=fpr,
            fnr=fnr,
            macro_f1=macro_f1,
            per_class_f1=per_class_f1,
            mean_iou=mean_iou,
            localization_accuracy_iou50=loc_acc,
            mean_latency_ms=mean_lat,
            p95_latency_ms=p95_lat,
            sla_compliance_rate=sla_rate,
        )

        return metrics, detailed_results

    @staticmethod
    def export_summary_csv(metrics: EvaluationMetrics, output_path: Union[str, Path]) -> None:
        """
        Exports metrics summary to CSV matching EXP-01 contract (results/exp-01/metrics_summary.csv).
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        rows = [
            ["Metric", "Value"],
            ["Total Samples", metrics.total_samples],
            ["True Positives (TP)", metrics.tp],
            ["False Positives (FP)", metrics.fp],
            ["False Negatives (FN)", metrics.fn],
            ["True Negatives (TN)", metrics.tn],
            ["Accuracy", f"{metrics.accuracy * 100:.2f}%"],
            ["Precision", f"{metrics.precision * 100:.2f}%"],
            ["Recall", f"{metrics.recall * 100:.2f}%"],
            ["F1-Score", f"{metrics.f1_score * 100:.2f}%"],
            ["Macro-F1", f"{metrics.macro_f1 * 100:.2f}%"],
            ["False Positive Rate (FPR)", f"{metrics.fpr * 100:.2f}%"],
            ["False Negative Rate (FNR)", f"{metrics.fnr * 100:.2f}%"],
            ["Mean IoU (Spatial Localization)", f"{metrics.mean_iou:.4f}"],
            ["Localization Accuracy (IoU >= 0.50)", f"{metrics.localization_accuracy_iou50 * 100:.2f}%"],
            ["Mean Pipeline Latency (ms)", metrics.mean_latency_ms],
            ["P95 Pipeline Latency (ms)", metrics.p95_latency_ms],
            ["SLA Compliance Rate (<1500ms)", f"{metrics.sla_compliance_rate * 100:.2f}%"],
        ]

        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(rows)
