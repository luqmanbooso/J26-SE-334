"""
Unit tests for Canonical Contract v2 (Phase B of HEART C3 Full Implementation Plan).
Verifies:
- Scientific truthfulness invariants: no_defect_detected requires complete status and zero findings
- Partial analysis with zero findings is strictly inconclusive
- Error status never produces clean verdict
- Physical pixel coordinate bounds validation [0 <= x1 < x2 <= width, 0 <= y1 < y2 <= height]
- Bi-directional conversion to Component 4 C3Verdict contract
"""

import pytest
from vision_oracle.contracts.v2 import (
    JobState,
    AnalysisStatus,
    AnalysisDecision,
    FindingType,
    ReviewStatus,
    CoveragePolicy,
    Coverage,
    ScreenshotRef,
    Finding,
    CaptureBundle,
    VerdictEnvelopeV2,
)


def test_finding_validates_coordinate_order():
    # Valid box
    f = Finding(
        type="component_overlap",
        bbox_xyxy=[100, 200, 300, 400],
        explanation="Valid bounding box",
    )
    assert f.bbox_xyxy == [100, 200, 300, 400]

    # Inverted horizontal coordinates (x1 >= x2)
    with pytest.raises(ValueError, match="Invalid horizontal box bounds"):
        Finding(
            type="component_overlap",
            bbox_xyxy=[300, 200, 100, 400],
            explanation="Invalid x coordinates",
        )

    # Inverted vertical coordinates (y1 >= y2)
    with pytest.raises(ValueError, match="Invalid vertical box bounds"):
        Finding(
            type="component_overlap",
            bbox_xyxy=[100, 400, 300, 200],
            explanation="Invalid y coordinates",
        )

    # Negative coordinates
    with pytest.raises(ValueError, match="Negative coordinates are invalid"):
        Finding(
            type="component_overlap",
            bbox_xyxy=[-10, 200, 300, 400],
            explanation="Negative x1 coordinate",
        )


def test_verdict_envelope_enforces_clean_verdict_invariants():
    screenshot = ScreenshotRef(width=1080, height=2400)

    # Valid clean verdict
    clean_verdict = VerdictEnvelopeV2(
        capture_id="cap_test_01",
        analysis_status=AnalysisStatus.COMPLETE,
        decision=AnalysisDecision.NO_DEFECT_DETECTED,
        screenshot=screenshot,
        findings=[],
    )
    assert clean_verdict.decision == AnalysisDecision.NO_DEFECT_DETECTED

    # Invariant violation: no_defect_detected with findings present
    with pytest.raises(ValueError, match="decision cannot be 'no_defect_detected' when 1 findings are present"):
        VerdictEnvelopeV2(
            capture_id="cap_test_01",
            analysis_status=AnalysisStatus.COMPLETE,
            decision=AnalysisDecision.NO_DEFECT_DETECTED,
            screenshot=screenshot,
            findings=[
                Finding(
                    type="text_truncation",
                    bbox_xyxy=[50, 50, 200, 100],
                    explanation="Truncated title",
                )
            ],
        )

    # Invariant violation: no_defect_detected with partial analysis status
    with pytest.raises(ValueError, match="decision cannot be 'no_defect_detected' when analysis_status is 'partial'"):
        VerdictEnvelopeV2(
            capture_id="cap_test_01",
            analysis_status=AnalysisStatus.PARTIAL,
            decision=AnalysisDecision.NO_DEFECT_DETECTED,
            screenshot=screenshot,
            findings=[],
        )


def test_verdict_envelope_enforces_partial_inconclusive_invariant():
    screenshot = ScreenshotRef(width=1080, height=2400)

    # Partial analysis with zero findings MUST be inconclusive
    verdict = VerdictEnvelopeV2(
        capture_id="cap_test_02",
        analysis_status=AnalysisStatus.PARTIAL,
        decision=AnalysisDecision.INCONCLUSIVE,
        screenshot=screenshot,
        findings=[],
        coverage=Coverage(policy="global_plus_tiles_v1", planned_views=4, completed_views=2),
    )
    assert verdict.decision == AnalysisDecision.INCONCLUSIVE

    # Invariant violation: Partial with zero findings cannot be clean or defect_detected
    with pytest.raises(ValueError, match="partial analysis with zero findings must produce decision='inconclusive'"):
        VerdictEnvelopeV2(
            capture_id="cap_test_02",
            analysis_status=AnalysisStatus.PARTIAL,
            decision=AnalysisDecision.DEFECT_DETECTED,
            screenshot=screenshot,
            findings=[],
        )


