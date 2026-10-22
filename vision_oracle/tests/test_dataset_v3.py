"""Dataset v3 rules and OwlEye label validation (no GPU, no real dataset needed)."""

import json

from PIL import Image, ImageDraw

from local_vision_oracle.dataset_v3 import (
    FUSION_PROMPT, VISION_PROMPT, assign_rico_splits, change_stats, contract, make_example,
)
from local_vision_oracle.owleye_labeling import validate_label


def _rico(app):
    return {"activity_name": f"{app}/Main", "activity": {"root": {"bounds": [0, 0, 1440, 2560], "children": []}}}


def test_app_grouping_follows_strictest_old_split(tmp_path):
    clean, data = tmp_path / "clean", tmp_path / "data"
    clean.mkdir(); data.mkdir()
    for sid, app in (("1", "a"), ("2", "a"), ("3", "b"), ("4", "c")):
        (clean / f"{sid}.json").write_text(json.dumps(_rico(app)))
    row = lambda p: {"images": [p], "messages": []}  # noqa: E731
    (data / "train.json").write_text(json.dumps([row("x/clean/1.jpg"), row("x/mutated_bugs/3_mut_overlap.jpg")]))
    (data / "val.json").write_text("[]")
    (data / "test.json").write_text(json.dumps([row("x/clean/2.jpg")]))
    s = assign_rico_splits(clean, data)
    assert s["1"][0] == s["2"][0] == "test"  # app "a" had a test screen
    assert s["3"][0] == "train"
    apps = {}
    for split, app in s.values():
        apps.setdefault(app, set()).add(split)
    assert all(len(v) == 1 for v in apps.values())


def test_change_stats_detects_invisible_and_misplaced():
    base = Image.new("RGB", (1080, 1920), "white")
    tiny = base.copy(); ImageDraw.Draw(tiny).rectangle([500, 900, 502, 902], fill="black")
    big = base.copy(); ImageDraw.Draw(big).rectangle([100, 200, 600, 500], fill="black")
    vis, _ = change_stats(base, tiny, [460, 460, 480, 480])
    assert vis < 0.002
    vis, cov = change_stats(base, big, [104, 92, 261, 556])
    assert vis > 0.002 and cov > 0.9
    _, cov = change_stats(base, big, [800, 800, 900, 900])
    assert cov < 0.1


def test_examples_share_label_and_differ_only_in_prompt():
    target = {"defect_type": "component_overlap", "bounding_box": [1, 2, 3, 4]}
    v = make_example("a.jpg", target, "Button [1,2,3,4]", fusion=False)
    f = make_example("a.jpg", target, "Button [1,2,3,4]", fusion=True)
    owl = make_example("b.jpg", target, None, fusion=True)
    assert v["messages"][1] == f["messages"][1]
    assert v["messages"][0]["content"] == "<image>" + VISION_PROMPT
    assert "Button [1,2,3,4]" in f["messages"][0]["content"]
    assert owl["messages"][0]["content"] == "<image>" + VISION_PROMPT  # no layout -> vision prompt
    assert contract(True)["hierarchy_prompt"] == FUSION_PROMPT and "hierarchy_prompt" not in contract(False)


def test_label_validation():
    ok = {"status": "labelled", "defect_type": "text_truncation", "bounding_box": [10, 20, 30, 40], "human_verified": False}
    assert validate_label("x", ok) == []
    assert validate_label("x", {**ok, "bounding_box": [30, 20, 10, 40]})
    assert validate_label("x", {**ok, "defect_type": "blurry"})
    assert validate_label("x", {"status": "unclear"}) == []
