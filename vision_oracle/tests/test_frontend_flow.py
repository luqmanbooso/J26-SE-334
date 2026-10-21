"""Pipeline-flow strip on the C3 workspace. Builds the real Tk window but never loads the model."""

import pytest

import vision_oracle.services.oracle_service  # noqa: F401  path guard first

ctk = pytest.importorskip("customtkinter")


@pytest.fixture
def workspace():
    try:
        root = ctk.CTk()
    except Exception as exc:  # no display available
        pytest.skip(f"Tk display unavailable: {exc}")
    from vision_oracle.frontend.workspace import C3Workspace
    ws = C3Workspace(root, service_factory=lambda: (_ for _ in ()).throw(AssertionError("model must not load")))
    ws.pack()
    root.update()
    yield ws
    root.destroy()


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
