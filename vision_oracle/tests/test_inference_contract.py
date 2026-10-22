"""Adapter inference-contract regressions (test doubles; no model accuracy measured)."""

import json
import sys
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from local_vision_oracle.engine import (
    TransformersInferenceBackend, contract_messages, load_inference_contract,
    resize_to_max_pixels,
)
from local_vision_oracle.dataset_v2 import TRAINING_PROMPT, compact_target


def _write(tmp_path, **kw):
    data = {"user_prompt": "Inspect.", "system_prompt": None, "image_max_pixels": 262144}
    data.update(kw)
    (tmp_path / "inference_contract.json").write_text(json.dumps(data), encoding="utf-8")
    return tmp_path


def test_missing_contract_returns_none(tmp_path):
    assert load_inference_contract(str(tmp_path)) is None
    assert load_inference_contract(None) is None


@pytest.mark.parametrize("bad", [{"user_prompt": ""}, {"image_max_pixels": 0}, {"image_max_pixels": "big"}])
def test_invalid_contract_rejected(tmp_path, bad):
    with pytest.raises(ValueError):
        load_inference_contract(str(_write(tmp_path, **bad)))


def test_contract_messages_use_default_system_when_null():
    msgs = contract_messages({"user_prompt": "Inspect.", "system_prompt": None})
    assert [m["role"] for m in msgs] == ["user"]
    assert msgs[0]["content"] == [{"type": "image"}, {"type": "text", "text": "Inspect."}]


def test_resize_matches_llamafactory_rule():
    out = resize_to_max_pixels(Image.new("RGB", (1080, 1920)), 262144)
    assert out.width * out.height <= 262144
    assert out.size == (384, 682)
    small = Image.new("RGB", (100, 100))
    assert resize_to_max_pixels(small, 262144).size == (100, 100)


def test_backend_enforces_contract_prompt_and_resolution(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(no_grad=nullcontext))

    class Inputs(dict):
        input_ids = [[1, 2]]

        def to(self, device):
            return self

    processor = Mock()
    processor.apply_chat_template.return_value = "rendered"
    processor.return_value = Inputs(input_ids=Inputs.input_ids)
    processor.batch_decode.return_value = ['{"has_defect": false}']
    model = Mock(device="cpu")
    model.generate.return_value = [[1, 2, 3]]
    backend = TransformersInferenceBackend(adapter_dir=str(_write(tmp_path)))
    backend.processor, backend.model = processor, model

    caller = [{"role": "system", "content": "Long schema prompt"},
              {"role": "user", "content": [{"type": "image"}, {"type": "text", "text": "x"}]}]
    backend.generate(caller, Image.new("RGB", (1080, 2400)))

    sent = processor.apply_chat_template.call_args.args[0]
    assert sent == contract_messages(backend.inference_contract)
    w, h = processor.call_args.kwargs["images"][0].size
    assert w * h <= 262144


def test_compact_target_drops_unpredictable_fields():
    v1 = {"has_defect": True, "defect_type": "component_overlap", "confidence": 1.0,
          "bounding_box": [10, 20, 1200, 40], "affected_element_id": "id/x", "explanation": "..."}
    assert json.loads(compact_target(v1)) == {
        "has_defect": True, "defect_type": "component_overlap", "bounding_box": [10, 20, 1000, 40]}
    clean = json.loads(compact_target({"defect_type": "none", "bounding_box": [1, 2, 3, 4]}))
    assert clean == {"has_defect": False, "defect_type": "none", "bounding_box": None}
    with pytest.raises(ValueError):
        compact_target({"defect_type": "made_up"})
    assert "data_binding_null" in TRAINING_PROMPT


def test_benchmark_summary_counts_invalid_as_missed():
    from local_vision_oracle.contract_benchmark import parse_output, summarize, box_iou
    assert parse_output('x {"has_defect": true, "defect_type": "component_overlap"} y')["has_defect"] is True
    assert parse_output('{"has_defect": "yes"}') is None
    assert parse_output("no json") is None
    assert box_iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    recs = [
        {"gold_has": True, "gold_type": "component_overlap", "pred_has": True,
         "pred_type": "component_overlap", "iou": 0.6, "latency_ms": 1},
        {"gold_has": True, "gold_type": "text_truncation", "pred_has": None,
         "pred_type": "INVALID", "iou": None, "latency_ms": 2},
        {"gold_has": False, "gold_type": "none", "pred_has": True,
         "pred_type": "component_overlap", "iou": None, "latency_ms": 3},
        {"gold_has": False, "gold_type": "none", "pred_has": False,
         "pred_type": "none", "iou": None, "latency_ms": 4},
    ]
    s = summarize(recs)
    assert (s["tp"], s["fn"], s["fp"], s["tn"]) == (1, 1, 1, 1)
    assert s["invalid_outputs"] == 1 and s["f1"] == 0.5
    assert s["iou_at_0_5_on_defects"] == 0.5


def test_auc_threshold_helpers():
    from local_vision_oracle.contract_benchmark import roc_auc, best_threshold, metrics_at
    scores, labels = [0.9, 0.8, 0.3, 0.1], [True, True, False, False]
    assert roc_auc(scores, labels) == 1.0
    assert best_threshold(scores, labels)["f1"] == 1.0
    m = metrics_at(scores, labels, 0.5)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (2, 0, 0, 2)
    assert roc_auc([0.5, 0.5], [True, False]) == 0.5


def test_threshold_path_clean_and_flagged(tmp_path):
    backend = TransformersInferenceBackend(adapter_dir=str(_write(tmp_path, decision_threshold=0.5)))
    backend.processor = Mock()
    backend.processor.apply_chat_template.return_value = "prompt"
    backend.model = Mock()
    img = Image.new("RGB", (1080, 1920))

    backend._defect_probability_from_prompt = lambda text, image: 0.2
    clean = json.loads(backend.generate([], img))
    assert clean == {"has_defect": False, "defect_type": "none", "bounding_box": None, "defect_probability": 0.2}

    backend._defect_probability_from_prompt = lambda text, image: 0.8
    seen = {}

    def fake_decode(text, image, max_new_tokens, temperature, stop_after_box=False):
        seen["text"], seen["stop"] = text, stop_after_box
        return ' "defect_type": "component_overlap", "confidence": 1.0, "bounding_box": [1, 2, 3, 4], "affected_element_id": "x'

    backend._decode = fake_decode
    out = json.loads(backend.generate([], img))
    assert seen["text"].endswith('{"has_defect": true,') and seen["stop"] is True
    assert out["has_defect"] is True and out["bounding_box"] == [1, 2, 3, 4]
    assert out["confidence"] == 0.8 and "affected_element_id" not in out
