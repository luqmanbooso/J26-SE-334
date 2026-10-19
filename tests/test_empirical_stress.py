"""
Adversarial Stress Test Suite for Milestone 1: Concurrency & ADB Resilience.
Author: Challenger Agent (challenger_c3_m1_1)
Target: J26-SE-334 Vision Oracle & Common Execution Layer.

Empirically challenges:
1. Lock inversion / Deadlock between DeviceLock and _inference_lock.
2. Truncated mid-stream PNG capture (partial USB packet drops).
3. Massive multi-endpoint concurrency burst (evaluate, evaluate_device, sequence, trigger).
4. GPU Mutual Exclusion invariance under chaotic thread scheduling.
5. In-flight ADB disconnection resilience without mutex poisoning.
"""

import io
import time
import base64
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from common.adb import AdbDevice, DeviceLock, NoDeviceError
from vision_oracle.server import app
from vision_oracle.services.oracle_service import OracleService, set_oracle_service
from vision_oracle.services.trigger_queue import process_c2_trigger_task
from local_vision_oracle.engine import OracleEngine, MockInferenceBackend
from local_vision_oracle.schemas import C3OracleResult, Verdict, LatencyBreakdown, DefectType


class StressTrackingBackend(MockInferenceBackend):
    """Measures exact concurrent GPU inference activations and total invocations."""
    def __init__(self, simulated_latency_s: float = 0.04):
        super().__init__(simulated_latency_ms=0)
        self.simulated_latency_s = simulated_latency_s
        self.active_inferences = 0
        self.max_concurrent_inferences = 0
        self.total_calls = 0
        self._lock = threading.Lock()

    def generate(self, messages: List[Dict[str, Any]], image: Image.Image, **kwargs: Any) -> str:
        with self._lock:
            self.active_inferences += 1
            if self.active_inferences > self.max_concurrent_inferences:
                self.max_concurrent_inferences = self.active_inferences
            self.total_calls += 1

        try:
            if self.simulated_latency_s > 0:
                time.sleep(self.simulated_latency_s)
            return super().generate(messages, image, **kwargs)
        finally:
            with self._lock:
                self.active_inferences -= 1


