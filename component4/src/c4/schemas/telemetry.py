"""Provider-neutral telemetry models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventSource(str, Enum):
    """Supported production telemetry providers."""

    SENTRY = "sentry"
    CRASHLYTICS = "crashlytics"


class EventKind(str, Enum):
    """Normalized event categories used by sessionization."""

    ACTION = "action"
    ERROR = "error"
    SCREEN = "screen"
    LIFECYCLE = "lifecycle"
    UNKNOWN = "unknown"


class NormalizedEvent(BaseModel):
    """A validated, provider-independent telemetry event."""

    model_config = ConfigDict(extra="allow")

    event_id: str
    session_id: str | None = None
    source: EventSource
    kind: EventKind = EventKind.UNKNOWN
    timestamp: datetime
    name: str
    action: str | None = None
    screen: str | None = None
    locator: dict[str, str] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
