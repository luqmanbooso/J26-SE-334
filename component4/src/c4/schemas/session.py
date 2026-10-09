"""Session and failure-journey models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from c4.schemas.telemetry import NormalizedEvent


class Session(BaseModel):
    """Chronologically ordered events belonging to one user session."""

    model_config = ConfigDict(extra="allow")

    session_id: str
    started_at: datetime
    ended_at: datetime | None = None
    events: list[NormalizedEvent] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FailureJourney(BaseModel):
    """A reproducible journey ending in an error or crash."""

    model_config = ConfigDict(extra="allow")

    journey_id: str
    session_id: str
    events: list[NormalizedEvent] = Field(default_factory=list)
    failure: NormalizedEvent
    metadata: dict[str, Any] = Field(default_factory=dict)
