"""Timing helpers for the base-vs-fine-tuned notebook. Fake backend and processor: no model is loaded."""

import pytest
from PIL import Image

import vision_oracle.services.oracle_service  # noqa: F401  path guard first
from local_vision_oracle import model_compare as mc


class FakeProcessor:
    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        return "prompt"

    def __call__(self, text, images, padding=True, return_tensors="pt"):
        torch = pytest.importorskip("torch")
        h, w = images[0].height // 14, images[0].width // 14
        return {"image_grid_thw": torch.tensor([[1, h, w]])}


class FakeBackend:
    def __init__(self, contract=None):
        self.inference_contract = contract
        self.processor = FakeProcessor()
        self.calls = 0
        self.last_call = {"verdict_ms": 12.0, "localization_ms": None, "defect_probability": 0.9}

    def generate(self, messages, image, **kwargs):
        self.calls += 1
        return '{"has_defect": true}'


def test_eval_image_follows_the_contract_budget_or_the_default_thumbnail():
    big = Image.new("RGB", (1080, 1920))
    assert big.width * big.height > 262144
    small = mc.eval_image(big, 262144)
    assert small.width * small.height <= 262144
    default = mc.eval_image(big)
    assert default.width <= 720 and default.height <= 1280
    assert default.width * default.height > small.width * small.height  # default path keeps more pixels


def test_measure_warms_up_then_times_and_reports_the_median():
    backend = FakeBackend({"image_max_pixels": 262144})
    ticks = iter([0.0, 0.010, 1.0, 1.030, 2.0, 2.020])  # three timed calls: 10, 30, 20 ms
    out = mc.measure(backend, Image.new("RGB", (1080, 1920)), [{"role": "user"}], repeats=3, clock=lambda: next(ticks))
    assert backend.calls == 4  # one warm-up plus three timed
    assert out["total_ms"] == pytest.approx(20.0, abs=0.5)
    assert out["verdict_ms"] == 12.0 and out["box_ms"] is None
    assert out["image_px"] <= 262144 and out["visual_tokens"] > 0
    assert out["defect_probability"] == 0.9 and "has_defect" in out["output"]


def test_fewer_pixels_mean_fewer_visual_tokens():
    torch = pytest.importorskip("torch")  # noqa: F841
    proc, img = FakeProcessor(), Image.new("RGB", (1080, 1920))
    wide = mc.visual_tokens(proc, mc.eval_image(img), "p")
    narrow = mc.visual_tokens(proc, mc.eval_image(img, 262144), "p")
    assert narrow < wide


def test_speedup_ratio_and_zero_guard():
    assert mc.speedup(60000, 5000) == 12.0
    assert mc.speedup(1, 0) == float("inf")
