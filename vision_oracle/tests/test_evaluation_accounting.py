import json

import pytest
from PIL import Image

from local_vision_oracle.evaluation_accounting import (
    parse_prediction, summarize_records, restore_records,
)
from local_vision_oracle import evaluate_test_split as evaluator


@pytest.mark.parametrize("output", [
    "broken JSON", "{}", "[]",
    '{"has_defect":"false","defect_type":"none"}',
    '{"has_defect":false,"defect_type":"component_overlap"}',
    '{"has_defect":true,"defect_type":"none"}',
    '{"has_defect":true,"defect_type":"invented"}',
    '{"has_defect":true,"defect_type":"component_overlap","bounding_box":[0,0,NaN,100]}',
    '{"has_defect":true,"defect_type":"component_overlap","bounding_box":[0,0,0,100]}',
    '{"has_defect":true,"defect_type":"component_overlap","confidence":true}',
])
def test_invalid_output_never_becomes_clean(output):
    with pytest.raises((ValueError, TypeError)):
        parse_prediction(output)


def record(truth, prediction, status="valid", box=None):
    return dict(true_has_defect=truth, pred_has_defect=prediction, status=status,
                true_bbox=[0, 0, 100, 100] if truth else None,
                pred_bbox=box, latency_ms=10)


def test_failure_aware_denominators_and_localization():
    result = summarize_records([
        record(True, True, box=[0, 0, 100, 100]),
        record(True, False),
        record(False, False),
        record(True, None, "invalid_output"),
        record(False, None, "inference_error"),
    ])
    assert result["confusion_matrix"] == dict(tp=1, tn=1, fp=0, fn=1)
    assert result["abstentions"] == dict(actual_defect=1, actual_clean=1)
    m = result["metrics"]
    assert m["valid_accuracy_pct"] == 66.67
    assert m["end_to_end_accuracy_pct"] == 40
    assert m["valid_recall_pct"] == 50
    assert m["end_to_end_defect_recall_pct"] == 33.33
    assert m["localization_recall_iou50_pct"] == 33.33
    assert m["mean_bbox_iou_all_localization_targets"] == 0.3333
    assert m["invalid_rate_pct"] == 40


def test_macro_f1_is_not_positive_class_f1():
    result = summarize_records([record(True, True), record(False, True), record(False, True)])
    assert result["metrics"]["valid_binary_f1_pct"] == 50
    assert result["metrics"]["valid_binary_macro_f1_pct"] == 25
    assert result["metrics"]["missing_predicted_boxes"] == 3


def test_all_failed_has_no_valid_metrics():
    m = summarize_records([record(True, None, "inference_error")])["metrics"]
    assert m["valid_accuracy_pct"] is None
    assert m["valid_binary_macro_f1_pct"] is None
    assert m["end_to_end_defect_recall_pct"] == 0
    assert m["invalid_rate_pct"] == 100


def test_multiclass_macro_uses_types_instead_of_binary_detection():
    records = [record(True, True), record(True, True)]
    for r, truth in zip(records, ("component_overlap", "text_truncation")):
        r.update(true_defect_type=truth, pred_defect_type="component_overlap")
    result = summarize_records(records)
    assert result["metrics"]["valid_binary_f1_pct"] == 100
    assert result["metrics"]["valid_multiclass_macro_f1_pct"] == 33.33
    assert result["valid_per_class"]["text_truncation"]["recall_pct"] == 0


@pytest.mark.parametrize("checkpoint", [
    {}, {"run_identity": {"old": True}, "detailed_records": []},
    {"run_identity": {"new": True}, "detailed_records": [{"index": 1, "status": "valid"}]},
])
def test_reject_unidentified_or_noncontiguous_checkpoint(checkpoint):
    with pytest.raises(ValueError):
        restore_records(checkpoint, {"new": True}, 10)


def test_evaluator_records_failures_and_resumes_without_inference(tmp_path, monkeypatch):
    base, weights = tmp_path / "base", tmp_path / "weights"
    base.mkdir()
    weights.mkdir()
    (base / "config.json").write_text("{}")
    (weights / "adapter_config.json").write_text("{}")
    image = tmp_path / "screen.png"
    Image.new("RGB", (1080, 2400)).save(image)
    samples = [
        dict(images=[str(image)], messages=[dict(role="assistant", content=json.dumps(
            dict(has_defect=True, defect_type="component_overlap", bounding_box=[0, 0, 100, 100])
        ))])
        for _ in range(4)
    ]
    samples[-1]["images"] = [str(tmp_path / "missing.png")]
    manifest = tmp_path / "test.json"
    manifest.write_text(json.dumps(samples))
    raw = json.dumps(dict(has_defect=True, defect_type="component_overlap",
                          bounding_box=[0, 0, 100, 100], explanation="detail " * 100))
    calls = []

    class Backend:
        def __init__(self, **kwargs):
            pass

        def _load_model(self):
            pass

        def generate(self, **kwargs):
            calls.append(kwargs)
            assert kwargs["image"].size == (1080, 2400)  # No benchmark-only thumbnail.
            if len(calls) == 1:
                return raw
            if len(calls) == 2:
                return "truncated JSON {"
            raise RuntimeError("inference failed")

    monkeypatch.setattr(evaluator, "TransformersInferenceBackend", Backend)
    options = dict(weights_path=str(weights), dataset_path=str(manifest),
                   base_model_path=str(base), output_dir=str(tmp_path / "out"))
    summary = evaluator.run_evaluation(**options)
    assert summary["status_counts"] == dict(valid=1, invalid_output=1, inference_error=1, input_error=1)
    assert summary["metrics"]["end_to_end_defect_recall_pct"] == 25
    records = json.loads((tmp_path / "out/evaluation_records_v2.json").read_text())
    assert records[0]["raw_output"] == raw
    assert all(r["pred_has_defect"] is None for r in records[1:])
    resumed = evaluator.run_evaluation(**options)
    assert len(calls) == 3
    assert resumed["metrics"] == summary["metrics"]
    # Same path with changed model bytes must not reuse old predictions.
    (weights / "adapter_config.json").write_text('{"changed":true}')
    with pytest.raises(ValueError, match="stale or incompatible"):
        evaluator.run_evaluation(**options)


@pytest.mark.parametrize("resolver", [
    evaluator.find_default_base_model, evaluator.find_default_dataset_path,
    evaluator.find_default_weights_dir,
])
def test_explicit_missing_paths_do_not_fall_back(tmp_path, resolver):
    with pytest.raises(FileNotFoundError):
        resolver(str(tmp_path / "missing"))
