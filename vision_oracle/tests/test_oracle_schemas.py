"""
Unit tests for C3 Local Vision Oracle Schemas.
Verifies data contract constraints, bounds validation, and SLA calculations.
"""

import pytest
from pydantic import ValidationError
from local_vision_oracle.schemas import (
    DefectType,
    Verdict,
    LatencyBreakdown,
    C3OracleResult,
)


def test_valid_clean_verdict():
    verdict = Verdict(
        has_defect=False,
        defect_type=DefectType.NONE,
        confidence=0.99,
        explanation="Screen elements render with proper spacing and visibility."
    )
    assert verdict.has_defect is False
    assert verdict.defect_type == DefectType.NONE
    assert verdict.confidence == 0.99
    assert verdict.bounding_box is None


def test_valid_defect_verdict():
    verdict = Verdict(
        has_defect=True,
        defect_type=DefectType.COMPONENT_OVERLAP,
        confidence=0.95,
        bounding_box=[100, 150, 300, 450],
        affected_element_id="com.example:id/submit_button",
        explanation="Submit button overlaps with bottom navigation bar."
    )
    assert verdict.has_defect is True
    assert verdict.defect_type == DefectType.COMPONENT_OVERLAP
    assert verdict.bounding_box == [100, 150, 300, 450]


def test_extensible_defect_type_with_subcategory():
    verdict = Verdict(
        has_defect=True,
        defect_type=DefectType.OTHER,
        sub_category="contrast_violation",
        confidence=0.88,
        explanation="Light gray text on white background violates WCAG AAA contrast."
    )
    assert verdict.defect_type == DefectType.OTHER
    assert verdict.sub_category == "contrast_violation"
    assert verdict.has_defect is True


def test_invalid_defect_type():
    with pytest.raises(ValidationError):
        Verdict(
            has_defect=True,
            defect_type="random_non_existent_bug",
            confidence=0.85
        )


def test_invalid_confidence_range():
    # Confidence > 1.0
    with pytest.raises(ValidationError):
        Verdict(
            has_defect=True,
            defect_type=DefectType.TEXT_TRUNCATION,
            confidence=1.5
        )
    # Confidence < 0.0
    with pytest.raises(ValidationError):
        Verdict(
            has_defect=True,
            defect_type=DefectType.TEXT_TRUNCATION,
            confidence=-0.1
        )


def test_bounding_box_validation():
    # Wrong coordinate count
    with pytest.raises(ValidationError):
        Verdict(
            has_defect=True,
            defect_type=DefectType.MISSING_COMPONENT,
            confidence=0.9,
            bounding_box=[100, 200]
        )

    # Coordinate out of [0, 1000] bounds
    with pytest.raises(ValidationError):
        Verdict(
            has_defect=True,
            defect_type=DefectType.MISSING_COMPONENT,
            confidence=0.9,
            bounding_box=[100, 200, 1050, 400]
        )

    # Inverted box orientation (ymin > ymax)
    with pytest.raises(ValidationError):
        Verdict(
            has_defect=True,
            defect_type=DefectType.MISSING_COMPONENT,
            confidence=0.9,
            bounding_box=[500, 200, 100, 400]
        )


def test_latency_breakdown_sla():
    # Within 1500 ms SLA
    lat_ok = LatencyBreakdown(
        capture_ms=120.0,
        preprocess_ms=45.0,
        prune_ms=15.0,
        inference_ms=1150.0
    )
    total = lat_ok.compute_total()
    assert total == 1330.0
    assert lat_ok.meets_sla is True

    # Exceeds 1500 ms SLA
    lat_slow = LatencyBreakdown(
        capture_ms=150.0,
        preprocess_ms=100.0,
        prune_ms=50.0,
        inference_ms=1300.0
    )
    total_slow = lat_slow.compute_total()
    assert total_slow == 1600.0
    assert lat_slow.meets_sla is False


def test_c3_oracle_result_envelope():
    verdict = Verdict(
        has_defect=True,
        defect_type=DefectType.UNRENDERED_ASSET,
        confidence=0.91,
        bounding_box=[200, 100, 500, 600]
    )
    latency = LatencyBreakdown(capture_ms=100.0, preprocess_ms=30.0, prune_ms=10.0, inference_ms=900.0)
    latency.compute_total()

    result = C3OracleResult(
        screen_id="screen_test_001",
        verdict=verdict,
        latency_breakdown=latency,
        timestamp="2026-09-30T09:00:00Z"
    )
    data = result.to_dict()
    assert data["screen_id"] == "screen_test_001"
    assert data["verdict"]["defect_type"] == "unrendered_asset"
    assert data["latency_breakdown"]["meets_sla"] is True
