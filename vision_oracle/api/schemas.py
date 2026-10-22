"""
API Request and Response schemas for Component 3 endpoints.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class C2TriggerPayload(BaseModel):
    """Payload sent by Component 2 after completing an action (IF-C2-to-C3)."""
    action_id: str = Field(..., description="Unique ID of user/simulated action.")
    session_id: str = Field(default="live_session", description="Testing session identifier.")
    target_element_id: Optional[str] = Field(default=None, description="Widget tapped or targeted.")
    app_package: Optional[str] = Field(default=None, description="Target app package under test.")
    stress_level: Optional[float] = Field(default=0.0, description="Biomechanical stress intensity [0, 1].")
    delay_ms: Optional[float] = Field(default=0.0, description="Delay observed or injected.")
    device_serial: Optional[str] = Field(default=None, description="Target ADB device serial.")
    action_started_epoch_ms: Optional[int] = Field(default=None)
    action_completed_epoch_ms: Optional[int] = Field(default=None)
    observation: Optional[dict] = Field(default=None)
    perturbation_event_ids: Optional[list] = Field(default=None)


class EvaluateRequest(BaseModel):
    """Payload for synchronous screen evaluation."""
    image_base64: Optional[str] = Field(default=None, description="Base64 encoded screenshot image.")
    image_path: Optional[str] = Field(default=None, description="Filesystem path to screenshot.")
    hierarchy_xml: Optional[str] = Field(default=None, description="Raw view hierarchy XML string.")
    screen_id: Optional[str] = Field(default=None, description="Explicit screen identifier.")
    session_id: Optional[str] = Field(default="live_session", description="Session identifier.")
    action_context: Optional[str] = Field(default=None, description="Contextual description of action.")
    enable_sahi: bool = Field(default=False, description="Experimental multi-slice tiling. Not validated with the current adapter; off by default.")


class SequenceEvaluateRequest(BaseModel):
    """Payload for multi-frame temporal freeze detection (FR3)."""
    image_paths: Optional[List[str]] = Field(default=None, description="List of screenshot paths.")
    image_base64_list: Optional[List[str]] = Field(default=None, description="List of base64 screenshots.")
    hierarchies: Optional[List[str]] = Field(default=None, description="List of hierarchy XML strings.")
    session_id: Optional[str] = Field(default="live_session", description="Session identifier.")
    time_delta_s: float = Field(default=2.5, description="Time difference between frames.")
    action_dispatched: bool = Field(default=True, description="True if an interactive action occurred.")
    action_context: Optional[str] = Field(default=None, description="Contextual description of action.")
