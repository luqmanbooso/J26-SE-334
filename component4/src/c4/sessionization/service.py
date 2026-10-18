"""Facade for deterministic session reconstruction and flow extraction."""

from __future__ import annotations

from collections.abc import Iterable

from c4.schemas import FailureJourney, NormalizedEvent, Session
from c4.sessionization.config import SessionizationConfig
from c4.sessionization.flow_extractor import extract_journeys
from c4.sessionization.grouper import group_sessions


class SessionizationService:
    """Run session grouping and failure-journey extraction."""

    def __init__(self, config: SessionizationConfig | None = None) -> None:
        self.config = config or SessionizationConfig()

    def group_sessions(self, events: Iterable[NormalizedEvent]) -> list[Session]:
        """Group normalized events into deterministic sessions."""
        return group_sessions(events, self.config)

    def extract_journeys(self, session: Session) -> list[FailureJourney]:
        """Extract failure journeys from one session."""
        return extract_journeys(session, self.config)

    def process(self, events: Iterable[NormalizedEvent]) -> list[FailureJourney]:
        """Group events and return journeys ordered by session and failure time."""
        journeys = [
            journey
            for session in self.group_sessions(events)
            for journey in self.extract_journeys(session)
        ]
        return sorted(
            journeys,
            key=lambda journey: (journey.failure.timestamp, journey.journey_id),
        )
