"""Core package for vision_oracle service configuration."""
from vision_oracle.core.config import (
    VERDICTS_DIR,
    SERVICE_PORT,
    SERVICE_TITLE,
    SERVICE_VERSION,
    ZERO_CLOUD_EGRESS,
    BASE_MODEL_PATH,
    LORA_WEIGHTS_PATH,
    resolve_path,
)

__all__ = [
    "VERDICTS_DIR",
    "SERVICE_PORT",
    "SERVICE_TITLE",
    "SERVICE_VERSION",
    "ZERO_CLOUD_EGRESS",
    "BASE_MODEL_PATH",
    "LORA_WEIGHTS_PATH",
    "resolve_path",
]
