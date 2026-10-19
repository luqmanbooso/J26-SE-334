"""
Fault injection and resilience test suite for Android Debug Bridge (ADB).
Verifies:
1. Screencap and Dump Hierarchy disconnection error normalization (NoDeviceError).
2. Transient disconnection retry with exponential backoff before declaring device lost.
3. Strict multi-device arbitration (resolve_serial).
4. FastAPI route mapping to HTTP 503 (Service Unavailable) with structured diagnostic JSON.
"""

import io
import time
import subprocess
from unittest.mock import patch, MagicMock
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from common.adb import AdbDevice, NoDeviceError
from vision_oracle.server import app, set_engine
from vision_oracle.services.oracle_service import OracleService, set_oracle_service
from local_vision_oracle.engine import OracleEngine, MockInferenceBackend


@pytest.fixture
def mock_oracle_client():
    engine = OracleEngine(backend=MockInferenceBackend())
    service = OracleService(engine=engine)
    set_oracle_service(service)
    set_engine(engine)
    return TestClient(app)


def _generate_valid_png_bytes(size=(10, 10), color="blue") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


# ============================================================================
# Unit Tests: Screencap Resilience & Exponential Backoff
# ============================================================================

def test_screencap_zero_bytes_exhausts_retries_and_raises_nodeviceerror(monkeypatch):
    """When screencap continuously returns 0 bytes, verify 2 retries with backoff then NoDeviceError."""
    d = AdbDevice(serial="test-phone", verify=False)
    call_count = 0
    sleeps = []

    def mock_run_bytes(*args, **kw):
        nonlocal call_count
        call_count += 1
        return b""

    monkeypatch.setattr(d, "run_bytes", mock_run_bytes)
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

    with pytest.raises(NoDeviceError, match="returned 0 bytes from device 'test-phone'"):
        d.screencap(as_pil=False, max_retries=2, backoff_s=0.2)

    assert call_count == 3  # Initial attempt + 2 retries
    assert sleeps == [0.2, 0.4]  # Exponential backoff: 0.2 * (2**0), 0.2 * (2**1)


def test_screencap_transient_disconnect_recovers_on_retry(monkeypatch):
    """When screencap drops initially (0 bytes) but returns valid PNG on 2nd attempt, recover cleanly."""
    d = AdbDevice(serial="test-phone", verify=False)
    valid_bytes = _generate_valid_png_bytes()
    streams = [b"", valid_bytes]
    sleeps = []

    def mock_run_bytes(*args, **kw):
        return streams.pop(0) if streams else valid_bytes

    monkeypatch.setattr(d, "run_bytes", mock_run_bytes)
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

    img = d.screencap(as_pil=True, max_retries=2, backoff_s=0.2)
    assert isinstance(img, Image.Image)
    assert img.size == (10, 10)
    assert len(sleeps) == 1
    assert sleeps[0] == 0.2


def test_screencap_corrupted_header_raises_nodeviceerror(monkeypatch):
    """Corrupted/offline ASCII stream from ADB raises NoDeviceError instead of generic RuntimeError."""
    d = AdbDevice(serial="test-phone", verify=False)
    monkeypatch.setattr(d, "run_bytes", lambda *args, **kw: b"error: device offline\n")
    monkeypatch.setattr(time, "sleep", lambda s: None)

    with pytest.raises(NoDeviceError, match="Failed to decode valid PNG signature"):
        d.screencap(as_pil=False, max_retries=1, backoff_s=0.01)


# ============================================================================
# Unit Tests: Dump Hierarchy Resilience & Exponential Backoff
# ============================================================================

