"""Validated contract for Component 3 visual verdicts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScreenshotEvidence(BaseModel):
    """Screenshot metadata associated with a visual verdict."""

    model_config = ConfigDict(extra="forbid")

    path: str | None = None
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class DefectRegion(BaseModel):
    """A rectangular region identified by Component 3."""

    model_config = ConfigDict(extra="forbid")

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    label: str | None = None


class C3Verdict(BaseModel):
    """Evidence-backed visual verdict consumed by Component 4."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1)
    verdict_id: str = Field(min_length=1)
    session_id: str | None = None
    has_gui_defect: bool | None = None
    defect_type: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    screenshot: ScreenshotEvidence | None = None
    regions: list[DefectRegion] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_defect_and_regions(self) -> C3Verdict:
        """Require defect context and keep regions within screenshot bounds."""
        if self.has_gui_defect is True and not self.defect_type:
            raise ValueError("defect_type is required when has_gui_defect is true")
        if self.regions and self.screenshot is None:
            raise ValueError("screenshot is required when regions are present")
        if self.screenshot is not None:
            for region in self.regions:
                if region.x + region.width > self.screenshot.width:
                    raise ValueError("defect region exceeds screenshot width")
                if region.y + region.height > self.screenshot.height:
                    raise ValueError("defect region exceeds screenshot height")
        return self
