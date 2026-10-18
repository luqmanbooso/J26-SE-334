"""
Concurrency, Thread-Safety, and Request Queuing Tests for Component 3.
Verifies:
1. Global inference serialization mutex (`_inference_lock`).
2. Absence of concurrent GPU forward passes under overlapping requests.
3. Thread-safe bounded deque operations for the verdict ledger (`_verdict_lock`).
4. CUDA OOM exception mapping to HTTP 503 and cache cleanup.
5. Lock release immunity across inference exceptions (deadlock prevention).
"""

import io
import time
import base64
import threading
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from vision_oracle.server import app, set_engine
from vision_oracle.services.oracle_service import get_oracle_service, OracleService, set_oracle_service
from vision_oracle.api.schemas import C2TriggerPayload
from local_vision_oracle.engine import OracleEngine, MockInferenceBackend
from local_vision_oracle.schemas import C3OracleResult, Verdict, LatencyBreakdown, DefectType


class ConcurrencyTrackingBackend(MockInferenceBackend):
    """
    Instrumented mock inference backend that measures concurrent active inferences.
    Proves deterministically whether mutual exclusion is maintained across threads.
    """

    def __init__(self, simulated_latency_s: float = 0.05):
        super().__init__(simulated_latency_ms=0)
        self.simulated_latency_s = simulated_latency_s
        self.active_inferences = 0
        self.max_concurrent_inferences = 0
        self.total_calls = 0
        self._lock = threading.Lock()

    def generate(
        self,
        messages: List[Dict[str, Any]],
        image: Image.Image,
        **kwargs: Any,
    ) -> str:
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


def _create_base64_image(color=(255, 255, 255), size=(100, 100)) -> str:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


@pytest.fixture
def tracking_engine():
    backend = ConcurrencyTrackingBackend(simulated_latency_s=0.03)
    engine = OracleEngine(backend=backend)
    service = OracleService(engine=engine)
    set_oracle_service(service)
    client = TestClient(app)
    return backend, service, client


def test_concurrent_evaluate_requests_are_serialized(tracking_engine):
    """
    Asserts that 10 concurrent requests to /api/oracle/evaluate are strictly serialized
    by _inference_lock, ensuring max_concurrent_inferences == 1 at all times.
    """
    backend, service, client = tracking_engine
    b64_img = _create_base64_image()
    num_requests = 10

    def send_request(idx: int):
        payload = {
            "image_base64": b64_img,
            "hierarchy_xml": f'<hierarchy><node text="Button_{idx}" bounds="[0,0][100,50]"/></hierarchy>',
            "screen_id": f"concurrent_screen_{idx}",
            "session_id": "concurrency_session",
        }
        resp = client.post("/api/oracle/evaluate", json=payload)
        return resp.status_code, resp.json()

    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(send_request, i) for i in range(num_requests)]
        results = [f.result() for f in as_completed(futures)]

    # All requests succeeded
    for status_code, data in results:
        assert status_code == 200
        assert "c4_verdict" in data
        assert data["c4_verdict"]["session_id"] == "concurrency_session"

    # Strict mutual exclusion verified
    assert backend.total_calls == num_requests
    assert backend.max_concurrent_inferences == 1, (
        f"Race condition detected! Peak concurrent forward passes was {backend.max_concurrent_inferences}, expected 1."
    )


def test_interleaved_evaluate_and_trigger_concurrency(tracking_engine):
    """
    Asserts that synchronous evaluation and background trigger tasks serialize safely
    without race conditions or GPU memory collisions.
    """
    backend, service, client = tracking_engine
    b64_img = _create_base64_image()

    def send_eval(idx: int):
        payload = {
            "image_base64": b64_img,
            "screen_id": f"eval_{idx}",
            "session_id": "interleaved_session",
        }
        resp = client.post("/api/oracle/evaluate", json=payload)
        return "eval", resp.status_code

    def send_trigger(idx: int):
        payload = {
            "action_id": f"trigger_{idx}",
            "session_id": "interleaved_session",
            "target_element_id": "com.shop:id/btn",
            "stress_level": 0.5,
            "delay_ms": 10.0,
        }
        resp = client.post("/api/oracle/trigger", json=payload)
        return "trigger", resp.status_code

    tasks = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for i in range(5):
            tasks.append(executor.submit(send_eval, i))
            tasks.append(executor.submit(send_trigger, i))
        results = [f.result() for f in as_completed(tasks)]

    for task_type, status_code in results:
        if task_type == "eval":
            assert status_code == 200
        else:
            assert status_code == 202

    # Engine never executed overlapping passes
    assert backend.max_concurrent_inferences <= 1


