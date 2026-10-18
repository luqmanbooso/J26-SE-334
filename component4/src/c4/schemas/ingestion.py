"""Ingestion diagnostics and batch results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from c4.schemas.telemetry import NormalizedEvent


class QuarantinedRecord(BaseModel):
    """A provider record rejected without aborting the payload."""

    record_index: int
    reason: str
    raw: dict[str, Any] = Field(default_factory=dict)


class IngestionReport(BaseModel):
    """Events accepted from one or more provider records."""

    events: list[NormalizedEvent] = Field(default_factory=list)
    quarantined: list[QuarantinedRecord] = Field(default_factory=list)
    deduped_count: int = Field(default=0, ge=0)

    @property
    def accepted_count(self) -> int:
        return len(self.events)
