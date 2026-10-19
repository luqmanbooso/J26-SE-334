"""
Unit and integration tests for Common Test Execution Driver Layer (common/driver.py).
Fulfills:
- Requirement R2: Common driver layer dispatching actions under cross-process ADB lock.
- Autonomous UI node discovery, settle delays, live capture, and C3 visual oracle evaluation.
- Inspection trace compilation and defect breakdown report generation.
"""

import io
import time
import pytest
from PIL import Image

from common.adb import AdbDevice
from common.driver import CommonTestDriver
from local_vision_oracle.engine import OracleEngine, MockInferenceBackend
from vision_oracle.services.oracle_service import OracleService


def _create_mock_png_bytes(size=(1080, 2400)) -> bytes:
    img = Image.new("RGB", size, (240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def mock_driver(monkeypatch):
    """Sets up CommonTestDriver with mocked ADB calls for fast unit testing."""
    valid_png = _create_mock_png_bytes()
    sample_xml = """<hierarchy rotation="0">
        <node class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">
            <node class="android.widget.Button" resource-id="com.solvance.android:id/btn_checkout"
                  text="Proceed to Checkout" bounds="[100,2000][980,2180]" clickable="true"/>
            <node class="android.widget.EditText" resource-id="com.solvance.android:id/edt_coupon"
                  text="Enter coupon" bounds="[100,1800][980,1950]" clickable="true"/>
        </node>
    </hierarchy>"""

    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": ["emulator-5554"]))
    monkeypatch.setattr(AdbDevice, "run_bytes", lambda *a, **k: valid_png)
    monkeypatch.setattr(AdbDevice, "dump_hierarchy", lambda *a, **k: sample_xml)
    monkeypatch.setattr(AdbDevice, "get_display_metrics", lambda *a, **k: {"width": 1080, "height": 2400, "density": 420})
    monkeypatch.setattr(AdbDevice, "shell", lambda *a, **k: "")
    monkeypatch.setattr(time, "sleep", lambda s: None)

    # Mock Oracle service
    engine = OracleEngine(backend=MockInferenceBackend())
    service = OracleService(engine=engine)

    return CommonTestDriver(
        serial="emulator-5554",
        package_name="com.solvance.android",
        settle_delay_s=0.01,
        oracle_service=service,
    )


def test_driver_extract_interactive_nodes(mock_driver):
    nodes = mock_driver.extract_interactive_nodes()
    assert len(nodes) == 2

    btn = nodes[0]
    assert btn["resource_id"] == "com.solvance.android:id/btn_checkout"
    assert btn["text"] == "Proceed to Checkout"
    assert btn["bounds"] == [100, 2000, 980, 2180]
    # Center cx = 100 + (880 // 2) = 540, cy = 2000 + (180 // 2) = 2090
    assert btn["center"] == (540, 2090)


def test_driver_execute_and_evaluate_step(mock_driver):
    nodes = mock_driver.extract_interactive_nodes()
    target = nodes[0]

    step_result = mock_driver.execute_and_evaluate_step(
        target=target,
        action_type="tap",
        session_id="test_driver_session",
    )

    assert "step_id" in step_result
    assert "Proceed to Checkout" in step_result["action"]
    assert "oracle_verdict" in step_result
    verdict = step_result["oracle_verdict"]
    assert "c4_verdict" in verdict
    assert verdict["c4_verdict"]["has_gui_defect"] is False


def test_driver_autonomous_crawl_loop(mock_driver):
    trace = mock_driver.crawl(max_steps=3, session_id="crawl_session_01")
    # Step 0 (initial) + 2 targets explored
    assert len(trace) == 3
    assert trace[0]["action"] == "initial_screen"
    assert "tap on" in trace[1]["action"]


def test_driver_compile_summary_report():
    sample_trace = [
        {
            "step_id": "step_1",
            "action": "initial_screen",
            "oracle_verdict": {
                "c4_verdict": {"has_gui_defect": False}
            },
        },
        {
            "step_id": "step_2",
            "action": "tap on Checkout Button",
            "oracle_verdict": {
                "c4_verdict": {
                    "has_gui_defect": True,
                    "defect_type": "component_overlap",
                    "regions": [{"x": 100, "y": 200, "width": 300, "height": 300, "label": "component_overlap"}],
                }
            },
        },
    ]

    report = CommonTestDriver.compile_summary_report(sample_trace)
    assert report["total_steps"] == 2
    assert report["clean_steps"] == 1
    assert report["defects_detected"] == 1
    assert report["defect_taxonomy_breakdown"] == {"component_overlap": 1}
    assert len(report["defect_findings"]) == 1
    assert report["defect_findings"][0]["defect_type"] == "component_overlap"
