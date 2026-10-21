"""Pipeline-flow strip on the C3 workspace. Builds the real Tk window but never loads the model."""

import pytest

import vision_oracle.services.oracle_service  # noqa: F401  path guard first

ctk = pytest.importorskip("customtkinter")


@pytest.fixture(scope="module")
def tk_root():
    # One Tk interpreter for the module: creating many in a row is flaky on Windows ("usable init.tcl").
    try:
        root = ctk.CTk()
    except Exception as exc:  # no display available
        pytest.skip(f"Tk display unavailable: {exc}")
    yield root
    root.destroy()


@pytest.fixture
def workspace(tk_root):
    from vision_oracle.frontend.workspace import C3Workspace
    ws = C3Workspace(tk_root, service_factory=lambda: (_ for _ in ()).throw(AssertionError("model must not load")))
    ws.pack()
    tk_root.update()
    yield ws
    ws.destroy()


def status(ws, index):
    return ws.stage_status[index].cget("text")


def test_initial_state_marks_c3_ready_and_upstream_not_run(workspace):
    assert [status(workspace, i) for i in range(4)] == ["Not run here", "Not run here", "Ready", "Waiting for a result"]


@pytest.mark.parametrize("decision,findings,expected", [
    ("defect_detected", [{}, {}], "2 findings"),
    ("defect_detected", [{}], "1 finding"),
    ("no_defect_detected", [], "No defect found"),
    ("inconclusive", [], "Inconclusive"),
])
def test_result_updates_c3_card_and_readies_c4(workspace, decision, findings, expected):
    workspace.flow_from_view({"verdict": {"decision": decision, "findings": findings}})
    assert status(workspace, 2) == expected
    assert status(workspace, 3) == "Review, then send"


def test_clearing_a_result_resets_the_strip(workspace):
    workspace.flow_from_view({"verdict": {"decision": "defect_detected", "findings": [{}]}})
    workspace.clear_result()
    assert status(workspace, 2) == "Ready" and status(workspace, 3) == "Waiting for a result"


def test_delivery_receipt_marks_c4_done(workspace):
    workspace.set_stage(3, "done", "Receipt received")
    assert status(workspace, 3) == "Receipt received"


def test_preview_walks_every_stage_then_restores(workspace):
    workspace.preview_flow()
    assert status(workspace, 0).startswith("Applies")
    workspace.after_cancel(workspace.preview_job)
    workspace.preview_job = None
    workspace.reset_flow()
    assert status(workspace, 0) == "Not run here"


def test_score_bar_draws_score_and_alert_level(workspace):
    workspace.draw_score(0.41, 0.30)
    texts = [workspace.score_canvas.itemcget(i, "text") for i in workspace.score_canvas.find_all()
             if workspace.score_canvas.type(i) == "text"]
    assert "model score 41%" in texts and "alert at 30%" in texts


def test_finding_cards_and_selection(workspace):
    findings = [{"type": "component_overlap", "element_ref": "TextView#title", "confidence": 0.8, "bbox_xyxy": [1, 1, 5, 5]},
                {"type": "data_binding_null", "confidence": None}]
    workspace.render_findings(findings)
    assert len(workspace.finding_cards) == 2
    workspace.select_finding(1)
    assert workspace.selected_finding == 1
    workspace.render_findings([])
    assert workspace.selected_finding is None


def test_model_tab_reads_adapter_files(workspace):
    text = workspace.model_summary()
    assert text.startswith("Adapter:") or "No adapter folder" in text


def test_model_selector_lists_adapters_and_switches(workspace, monkeypatch):
    import vision_oracle.services.oracle_service as svc
    from pathlib import Path
    monkeypatch.setattr(svc, "_ADAPTER_OVERRIDE", None)
    assert workspace.adapter_choices, "expected at least the default adapter"
    fusion = next((label for label in workspace.adapter_choices if label.startswith("Fusion")), None)
    if fusion is None:
        pytest.skip("fusion adapter not on disk")
    workspace.choose_model(fusion)
    assert Path(svc.active_adapter()).name == "c3_v3_fusion_1ep"
    assert "c3_v3_fusion_1ep" in workspace.model_summary()
    assert "Model changed" in workspace.status.cget("text")


def test_model_selector_refuses_while_busy(workspace, monkeypatch):
    import vision_oracle.services.oracle_service as svc
    monkeypatch.setattr(svc, "_ADAPTER_OVERRIDE", None)
    label = next(iter(workspace.adapter_choices))
    workspace.busy = True
    before = svc.active_adapter()
    workspace.choose_model(label)
    workspace.busy = False
    assert svc.active_adapter() == before