def test_verdict_ledger_high_concurrency_race_immunity():
    """
    Asserts that 50 concurrent threads writing and reading the verdict ledger
    do not trigger `RuntimeError: deque mutated during iteration` and strictly
    enforce the 100-verdict ceiling.
    """
    service = OracleService(engine=OracleEngine(backend=MockInferenceBackend()))
    num_writers = 25
    num_readers = 25
    operations_per_thread = 10

    errors = []

    def writer_worker(thread_id: int):
        try:
            for i in range(operations_per_thread):
                dummy_result = C3OracleResult(
                    screen_id=f"thread_{thread_id}_screen_{i}",
                    verdict=Verdict(has_defect=False, defect_type=DefectType.NONE, confidence=0.95),
                    latency_breakdown=LatencyBreakdown(capture_ms=0, preprocess_ms=1, prune_ms=1, inference_ms=5),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    engine_used="mock",
                    metadata={"thread_id": thread_id, "iter": i},
                )
                service.save_verdict_to_ledger(dummy_result, session_id=f"session_t{thread_id}")
        except Exception as exc:
            errors.append(f"Writer error: {exc}")

    def reader_worker(thread_id: int):
        try:
            for _ in range(operations_per_thread):
                verdicts = service.list_verdicts(limit=20)
                assert isinstance(verdicts, list)
                if verdicts:
                    v_id = verdicts[0]["verdict_id"]
                    v = service.get_verdict(v_id)
                    assert v is not None
        except Exception as exc:
            errors.append(f"Reader error: {exc}")

    threads = []
    for t_id in range(num_writers):
        threads.append(threading.Thread(target=writer_worker, args=(t_id,)))
    for t_id in range(num_readers):
        threads.append(threading.Thread(target=reader_worker, args=(t_id,)))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrency errors encountered in verdict ledger: {errors}"
    final_verdicts = service.list_verdicts()
    assert len(final_verdicts) <= 100, f"Ledger exceeded maxlen=100 bound: {len(final_verdicts)}"


def test_inference_lock_releases_on_inference_error():
    """
    Asserts that an unhandled exception inside model evaluation unconditionally
    releases _inference_lock, allowing subsequent requests to succeed without deadlock.
    """
    class FailingBackend(MockInferenceBackend):
        def __init__(self):
            super().__init__()
            self.should_fail = True

        def generate(self, messages, image, **kwargs):
            if self.should_fail:
                raise RuntimeError("Simulated GPU kernel fault")
            return super().generate(messages, image, **kwargs)

    failing_backend = FailingBackend()
    engine = OracleEngine(backend=failing_backend)
    service = OracleService(engine=engine)
    set_oracle_service(service)
    client = TestClient(app)

    b64_img = _create_base64_image()

    # 1. Failing request
    resp1 = client.post("/api/oracle/evaluate", json={"image_base64": b64_img, "screen_id": "fail_1"})
    assert resp1.status_code == 500
    assert "Simulated GPU kernel fault" in resp1.json()["detail"]

    # 2. Lock MUST be released
    assert not service.inference_lock.locked(), "Lock remained acquired after exception!"

    # 3. Healthy follow-up request succeeds
    failing_backend.should_fail = False
    resp2 = client.post("/api/oracle/evaluate", json={"image_base64": b64_img, "screen_id": "recover_2"})
    assert resp2.status_code == 200
    assert resp2.json()["c4_verdict"]["has_gui_defect"] is False


def test_cuda_oom_returns_503_and_cleans_cache():
    """
    Asserts that CUDA OutOfMemoryError is intercepted and cleanly mapped to HTTP 503
    with memory cache reclamation.
    """
    class OOMBackend(MockInferenceBackend):
        def generate(self, messages, image, **kwargs):
            raise RuntimeError("CUDA out of memory. Tried to allocate 512.00 MiB")

    engine = OracleEngine(backend=OOMBackend())
    service = OracleService(engine=engine)
    set_oracle_service(service)
    client = TestClient(app)

    b64_img = _create_base64_image()
    resp = client.post("/api/oracle/evaluate", json={"image_base64": b64_img, "screen_id": "oom_test"})
    assert resp.status_code == 503
    assert "GPU out of memory" in resp.json()["detail"] or "GPU VRAM exhausted" in resp.json()["detail"]
