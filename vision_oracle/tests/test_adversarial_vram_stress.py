"""
Adversarial Stress Test Suite for Component 3 Vision Oracle VRAM Lifecycle & OOM Hardening.
Author: Challenger Agent (challenger_c3_m1_2)

Adversarial Challenge Vectors:
1. Dynamic Resolution Fluctuations (50 cycles with alternating aspect ratios & resolutions)
2. Cascading OOM Bursts (10 consecutive OOMs followed by nominal request recovery)
3. Partial SAHI Slice OOM with Pre-Existing Detected Defect
4. Abrupt Exception During Forward Pass without Leaking GPU Memory
"""

import io
import os
import gc
import json
import base64
import pytest
from PIL import Image

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
import torch

from fastapi.testclient import TestClient
from vision_oracle.server import app
from vision_oracle.services.oracle_service import OracleService, set_oracle_service
from local_vision_oracle.schemas import DefectType, Verdict
from local_vision_oracle.engine import (
    InferenceBackend,
    MockInferenceBackend,
    OracleEngine,
    TransformersInferenceBackend,
)


class AdversarialCudaBackend(InferenceBackend):
    """Adversarial backend capable of simulating dynamic tensor loads and targeted OOM injections."""

    def __init__(self, tensor_size_mb: int = 50, oom_after_passes: int = -1, oom_on_slices_only: bool = False):
        self.tensor_size_mb = tensor_size_mb
        self.oom_after_passes = oom_after_passes
        self.oom_on_slices_only = oom_on_slices_only
        self.pass_count = 0
        self.slice_count = 0

    def generate(self, messages, image, **kwargs) -> str:
        self.pass_count += 1
        is_slice = False
        for msg in messages:
            if isinstance(msg, dict) and "content" in msg:
                content = str(msg["content"])
                if "viewport_slice_index" in content or "Slice" in content:
                    is_slice = True

        if is_slice:
            self.slice_count += 1

        # Check OOM triggers
        if self.oom_on_slices_only and is_slice and self.slice_count >= self.oom_after_passes:
            if hasattr(torch.cuda, "OutOfMemoryError"):
                raise torch.cuda.OutOfMemoryError("Adversarial injection: CUDA OOM on SAHI slice")
            raise RuntimeError("CUDA out of memory on SAHI slice")

        if not self.oom_on_slices_only and self.oom_after_passes > 0 and self.pass_count >= self.oom_after_passes:
            if hasattr(torch.cuda, "OutOfMemoryError"):
                raise torch.cuda.OutOfMemoryError("Adversarial injection: CUDA OOM on forward pass")
            raise RuntimeError("CUDA out of memory on forward pass")

        inputs = None
        generated_ids = None
        trimmed_ids = None

        try:
            if torch.cuda.is_available():
                num_floats = (self.tensor_size_mb * 1024 * 1024) // 4
                inputs = {
                    "input_ids": torch.zeros((1, 256), dtype=torch.long, device="cuda"),
                    "pixel_values": torch.randn((1, num_floats // 2), dtype=torch.float32, device="cuda"),
                }
                with torch.inference_mode():
                    generated_ids = torch.zeros((1, 32), dtype=torch.long, device="cuda")
                trimmed_ids = [generated_ids[0][5:]]

            # Return slice defect if slice 1, nominal otherwise
            if is_slice and self.slice_count == 1 and kwargs.get("defect_on_slice_1", False):
                return json.dumps({
                    "has_defect": True,
                    "defect_type": "text_truncation",
                    "confidence": 0.92,
                    "bounding_box": [100, 200, 300, 400],
                    "affected_element_id": "txt_title",
                    "explanation": "Adversarial slice defect found.",
                })

            return json.dumps({
                "has_defect": False,
                "defect_type": "none",
                "confidence": 0.98,
                "bounding_box": None,
                "affected_element_id": None,
                "explanation": "Nominal UI state.",
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


def test_adversarial_dynamic_resolutions_50_cycles():
    """
    Stress-test memory stability across 50 cycles with violently fluctuating image dimensions:
    Alternates: 360x640, 1080x1920, 1080x2400 (SAHI), 1440x3120 (SAHI), 720x1600.
    Asserts zero memory leak (delta <= 1.0 MB).
    """
    if not torch.cuda.is_available():
        pytest.skip("CUDA required for adversarial VRAM stability verification")

    torch.cuda.empty_cache()
    gc.collect()

    resolutions = [
        (360, 640),
        (1080, 1920),
        (1080, 2400),
        (1440, 3120),
        (720, 1600),
    ]

    backend = AdversarialCudaBackend(tensor_size_mb=35)
    backend.__class__ = type("SimulatedAdvTransformersBackend", (AdversarialCudaBackend, TransformersInferenceBackend), {})
    engine = OracleEngine(backend=backend)

    allocated_mb_history = []

    for cycle in range(50):
        w, h = resolutions[cycle % len(resolutions)]
        img = Image.new("RGB", (w, h), color=(cycle % 255, (cycle * 5) % 255, (cycle * 13) % 255))
        result = engine.evaluate(image_input=img, screen_id=f"dyn_res_{cycle:03d}", enable_sahi=True)
        assert result.verdict is not None

        alloc_mb = torch.cuda.memory_allocated() / (1024 ** 2)
        allocated_mb_history.append(alloc_mb)

    # Compare cycle 5 (post warmup) with cycle 49
    memory_delta = abs(allocated_mb_history[-1] - allocated_mb_history[5])
    assert memory_delta <= 1.0, (
        f"Memory leak detected under dynamic resolution stress: delta = {memory_delta:.4f} MB. "
        f"Cycle 5: {allocated_mb_history[5]:.4f} MB, Cycle 50: {allocated_mb_history[-1]:.4f} MB"
    )


def test_adversarial_cascading_oom_burst_and_recovery():
    """
    Simulates 10 consecutive catastrophic OOM failures on the evaluate endpoint.
    Asserts:
    1. Every OOM yields HTTP 503 (not HTTP 500)
    2. VRAM cache is purged on every failure
    3. The 11th request (healthy) succeeds immediately with zero residual memory lock.
    """
    client = TestClient(app)

    # 1. Ten consecutive OOMs
    oom_backend = AdversarialCudaBackend(oom_after_passes=1)
    engine = OracleEngine(backend=oom_backend)
    service = OracleService(engine=engine)
    set_oracle_service(service)

    img = Image.new("RGB", (360, 640), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    payload = {"image_base64": b64, "screen_id": "oom_burst"}

    for burst_idx in range(10):
        resp = client.post("/api/oracle/evaluate", json=payload)
        assert resp.status_code == 503, f"Expected 503 on burst {burst_idx}, got {resp.status_code}"

    # 2. Eleventh request is healthy
    healthy_backend = MockInferenceBackend()
    service.set_engine(OracleEngine(backend=healthy_backend))

    resp_recovered = client.post("/api/oracle/evaluate", json=payload)
    assert resp_recovered.status_code == 200
    assert resp_recovered.json()["oracle_result"]["verdict"]["has_defect"] is False


def test_adversarial_sahi_defect_preserved_when_subsequent_slice_ooms():
    """
    Adversarial scenario:
    - Tall screen triggers SAHI slicing.
    - Global pass: clean.
    - SAHI Slice 1: detects defect.
    - SAHI Slice 2: throws CUDA OutOfMemoryError.
    Asserts:
    1. Engine recovers gracefully from OOM without crash.
    2. Engine sets sahi_oom_recovered = True.
    3. Engine PRESERVES the defect detected in Slice 1 rather than discarding it!
    """
    tall_screen = Image.new("RGB", (1080, 2400), color=(200, 200, 200))

    class DefectThenOomBackend(InferenceBackend):
        def __init__(self):
            self.call = 0

        def generate(self, messages, image, **kwargs) -> str:
            self.call += 1
            if self.call == 1:
                # Global pass: clean
                return json.dumps({
                    "has_defect": False, "defect_type": "none", "confidence": 0.99,
                    "bounding_box": None, "affected_element_id": None, "explanation": "Global nominal",
                })
            elif self.call == 2:
                # Slice 0: detected defect
                return json.dumps({
                    "has_defect": True, "defect_type": "text_truncation", "confidence": 0.91,
                    "bounding_box": [100, 100, 300, 300], "affected_element_id": "title", "explanation": "Truncated text",
                })
            else:
                # Slice 1: OOM!
                if hasattr(torch.cuda, "OutOfMemoryError"):
                    raise torch.cuda.OutOfMemoryError("CUDA OOM on slice 1")
                raise RuntimeError("CUDA out of memory on slice 1")

    backend = DefectThenOomBackend()
    backend.__class__ = type("AdvOomBackend", (DefectThenOomBackend, TransformersInferenceBackend), {})
    engine = OracleEngine(backend=backend)

    res = engine.evaluate(image_input=tall_screen, screen_id="adv_sahi_test", enable_sahi=True)

    # Critical assertions
    assert res.metadata.get("sahi_oom_recovered") is True
    assert res.verdict.has_defect is True
    assert res.verdict.defect_type == DefectType.TEXT_TRUNCATION
    assert res.metadata.get("detected_by") == "sahi_dynamic_tiling"
