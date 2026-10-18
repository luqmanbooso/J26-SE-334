import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from c4.c3_interface import C3Verdict
from c4.schemas import EventKind, EventSource, FailureJourney, NormalizedEvent, SynthStep
from c4.synthesis import (
    AppiumScriptGenerator,
    PromptBuilder,
    StepParser,
    SynthesisService,
)
from c4.synthesis.qwen_client import OllamaQwenClient
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
    assert '"has_gui_defect": false' in first
    assert "Allowed actions: tap, input, navigate, scroll, back." in first
    assert '"raw"' not in first


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
    assert "AppiumBy.ACCESSIBILITY_ID" in script
    assert "**" not in script
    assert "driver.quit()" in script


def test_appium_generator_compiles_all_action_types() -> None:
    steps = [
        SynthStep(index=0, action="tap", target={"resource_id": "submit"}),
        SynthStep(index=1, action="input", target={"text": "Name"}, value="Ada"),
        SynthStep(index=2, action="navigate", target={"xpath": "//button"}),
        SynthStep(index=3, action="back"),
        SynthStep(index=4, action="scroll"),
    ]

    script = AppiumScriptGenerator().generate(steps)

    compile(script, "<generated>", "exec")
    assert "AppiumBy.ID" in script
    assert 'driver.execute_script("mobile: scrollGesture"' in script
    assert "driver.swipe(" not in script


def test_text_locator_escapes_quote_and_backslash() -> None:
    script = AppiumScriptGenerator().generate(
        [
            SynthStep(
                index=0,
                action="tap",
                target={"text": 'Save "as" C:\\tmp'},
            )
        ]
    )

    compile(script, "<generated>", "exec")
    expected_locator = 'new UiSelector().text("Save \\"as\\" C:\\\\tmp")'
    assert repr(expected_locator) in script


def test_parser_accepts_think_fence_wrapper_and_bare_array() -> None:
    parser = StepParser()
    wrapped = '<think>reasoning</think>\n```json\n{"steps":[{"index":0,"action":"back"}]}\n```'

    assert parser.parse(wrapped)[0].action == "back"
    assert parser.parse('[{"index":0,"action":"back"}]')[0].action == "back"


@pytest.mark.parametrize(
    "payload",
    [
        '[{"index":0,"action":"delete_account"}]',
        '[{"index":0,"action":"tap"}]',
        '[{"index":0,"action":"input","target":{"text":"Name"}}]',
        '[{"index":0,"action":"tap","target":{"bad":"x"}}]',
        json.dumps(
            [{"index": index, "action": "back"} for index in range(31)]
        ),
    ],
)
def test_parser_rejects_unsafe_or_oversized_steps(payload: str) -> None:
    with pytest.raises(StepParsingError):
        StepParser().parse(payload)


def test_parser_reindexes_steps() -> None:
    steps = StepParser().parse(
        '[{"index":4,"action":"back"},{"index":9,"action":"scroll"}]'
    )

    assert [step.index for step in steps] == [0, 1]
    assert all(step.metadata["reindexed"] is True for step in steps)


def test_validate_grounding_marks_locators_and_clears_unknown_source() -> None:
    steps = StepParser().parse(
        json.dumps(
            [
                {
                    "index": 0,
                    "action": "tap",
                    "target": {"accessibility_id": "submit"},
                    "source_event_id": "unknown",
                },
                {
                    "index": 1,
                    "action": "tap",
                    "target": {"text": "invented"},
                    "source_event_id": "payload:breadcrumb:0",
                },
            ]
        )
    )

    grounded = StepParser().validate_grounding(steps, journey())

    assert grounded[0].metadata["grounded"] is True
    assert grounded[0].source_event_id is None
    assert grounded[1].metadata["grounded"] is False


def test_prompt_can_omit_c3_and_retry_contains_error() -> None:
    builder = PromptBuilder(include_c3=False)
    prompt = builder.build(journey(), verdict())
    retry = builder.build_retry(prompt, "bad action", "invalid response")

    assert "C3 evidence:" not in prompt
    assert "bad action" in retry
    assert "invalid response" in retry


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.prompts: list[str] = []
        self.model = "fake-model"

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.responses.pop(0)


class FakeC3:
    def __init__(self) -> None:
        self.calls = 0

    def get_verdict(self, session_id: str, failure: NormalizedEvent, journey: FailureJourney) -> C3Verdict:
        self.calls += 1
        return verdict()


VALID_RESPONSE = json.dumps(
    [
        {
            "index": 0,
            "action": "tap",
            "target": {"accessibility_id": "submit"},
            "source_event_id": "payload:breadcrumb:0",
        }
    ]
)


def test_synthesis_service_generates_on_first_attempt() -> None:
    llm = FakeLLM([VALID_RESPONSE])

    result = SynthesisService(llm).synthesize(journey())

    assert result.status == "generated"
    assert len(result.attempts) == 1
    assert result.script is not None


def test_synthesis_service_retries_invalid_output() -> None:
    llm = FakeLLM(["not json", VALID_RESPONSE])

    result = SynthesisService(llm).synthesize(journey())

    assert result.status == "generated"
    assert len(result.attempts) == 2
    assert "Model response" in llm.prompts[1]


def test_synthesis_service_fails_after_max_attempts() -> None:
    llm = FakeLLM(["not json", "still not json"])

    result = SynthesisService(llm, max_attempts=2).synthesize(journey())

    assert result.status == "failed"
    assert len(result.attempts) == 2
    assert result.reason


def test_synthesis_service_skips_non_reproducible_without_llm_call() -> None:
    llm = FakeLLM([VALID_RESPONSE])
    failing_journey = journey().model_copy(
        update={"metadata": {"reproducible": False}}
    )

    result = SynthesisService(llm).synthesize(failing_journey)

    assert result.status == "skipped_not_reproducible"
    assert llm.prompts == []


def test_synthesis_service_can_disable_c3() -> None:
    llm = FakeLLM([VALID_RESPONSE])
    c3 = FakeC3()

    result = SynthesisService(llm, c3_client=c3, use_c3=False).synthesize(journey())

    assert result.c3_used is False
    assert c3.calls == 0


def test_qwen_client_request_body(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class Response:
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"response":"[]"}'

    def fake_urlopen(request: Any, timeout: float) -> Response:
        captured.update(json.loads(request.data.decode("utf-8")))
        return Response()

    monkeypatch.setattr("c4.synthesis.qwen_client.urlopen", fake_urlopen)
    client = OllamaQwenClient()

    assert client.generate("prompt") == "[]"
    assert captured["format"] == "json"
    assert captured["think"] is False
    assert captured["options"]["num_ctx"] == 8192
    assert captured["options"]["seed"] == 42


@pytest.mark.live_llm
def test_live_qwen_synthesis() -> None:
    if __import__("os").environ.get("C4_LIVE_LLM") != "1":
        pytest.skip("Set C4_LIVE_LLM=1 to run Ollama integration test")
    result = SynthesisService(OllamaQwenClient()).synthesize(journey())
    assert result.status == "generated"
