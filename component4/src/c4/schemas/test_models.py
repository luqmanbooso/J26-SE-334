"""Synthesized test models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TestStep(BaseModel):
    """One executable action in a synthesized Appium journey."""

    model_config = ConfigDict(extra="allow")

    index: int = Field(ge=0)
    action: str
    target: dict[str, str] = Field(default_factory=dict)
    value: str | None = None
    source_event_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
