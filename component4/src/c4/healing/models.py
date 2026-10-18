"""Models for deterministic locator healing decisions."""

from __future__ import annotations

from enum import Enum
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealingConfig(BaseModel):
    """Policy and ranking settings for locator healing."""

    model_config = ConfigDict(extra="forbid")

    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    ambiguity_margin: float = Field(default=0.05, ge=0.0, le=1.0)
    max_candidates_ranked: int = Field(default=300, ge=1)
    top_k_reported: int = Field(default=5, ge=1)
    max_heal_rounds: int = Field(default=3, ge=1)
    embedder: Literal["sbert", "lexical"] = "sbert"
    sbert_model: str = "sentence-transformers/all-MiniLM-L6-v2"


class HealingStatus(str, Enum):
    """Outcome of a healing attempt."""

    HEALED = "healed"
    REFUSED_LOW_CONFIDENCE = "refused_low_confidence"
    REFUSED_AMBIGUOUS = "refused_ambiguous"
    REFUSED_NOT_UNIQUE = "refused_not_unique"
    REFUSED_NO_CANDIDATES = "refused_no_candidates"
    NOT_APPLICABLE = "not_applicable"


class ElementDescriptor(BaseModel):
    """Stable semantic and structural attributes of a UI element."""

    model_config = ConfigDict(extra="forbid")

    resource_id: str | None = None
    text: str | None = None
    content_desc: str | None = None
    class_name: str | None = None
    package: str | None = None
    bounds: tuple[int, int, int, int] | None = None
    clickable: bool | None = None
    ancestors: list[str] = Field(default_factory=list)
    sibling_texts: list[str] = Field(default_factory=list)

    def semantic_text(self) -> str:
        """Return deterministic tokens for semantic ranking."""
        values: list[str] = []
        for value in (self.text, self.content_desc):
            if value:
                tokens = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
                tokens = re.sub(r"[_./:]+", " ", tokens)
                values.extend(tokens.lower().split())
        if not self.text and not self.content_desc and self.resource_id:
            resource = self.resource_id.split(":", 1)[-1]
            resource = resource.split("/", 1)[-1]
            tokens = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", resource)
            tokens = re.sub(r"[_./:]+", " ", tokens)
            values.extend(token for token in tokens.lower().split() if token != "id")
        if self.class_name:
            values.append(self.class_name.rsplit(".", 1)[-1].lower())
        return " ".join(values)


class CandidateScore(BaseModel):
    """Ranked candidate and its semantic score."""

    model_config = ConfigDict(extra="forbid")

    node_index: int
    descriptor: ElementDescriptor
    score: float
    locator_preview: str | None = None


class HealingDecision(BaseModel):
    """Auditable result of one healing attempt."""

    model_config = ConfigDict(extra="forbid")

    status: HealingStatus
    step_index: int
    action: str | None
    original_locator: dict[str, str]
    healed_locator: dict[str, str] | None = None
    confidence: float | None = None
    margin: float | None = None
    candidates_total: int = 0
    candidates_after_narrowing: int = 0
    candidates_ranked: int = 0
    top_candidates: list[CandidateScore] = Field(default_factory=list, max_length=5)
    embedder: str
    threshold: float
    latency_ms: float = Field(ge=0.0)
    reason: str | None = None
    healed_script: str | None = None
    rule_counts: dict[str, int] = Field(default_factory=dict)
    r6_applied: bool = False
