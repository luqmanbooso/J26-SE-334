"""A generated test must cover every replayable event of its journey, in order."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from c4.schemas import EventKind, EventSource, FailureJourney, NormalizedEvent
from c4.synthesis import PromptBuilder, StepParser, SynthesisService
from c4.synthesis.step_parser import StepParsingError

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _event(index, action, **locator):
    return NormalizedEvent(
        event_id=f"e{index}", session_id="s", source=EventSource.TRACE, kind=EventKind.ACTION,
        timestamp=START + timedelta(seconds=index), name=action, action=action, locator=locator,
    )


def _journey(*events):
    failure = NormalizedEvent(
        event_id="boom", session_id="s", source=EventSource.TRACE, kind=EventKind.ERROR,
        timestamp=START + timedelta(seconds=99), name="Crash", error={"type": "Crash"},
    )
    return FailureJourney(journey_id="j", session_id="s", events=list(events), failure=failure,
                          metadata={"action_count": len(events)})


def _steps(*items):
    return StepParser().parse(json.dumps({"steps": [
        {"index": i, "action": action, "target": target, "value": value, "source_event_id": None}
        for i, (action, target, value) in enumerate(items)
    ]}))


JOURNEY = _journey(
    _event(1, "tap", text="Next"),
    _event(2, "tap", resource_id="app:id/ok", text="OK"),
    _event(3, "input", resource_id="app:id/name", value="x"),
    _event(4, "scroll"),
    _event(5, "back"),
    _event(6, "tap", text="Next"),
)
ALL = [
    ("tap", {"text": "Next"}, None), ("tap", {"resource_id": "app:id/ok"}, None),
    ("input", {"resource_id": "app:id/name"}, "x"), ("scroll", {}, None), ("back", {}, None),
    ("tap", {"text": "Next"}, None),
]


def test_complete_steps_pass_even_with_fewer_locator_keys_and_extra_steps() -> None:
    parser = StepParser()
    assert parser.validate_coverage(_steps(*ALL), JOURNEY)
    assert parser.validate_coverage(_steps(*ALL, ("tap", {"text": "Extra"}, None)), JOURNEY)


def test_repeated_identical_events_must_all_appear() -> None:
    journey = _journey(_event(1, "tap", text="Next"), _event(2, "tap", text="Next"), _event(3, "tap", text="Next"))
    one = _steps(("tap", {"text": "Next"}, None))
    with pytest.raises(StepParsingError, match="omit 2 of 3 journey events.*e2, e3"):
        StepParser().validate_coverage(one, journey)


def test_a_single_step_for_a_three_event_journey_is_rejected() -> None:
    journey = _journey(_event(1, "tap", text="How to run"), _event(2, "tap", resource_id="android:id/button1"),
                       _event(3, "tap", resource_id="org.kiwix:id/pause"))
    only_middle = _steps(("tap", {"resource_id": "android:id/button1"}, None))
    with pytest.raises(StepParsingError, match="omit 2 of 3"):
        StepParser().validate_coverage(only_middle, journey)


def test_steps_in_the_wrong_order_or_with_foreign_values_do_not_cover() -> None:
    reordered = [ALL[1], ALL[0], *ALL[2:]]
    with pytest.raises(StepParsingError):
        StepParser().validate_coverage(_steps(*reordered), JOURNEY)
    foreign = [("tap", {"text": "Other"}, None), *ALL[1:]]
    with pytest.raises(StepParsingError, match="omit"):
        StepParser().validate_coverage(_steps(*foreign), JOURNEY)


def test_events_that_cannot_become_steps_are_not_required() -> None:
    journey = _journey(_event(1, "tap"), _event(2, "long_press", text="x"), _event(3, "tap", text="Go"))
    assert StepParser().validate_coverage(_steps(("tap", {"text": "Go"}, None)), journey)


class _LLM:
    model = "fake"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.responses.pop(0)


def _response(items):
    return json.dumps({"steps": [{"index": i, "action": a, "target": t, "value": v, "source_event_id": None}
                                 for i, (a, t, v) in enumerate(items)]})


def test_service_retries_with_feedback_until_the_journey_is_covered() -> None:
    llm = _LLM(_response(ALL[:1]), _response(ALL))

    result = SynthesisService(llm, use_c3=False).synthesize(JOURNEY)

    assert result.status == "generated" and len(result.steps) == 6 and len(result.attempts) == 2
    assert "omit 5 of 6 journey events" in llm.prompts[1] and "missing: e2" in llm.prompts[1]
    assert result.attempts[0].error and "omit" in result.attempts[0].error


def test_service_reports_failure_when_the_model_never_covers_the_journey() -> None:
    llm = _LLM(*[_response(ALL[:1])] * 3)

    result = SynthesisService(llm, use_c3=False).synthesize(JOURNEY)

    assert result.status == "failed" and result.script is None and "omit" in result.reason


def test_prompt_version_two_demands_one_step_per_event() -> None:
    builder = PromptBuilder(include_c3=False)
    prompt = builder.build(JOURNEY, None)

    assert builder.prompt_version == "synthesis_v2"
    assert "exactly one step for every journey event" in prompt and "repeated identical events" in prompt
