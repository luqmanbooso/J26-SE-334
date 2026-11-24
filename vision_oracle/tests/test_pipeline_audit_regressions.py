"""Regressions for bugs found in the 21 October 2026 pipeline audit (no GPU)."""

import json
from types import SimpleNamespace

from PIL import Image

from local_vision_oracle.pruner import HierarchyPruner

RICO = {"activity_name": "app/Main", "activity": {"root": {
    "class": "android.widget.FrameLayout", "bounds": [0, 0, 1440, 2392], "visibility": "visible",
    "children": [
        {"class": "android.widget.TextView", "text": "Hello", "bounds": [100, 200, 900, 300], "visibility": "visible"},
        {"class": "android.widget.TextView", "text": "hidden", "bounds": [100, 200, 900, 300], "visibility": "gone"},
        {"class": "android.widget.Button", "text": "Go", "clickable": True, "bounds": [100, 400, 600, 500],
         "visibility": "visible", "children": [
             {"class": "android.widget.TextView", "text": "Go", "bounds": [120, 410, 580, 490], "visibility": "visible"}]},
    ]}}}

XML_ROW = """<hierarchy><node class="android.widget.FrameLayout" bounds="[0,0][1080,2400]" text="" clickable="false">
<node class="android.widget.LinearLayout" resource-id="app:id/row" text="Contact" clickable="true" bounds="[0,300][1080,450]">
<node class="android.widget.ImageView" resource-id="app:id/photo" text="photo" clickable="true" bounds="[20,310][200,440]"/>
</node></node></hierarchy>"""


def test_rico_hierarchy_is_read_from_activity_root():
    nodes = HierarchyPruner().prune(RICO)
    assert [n.text for n in nodes] == ["Hello", "Go", "Go"]  # hidden view skipped
    assert nodes[0].bounds == [78, 69, 117, 625]  # normalised to the 1440x2560 Rico device


def test_parent_child_and_hidden_views_are_not_collisions():
    p = HierarchyPruner()
    assert p.detect_layout_collisions(p.prune(RICO)) == []
    p = HierarchyPruner(screen_width=1080, screen_height=2400)
    assert p.detect_layout_collisions(p.prune(XML_ROW)) == []


def test_sibling_overlap_is_still_detected():
    data = json.loads(json.dumps(RICO))
    data["activity"]["root"]["children"].append(
        {"class": "android.widget.TextView", "text": "Overlap", "bounds": [300, 220, 1000, 320], "visibility": "visible"})
    p = HierarchyPruner()
    assert p.detect_layout_collisions(p.prune(data))


def test_legacy_engine_does_not_short_circuit_on_layout_rule():
    from local_vision_oracle.engine import OracleEngine, MockInferenceBackend
    data = json.loads(json.dumps(RICO))
    data["activity"]["root"]["children"].append(
        {"class": "android.widget.TextView", "text": "Overlap", "bounds": [300, 220, 1000, 320], "visibility": "visible"})
    res = OracleEngine(backend=MockInferenceBackend()).evaluate(
        image_input=Image.new("RGB", (1080, 1920), "white"), raw_hierarchy=data, enable_sahi=False)
    assert res.metadata.get("detected_by") != "ast_collision_detector"
    assert res.metadata.get("layout_collisions")  # kept as evidence


def test_cli_benchmark_refuses_real_mode_without_backend(tmp_path, capsys):
    from local_vision_oracle import cli
    ds = tmp_path / "d.json"
    ds.write_text("[]")
    rc = cli.cmd_benchmark(SimpleNamespace(dataset=str(ds), mock=False, output=str(tmp_path / "o.csv")))
    assert rc == 2 and "only supports --mock" in capsys.readouterr().err


def test_element_ref_comes_from_captured_layout_not_the_model():
    import json as _json
    from vision_oracle.contracts.v2 import CaptureBundle
    from vision_oracle.local_vision_oracle.pipeline import AnalysisPipeline

    class Fake:
        inference_contract = {"decision_threshold": 0.5, "image_max_pixels": 262144, "user_prompt": "x"}
        last_call = {}

        def __init__(self, element):
            self.element = element

        def generate(self, messages, image, **kw):
            return _json.dumps({"has_defect": True, "defect_type": "component_overlap",
                                "bounding_box": [125, 0, 190, 1000], "affected_element_id": self.element})

    xml = ('<hierarchy><node class="android.widget.FrameLayout" bounds="[0,0][1080,2400]" text="" clickable="false">'
           '<node class="android.widget.Button" resource-id="app:id/sign_in" text="Sign in" clickable="true" bounds="[0,312][1080,444]"/>'
           '</node></hierarchy>')
    img = Image.new("RGB", (1080, 2400))
    for invented in ("made_up_id", None):
        b = CaptureBundle(capture_id="c", session_id="s", action_id="act_1", width=1080, height=2400,
                          image_sha256="x", artifact_path="x.png", raw_hierarchy=xml, hierarchy_status="available")
        v = AnalysisPipeline(backend=Fake(invented)).analyze(bundle=b, image=img, coverage_policy="global_only")
        assert v.findings[0].element_ref == "app:id/sign_in"
        assert v.to_c4_verdict().evidence["handover_outcome"] == "ready_for_test_generation"
    b = CaptureBundle(capture_id="c", session_id="s", action_id="act_1", width=1080, height=2400,
                      image_sha256="x", artifact_path="x.png", hierarchy_status="missing")
    v = AnalysisPipeline(backend=Fake("made_up_id")).analyze(bundle=b, image=img, coverage_policy="global_only")
    assert v.findings[0].element_ref is None  # no layout: invented ids are not passed on
