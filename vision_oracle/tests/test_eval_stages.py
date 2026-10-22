"""Staged evaluation runner: subsets, metrics, gates, recompute (no GPU)."""

import json
from pathlib import Path

import pytest

from local_vision_oracle import eval_stages as es


def _manifest(tmp_path):
    rows = []
    for i in range(40):
        t = ["none", "component_overlap", "text_truncation", "missing_component", "data_binding_null"][i % 5]
        img = f"C:/Games/OwlEye/Dataset/bug-aug/bug-aug/bug.{i}.jpg" if (t != "none" and i % 2) else \
              f"D:/x/mutated_v3/val/{i}_v3_overlap.jpg" if t != "none" else f"D:/x/clean/{i}.jpg"
        ans = {"has_defect": t != "none", "defect_type": t, "bounding_box": [100, 100, 200, 200] if t != "none" else None}
        rows.append({"messages": [{"role": "user", "content": "<image>x"}, {"role": "assistant", "content": json.dumps(ans)}],
                     "images": [img]})
    p = tmp_path / "val.json"
    p.write_text(json.dumps(rows))
    return str(p)


def test_subsets_are_fixed_and_stratified(tmp_path):
    m = _manifest(tmp_path)
    a, b = es.load_subset("smoke", m), es.load_subset("smoke", m)
    assert [x["image"] for x in a] == [x["image"] for x in b] and len(a) == 24
    assert {x["gold_type"] for x in a} == {"none", "component_overlap", "text_truncation", "missing_component", "data_binding_null"}
    assert len(es.load_subset("full", m)) == 40


def _records():
    recs = []
    for i in range(20):
        g = i % 2 == 0
        recs.append({"image": f"{i}", "source": "rico_clean" if not g else "rico_mutated", "gold_has": g,
                     "gold_type": "component_overlap" if g else "none", "gold_box": [100, 100, 300, 300] if g else None,
                     "p_defect": 0.9 if g else 0.1, "latency_ms": 10.0 + i,
                     "pred_has": g, "pred_type": "component_overlap" if g else "none",
                     "pred_box": [100, 100, 300, 300] if g else None})
    recs[0].update(pred_has=None, pred_type="invalid", pred_box=None)
    return recs


def test_score_and_e2e_metrics():
    recs = _records()
    s = es.compute_metrics(recs, "score", 0.5)
    assert s["auc"] == 1.0 and s["at_contract_threshold"]["f1"] == 1.0
    e = es.compute_metrics(recs, "e2e", 0.5)
    assert e["binary"]["fn"] == 1 and e["invalid_rate"] == 0.05
    assert e["confusion_matrix"]["component_overlap"]["invalid"] == 1
    assert e["localization"]["recall_at_iou_0.5"] == pytest.approx(9 / 10)
    assert es.gate(e, "e2e")["passed"]


def test_gate_rejects_broken_runs():
    recs = _records()
    for r in recs:
        r.update(pred_has=True, pred_type="component_overlap", p_defect=0.5)
    assert not es.gate(es.compute_metrics(recs, "e2e", 0.5), "e2e")["passed"]
    assert not es.gate(es.compute_metrics(recs, "score", 0.5), "score")["passed"]


def test_recompute_matches_saved(tmp_path):
    recs = _records()
    doc = {"identity": {"mode": "e2e", "contract": {"decision_threshold": 0.5}},
           "metrics": es.compute_metrics(recs, "e2e", 0.5), "records": recs}
    p = tmp_path / "run.json"
    p.write_text(json.dumps(doc))
    assert es.recompute(str(p)) == doc["metrics"]