def _create_test_png_bytes(size=(100, 100), color=(100, 150, 200)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_base64_img(size=(100, 100)) -> str:
    return base64.b64encode(_create_test_png_bytes(size)).decode("utf-8")


@pytest.fixture
def stress_client():
    backend = StressTrackingBackend(simulated_latency_s=0.03)
    engine = OracleEngine(backend=backend)
    service = OracleService(engine=engine)
    set_oracle_service(service)
    client = TestClient(app)
    return backend, service, client


# ============================================================================
# Challenge 1: Truncated PNG / Mid-Flight Stream Disconnection
# ============================================================================

def test_screencap_truncated_png_detection(monkeypatch):
    """
    Challenge: A device drops USB mid-screencap after transmitting the PNG header.
    PIL Image.open is lazy and does not read pixels.
    If screencap does not verify/load the image, corrupted handles propagate to
    engine.evaluate() and trigger unhandled HTTP 500 instead of HTTP 503.
    """
    valid_png = _create_test_png_bytes(size=(50, 50))
    # Truncate halfway through IDAT
    truncated_png = valid_png[: len(valid_png) // 2]

    dev = AdbDevice(serial="flaky-phone", verify=False)
    monkeypatch.setattr(dev, "run_bytes", lambda *a, **k: truncated_png)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    # Calling screencap(as_pil=True) must detect truncation and raise NoDeviceError
    try:
        img = dev.screencap(as_pil=True, max_retries=1, backoff_s=0.01)
        # If screencap returned an unloaded image, verify whether loading fails:
        img.load()
        pytest.fail("Expected NoDeviceError or truncation failure on partial PNG stream!")
    except NoDeviceError:
        pass  # Properly handled
    except OSError as err:
        pytest.fail(f"VULNERABILITY: screencap allowed truncated image to escape as {type(err).__name__}: {err}")


def test_route_evaluate_device_truncated_png_fails_with_500_instead_of_503(stress_client, monkeypatch):
    """
    Empirical proof of API failure: When screencap returns truncated PNG bytes,
    evaluate_device crashes downstream in OracleEngine with OSError,
    which is not caught by NoDeviceError handler, leaking an HTTP 500 internal server error.
    """
    backend, service, client = stress_client
    valid_png = _create_test_png_bytes(size=(50, 50))
    truncated_png = valid_png[: len(valid_png) // 2]

    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": ["flaky-phone"]))
    monkeypatch.setattr(AdbDevice, "run_bytes", lambda *a, **k: truncated_png)
    monkeypatch.setattr(
        AdbDevice,
        "dump_hierarchy",
        lambda *a, **k: '<hierarchy><node bounds="[0,0][100,50]"/></hierarchy>',
    )
    monkeypatch.setattr(
        AdbDevice,
        "get_display_metrics",
        lambda *a, **k: {"width": 1080, "height": 2400, "density": 420},
    )
    monkeypatch.setattr(time, "sleep", lambda s: None)

    resp = client.post("/api/oracle/evaluate_device?serial=flaky-phone")
    # If the bug exists, resp.status_code is 500, but the spec and Objective #2 demand HTTP 503!
    assert resp.status_code == 503, f"Expected HTTP 503 for disconnected/truncated device screencap, got HTTP {resp.status_code}: {resp.json()}"



# ============================================================================
# Challenge 2: Massive Multi-Endpoint Concurrency Stress Test
# ============================================================================

def test_massive_multi_endpoint_concurrency_burst(stress_client, monkeypatch):
    """
    Challenge: 30 concurrent overlapping requests across /evaluate, /evaluate_device,
    /sequence, and /trigger.
    Proves whether GPU forward passes strictly maintain mutual exclusion (max_concurrent == 1),
    verdict ledger maintains data integrity, and no deadlocks occur.
    """
    backend, service, client = stress_client
    valid_png = _create_test_png_bytes()
    b64_img = base64.b64encode(valid_png).decode("utf-8")

    # Mock ADB operations for evaluate_device
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": ["stress-phone"]))
    monkeypatch.setattr(AdbDevice, "run_bytes", lambda *a, **k: valid_png)
    monkeypatch.setattr(
        AdbDevice,
        "dump_hierarchy",
        lambda *a, **k: '<hierarchy><node class="android.widget.Button" text="Stress" bounds="[0,0][100,50]"/></hierarchy>',
    )
    monkeypatch.setattr(
        AdbDevice,
        "get_display_metrics",
        lambda *a, **k: {"width": 1080, "height": 2400, "density": 420},
    )

    results = []
    lock = threading.Lock()

    def call_evaluate(i: int):
        resp = client.post("/api/oracle/evaluate", json={
            "image_base64": b64_img,
            "screen_id": f"eval_{i}",
            "session_id": "burst_session",
        })
        with lock:
            results.append(("evaluate", resp.status_code, resp.json()))

    def call_evaluate_device(i: int):
        resp = client.post("/api/oracle/evaluate_device?serial=stress-phone")
        with lock:
            results.append(("evaluate_device", resp.status_code, resp.json()))

    def call_sequence(i: int):
        resp = client.post("/api/oracle/sequence", json={
            "image_base64_list": [b64_img, b64_img],
            "time_delta_s": 1.0,
            "session_id": "burst_session",
        })
        with lock:
            results.append(("sequence", resp.status_code, resp.json()))

    def call_trigger(i: int):
        resp = client.post("/api/oracle/trigger", json={
            "action_id": f"trigger_{i}",
            "session_id": "burst_session",
            "device_serial": "stress-phone",
        })
        with lock:
            results.append(("trigger", resp.status_code, resp.json()))

    threads = []
    # 8 evaluate, 8 evaluate_device, 6 sequence, 8 trigger = 30 tasks
    for i in range(8):
        threads.append(threading.Thread(target=call_evaluate, args=(i,)))
        threads.append(threading.Thread(target=call_evaluate_device, args=(i,)))
    for i in range(6):
        threads.append(threading.Thread(target=call_sequence, args=(i,)))
    for i in range(8):
        threads.append(threading.Thread(target=call_trigger, args=(i,)))

    start_time = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30.0)

    elapsed = time.time() - start_time

    # Assert no deadlocks
    for t in threads:
        assert not t.is_alive(), "Deadlock detected! Thread failed to join within 30s."

    # Assert all responses are successful
    assert len(results) == 30, f"Expected 30 results, got {len(results)}"
    for endpoint, status, body in results:
        if endpoint == "trigger":
            assert status == 202, f"Trigger failed with {status}: {body}"
        else:
            assert status == 200, f"{endpoint} failed with {status}: {body}"

    # Strict GPU mutual exclusion
    assert backend.max_concurrent_inferences == 1, (
        f"Concurrency violation! Peak concurrent inferences was {backend.max_concurrent_inferences}, expected 1."
    )

    # Verdict ledger consistency
    verdicts = service.list_verdicts()
    assert len(verdicts) <= 100
    assert len(verdicts) >= 22  # At least the 22 synchronous evaluations recorded


# ============================================================================
# Challenge 3: In-Flight ADB Drop Does Not Poison Inference Mutex
# ============================================================================

def test_adb_drop_mid_flight_does_not_poison_service_mutex(stress_client, monkeypatch):
    """
    Challenge: If an evaluate_device request crashes due to sudden device disconnection,
    verify that:
    1. It returns HTTP 503 (not 500).
    2. The service inference mutex is immediately freed.
    3. Subsequent /evaluate requests proceed smoothly without blocking.
    """
    backend, service, client = stress_client
    b64_img = _create_base64_img()

    # Device drops
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": ["vanished-device"]))
    monkeypatch.setattr(AdbDevice, "run_bytes", lambda *a, **k: b"")
    monkeypatch.setattr(time, "sleep", lambda s: None)

    # 1. Failing device request
    resp1 = client.post("/api/oracle/evaluate_device?serial=vanished-device")
    assert resp1.status_code == 503
    assert resp1.json()["detail"]["error"] == "device_unavailable"

    # 2. Verify mutex is not locked
    assert not service.inference_lock.locked(), "Inference lock was left locked after ADB drop!"

    # 3. Healthy follow-up evaluate request
    resp2 = client.post("/api/oracle/evaluate", json={
        "image_base64": b64_img,
        "screen_id": "healthy_after_drop",
    })
    assert resp2.status_code == 200
    assert "c4_verdict" in resp2.json()


# ============================================================================
# Challenge 4: DeviceLock and Inference Lock Ordering (Deadlock Safety)
# ============================================================================

def test_devicelock_and_inferencelock_deadlock_freedom(stress_client, monkeypatch):
    """
    Challenge: An external crawler / runner holds DeviceLock(serial) while calling /evaluate.
    Simultaneously, evaluate_device(serial) is called.
    Verifies that device operations and inference locks do not form an ABBA deadlock.
    """
    backend, service, client = stress_client
    valid_png = _create_test_png_bytes()
    b64_img = base64.b64encode(valid_png).decode("utf-8")

    serial = "shared-test-device"
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": [serial]))
    monkeypatch.setattr(AdbDevice, "run_bytes", lambda *a, **k: valid_png)
    monkeypatch.setattr(
        AdbDevice,
        "dump_hierarchy",
        lambda *a, **k: '<hierarchy><node text="Safe" bounds="[0,0][100,50]"/></hierarchy>',
    )
    monkeypatch.setattr(
        AdbDevice,
        "get_display_metrics",
        lambda *a, **k: {"width": 1080, "height": 2400, "density": 420},
    )

    stage = "init"
    deadlock_detected = False

    def external_runner():
        nonlocal stage
        # Simulate crawler acquiring DeviceLock with short timeout
        with DeviceLock(serial, timeout=3.0):
            stage = "runner_has_device_lock"
            time.sleep(0.1)  # Allow other thread to attempt evaluate_device
            # External runner calls evaluate with screenshot
            resp = client.post("/api/oracle/evaluate", json={"image_base64": b64_img, "screen_id": "crawler_screen"})
            assert resp.status_code == 200

    def background_device_eval():
        # Waits until runner has device lock
        deadline = time.time() + 2.0
        while stage != "runner_has_device_lock" and time.time() < deadline:
            time.sleep(0.01)

        # Now calls evaluate_device with device having short lock timeout
        dev = AdbDevice(serial=serial, lock_timeout=2.0, verify=False)
        try:
            service.evaluate_device(device=dev)
        except TimeoutError:
            # If evaluate_device timed out waiting for DeviceLock, that's expected serialization
            pass

    t1 = threading.Thread(target=external_runner)
    t2 = threading.Thread(target=background_device_eval)

    t1.start()
    t2.start()

    t1.join(timeout=10.0)
    t2.join(timeout=10.0)

    assert not t1.is_alive(), "Thread 1 deadlocked!"
    assert not t2.is_alive(), "Thread 2 deadlocked!"
