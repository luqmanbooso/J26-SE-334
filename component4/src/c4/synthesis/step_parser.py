"""Validation of model-generated synthesis steps."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from c4.schemas import SynthStep


class StepParsingError(ValueError):
    """Raised when a model response is not a valid step list."""


class StepParser:
    """Parse strict JSON model output into validated ``SynthStep`` objects."""

    def parse(self, response: str | Sequence[Mapping[str, Any]]) -> list[SynthStep]:
        """Parse a JSON array or already-decoded sequence of step objects."""
        payload: Any = response
        if isinstance(response, str):
            try:
                payload = json.loads(response)
            except json.JSONDecodeError as error:
                raise StepParsingError("Model response is not valid JSON") from error
        if not isinstance(payload, list):
            raise StepParsingError("Model response must be a JSON array")
        try:
            steps = [SynthStep.model_validate(item) for item in payload]
        except (ValidationError, TypeError) as error:
            raise StepParsingError("Model response contains an invalid step") from error
        indexes = [step.index for step in steps]
        if indexes != list(range(len(steps))):
            raise StepParsingError("Step indexes must be contiguous and start at zero")
        return steps
