"""Interactive report: the reliability banner (no device, no Plotly needed).

The banner's job is that a disrupted replay can never quietly look like a clean
one — so a stuck/relaunched run shows a prominent warning at the top of the report,
while a clean run (or a map run, which writes no verdict) shows none.
"""
import json

from engine.interactive_report import _reliability_banner, build_report

_TL = {"run_id": "r", "persona_id": "rushed", "records": [
    {"t_ms": 1, "target_element_id": "A", "x": 1, "y": 1, "hit_flag": True,
     "error_px": 2.0, "stress_s": 0.1, "cognitive_state": "calm"},
]}


def test_banner_empty_for_ok_or_missing():
    assert _reliability_banner(None) == ""
    assert _reliability_banner({}) == ""
    assert _reliability_banner({"level": "ok", "message": "clean"}) == ""


def test_banner_unreliable_is_prominent_and_carries_counts():
    html = _reliability_banner({
        "level": "unreliable", "message": "stuck at login",
        "taps": 119, "relaunches": 16, "drifts": 0, "verified": 0})
    assert 'class="banner unreliable"' in html
    assert "unreliable" in html.lower()
    assert "16 relaunches" in html
    assert "stuck at login" in html


def test_build_report_autoloads_reliability_sidecar(tmp_path):
    tl = tmp_path / "x_timeline.json"
    tl.write_text(json.dumps(_TL), encoding="utf-8")
    # the sidecar a replay run leaves next to the timeline
    (tmp_path / "x_reliability.json").write_text(json.dumps({
        "level": "unreliable", "message": "blind + relaunched",
        "taps": 119, "relaunches": 16, "drifts": 0, "verified": 0}), encoding="utf-8")

    out = build_report(str(tl))                      # no reliability arg → auto-load
    doc = (tmp_path / "x_report.html").read_text(encoding="utf-8")
    assert out.endswith("x_report.html")
    assert 'class="banner unreliable"' in doc
    assert "blind + relaunched" in doc


def test_build_report_no_banner_without_sidecar(tmp_path):
    tl = tmp_path / "map_timeline.json"
    tl.write_text(json.dumps(_TL), encoding="utf-8")   # a map run: no sidecar
    build_report(str(tl))
    doc = (tmp_path / "map_report.html").read_text(encoding="utf-8")
    assert 'class="banner' not in doc
