"""
Validation of CUDA Memory Lifecycle and Zero VRAM Leaks across 50 Consecutive Cycles.
Hardware Budget Target: NVIDIA GeForce RTX 3050 (4GB VRAM).

Tests:
1. Environment configuration: PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
2. Tensor deallocation and CUDA cache purge across 50 consecutive cycles (zero leak assertion: Delta <= 1MB)
3. SAHI high-resolution tiling memory stability across 50 cycles
4. Graceful handling of torch.cuda.OutOfMemoryError in SAHI fallback (recovering to global verdict)
5. FastAPI route recovery returning HTTP 503 with cache cleanup on OOM
6. Optional real Qwen2-VL 4-bit CUDA benchmark (50 consecutive inference passes)
"""

import os
import gc
import io
import json
import base64
import pytest
from pathlib import Path
from PIL import Image

# Ensure allocator configuration is set before PyTorch initialization
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
import torch

from fastapi.testclient import TestClient
from vision_oracle.server import app, set_engine
from vision_oracle.services.oracle_service import get_oracle_service, OracleService, set_oracle_service
from local_vision_oracle.schemas import DefectType, Verdict, C3OracleResult
from local_vision_oracle.engine import (
    InferenceBackend,
    MockInferenceBackend,
    OracleEngine,
    TransformersInferenceBackend,
)


@pytest.fixture
def tall_mobile_screen() -> Image.Image:
    """Creates a tall mobile screen (1080x2400) that triggers all 3 SAHI vertical slices."""
    return Image.new("RGB", (1080, 2400), color=(245, 245, 245))


