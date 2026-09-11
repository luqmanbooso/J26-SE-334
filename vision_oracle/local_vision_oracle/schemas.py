"""
Data Contract Schemas for C3 Localized Multimodal Oracle.
Grounded in Proposal FR3, FR4, FR7 and NFR SLA criteria.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class DefectType(str, Enum):
    """
    Academic 5-class non-crash UI bug taxonomy + clean state.
    Synthesized from OwlEye (ICSE 2020), OLLM (Ju et al. 2024), and RegDroid (ICSE 2022).
    """
    NONE = "none"
    COMPONENT_OVERLAP = "component_overlap"
    TEXT_TRUNCATION = "text_truncation"
    MISSING_COMPONENT = "missing_component"
    UNRENDERED_ASSET = "unrendered_asset"
    FUNCTIONAL_INCONGRUENCE = "functional_incongruence"
    OTHER = "other_defect"


class Verdict(BaseModel):
    """
    Core bug verdict emitted by the Oracle.
    Feeds directly into Component 4 (Self-Healing Telemetry).
    """
    has_defect: bool = Field(
        ..., 
        description="True if non-crash UI defect is detected, False if screen renders cleanly."
    )
    defect_type: DefectType = Field(
        default=DefectType.NONE, 
        description="Classification of defect according to academic 5-class taxonomy + other."
    )
    sub_category: Optional[str] = Field(
        default=None,
        description="Granular sub-category or edge case description (e.g. keyboard_occlusion, contrast_violation, rtl_alignment)."
    )
    confidence: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Confidence score of the oracle prediction, normalized between 0.0 and 1.0."
    )
    bounding_box: Optional[List[int]] = Field(
        default=None, 
        description="Normalized coordinates [ymin, xmin, ymax, xmax] in range [0, 1000]."
    )
    affected_element_id: Optional[str] = Field(
        default=None, 
        description="Resource-ID or text of affected widget from pruned View Hierarchy."
    )
    explanation: str = Field(
        default="", 
        description="Concise diagnostic explanation of why this screen exhibits a bug."
    )

    @field_validator("bounding_box")
    @classmethod
    def validate_bounding_box(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is not None:
            if len(v) != 4:
                raise ValueError("bounding_box must contain exactly 4 coordinates: [ymin, xmin, ymax, xmax]")
            for coord in v:
                if coord < 0 or coord > 1000:
                    raise ValueError(f"Coordinate {coord} out of normalized bounds [0, 1000]")
            if v[0] > v[2] or v[1] > v[3]:
                raise ValueError(f"Invalid bounding box orientation: [ymin={v[0]}, xmin={v[1]}, ymax={v[2]}, xmax={v[3]}]")
        return v


class LatencyBreakdown(BaseModel):
    """
    Fine-grained stage-by-stage execution latency in milliseconds.
    Grounded in Proposal NFR criteria: Total pipeline < 1500 ms SLA.
    """
    capture_ms: float = Field(default=0.0, description="Screen and hierarchy capture latency.")
    preprocess_ms: float = Field(default=0.0, description="Image normalization and tensor preparation.")
    prune_ms: float = Field(default=0.0, description="View hierarchy AST pruning latency.")
    inference_ms: float = Field(default=0.0, description="Local VLM model forward-pass latency.")
    total_pipeline_ms: float = Field(default=0.0, description="Total wall-clock pipeline time.")
    meets_sla: bool = Field(default=True, description="True if total_pipeline_ms <= 1500.0 ms.")

    def compute_total(self) -> float:
        self.total_pipeline_ms = round(
            self.capture_ms + self.preprocess_ms + self.prune_ms + self.inference_ms, 2
        )
        self.meets_sla = self.total_pipeline_ms <= 1500.0
        return self.total_pipeline_ms


class C3OracleResult(BaseModel):
    """
    Complete telemetry envelope published to Test Results Store.
    Grounded in Proposal FR7.
    """
    screen_id: str = Field(..., description="Unique screen identifier or file hash.")
    verdict: Verdict = Field(..., description="Bug verdict and bounding box evidence.")
    latency_breakdown: LatencyBreakdown = Field(..., description="Execution timing breakdown.")
    timestamp: str = Field(..., description="ISO 8601 evaluation timestamp.")
    engine_used: str = Field(default="qwen2-vl-awq-4bit", description="Inference engine descriptor.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary app/test state metadata.")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
