"""Compact model output (action, target, value only) is accepted and linked to its events."""

import json
from datetime import datetime, timedelta, timezone

from c4.schemas import EventKind, EventSource, FailureJourney, NormalizedEvent
from c4.synthesis import PromptBuilder, StepParser, SynthesisService

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _event(index, action, **locator):
    return NormalizedEvent(
        event_id=f"e{index}", session_id="s", source=EventSource.TRACE, kind=EventKind.ACTION,
        timestamp=START + timedelta(seconds=index), name=action, action=action,
        locator=locator, attributes={"value": "ada"} if action == "input" else {},
    )


def _journey():
    failure = NormalizedEvent(
        event_id="boom", session_id="s", source=EventSource.TRACE, kind=EventKind.ERROR,
        timestamp=START + timedelta(seconds=99), name="Crash", error={"type": "Crash"},
    )
    events = [_event(1, "tap", text="Login"), _event(2, "input", resource_id="user"),
              _event(3, "scroll"), _event(4, "tap", text="Login")]
    return FailureJourney(journey_id="j", session_id="s", events=events, failure=failure, metadata={})


COMPACT = json.dumps({"steps": [
    {"action": "tap", "target": {"text": "Login"}},
    {"action": "input", "target": {"resource_id": "user"}, "value": "ada"},
    {"action": "scroll"},
    {"action": "tap", "target": {"text": "Login"}},
]})


def test_steps_without_index_value_source_or_metadata_are_accepted() -> None:
    steps = StepParser().parse(COMPACT)

    assert [s.index for s in steps] == [0, 1, 2, 3]
    assert [s.action for s in steps] == ["tap", "input", "scroll", "tap"]
    assert steps[1].value == "ada" and steps[2].target == {} and steps[0].source_event_id is None


def test_an_input_step_without_a_value_is_still_rejected() -> None:
    from c4.synthesis.step_parser import StepParsingError
    import pytest

    bad = json.dumps({"steps": [{"action": "input", "target": {"resource_id": "user"}}]})
    with pytest.raises(StepParsingError, match="non-null value"):
        StepParser().parse(bad)


def test_coverage_links_each_step_to_its_event_whatever_the_model_wrote() -> None:
    journey = _journey()
    wrong = json.dumps({"steps": [
        {"action": "tap", "target": {"text": "Login"}, "source_event_id": "made-up"},
        {"action": "input", "target": {"resource_id": "user"}, "value": "ada", "source_event_id": "e4"},
        {"action": "scroll"},
        {"action": "tap", "target": {"text": "Login"}},
    ]})
    steps = StepParser().validate_coverage(StepParser().validate_grounding(StepParser().parse(wrong), journey), journey)

    assert [s.source_event_id for s in steps] == ["e1", "e2", "e3", "e4"]


class _LLM:
    model = "fake"

    def __init__(self, response):
        self.response, self.prompts = response, []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.response


def test_service_generates_from_compact_output_and_keeps_event_links() -> None:
    result = SynthesisService(_LLM(COMPACT), use_c3=False).synthesize(_journey())

    assert result.status == "generated" and len(result.attempts) == 1
    assert [s.source_event_id for s in result.steps] == ["e1", "e2", "e3", "e4"]
    assert "ada" in result.script


def test_prompt_asks_for_compact_steps() -> None:
    prompt = PromptBuilder(include_c3=False).build(_journey(), None)

    assert "Do not output index, source_event_id or metadata" in prompt
    assert '"metadata"' not in prompt.split("Journey:")[0]


def test_evaluation_counts_retries_not_parts_as_attempts() -> None:
    from c4.synthesis.service import SynthesisAttempt
    from evaluation.run_synthesis_eval import _row

    journey = _journey()
    result = SynthesisService(_LLM(COMPACT), use_c3=False).synthesize(journey)

    def attempts(*numbers):
        return result.model_copy(update={"attempts": [SynthesisAttempt(attempt=n, response_chars=1) for n in numbers]})

    assert _row(journey, attempts(1), None)["attempts"] == 1
    assert _row(journey, attempts(1, 1, 1), None)["attempts"] == 1
    assert _row(journey, attempts(1, 1, 2, 1), None)["attempts"] == 2
    assert _row(journey, attempts(1, 2, 3), None)["attempts"] == 3