def test_verdict_envelope_enforces_error_status_invariant():
    screenshot = ScreenshotRef(width=1080, height=2400)

    # Error status must never be reported as no_defect_detected
    with pytest.raises(ValueError, match="decision cannot be 'no_defect_detected'"):
        VerdictEnvelopeV2(
            capture_id="cap_test_03",
            analysis_status=AnalysisStatus.ERROR,
            decision=AnalysisDecision.NO_DEFECT_DETECTED,
            screenshot=screenshot,
            findings=[],
        )


def test_verdict_envelope_enforces_physical_pixel_bounds():
    screenshot = ScreenshotRef(width=1080, height=2400)

    # Out of bounds finding (x2=1100 exceeds width=1080)
    with pytest.raises(ValueError, match="exceed screenshot dimensions"):
        VerdictEnvelopeV2(
            capture_id="cap_test_04",
            analysis_status=AnalysisStatus.COMPLETE,
            decision=AnalysisDecision.DEFECT_DETECTED,
            screenshot=screenshot,
            findings=[
                Finding(
                    type="component_overlap",
                    bbox_xyxy=[100, 100, 1100, 500],
                    explanation="Exceeds screen width",
                )
            ],
        )


def test_verdict_envelope_converts_to_c4_contract():
    screenshot = ScreenshotRef(width=1080, height=2400, storage_path="/path/to/screen.png")
    v2 = VerdictEnvelopeV2(
        capture_id="cap_test_05",
        session_id="session_c4_test",
        analysis_status=AnalysisStatus.COMPLETE,
        decision=AnalysisDecision.DEFECT_DETECTED,
        screenshot=screenshot,
        findings=[
            Finding(
                type="component_overlap",
                bbox_xyxy=[100, 200, 500, 600],
                explanation="Overlap between header and banner",
                confidence=0.92,
            )
        ],
    )

    c4_verdict = v2.to_c4_verdict()
    assert c4_verdict.schema_version == "2.0.0"
    assert c4_verdict.has_gui_defect is True
    assert c4_verdict.defect_type == "component_overlap"
    assert c4_verdict.confidence == 0.92
    assert len(c4_verdict.regions) == 1
    region = c4_verdict.regions[0]
    assert region.x == 100
    assert region.y == 200
    assert region.width == 400
    assert region.height == 400
    assert region.label == "component_overlap"


def test_verdict_envelope_multi_finding_and_primary_finding_semantics():
    screenshot = ScreenshotRef(width=1080, height=2400, storage_path="/path/to/screen.png")
    f1 = Finding(
        type="component_overlap",
        bbox_xyxy=[100, 200, 500, 600],
        explanation="Header overlaps banner",
        confidence=0.90,
    )
    f2 = Finding(
        type="text_truncation",
        bbox_xyxy=[50, 700, 300, 800],
        explanation="Title truncated",
        confidence=0.85,
    )
    f3 = Finding(
        type="missing_image",
        bbox_xyxy=[200, 900, 600, 1200],
        explanation="Broken image placeholder",
        confidence=0.75,
    )

    # 1. Automatic primary_finding assignment
    v2_auto = VerdictEnvelopeV2(
        capture_id="cap_multi_01",
        analysis_status=AnalysisStatus.COMPLETE,
        decision=AnalysisDecision.DEFECT_DETECTED,
        screenshot=screenshot,
        findings=[f1, f2, f3],
    )
    assert v2_auto.scope == {"mode": "single_primary_visual_finding", "exhaustive": False}
    assert v2_auto.primary_finding == f1
    assert len(v2_auto.findings) == 3

    # Bi-directional adapter preserves all 3 regions but uses primary_finding for defect_type
    c4_auto = v2_auto.to_c4_verdict()
    assert c4_auto.has_gui_defect is True
    assert c4_auto.defect_type == "component_overlap"
    assert c4_auto.confidence == 0.90
    assert len(c4_auto.regions) == 3

    # 2. Explicit primary_finding designation (e.g. f2 is primary)
    v2_explicit = VerdictEnvelopeV2(
        capture_id="cap_multi_02",
        analysis_status=AnalysisStatus.COMPLETE,
        decision=AnalysisDecision.DEFECT_DETECTED,
        screenshot=screenshot,
        primary_finding=f2,
        findings=[f1, f2, f3],
    )
    assert v2_explicit.primary_finding == f2
    c4_explicit = v2_explicit.to_c4_verdict()
    assert c4_explicit.defect_type == "text_truncation"
    assert c4_explicit.confidence == 0.85
    assert len(c4_explicit.regions) == 3
