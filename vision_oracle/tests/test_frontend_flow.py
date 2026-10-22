"""C3 workspace UI. Builds the real Tk window but never loads the model."""

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


def test_default_model_is_the_v3_vision_adapter(monkeypatch):
    import os
    import vision_oracle.services.oracle_service as svc
    from vision_oracle.core.config import LORA_WEIGHTS_PATH
    if os.getenv("C3_ADAPTER"):
        pytest.skip("C3_ADAPTER overrides the default on this machine")
    monkeypatch.setattr(svc, "_ADAPTER_OVERRIDE", None)
    assert LORA_WEIGHTS_PATH is not None and LORA_WEIGHTS_PATH.name == "c3_v3_vision_1ep"
    assert svc.active_adapter() == LORA_WEIGHTS_PATH


def test_score_bar_hidden_until_there_is_a_score(workspace):
    workspace.draw_score(None, None)
    assert not workspace.score_canvas.winfo_manager()
    workspace.draw_score(0.5, 0.3)
    assert workspace.score_canvas.winfo_manager() == "grid"


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


def test_own_app_capture_is_discoverable(workspace):
    texts = []
    for w in workspace.controls:
        try:
            texts.append(w.cget("text"))
        except (ValueError, KeyError, Exception):
            pass
    assert "Capture my app (phone)" in texts
    guide = workspace.guide.cget("text")
    assert "your own app" in guide.lower() and "History" in guide


def test_live_rows_keep_only_c2_actions_after_start():
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from vision_oracle.frontend.workspace import C3Workspace
    start = datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc)
    pairs = [
        (SimpleNamespace(action_id="live-0001"), (start + timedelta(seconds=5)).isoformat()),   # kept
        (SimpleNamespace(action_id=None), (start + timedelta(seconds=6)).isoformat()),          # manual inspection
        (SimpleNamespace(action_id="live-old"), (start - timedelta(minutes=5)).isoformat()),    # before the receiver
        (SimpleNamespace(action_id="live-0002"), start + timedelta(seconds=9)),                 # datetime, kept
    ]
    kept = [v.action_id for v, _ in C3Workspace.live_rows_since(pairs, start)]
    assert kept == ["live-0001", "live-0002"]


def test_receiver_starts_offers_url_and_stops(workspace, monkeypatch):
    import uvicorn

    class FakeServer:
        def __init__(self, config):
            self.started, self.should_exit = True, False

        def run(self):
            pass

    monkeypatch.setattr(uvicorn, "Server", FakeServer)
    monkeypatch.setattr(uvicorn, "Config", lambda *a, **k: None)
    offered = []
    workspace.receiver_url_callback = offered.append
    workspace.start_receiver()
    if workspace.receiver is None:
        pytest.skip(workspace.live_status.cget("text"))  # port already in use on this machine
    assert offered == [workspace.live_url]
    assert workspace.live_button.cget("text") == "Stop receiving"
    workspace.stop_receiver()
    assert workspace.receiver is None and workspace.live_button.cget("text") == "Start receiving"


def test_history_names_where_a_result_came_from():
    from vision_oracle.frontend.workspace import C3Workspace
    assert C3Workspace.source_of({"action_id": "live_session-0003", "session_id": "live_session", "metadata": {}}) == "C2 action live_session-0003"
    assert C3Workspace.source_of({"metadata": {"device_serial": "R58M", "app_package": "com.shop"}}) == "phone · com.shop"
    assert C3Workspace.source_of({"metadata": {}}) == "screenshot file"


def test_live_tab_explains_an_empty_list(workspace, monkeypatch):
    import uvicorn

    class FakeServer:
        def __init__(self, config):
            self.started, self.should_exit = False, False

        def run(self):
            pass

    monkeypatch.setattr(uvicorn, "Server", FakeServer)
    monkeypatch.setattr(uvicorn, "Config", lambda *a, **k: None)
    workspace.start_receiver()
    if workspace.receiver is None:
        pytest.skip(workspace.live_status.cget("text"))
    assert workspace.live_progress.winfo_manager() == "pack"  # visible while the model loads
    workspace.show_live(True, [])
    assert "connect a phone" in workspace.live_empty.cget("text")
    assert not workspace.live_progress.winfo_manager()
    workspace.stop_receiver()
    assert workspace.live_button.cget("text") == "Start receiving"


def test_save_phone_screen_without_a_phone_says_what_to_do(workspace, monkeypatch):
    import vision_oracle.frontend.workspace as wsmod
    shown = []
    monkeypatch.setattr(wsmod.messagebox, "showinfo", lambda title, msg, **k: shown.append(msg))
    workspace.device.set("No device")
    workspace.save_phone_screen()
    assert shown and "Connect your phone" in shown[0]


def test_save_phone_screen_writes_image_and_xml_and_loads_them(workspace, tk_root, monkeypatch, tmp_path):
    import time
    from PIL import Image
    import common.adb as adb
    import vision_oracle.frontend.workspace as wsmod

    class FakeDevice:
        serial = "R58M-test"

        def __init__(self, serial=None, verify=True):
            pass

        @staticmethod
        def resolve_serial(serial=None):
            return "R58M-test"

        def screencap(self, as_pil=True):
            return Image.new("RGB", (90, 160), "white")

        def dump_hierarchy(self, max_age_s=0.0):
            return "<hierarchy><node class='android.widget.TextView'/></hierarchy>"

    monkeypatch.setattr(adb, "AdbDevice", FakeDevice)
    monkeypatch.setattr(wsmod, "C3_ROOT", tmp_path)
    workspace.device.configure(values=["R58M-test"]);workspace.device.set("R58M-test")
    workspace.save_phone_screen()
    deadline = time.time() + 10
    while time.time() < deadline and not workspace.hierarchy_path:
        tk_root.update();time.sleep(0.05)
    saved = tmp_path / "results" / "captured_screens"
    pngs, xmls = list(saved.glob("*.png")), list(saved.glob("*.xml"))
    assert len(pngs) == 1 and len(xmls) == 1 and pngs[0].stem == xmls[0].stem
    assert "TextView" in xmls[0].read_text(encoding="utf-8")
    assert workspace.image_path == str(pngs[0].resolve()) and workspace.hierarchy_path == str(xmls[0])
    assert "press Inspect screenshot" in workspace.status.cget("text")
