"""
Unit Tests for Empirical Evaluator, IoU, and McNemar Significance Testing.
"""

import json
import pytest
from pathlib import Path
from PIL import Image

from local_vision_oracle.schemas import DefectType
from local_vision_oracle.engine import OracleEngine, MockInferenceBackend
from local_vision_oracle.evaluation import (
    compute_bbox_iou,
    mcnemar_test,
    EvaluationItem,
    Evaluator,
    EvaluationMetrics,
)


def test_compute_bbox_iou():
    # Exact overlap
    box1 = [100, 100, 200, 200]
    box2 = [100, 100, 200, 200]
    assert compute_bbox_iou(box1, box2) == 1.0

    # No overlap
    box3 = [300, 300, 400, 400]
    assert compute_bbox_iou(box1, box3) == 0.0

    # Partial overlap (50% area overlap)
    # box1: [0, 0, 10, 10] -> area 100
    # box4: [0, 0, 10, 5]  -> area 50, intersection 50, union 100 -> IoU = 0.5
    box_a = [0, 0, 10, 10]
    box_b = [0, 0, 10, 5]
    assert compute_bbox_iou(box_a, box_b) == 0.5

    # Invalid / empty boxes
    assert compute_bbox_iou(None, box1) == 0.0
    assert compute_bbox_iou([0, 0], box1) == 0.0
    assert compute_bbox_iou([10, 10, 0, 0], box1) == 0.0


def test_mcnemar_significance():
    # Case 1: Identical performance
    res_eq = mcnemar_test(b=10, c=10)
    assert res_eq["chi2"] == 0.0
    assert res_eq["p_value"] == 1.0
    assert res_eq["significant"] is False

    # Case 2: Highly significant win for Model A (e.g. EXP-03 OwlEye baseline)
    # b = 60 (A wins), c = 8 (B wins)
    # (|60 - 8| - 1)^2 / 68 = 51^2 / 68 = 2601 / 68 = 38.25
    res_sig = mcnemar_test(b=60, c=8)
    assert res_sig["chi2"] > 35.0
    assert res_sig["p_value"] < 0.001
    assert res_sig["significant"] is True

    # Case 3: Empty comparisons
    res_empty = mcnemar_test(b=0, c=0)
    assert res_empty["p_value"] == 1.0
    assert res_empty["significant"] is False


def test_evaluator_dataset(tmp_path):
    # Setup test images
    img1 = tmp_path / "img1.png"
    img2 = tmp_path / "img2.png"
    Image.new("RGB", (1080, 2400), color=(255, 255, 255)).save(img1)
    Image.new("RGB", (1080, 2400), color=(200, 200, 200)).save(img2)

    # Item 1: Expected clean, predicted clean
    item1 = EvaluationItem(
        screen_id="clean_01",
        image_path=str(img1),
        expected_has_defect=False,
    )

    # Item 2: Expected defect (overlap)
    item2 = EvaluationItem(
        screen_id="defect_02",
        image_path=str(img2),
        expected_has_defect=True,
        expected_defect_type=DefectType.COMPONENT_OVERLAP,
        expected_bounding_box=[100, 100, 300, 300],
    )

    def custom_responses(messages, image):
        # If item 2 image
        if "clean_01" in str(messages):
            return json.dumps({"has_defect": False, "defect_type": "none", "confidence": 0.99})
        return json.dumps({
            "has_defect": True,
            "defect_type": "component_overlap",
            "confidence": 0.94,
            "bounding_box": [100, 100, 300, 300],
            "explanation": "Overlap detected",
        })

    backend = MockInferenceBackend(response_fn=custom_responses, simulated_latency_ms=0.0)
    engine = OracleEngine(backend=backend)
    evaluator = Evaluator(engine=engine)

    metrics, detailed = evaluator.evaluate_dataset([item1, item2])

    assert metrics.total_samples == 2
    assert metrics.tp == 1
    assert metrics.tn == 1
    assert metrics.fp == 0
    assert metrics.fn == 0
    assert metrics.accuracy == 1.0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1_score == 1.0
    assert metrics.mean_iou == 1.0
    assert metrics.localization_accuracy_iou50 == 1.0
    assert metrics.sla_compliance_rate == 1.0

    # Test CSV export
    csv_file = tmp_path / "summary.csv"
    evaluator.export_summary_csv(metrics, csv_file)
    assert csv_file.exists()
    content = csv_file.read_text(encoding="utf-8")
    assert "F1-Score,100.00%" in content
