"""Deterministic prompt construction for test synthesis."""

from __future__ import annotations

import json

from c4.c3_interface.contract import C3Verdict
from c4.schemas import FailureJourney


class PromptBuilder:
    """Build a constrained JSON-only synthesis prompt."""

    def build(self, journey: FailureJourney, verdict: C3Verdict) -> str:
        """Serialize journey and C3 evidence in a stable prompt format."""
        input_data = {
            "journey": journey.model_dump(mode="json"),
            "c3_verdict": verdict.model_dump(mode="json"),
        }
        serialized = json.dumps(input_data, indent=2, sort_keys=True)
        return (
            "You are a mobile test synthesis engine. "
            "Convert the failure journey into a minimal executable Appium flow.\n"
            "Return only a JSON array of steps. Each step must contain "
            "index, action, target, value, source_event_id, and metadata.\n"
            "Use target locator attributes from the journey when available. "
            "Do not invent credentials or destructive actions.\n\n"
            f"INPUT:\n{serialized}\n"
        )
