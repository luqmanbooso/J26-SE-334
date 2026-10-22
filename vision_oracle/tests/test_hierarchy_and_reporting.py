"""Shared hierarchy text, fusion contract prompts and honest verdict reporting (no GPU)."""

import json

import pytest
from PIL import Image

from local_vision_oracle.engine import contract_messages, contract_prompt_text, load_inference_contract
from local_vision_oracle.hierarchy_text import (
    elements_from_rico, elements_from_uiautomator, format_hierarchy, hierarchy_text,
)

RICO = {"activity": {"root": {
    "class": "android.widget.FrameLayout", "bounds": [0, 0, 1440, 2560], "visibility": "visible",
    "children": [
        {"class": "com.app.q", "ancestors": ["android.widget.Button", "android.view.View"],
         "resource-id": "com.app:id/sign_in", "text": "Sign In", "clickable": True,
         "bounds": [0, 2152, 1440, 2320], "visibility": "visible"},
        {"class": "android.widget.ImageView", "resource-id": "com.app:id/logo", "content-desc": [None],
         "bounds": [240, 260, 1200, 1020], "visibility": "visible"},
        {"class": "android.widget.TextView", "text": "hidden", "bounds": [0, 0, 100, 100], "visibility": "gone"},
        {"class": "android.widget.TextView", "text": "zero", "bounds": [10, 10, 10, 50], "visibility": "visible"},
    ]}}}

XML = """<?xml version='1.0' encoding='UTF-8'?><hierarchy rotation="0">
<node class="android.widget.FrameLayout" bounds="[0,0][1440,2560]" text="" resource-id="" clickable="false">
<node class="android.widget.Button" resource-id="com.app:id/sign_in" text="Sign In" clickable="true" bounds="[0,2152][1440,2320]" />
<node class="android.widget.ImageView" resource-id="com.app:id/logo" text="" clickable="false" bounds="[240,260][1200,1020]" />
<node class="android.widget.TextView" text="hidden" visible-to-user="false" bounds="[0,0][100,100]" />
</node></hierarchy>"""


def test_rico_and_uiautomator_give_identical_text():
    rico, xml = hierarchy_text(RICO), hierarchy_text(XML)
    assert rico == xml
    assert rico.splitlines() == [
        "ImageView#logo [102,167,398,833]",
        'Button#sign_in "Sign In" [841,0,906,1000] click',
    ]


def test_rico_obfuscated_class_uses_framework_ancestor_and_skips_invisible():
    names = [e.class_name for e in elements_from_rico(RICO)]
    assert "android.widget.Button" in names and "com.app.q" not in names
    assert all("hidden" not in e.text and "zero" not in e.text for e in elements_from_rico(RICO))


def test_format_caps_nodes_in_reading_order():
    els = elements_from_uiautomator(XML) * 15
    text = format_hierarchy(els, max_nodes=4)
    assert len(text.splitlines()) == 5 and text.endswith("26 more elements omitted")


def test_missing_or_empty_hierarchy_gives_none():
    assert hierarchy_text(None) is None and hierarchy_text("   ") is None and hierarchy_text("<bad") is None


def _contract(tmp_path, **extra):
    data = {"user_prompt": "Inspect {json}.", "system_prompt": None, "image_max_pixels": 262144, **extra}
    (tmp_path / "inference_contract.json").write_text(json.dumps(data), encoding="utf-8")
    return load_inference_contract(str(tmp_path))


def test_fusion_prompt_used_only_with_hierarchy(tmp_path):
    c = _contract(tmp_path, hierarchy_prompt='Layout:\n{hierarchy}\nInspect {"has_defect": ...}.')
    assert contract_prompt_text(c, "Button [1,2,3,4]") == 'Layout:\nButton [1,2,3,4]\nInspect {"has_defect": ...}.'
    assert contract_prompt_text(c, None) == "Inspect {json}."
    vision_only = _contract(tmp_path)
    assert contract_prompt_text(vision_only, "Button [1,2,3,4]") == "Inspect {json}."
    assert contract_messages(c, "X")[0]["content"][1]["text"].startswith("Layout:\nX")


def test_hierarchy_prompt_without_placeholder_rejected(tmp_path):
    with pytest.raises(ValueError):
        _contract(tmp_path, hierarchy_prompt="no placeholder")


class _ReportingBackend:
    """Mimics TransformersInferenceBackend reporting without a model."""

    def __init__(self, contract, p):
        self.inference_contract, self.p, self.seen = contract, p, []
        self.last_call = {}

    def generate(self, messages, image, hierarchy_text=None, **kwargs):
        self.seen.append(hierarchy_text)
        used = bool(hierarchy_text) and bool(self.inference_contract.get("hierarchy_prompt"))
        self.last_call = {"model_input": "screenshot+hierarchy" if used else "screenshot",
                          "defect_probability": self.p, "decision_threshold": 0.5,
                          "verdict_ms": 600.0, "localization_ms": None}
        return json.dumps({"has_defect": False, "defect_type": "none", "bounding_box": None})


@pytest.mark.parametrize("fusion", [False, True])
def test_pipeline_reports_model_input_probability_and_timings(tmp_path, fusion):
    from vision_oracle.contracts.v2 import CaptureBundle
    from vision_oracle.frontend.presentation import model_lines
    from vision_oracle.local_vision_oracle.pipeline import AnalysisPipeline

    extra = {"hierarchy_prompt": "L:\n{hierarchy}\nInspect."} if fusion else {}
    backend = _ReportingBackend(_contract(tmp_path, **extra), 0.31)
    bundle = CaptureBundle(capture_id="cap_test", session_id="s", width=1440, height=2560,
                           image_sha256="x", artifact_path="x.png", raw_hierarchy=XML, hierarchy_status="available")
    verdict = AnalysisPipeline(backend=backend, model_run_id="t").analyze(
        bundle=bundle, image=Image.new("RGB", (1440, 2560)), coverage_policy="global_only")

    md = verdict.metadata
    assert md["defect_probability"] == 0.31 and md["hierarchy_used_by_model"] is fusion
    assert verdict.timings_ms["verdict_ms"] == 600.0
    assert (backend.seen[0] is not None) is fusion  # vision-only adapters never get layout text
    text = " ".join(model_lines(md, verdict.timings_ms))
    assert "31%" in text and "not a calibrated probability" in text and "decision 0.6s" in text
    assert ("not read by this model" in text) is (not fusion)


def test_every_trained_defect_type_is_accepted_by_the_app():
    """Regression: data_binding_null was trained but rejected, turning findings into 'inconclusive'."""
    from vision_oracle.contracts.v2 import FindingType
    from local_vision_oracle.dataset_v2 import DEFECT_TYPES
    assert {t for t in DEFECT_TYPES if t != "none"} <= {t.value for t in FindingType}
