"""Compact, deterministic synthesis prompt construction."""

from __future__ import annotations

import json
from pathlib import Path

from c4.c3_interface.contract import C3Verdict
from c4.schemas import FailureJourney


class PromptBuilder:
    """Build prompts from compact journey and optional C3 evidence views."""

    prompt_version = "synthesis_v1"

    def __init__(
        self,
        template_path: Path | None = None,
        include_c3: bool = True,
    ) -> None:
        self.template_path = template_path or (
            Path(__file__).parents[3] / "configs" / "prompts" / "synthesis_v1.txt"
        )
        self.include_c3 = include_c3

    def build(self, journey: FailureJourney, verdict: C3Verdict | None) -> str:
        """Build a deterministic prompt without provider raw payloads."""
        journey_view = {
            "journey_id": journey.journey_id,
            "session_id": journey.session_id,
            "events": [
                {
                    "event_id": event.event_id,
                    "action": event.action,
                    "screen": event.screen,
                    "name": event.name,
                    "locator": event.locator,
                    "value": event.attributes.get("value"),
                }
                for event in journey.events
            ],
            "failure": {
                "exception_type": journey.metadata.get("exception_type", journey.failure.name),
                "message": _failure_message(journey),
                "failing_screen": journey.metadata.get("failing_screen"),
            },
        }
        c3_view = ""
        if self.include_c3 and verdict is not None:
            evidence = json.dumps(verdict.evidence, sort_keys=True)
            c3_view = json.dumps(
                {
                    "has_gui_defect": verdict.has_gui_defect,
                    "defect_type": verdict.defect_type,
                    "confidence": verdict.confidence,
                    "region_labels": [region.label for region in verdict.regions],
                    "evidence": evidence[:1000],
                },
                sort_keys=True,
            )
            c3_view = f"C3 evidence:\n{c3_view}"
        template = self.template_path.read_text(encoding="utf-8")
        return (
            template.replace("{{JOURNEY}}", json.dumps(journey_view, indent=2, sort_keys=True))
            .replace("{{C3_SECTION}}", c3_view)
        )

    def build_retry(
        self,
        base_prompt: str,
        error_message: str,
        previous_response: str,
    ) -> str:
        """Append bounded feedback for a subsequent model attempt."""
        return (
            f"{base_prompt}\n\nYour previous output was invalid: {error_message}.\n"
            "Return only valid JSON in the required format.\n"
            f"Previous output:\n{previous_response[:500]}"
        )


def _failure_message(journey: FailureJourney) -> str:
    error = journey.failure.error or {}
    message = error.get("value") or error.get("message") or journey.failure.name
    return str(message)[:300]
