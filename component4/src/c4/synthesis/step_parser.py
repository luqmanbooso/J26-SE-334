"""Cleaning and validation of model-generated synthesis steps."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from c4.schemas import FailureJourney, SynthStep
from c4.sessionization.actions import CanonicalAction, canonicalize_action
from c4.synthesis.locators import ALLOWED_TARGET_KEYS


class StepParsingError(ValueError):
    """Raised when a model response is not a valid synthesis result."""


class StepParser:
    """Parse, constrain, and ground model-generated steps."""

    def parse(self, response: str | Sequence[Mapping[str, Any]]) -> list[SynthStep]:
        """Parse a JSON array or ``{"steps": [...]}`` response."""
        payload: Any = response
        if isinstance(response, str):
            payload = _extract_json(response)
        if isinstance(payload, Mapping):
            payload = payload.get("steps")
        if not isinstance(payload, list):
            raise StepParsingError("Model response must contain a JSON step array")
        if len(payload) > 30:
            raise StepParsingError("Model response contains more than 30 steps")
        steps: list[SynthStep] = []
        try:
            for item in payload:
                if not isinstance(item, Mapping):
                    raise StepParsingError("Each step must be an object")
                action = canonicalize_action(_string(item.get("action")))
                if action is CanonicalAction.UNKNOWN:
                    raise StepParsingError(f"Unsupported action: {item.get('action')!r}")
                target = item.get("target", {})
                if not isinstance(target, Mapping):
                    raise StepParsingError("Step target must be an object")
                target_dict = {str(key): str(value) for key, value in target.items()}
                if set(target_dict) - ALLOWED_TARGET_KEYS:
                    raise StepParsingError("Step target contains an unsupported key")
                if action in {
                    CanonicalAction.TAP,
                    CanonicalAction.INPUT,
                    CanonicalAction.NAVIGATE,
                } and not target_dict:
                    raise StepParsingError(f"{action.value} requires a target")
                if action is CanonicalAction.INPUT and item.get("value") is None:
                    raise StepParsingError("input requires a non-null value")
                steps.append(
                    SynthStep.model_validate(
                        {
                            **dict(item),
                            "action": action.value,
                            "target": target_dict,
                        }
                    )
                )
        except (ValidationError, TypeError) as error:
            raise StepParsingError("Model response contains an invalid step") from error
        indexes = [step.index for step in steps]
        if indexes != list(range(len(steps))):
            for index, step in enumerate(steps):
                step.index = index
                step.metadata["reindexed"] = True
        return steps

    def validate_grounding(
        self,
        steps: list[SynthStep],
        journey: FailureJourney,
    ) -> list[SynthStep]:
        """Mark locator grounding and clear unknown source event references."""
        events = [*journey.events, journey.failure]
        event_ids = {event.event_id for event in events}
        locator_values = {
            value
            for event in journey.events
            for value in event.locator.values()
        }
        for step in steps:
            step.metadata["grounded"] = all(
                value in locator_values for value in step.target.values()
            )
            if step.source_event_id not in event_ids:
                step.source_event_id = None
        return steps


def _extract_json(response: str) -> Any:
    cleaned = re.sub(r"<think>.*?</think>", "", response, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"```(?:json)?", "", cleaned, flags=re.IGNORECASE).replace("```", "")
    decoder = json.JSONDecoder()
    for index, character in enumerate(cleaned):
        if character not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, (list, dict)):
            return value
    raise StepParsingError("Model response does not contain a JSON object or array")


def _string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
