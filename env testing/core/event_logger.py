import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

class EventLogger:
    """Logs timestamped perturbation events with runtime telemetry for failure attribution."""

    def __init__(self, output_path: str = "perturbation_event_log.json"):
        self.output_path = output_path
        self.events: List[Dict[str, Any]] = []

    def record(
        self,
        category: str,
        action: str,
        parameters: Dict[str, Any],
        status: str = "APPLIED",
        telemetry_snapshot: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Records an environmental perturbation event with high-precision timestamp."""
        epoch_ms = int(time.time() * 1000)
        timestamp_iso = datetime.now().isoformat()

        entry = {
            "epoch_ms": epoch_ms,
            "timestamp": timestamp_iso,
            "category": category,
            "action": action,
            "parameters": parameters,
            "status": status,
            "telemetry": telemetry_snapshot or {}
        }
        self.events.append(entry)
        param_summary = ", ".join(f"{k}={v}" for k, v in parameters.items())
        print(f"[{timestamp_iso}] [{category}] {action} ({status}) -> {param_summary}")
        return entry

    def get_events(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns recorded events, optionally filtered by category."""
        if category:
            return [e for e in self.events if e.get("category") == category]
        return list(self.events)

    def get_recent(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Returns the most recent events."""
        return self.events[-limit:]

    def clear(self) -> None:
        """Clears in-memory events."""
        self.events = []

    def save(self) -> None:
        """Persists perturbation event log to disk."""
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=2)
        print(f"[+] Perturbation telemetry written ({len(self.events)} events) to: {self.output_path}")
