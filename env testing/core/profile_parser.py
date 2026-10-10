import os
import json
from typing import Dict, Any, Tuple
import yaml

class ProfileValidationError(Exception):
    """Raised when an environmental stress profile violates schema constraints."""
    pass

class ProfileParser:
    """Parses and validates structured YAML and JSON environmental stress profiles.
    
    Implements specification defined in HEART Proposal Section 5 (Functional Requirements).
    """

    ALLOWED_THERMAL_STATES = {"None", "Normal", "Warn", "Critical"}
    ALLOWED_BANDWIDTH_PROFILES = {"nominal", "lte", "3g", "edge", "offline", "unthrottled"}

    @classmethod
    def parse_file(cls, filepath: str) -> Dict[str, Any]:
        """Loads and parses a stress profile from a YAML or JSON file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Profile configuration file not found: {filepath}")

        ext = os.path.splitext(filepath)[1].lower()
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if ext in [".yaml", ".yml"]:
            return cls.parse_yaml_string(content)
        elif ext == ".json":
            return cls.parse_json_string(content)
        else:
            raise ProfileValidationError(f"Unsupported profile extension: '{ext}'. Must be .yaml, .yml, or .json")

    @classmethod
    def parse_yaml_string(cls, yaml_content: str) -> Dict[str, Any]:
        """Parses and validates YAML string."""
        try:
            data = yaml.safe_load(yaml_content)
        except Exception as e:
            raise ProfileValidationError(f"YAML parsing error: {str(e)}")

        if not isinstance(data, dict):
            raise ProfileValidationError("Profile configuration must be a key-value mapping.")

        return cls.validate_schema(data)

    @classmethod
    def parse_json_string(cls, json_content: str) -> Dict[str, Any]:
        """Parses and validates JSON string."""
        try:
            data = json.loads(json_content)
        except Exception as e:
            raise ProfileValidationError(f"JSON parsing error: {str(e)}")

        if not isinstance(data, dict):
            raise ProfileValidationError("Profile configuration must be a key-value mapping.")

        return cls.validate_schema(data)

    @classmethod
    def validate_schema(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Validates stress profile fields and types against HEART specifications."""
        profile: Dict[str, Any] = {
            "name": str(raw.get("name", "Custom Stress Profile")),
            "description": str(raw.get("description", "")),
            "targetModule": str(raw.get("targetModule", "Checkout Service")),
            "cpuStress": int(raw.get("cpuStress", 0)),
            "ramStress": int(raw.get("ramStress", 0)),
            "diskIo": int(raw.get("diskIo", 0)),
            "latency": int(raw.get("latency", 0)),
            "packetLoss": int(raw.get("packetLoss", 0)),
            "dnsFailure": bool(raw.get("dnsFailure", False)),
            "thermalState": str(raw.get("thermalState", "None")),
            "networkProfile": str(raw.get("networkProfile", "Nominal")),
            "interruptionType": str(raw.get("interruptionType", "None")),
            "interruptionFreq": int(raw.get("interruptionFreq", 0))
        }

        # Range checks
        if not (0 <= profile["cpuStress"] <= 100):
            raise ProfileValidationError(f"cpuStress must be between 0 and 100, got {profile['cpuStress']}")

        if not (0 <= profile["ramStress"] <= 100):
            raise ProfileValidationError(f"ramStress must be between 0 and 100, got {profile['ramStress']}")

        if not (0 <= profile["latency"] <= 10000):
            raise ProfileValidationError(f"latency must be between 0 and 10000 ms, got {profile['latency']}")

        if not (0 <= profile["packetLoss"] <= 100):
            raise ProfileValidationError(f"packetLoss must be between 0 and 100 %, got {profile['packetLoss']}")

        if profile["thermalState"] not in cls.ALLOWED_THERMAL_STATES:
            raise ProfileValidationError(
                f"thermalState '{profile['thermalState']}' invalid. Allowed: {cls.ALLOWED_THERMAL_STATES}"
            )

        return profile

    @classmethod
    def to_yaml_string(cls, profile: Dict[str, Any]) -> str:
        """Serializes a validated profile to formatted YAML string."""
        validated = cls.validate_schema(profile)
        return yaml.dump(validated, default_flow_style=False, sort_keys=False)
