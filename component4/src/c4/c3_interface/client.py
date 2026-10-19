"""Provider-neutral Component 3 client interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from c4.schemas import FailureJourney, NormalizedEvent

from c4.c3_interface.contract import C3Verdict


@runtime_checkable
class C3Client(Protocol):

    """Client capable of obtaining a Component 3 verdict."""

    def get_verdict(
        self,
        session_id: str,
        failure: NormalizedEvent,
        journey: FailureJourney | None = None,
        *,
        hierarchy_xml: str | None = None,
        screenshot_path: str | None = None,
        screenshot_width: int | None = None,
        screenshot_height: int | None = None,
    ) -> C3Verdict:
        """Return visual evidence for a failure."""