class CudaSimulatedInferenceBackend(InferenceBackend):
    """
    Simulates VLM CUDA inference by allocating real GPU tensors (50MB - 100MB)
    during forward pass and executing the exact deallocation and empty_cache lifecycle.
    """

    def __init__(self, tensor_size_mb: int = 50, throw_oom: bool = False):
        self.tensor_size_mb = tensor_size_mb
        self.throw_oom = throw_oom
        self.call_count = 0

    def generate(self, messages, image, **kwargs) -> str:
        self.call_count += 1
        if self.throw_oom:
            if hasattr(torch.cuda, "OutOfMemoryError"):
                raise torch.cuda.OutOfMemoryError("Simulated CUDA OOM on 4GB budget.")
            raise RuntimeError("CUDA out of memory. Tried to allocate 512.00 MiB")

        inputs = None
        generated_ids = None
        trimmed_ids = None

        try:
            if torch.cuda.is_available():
                # Allocate real CUDA memory representing visual tokens & activations
                num_floats = (self.tensor_size_mb * 1024 * 1024) // 4
                inputs = {
                    "input_ids": torch.zeros((1, 512), dtype=torch.long, device="cuda"),
                    "pixel_values": torch.randn((1, num_floats // 2), dtype=torch.float32, device="cuda"),
                }
                with torch.inference_mode():
                    generated_ids = torch.zeros((1, 64), dtype=torch.long, device="cuda")
                trimmed_ids = [generated_ids[0][10:]]

            return json.dumps({
                "has_defect": False,
                "defect_type": "none",
                "confidence": 0.99,
                "bounding_box": None,
                "affected_element_id": None,
                "explanation": "Simulated nominal UI without defects.",
            })
        finally:
            if inputs is not None:
                for k in list(inputs.keys()):
                    del inputs[k]
                del inputs
            if generated_ids is not None:
                del generated_ids
            if trimmed_ids is not None:
                del trimmed_ids
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()


def test_pytorch_cuda_alloc_conf_configured():
    """Verify that PYTORCH_CUDA_ALLOC_CONF is configured with expandable_segments:True."""
    alloc_conf = os.environ.get("PYTORCH_CUDA_ALLOC_CONF", "")
    assert "expandable_segments:True" in alloc_conf, (
        f"Expected 'expandable_segments:True' in PYTORCH_CUDA_ALLOC_CONF, got: {alloc_conf}"
    )


def test_cuda_memory_lifecycle_50_cycles(tall_mobile_screen):
    """
    Executes 50 consecutive evaluation cycles with CUDA allocations and SAHI dynamic slicing.
    Asserts that VRAM allocation remains strictly stable (Delta <= 1MB).
    """
    if not torch.cuda.is_available():
        pytest.skip("CUDA is not available on this environment.")

    torch.cuda.empty_cache()
    gc.collect()

    backend = CudaSimulatedInferenceBackend(tensor_size_mb=40)
    # Make backend simulate TransformersInferenceBackend so SAHI dynamic slicing runs
    backend.__class__ = type("SimulatedTransformersBackend", (CudaSimulatedInferenceBackend, TransformersInferenceBackend), {})
    engine = OracleEngine(backend=backend)

    allocated_records = []
    reserved_records = []

    for cycle in range(50):
        result = engine.evaluate(
            image_input=tall_mobile_screen,
            screen_id=f"cycle_{cycle:03d}",
            enable_sahi=True,
        )
        assert result.verdict.has_defect is False

        allocated_mb = torch.cuda.memory_allocated() / (1024 ** 2)
        reserved_mb = torch.cuda.memory_reserved() / (1024 ** 2)
        allocated_records.append(allocated_mb)
        reserved_records.append(reserved_mb)

    # Evaluate stability: compare cycle 5 (post-warmup) with cycle 49
    delta_allocated = abs(allocated_records[-1] - allocated_records[5])
    assert delta_allocated <= 1.0, (
        f"VRAM leak detected! Allocated memory grew by {delta_allocated:.3f} MB across cycles. "
        f"Cycle 5: {allocated_records[5]} MB, Cycle 50: {allocated_records[-1]} MB"
    )
    # Total calls should be 50 cycles * (1 global + 3 slices) = 200 passes
    assert backend.call_count == 200


def test_sahi_oom_graceful_recovery_to_global_verdict(tall_mobile_screen):
    """
    Verifies that if a CUDA OutOfMemoryError occurs during a SAHI slice pass,
    the engine purges VRAM, sets sahi_oom_recovered=True, and falls back to the global verdict.
    """
    class SahiOomBackend(InferenceBackend):
        def __init__(self):
            self.pass_num = 0

        def generate(self, messages, image, **kwargs) -> str:
            self.pass_num += 1
            # Pass 1 is global (succeeds), subsequent passes are SAHI slices (throw OOM)
            if self.pass_num == 1:
                return json.dumps({
                    "has_defect": False,
                    "defect_type": "none",
                    "confidence": 0.95,
                    "bounding_box": None,
                    "affected_element_id": None,
                    "explanation": "Global pass detected nominal UI.",
                })
            if hasattr(torch.cuda, "OutOfMemoryError"):
                raise torch.cuda.OutOfMemoryError("CUDA OOM on SAHI slice pass.")
            raise RuntimeError("CUDA out of memory on SAHI slice pass.")

    backend = SahiOomBackend()
    backend.__class__ = type("OomTransformersBackend", (SahiOomBackend, TransformersInferenceBackend), {})
    engine = OracleEngine(backend=backend)

    result = engine.evaluate(
        image_input=tall_mobile_screen,
        screen_id="test_sahi_oom_recovery",
        enable_sahi=True,
    )

    assert result.verdict.has_defect is False
    assert result.metadata.get("sahi_oom_recovered") is True


def test_api_evaluate_oom_returns_503_and_recovers():
    """
    Verifies that when a CUDA OOM occurs during global evaluation, the FastAPI route:
    1. Returns HTTP 503 instead of crashing with HTTP 500
    2. Clears the VRAM cache
    3. Allows subsequent requests to succeed
    """
    client = TestClient(app)

    # 1. Inject failing engine that raises OOM
    oom_backend = CudaSimulatedInferenceBackend(throw_oom=True)
    engine = OracleEngine(backend=oom_backend)
    service = OracleService(engine=engine)
    set_oracle_service(service)

    img = Image.new("RGB", (360, 640), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    payload = {"image_base64": b64, "screen_id": "oom_screen"}
    response = client.post("/api/oracle/evaluate", json=payload)

    assert response.status_code == 503
    assert "GPU VRAM exhausted" in response.json()["detail"] or "GPU out of memory" in response.json()["detail"]

    # 2. Inject healthy engine and verify recovery
    healthy_backend = MockInferenceBackend()
    service.set_engine(OracleEngine(backend=healthy_backend))

    recovered_response = client.post("/api/oracle/evaluate", json=payload)
    assert recovered_response.status_code == 200
    assert recovered_response.json()["oracle_result"]["verdict"]["has_defect"] is False


def test_api_sequence_oom_returns_503():
    """Verifies that sequence evaluation catches OOM and returns HTTP 503."""
    client = TestClient(app)
    oom_backend = CudaSimulatedInferenceBackend(throw_oom=True)
    engine = OracleEngine(backend=oom_backend)
    service = OracleService(engine=engine)
    set_oracle_service(service)

    img1 = Image.new("RGB", (360, 640), color=(255, 255, 255))
    buf1 = io.BytesIO()
    img1.save(buf1, format="PNG")
    b64_1 = base64.b64encode(buf1.getvalue()).decode("utf-8")

    img2 = Image.new("RGB", (360, 640), color=(0, 0, 0))
    buf2 = io.BytesIO()
    img2.save(buf2, format="PNG")
    b64_2 = base64.b64encode(buf2.getvalue()).decode("utf-8")

    payload = {
        "image_base64_list": [b64_1, b64_2],
        "time_delta_s": 2.0,
        "action_dispatched": True,
    }
    response = client.post("/api/oracle/sequence", json=payload)
    assert response.status_code == 503
    assert "GPU VRAM exhausted" in response.json()["detail"] or "GPU out of memory" in response.json()["detail"]


@pytest.mark.skipif(
    not torch.cuda.is_available() or not Path("D:/university/Resesarch/RD/models/Qwen2-VL-2B-Instruct").exists(),
    reason="Requires physical NVIDIA GPU and local Qwen2-VL-2B model weights",
)
def test_real_qwen2_vl_vram_50_cycles_benchmark(tall_mobile_screen):
    """
    Physical hardware validation on NVIDIA RTX 3050 (4GB):
    Loads real 4-bit quantized Qwen2-VL-2B-Instruct with LoRA adapter and executes
    50 consecutive evaluation passes, recording real VRAM telemetry.
    """
    from vision_oracle.services.oracle_service import create_default_engine

    engine = create_default_engine()
    telemetry = []

    for i in range(50):
        res = engine.evaluate(
            image_input=tall_mobile_screen,
            screen_id=f"real_qwen_cycle_{i:02d}",
            enable_sahi=False,  # Single pass per cycle for fast execution
        )
        alloc_mb = torch.cuda.memory_allocated() / (1024 ** 2)
        telemetry.append(alloc_mb)

    delta = abs(telemetry[-1] - telemetry[2])
    assert delta <= 5.0, f"Memory drifted by {delta:.2f} MB across 50 real inference cycles!"
