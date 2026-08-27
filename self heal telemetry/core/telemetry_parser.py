import json
from typing import List, Dict, Any

class TelemetryParser:
    """Extracts reproducible user action flows from Sentry / Firebase telemetry."""
    @staticmethod
    def load_trace(json_path: str) -> List[Dict[str, Any]]:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        breadcrumbs = data.get("breadcrumbs", [])
        print(f"[Telemetry Ingestion] Extracted {len(breadcrumbs)} interaction breadcrumbs from {json_path}")
        return breadcrumbs
