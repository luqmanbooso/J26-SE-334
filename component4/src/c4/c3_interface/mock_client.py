"""Deterministic in-memory Component 3 client for tests and local development."""

from __future__ import annotations

from collections.abc import Mapping

from c4.schemas import FailureJourney, NormalizedEvent

from c4.c3_interface.contract import C3Verdict


class MockC3Client:
    """Return configured verdicts or a deterministic no-defect verdict."""

    def __init__(
        self,
        verdicts: Mapping[str, C3Verdict] | None = None,
    ) -> None:
        self._verdicts = dict(verdicts or {})

    def get_verdict(
        self,
        session_id: str,
        failure: NormalizedEvent,
        journey: FailureJourney | None = None,
    ) -> C3Verdict:
        """Return a deep copy so callers cannot mutate configured fixtures."""
        verdict = self._verdicts.get(session_id)
        if verdict is None:
            return C3Verdict(
                schema_version="1.0",
                verdict_id=f"mock-{session_id}",
                session_id=session_id,
                has_gui_defect=False,
                defect_type=None,
                confidence=0.0,
            )
        return verdict.model_copy(deep=True)
