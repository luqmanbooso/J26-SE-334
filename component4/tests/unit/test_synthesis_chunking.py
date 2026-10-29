"""Long journeys are generated in ordered parts, each with its own retries and checks."""

import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from c4.schemas import EventKind, EventSource, FailureJourney, NormalizedEvent
from c4.synthesis import SynthesisService

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _journey(count):
    events = [
        NormalizedEvent(
            event_id=f"e{i}", session_id="s", source=EventSource.TRACE, kind=EventKind.ACTION,
            timestamp=START + timedelta(seconds=i), name="tap", action="tap", locator={"text": f"item {i}"},
        )
        for i in range(count)
    ]
    failure = NormalizedEvent(
        event_id="boom", session_id="s", source=EventSource.TRACE, kind=EventKind.ERROR,
        timestamp=START + timedelta(seconds=count + 1), name="Crash", error={"type": "Crash"},
    )
    return FailureJourney(journey_id="j", session_id="s", events=events, failure=failure, metadata={})


def _steps_for(prompt, skip_last=False):
    ids = re.findall(r'"event_id": "(e\d+)"', prompt)
    ids = ids[:-1] if skip_last else ids
    return json.dumps({"steps": [
        {"index": n, "action": "tap", "target": {"text": f"item {event_id[1:]}"}, "value": None,
         "source_event_id": event_id} for n, event_id in enumerate(ids)
    ]})


class _LLM:
    """Answers each prompt with a step for every event it lists, optionally misbehaving on one part."""

    model = "fake"

    def __init__(self, bad_part_event=None, bad_times=0):
        self.prompts = []
        self.bad_part_event = bad_part_event
        self.bad_times = bad_times

    def generate(self, prompt):
        self.prompts.append(prompt)
        first_id = re.search(r'"event_id": "(e\d+)"', prompt).group(1)
        if self.bad_part_event == first_id and self.bad_times > 0:
            self.bad_times -= 1
            return _steps_for(prompt, skip_last=True)
        return _steps_for(prompt)


def test_long_journey_is_generated_in_ordered_parts_and_merged() -> None:
    llm = _LLM()

    result = SynthesisService(llm, use_c3=False, chunk_size=8).synthesize(_journey(20))

    assert result.status == "generated" and len(llm.prompts) == 3
    assert [s.index for s in result.steps] == list(range(20))
    assert [s.target["text"] for s in result.steps] == [f"item {i}" for i in range(20)]
    assert all(f"item {i}" in result.script for i in range(20))
    assert '"event_id": "e0"' in llm.prompts[0] and '"event_id": "e8"' not in llm.prompts[0]
    assert '"event_id": "e8"' in llm.prompts[1] and '"event_id": "e0"' not in llm.prompts[1]
    assert [a.part for a in result.attempts] == ["part 1 of 3", "part 2 of 3", "part 3 of 3"]


def test_journeys_beyond_the_thirty_step_limit_can_be_generated() -> None:
    result = SynthesisService(_LLM(), use_c3=False, chunk_size=8).synthesize(_journey(40))
    assert result.status == "generated" and len(result.steps) == 40


def test_only_the_failing_part_is_retried() -> None:
    llm = _LLM(bad_part_event="e8", bad_times=1)

    result = SynthesisService(llm, use_c3=False, chunk_size=8).synthesize(_journey(20))

    assert result.status == "generated" and len(llm.prompts) == 4
    assert [(a.part, a.error is None) for a in result.attempts] == [
        ("part 1 of 3", True), ("part 2 of 3", False), ("part 2 of 3", True), ("part 3 of 3", True),
    ]
    assert "omit 1 of 8 journey events" in llm.prompts[2] and "missing: e15" in llm.prompts[2]


def test_a_part_that_never_passes_fails_the_journey_and_names_the_part() -> None:
    llm = _LLM(bad_part_event="e8", bad_times=99)

    result = SynthesisService(llm, use_c3=False, chunk_size=8, max_attempts=2).synthesize(_journey(20))

    assert result.status == "failed" and result.script is None and result.steps == []
    assert result.reason.startswith("part 2 of 3: ") and "omit" in result.reason
    assert len(llm.prompts) == 1 + 2


def test_short_journeys_and_disabled_chunking_use_one_request() -> None:
    short = _LLM()
    assert SynthesisService(short, use_c3=False, chunk_size=8).synthesize(_journey(8)).status == "generated"
    assert len(short.prompts) == 1

    whole = _LLM()
    result = SynthesisService(whole, use_c3=False, chunk_size=None).synthesize(_journey(20))
    assert result.status == "generated" and len(whole.prompts) == 1
    assert [a.part for a in result.attempts] == [None]


def test_chunk_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        SynthesisService(_LLM(), chunk_size=0)


def test_progress_names_each_part_attempt_and_rejection() -> None:
    messages = []
    llm = _LLM(bad_part_event="e8", bad_times=1)

    SynthesisService(llm, use_c3=False, chunk_size=8, progress=messages.append).synthesize(_journey(20))

    assert messages[0] == "Generating part 1 of 3, attempt 1 of 3"
    assert "part 2 of 3: attempt 1 rejected, Steps omit 1 of 8 journey events" in messages[2]
    assert "Generating part 2 of 3, attempt 2 of 3" in messages
    assert messages[-1] == "Generating part 3 of 3, attempt 1 of 3"


def test_progress_for_a_short_journey_and_a_failing_callback() -> None:
    messages = []
    SynthesisService(_LLM(), use_c3=False, progress=messages.append).synthesize(_journey(3))
    assert messages == ["Generating test steps, attempt 1 of 3"]

    def broken(message):
        raise RuntimeError("ui closed")

    assert SynthesisService(_LLM(), use_c3=False, progress=broken).synthesize(_journey(3)).status == "generated"
