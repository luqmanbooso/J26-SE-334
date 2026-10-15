from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from c4.c3_interface import (
    C3Verdict,
    DefectRegion,
    MockC3Client,
    ScreenshotEvidence,
)
from c4.schemas import EventKind, EventSource, NormalizedEvent


def failure() -> NormalizedEvent:
    return NormalizedEvent(
        event_id="payload:error",
        session_id="session-1",
        source=EventSource.SENTRY,
        kind=EventKind.ERROR,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        name="failure",
    )


def verdict(**overrides: object) -> C3Verdict:
    values: dict[str, object] = {
        "schema_version": "1.0",
        "verdict_id": "verdict-1",
        "session_id": "session-1",
        "has_gui_defect": True,
        "defect_type": "OVERFLOW_Y_COLLISION",
        "confidence": 0.94,
        "screenshot": ScreenshotEvidence(width=1080, height=2400),
        "regions": [DefectRegion(x=10, y=20, width=100, height=200)],
        "evidence": {"source": "mock"},
        "metadata": {},
    }
    values.update(overrides)
    return C3Verdict.model_validate(values)


def test_valid_verdict_is_parsed() -> None:
    result = verdict()

    assert result.defect_type == "OVERFLOW_Y_COLLISION"
    assert result.regions[0].width == 100


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_must_be_between_zero_and_one(confidence: float) -> None:
    with pytest.raises(ValidationError):
        verdict(confidence=confidence)


def test_positive_verdict_requires_defect_type() -> None:
    with pytest.raises(ValidationError, match="defect_type"):
        verdict(defect_type=None)


def test_regions_must_fit_screenshot() -> None:
    with pytest.raises(ValidationError, match="screenshot width"):
        verdict(regions=[DefectRegion(x=1000, y=0, width=100, height=20)])


def test_regions_require_screenshot() -> None:
    with pytest.raises(ValidationError, match="screenshot"):
        verdict(screenshot=None)


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        verdict(unexpected="not allowed")


def test_mock_client_returns_configured_verdict_copy() -> None:
    configured = verdict()
    client = MockC3Client({"session-1": configured})

    result = client.get_verdict("session-1", failure())
    result.metadata["changed"] = True

    assert configured.metadata == {}
    assert result.metadata == {"changed": True}


def test_mock_client_returns_deterministic_default_for_unknown_session() -> None:
    client = MockC3Client()

    first = client.get_verdict("unknown", failure())
    second = client.get_verdict("unknown", failure())

    assert first == second
    assert first.verdict_id == "mock-unknown"
    assert first.has_gui_defect is False
    assert first.confidence == 0.0


def test_mock_client_does_not_depend_on_failure_payload() -> None:
    client = MockC3Client()

    first = client.get_verdict("session-1", failure())
    second = client.get_verdict(
        "session-1",
        failure().model_copy(update={"name": "different failure"}),
    )

    assert first == second
