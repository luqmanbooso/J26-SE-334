import json
import time
from datetime import datetime
from typing import Any, Dict, List

class EventLogger:
    """Logs timestamped perturbation events for failure attribution."""

    def __init__(self, output_path: str = "perturbation_event_log.json"):
        self.output_path = output_path
        self.events: List[Dict[str, Any]] = []

    def record(self, category: str, action: str, parameters: Dict[str, Any], status: str = "APPLIED") -> None:
        timestamp_iso = datetime.now().isoformat()
        epoch_ms = int(time.time() * 1000)

        entry = {
            "epoch_ms": epoch_ms,
            "timestamp": timestamp_iso,
            "category": category,
            "action": action,
            "parameters": parameters,
            "status": status
        }
        self.events.append(entry)
        print(f"[{timestamp_iso}] [{category}] {action} -> {parameters}")

    def save(self) -> None:
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=2)
        print(f"[+] Perturbation telemetry written to: {self.output_path}")
