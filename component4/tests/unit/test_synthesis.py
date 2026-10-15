import ast
import json
from datetime import datetime, timezone

import pytest

from c4.c3_interface import C3Verdict
from c4.schemas import EventKind, EventSource, FailureJourney, NormalizedEvent, SynthStep
from c4.synthesis import AppiumScriptGenerator, PromptBuilder, StepParser
from c4.synthesis.step_parser import StepParsingError


def journey() -> FailureJourney:
    action = NormalizedEvent(
        event_id="payload:breadcrumb:0",
        session_id="session-1",
        source=EventSource.SENTRY,
        kind=EventKind.ACTION,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        name="Submit",
        action="tap",
        locator={"accessibility_id": "submit"},
    )
    failure = action.model_copy(
        update={
            "event_id": "payload:error",
            "kind": EventKind.ERROR,
            "action": None,
            "error": {"type": "ValueError"},
            "name": "ValueError",
        }
    )
    return FailureJourney(
        journey_id="session-1:payload:error",
        session_id="session-1",
        events=[action],
        failure=failure,
        metadata={"action_count": 1},
    )


def verdict() -> C3Verdict:
    return C3Verdict(
        schema_version="1.0",
        verdict_id="verdict-1",
        session_id="session-1",
        has_gui_defect=False,
        confidence=0.0,
    )


def test_prompt_builder_is_deterministic_and_contains_inputs() -> None:
    builder = PromptBuilder()

    first = builder.build(journey(), verdict())
    second = builder.build(journey(), verdict())

    assert first == second
    assert "session-1:payload:error" in first
    assert '"verdict_id": "verdict-1"' in first


def test_step_parser_validates_json_steps() -> None:
    response = json.dumps(
        [
            {
                "index": 0,
                "action": "tap",
                "target": {"accessibility_id": "submit"},
                "value": None,
                "source_event_id": "event-1",
                "metadata": {},
            }
        ]
    )

    steps = StepParser().parse(response)

    assert steps == [
        SynthStep(
            index=0,
            action="tap",
            target={"accessibility_id": "submit"},
            source_event_id="event-1",
        )
    ]


@pytest.mark.parametrize(
    "response",
    ["not json", "{}", '[{"index": 1, "action": "tap"}]', '[{"index": 0}]'],
)
def test_step_parser_rejects_invalid_model_output(response: str) -> None:
    with pytest.raises(StepParsingError):
        StepParser().parse(response)


def test_appium_generator_returns_valid_python_source() -> None:
    steps = [
        SynthStep(
            index=0,
            action="tap",
            target={"accessibility_id": "submit"},
            source_event_id="event-1",
        )
    ]

    script = AppiumScriptGenerator().generate(steps)

    ast.parse(script)
    assert "webdriver.Remote" in script
    assert "accessibility_id" in script
    assert "driver.quit()" in script
