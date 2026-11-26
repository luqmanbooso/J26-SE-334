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

        raw_timeline = raw.get("timeline")
        if raw_timeline is not None:
            if not isinstance(raw_timeline, list):
                raise ProfileValidationError("'timeline' must be a list of scheduled event objects.")
            normalized_timeline = []
            for idx, item in enumerate(raw_timeline):
                if not isinstance(item, dict) or not item.get("action"):
                    raise ProfileValidationError(f"Timeline entry #{idx} must be a dict with 'action'.")
                offset_ms = item.get("offset_ms")
                if offset_ms is None:
                    offset_ms = int(float(item.get("offset_sec", 0.0)) * 1000)
                offset_ms = int(offset_ms)
                if offset_ms < 0:
                    raise ProfileValidationError(f"Timeline entry #{idx} offset_ms cannot be negative.")
                normalized_timeline.append({
                    "offset_ms": offset_ms,
                    "step": str(item.get("step", "IMMEDIATE")).upper(),
                    "action": str(item["action"]),
                    "params": dict(item.get("params") or {}),
                })
            normalized_timeline.sort(key=lambda e: e["offset_ms"])
            profile["timeline"] = normalized_timeline

        return profile

    @classmethod
    def compile_timeline(cls, raw: Dict[str, Any]) -> list:
        """Compiles a YAML/JSON stress profile into an ordered executable event timeline."""
        validated = cls.validate_schema(raw)
        if validated.get("timeline"):
            return list(validated["timeline"])

        timeline = []
        if validated["cpuStress"] > 0:
            timeline.append({"offset_ms": 0, "step": "PRE_INPUT", "action": "cpu", "params": {"target_pct": validated["cpuStress"]}})
        if validated["ramStress"] > 0:
            timeline.append({"offset_ms": 0, "step": "PRE_INPUT", "action": "ram", "params": {"pressure_pct": validated["ramStress"]}})
        if validated["diskIo"] > 0:
            timeline.append({"offset_ms": 0, "step": "PRE_INPUT", "action": "disk_io", "params": {"duration_mb": max(10, validated["diskIo"] // 2)}})
        if validated["thermalState"] != "None":
            timeline.append({"offset_ms": 50, "step": "PRE_INPUT", "action": "thermal", "params": {"state": validated["thermalState"]}})
        if validated["latency"] > 0:
            timeline.append({"offset_ms": 100, "step": "MID_TRANSACTION", "action": "latency", "params": {"latency_ms": validated["latency"]}})
        if validated["packetLoss"] > 0:
            timeline.append({"offset_ms": 100, "step": "MID_TRANSACTION", "action": "packet_loss", "params": {"loss_pct": validated["packetLoss"]}})
        if validated["dnsFailure"]:
            timeline.append({"offset_ms": 150, "step": "MID_TRANSACTION", "action": "dns_fail", "params": {"enabled": True}})
        net_prof = validated["networkProfile"].lower()
        if "edge" in net_prof or "2g" in net_prof:
            timeline.append({"offset_ms": 100, "step": "MID_TRANSACTION", "action": "bandwidth", "params": {"profile": "edge"}})
        elif "cellular dead zone" in net_prof or "offline" in net_prof:
            timeline.append({"offset_ms": 100, "step": "MID_TRANSACTION", "action": "network_mode", "params": {"mode": "offline"}})
        elif "4g" in net_prof:
            timeline.append({"offset_ms": 100, "step": "MID_TRANSACTION", "action": "bandwidth", "params": {"profile": "lte"}})
        itype = validated["interruptionType"]
        if "Call" in itype:
            timeline.append({"offset_ms": 200, "step": "ASYNC_WAIT", "action": "call", "params": {"phone_number": "15555215554"}})
        if "Low Battery" in itype:
            timeline.append({"offset_ms": 200, "step": "PRE_INPUT", "action": "battery", "params": {"level": 3, "unplugged": True}})
        if "LMK" in itype:
            timeline.append({"offset_ms": 250, "step": "ASYNC_WAIT", "action": "ram", "params": {"pressure_pct": 95}})
        return timeline

    @classmethod
    def to_yaml_string(cls, profile: Dict[str, Any]) -> str:
        """Serializes a validated profile to formatted YAML string."""
        validated = cls.validate_schema(profile)
        return yaml.dump(validated, default_flow_style=False, sort_keys=False)
