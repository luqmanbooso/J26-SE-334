"""Target application configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TargetAppConfig(BaseModel):
    """Android application and Appium target settings."""

    model_config = ConfigDict(extra="forbid")

    package: str
    activity: str | None = None
    apk_path: str | None = None
    udid: str | None = None
    appium_url: str = "http://127.0.0.1:4723"
    adb_path: str = "adb"
    no_reset: bool = True
    new_command_timeout: int = 120
    setup_commands: list[list[str]] = Field(default_factory=list)

    @field_validator("package")
    @classmethod
    def package_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("package must not be empty")
        return value

    @model_validator(mode="after")
    def validate_launch_configuration(self) -> "TargetAppConfig":
        if not (self.activity or self.apk_path or self.setup_commands):
            raise ValueError(
                "at least one of activity, apk_path, or setup_commands is required"
            )
        return self

    def capabilities(self) -> dict[str, Any]:
        """Return capabilities suitable for UiAutomator2."""
        capabilities: dict[str, Any] = {
            "platformName": "Android",
            "automationName": "UiAutomator2",
            "appPackage": self.package,
            "noReset": self.no_reset,
            "newCommandTimeout": self.new_command_timeout,
        }
        if self.activity:
            capabilities["appActivity"] = self.activity
        if self.apk_path:
            capabilities["app"] = self.apk_path
        if self.udid:
            capabilities["udid"] = self.udid
        return capabilities


def load_target_config(path: str | Path) -> TargetAppConfig:
    """Load and validate a target configuration JSON file."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Unable to load target config: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError("target config must be a JSON object")
    return TargetAppConfig.model_validate(payload)
