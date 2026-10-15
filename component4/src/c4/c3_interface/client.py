"""Provider-neutral Component 3 client interface."""

from __future__ import annotations

from typing import Protocol

from c4.schemas import FailureJourney, NormalizedEvent

from c4.c3_interface.contract import C3Verdict


class C3Client(Protocol):
    """Client capable of obtaining a Component 3 verdict."""

    def get_verdict(
        self,
        session_id: str,
        failure: NormalizedEvent,
        journey: FailureJourney | None = None,
    ) -> C3Verdict:
        """Return visual evidence for a failure."""
