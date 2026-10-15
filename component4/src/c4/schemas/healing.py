"""Locator healing result models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealingDecision(str, Enum):
    """Policy outcome for a locator healing attempt."""

    HEALED = "healed"
    REFUSED = "refused"
    NOT_NEEDED = "not_needed"


class HealResult(BaseModel):
    """Auditable result of a single locator healing attempt."""

    model_config = ConfigDict(extra="allow")

    decision: HealingDecision
    original_locator: dict[str, str] = Field(default_factory=dict)
    replacement_locator: dict[str, str] | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    strategy: str | None = None
    candidate_count: int = Field(default=0, ge=0)
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