def test_dump_hierarchy_empty_output_retries_and_raises_nodeviceerror(monkeypatch):
    """When dump output lacks <hierarchy>, verify retries with backoff then NoDeviceError."""
    d = AdbDevice(serial="test-phone", verify=False)
    calls = 0
    sleeps = []

    def fake_subprocess_run(argv, **kw):
        nonlocal calls
        if "cat" in argv:
            calls += 1
            return subprocess.CompletedProcess(argv, 0, stdout="junk string without tags", stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

    with pytest.raises(NoDeviceError, match="no <hierarchy> element"):
        d.dump_hierarchy(max_age_s=0.0, max_retries=2, backoff_s=0.2)

    assert calls == 3
    assert sleeps == [0.2, 0.4]


def test_dump_hierarchy_transient_failure_recovers_on_retry(monkeypatch):
    """Transient missing hierarchy recovers when device returns valid XML on subsequent retry."""
    d = AdbDevice(serial="test-phone", verify=False)
    valid_xml = '<hierarchy><node bounds="[0,0][1080,2400]"/></hierarchy>'
    responses = ["", valid_xml]
    sleeps = []

    def fake_subprocess_run(argv, **kw):
        if "cat" in argv:
            out = responses.pop(0) if responses else valid_xml
            return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

    res = d.dump_hierarchy(max_age_s=0.0, max_retries=2, backoff_s=0.2)
    assert "<hierarchy>" in res
    assert len(sleeps) == 1
    assert sleeps[0] == 0.2


# ============================================================================
# Unit Tests: Multi-Device Arbitration & Liveness
# ============================================================================

def test_multi_device_arbitration_resolution(monkeypatch):
    """Consistent arbitration across 0 devices, 1 device, and multiple devices."""
    # 0 devices
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": []))
    with pytest.raises(NoDeviceError, match="no Android device"):
        AdbDevice.resolve_serial()

    # 1 device auto-resolved
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": ["emulator-5554"]))
    assert AdbDevice.resolve_serial() == "emulator-5554"
    assert AdbDevice.resolve_serial("emulator-5554") == "emulator-5554"

    # Multiple devices without serial raises
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": ["dev1", "dev2"]))
    with pytest.raises(NoDeviceError, match="pass serial="):
        AdbDevice.resolve_serial()

    # Multiple devices with explicit serial succeeds
    assert AdbDevice.resolve_serial("dev2") == "dev2"

    # Multiple devices with unknown serial raises
    with pytest.raises(NoDeviceError, match="not attached"):
        AdbDevice.resolve_serial("dev99")


def test_adb_device_is_connected_helper(monkeypatch):
    """is_connected() accurately checks device readiness without raising."""
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": ["emulator-5554"]))
    dev = AdbDevice(serial="emulator-5554", verify=False)
    assert dev.is_connected() is True

    dev_missing = AdbDevice(serial="emulator-9999", verify=False)
    assert dev_missing.is_connected() is False


# ============================================================================
# Integration Tests: FastAPI Endpoints Mapping to HTTP 503
# ============================================================================

def test_route_evaluate_device_no_device_returns_503(mock_oracle_client, monkeypatch):
    """Calling POST /api/oracle/evaluate_device with no attached device returns HTTP 503."""
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": []))

    response = mock_oracle_client.post("/api/oracle/evaluate_device")
    assert response.status_code == 503
    data = response.json()
    assert "detail" in data
    assert data["detail"]["error"] == "device_unavailable"
    assert "resolution" in data["detail"]


def test_route_evaluate_device_screencap_drop_returns_503(mock_oracle_client, monkeypatch):
    """Mid-evaluation screencap drop maps cleanly to HTTP 503 with descriptive JSON."""
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": ["emulator-5554"]))
    monkeypatch.setattr(AdbDevice, "run_bytes", lambda *args, **kw: b"")
    monkeypatch.setattr(time, "sleep", lambda s: None)

    response = mock_oracle_client.post("/api/oracle/evaluate_device")
    assert response.status_code == 503
    data = response.json()
    assert data["detail"]["error"] == "device_unavailable"
    assert "screencap returned 0 bytes" in data["detail"]["message"]


def test_route_evaluate_device_dump_drop_returns_503(mock_oracle_client, monkeypatch):
    """Mid-evaluation hierarchy drop maps cleanly to HTTP 503 with descriptive JSON."""
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": ["emulator-5554"]))
    valid_png = _generate_valid_png_bytes()
    monkeypatch.setattr(AdbDevice, "run_bytes", lambda *args, **kw: valid_png)

    def fake_subprocess_run(argv, **kw):
        return subprocess.CompletedProcess(argv, 0, stdout="corrupted cat without hierarchy", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    response = mock_oracle_client.post("/api/oracle/evaluate_device")
    assert response.status_code == 503
    data = response.json()
    assert data["detail"]["error"] == "device_unavailable"
    assert "no <hierarchy> element" in data["detail"]["message"]


def test_route_evaluate_device_multi_device_ambiguity_returns_503(mock_oracle_client, monkeypatch):
    """Ambiguous multi-device state without serial parameter returns HTTP 503."""
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": ["dev1", "dev2"]))

    response = mock_oracle_client.post("/api/oracle/evaluate_device")
    assert response.status_code == 503
    data = response.json()
    assert data["detail"]["error"] == "device_unavailable"
    assert "pass serial=" in data["detail"]["message"]


def test_route_evaluate_device_transient_drop_recovers_to_200(mock_oracle_client, monkeypatch):
    """Transient drop on 1st screencap attempt automatically recovers on retry to return HTTP 200."""
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": ["emulator-5554"]))
    valid_png = _generate_valid_png_bytes()
    streams = [b"", valid_png]

    monkeypatch.setattr(AdbDevice, "run_bytes", lambda *a, **k: streams.pop(0) if streams else valid_png)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    valid_xml = '<hierarchy><node class="android.widget.TextView" text="Home" bounds="[0,0][100,50]"/></hierarchy>'

    def fake_subprocess_run(argv, **kw):
        if "cat" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout=valid_xml, stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)

    response = mock_oracle_client.post("/api/oracle/evaluate_device")
    assert response.status_code == 200
    data = response.json()
    assert "oracle_result" in data
    assert "c4_verdict" in data
    assert data["c4_verdict"]["schema_version"] == "1.0.0"
