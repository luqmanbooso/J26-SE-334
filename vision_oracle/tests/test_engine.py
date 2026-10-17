"""
Unit and Integration Tests for C3 OracleEngine and Backends.
Validates end-to-end execution, SLA telemetry, input formats, and failure resilience.
"""

import io
import json
import pytest
from pathlib import Path
from PIL import Image

from local_vision_oracle.schemas import (
    DefectType,
    Verdict,
    LatencyBreakdown,
    C3OracleResult,
)
from local_vision_oracle.pruner import HierarchyPruner, PrunedNode
from local_vision_oracle.preprocessor import ImagePreprocessor
from local_vision_oracle.prompt import PromptBuilder
from local_vision_oracle.engine import (
    InferenceBackend,
    MockInferenceBackend,
    OracleEngine,
)


@pytest.fixture
def sample_image() -> Image.Image:
    """Creates a dummy RGB test image (1080x2400)."""
    return Image.new("RGB", (1080, 2400), color=(240, 240, 240))


@pytest.fixture
def sample_xml() -> str:
    return """<?xml version="1.0" encoding="utf-8"?>
    <hierarchy rotation="0">
      <node class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">
        <node class="android.widget.TextView" resource-id="com.app:id/title" text="Checkout" bounds="[100,200][980,350]" />
        <node class="android.widget.Button" resource-id="com.app:id/pay_btn" text="Pay $50" bounds="[100,2000][980,2200]" clickable="true" />
      </node>
    </hierarchy>
    """


@pytest.fixture
def sample_rico_json() -> dict:
    return {
        "class": "android.widget.FrameLayout",
        "bounds": [0, 0, 1080, 2400],
        "children": [
            {
                "class": "android.widget.TextView",
                "resource-id": "com.app:id/balance",
                "text": "Wallet: $100.00",
                "bounds": [50, 100, 500, 200],
            },
            {
                "class": "android.widget.Button",
                "resource-id": "com.app:id/topup_btn",
                "text": "Top Up",
                "bounds": [50, 300, 500, 450],
                "clickable": True,
            },
        ],
    }


def test_mock_backend_default(sample_image):
    backend = MockInferenceBackend(simulated_latency_ms=5.0)
    messages = [{"role": "user", "content": "Test"}]
    output = backend.generate(messages, sample_image)

    data = json.loads(output)
    assert data["has_defect"] is False
    assert data["defect_type"] == "none"
    assert backend.call_count == 1
    assert backend.last_messages == messages


def test_mock_backend_custom_response(sample_image):
    defect_json = json.dumps({
        "has_defect": True,
        "defect_type": "component_overlap",
        "confidence": 0.95,
        "bounding_box": [500, 100, 600, 900],
        "affected_element_id": "com.app:id/btn_submit",
        "explanation": "Submit button occluded by floating banner.",
    })
    backend = MockInferenceBackend(default_response=defect_json, simulated_latency_ms=0.0)
    engine = OracleEngine(backend=backend)

    result = engine.evaluate(
        image_input=sample_image,
        screen_id="test_screen_001",
    )

    assert isinstance(result, C3OracleResult)
    assert result.screen_id == "test_screen_001"
    assert result.verdict.has_defect is True
    assert result.verdict.defect_type == DefectType.COMPONENT_OVERLAP
    assert result.verdict.bounding_box == [500, 100, 600, 900]
    assert result.verdict.affected_element_id == "com.app:id/btn_submit"
    assert result.latency_breakdown.meets_sla is True


def test_engine_with_xml_hierarchy(sample_image, sample_xml):
    engine = OracleEngine(backend=MockInferenceBackend(simulated_latency_ms=1.0))
    result = engine.evaluate(
        image_input=sample_image,
        raw_hierarchy=sample_xml,
        action_context="User tapped checkout button",
    )

    assert result.metadata["action_context"] == "User tapped checkout button"
    assert "pruning_stats" in result.metadata
    assert result.metadata["pruning_stats"]["raw_nodes"] == 4
    assert result.metadata["pruning_stats"]["pruned_nodes"] == 2
    assert result.latency_breakdown.prune_ms >= 0.0
    assert result.latency_breakdown.preprocess_ms >= 0.0
    assert result.latency_breakdown.inference_ms >= 0.0
    assert result.latency_breakdown.total_pipeline_ms >= 0.0


def test_engine_with_rico_json(sample_image, sample_rico_json):
    engine = OracleEngine(backend=MockInferenceBackend(simulated_latency_ms=1.0))
    result = engine.evaluate(
        image_input=sample_image,
        raw_hierarchy=sample_rico_json,
    )

    assert "pruning_stats" in result.metadata
    assert result.metadata["pruning_stats"]["raw_nodes"] == 3
    assert result.metadata["pruning_stats"]["pruned_nodes"] == 2


def test_engine_auto_screen_id_generation(sample_image):
    engine = OracleEngine()
    result1 = engine.evaluate(image_input=sample_image)
    result2 = engine.evaluate(image_input=sample_image)

    assert result1.screen_id.startswith("scr_")
    assert result1.screen_id == result2.screen_id


def test_engine_bytes_input(sample_image):
    buf = io.BytesIO()
    sample_image.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    engine = OracleEngine()
    result = engine.evaluate(image_input=png_bytes)

    assert isinstance(result, C3OracleResult)
    assert result.verdict.has_defect is False


def test_engine_sla_breach_detection(sample_image):
    # Simulate high latency backend exceeding 1500 ms SLA
    backend = MockInferenceBackend(simulated_latency_ms=1550.0)
    engine = OracleEngine(backend=backend)

    result = engine.evaluate(image_input=sample_image)

    assert result.latency_breakdown.total_pipeline_ms > 1500.0
    assert result.latency_breakdown.meets_sla is False


def test_engine_pre_parsed_pruned_nodes(sample_image):
    nodes = [
        PrunedNode(
            element_id="btn_1",
            class_name="Button",
            text="Click",
            content_desc="",
            bounds=[100, 100, 200, 200],
            clickable=True,
            scrollable=False,
        )
    ]
    engine = OracleEngine(backend=MockInferenceBackend())
    result = engine.evaluate(image_input=sample_image, raw_hierarchy=nodes)

    assert isinstance(result, C3OracleResult)
    assert result.verdict.has_defect is False
