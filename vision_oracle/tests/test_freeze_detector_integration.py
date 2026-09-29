"""
Unit tests for Temporal Freeze Detector integration into OracleEngine.
Verifies Proposal FR3 (frozen states) and Appendix F temporal heuristics.
"""

import pytest
from PIL import Image
import numpy as np

from local_vision_oracle.engine import OracleEngine, MockInferenceBackend
from local_vision_oracle.schemas import DefectType, C3OracleResult
from local_vision_oracle.freeze_detector import TemporalFreezeDetector


def create_solid_image(color=(255, 255, 255), size=(720, 1280)) -> Image.Image:
    return Image.new("RGB", size, color)


def create_modified_image(size=(720, 1280)) -> Image.Image:
    img = Image.new("RGB", size, (255, 255, 255))
    # Draw significant dark block to create > 10% pixel difference
    arr = np.array(img)
    arr[200:800, 100:600] = [20, 20, 20]
    return Image.fromarray(arr)


def test_temporal_freeze_detected_on_identical_screens():
    """Identical consecutive frames after an action must be flagged as frozen state."""
    engine = OracleEngine(backend=MockInferenceBackend())
    
    frame1 = create_solid_image((240, 240, 240))
    frame2 = create_solid_image((240, 240, 240))  # Identical
    
    result = engine.evaluate(
        image_input=frame2,
        previous_image=frame1,
        time_delta_s=2.5,
        action_dispatched=True,
        action_context="Tap Submit Button",
    )
    
    assert result.verdict.has_defect is True
    assert result.verdict.defect_type == DefectType.FROZEN_STATE
    assert result.verdict.confidence >= 0.90
    assert result.metadata.get("detected_by") == "temporal_freeze_detector"
    assert "freeze_details" in result.metadata
    assert result.latency_breakdown.meets_sla is True


def test_temporal_freeze_not_detected_on_dynamic_transition():
    """Distinct frames indicating UI transition must not be flagged as frozen state."""
    engine = OracleEngine(backend=MockInferenceBackend())
    
    frame1 = create_solid_image()
    frame2 = create_modified_image()
    
    result = engine.evaluate(
        image_input=frame2,
        previous_image=frame1,
        time_delta_s=2.5,
        action_dispatched=True,
    )
    
    # Transition succeeded, so not detected by temporal freeze
    assert result.metadata.get("detected_by") != "temporal_freeze_detector"


def test_indeterminate_spinner_detected_on_persistent_hierarchy():
    """Persistent loading indicator across time threshold must be flagged as frozen state."""
    engine = OracleEngine(backend=MockInferenceBackend())
    
    frame1 = create_solid_image()
    frame2 = create_solid_image()
    
    spinner_xml = (
        '<hierarchy rotation="0">'
        '  <node class="android.widget.FrameLayout" bounds="[0,0][720,1280]">'
        '    <node class="android.widget.ProgressBar" resource-id="com.app:id/network_spinner" '
        '          bounds="[280,560][440,720]"/>'
        '  </node>'
        '</hierarchy>'
    )
    
    result = engine.evaluate(
        image_input=frame2,
        raw_hierarchy=spinner_xml,
        previous_image=frame1,
        previous_hierarchy=spinner_xml,
        time_delta_s=4.0,  # Exceeds default spinner_timeout_s = 3.5
        action_dispatched=True,
    )
    
    assert result.verdict.has_defect is True
    assert result.verdict.defect_type == DefectType.FROZEN_STATE
    assert result.verdict.affected_element_id == "com.app:id/network_spinner"
    assert result.metadata.get("detected_by") == "temporal_freeze_detector"


def test_evaluate_sequence_helper():
    """evaluate_sequence must evaluate multi-frame sequence and detect freeze."""
    engine = OracleEngine(backend=MockInferenceBackend())
    
    f1 = create_solid_image((255, 255, 255))
    f2 = create_solid_image((255, 255, 255))
    f3 = create_solid_image((255, 255, 255))
    
    result = engine.evaluate_sequence(
        screens=[f1, f2, f3],
        time_delta_s=3.0,
        action_dispatched=True,
        action_context="Swipe down to refresh",
    )
    
    assert result.verdict.has_defect is True
    assert result.verdict.defect_type == DefectType.FROZEN_STATE
    assert "Swipe down to refresh" in result.verdict.explanation


def test_evaluate_sequence_rejects_insufficient_frames():
    """evaluate_sequence requires at least 2 frames for temporal analysis."""
    engine = OracleEngine(backend=MockInferenceBackend())
    
    with pytest.raises(ValueError, match="at least 2 screen frames"):
        engine.evaluate_sequence(screens=[create_solid_image()])


def test_freeze_verdict_converts_to_c4_contract():
    """Frozen state verdict must map seamlessly to C4 C3Verdict contract."""
    from c4.c3_interface.contract import C3Verdict
    
    engine = OracleEngine(backend=MockInferenceBackend())
    frame1 = create_solid_image()
    frame2 = create_solid_image()
    
    result = engine.evaluate_sequence(
        screens=[frame1, frame2],
        time_delta_s=2.5,
        action_dispatched=True,
    )
    
    c4_verdict = engine.to_c4_verdict(result, session_id="test_session_freeze")
    assert isinstance(c4_verdict, C3Verdict)
    assert c4_verdict.has_gui_defect is True
    assert c4_verdict.defect_type == "frozen_state"
    assert c4_verdict.confidence >= 0.90
    assert len(c4_verdict.regions) > 0
    assert c4_verdict.regions[0].label == "frozen_state"
