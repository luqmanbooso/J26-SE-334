"""Regression tests for the C3 -> journey -> synthesis -> execution -> healing UI flow."""

import json
from datetime import datetime, timezone
from pathlib import Path

from c4.c3_interface import C3Verdict, InboxC3Client
from c4.execution.models import ExecutionResult, ExecutionStatus, FailureInfo, FailureKind
from c4.ui.controller import C4DemoController

SAMPLE = Path(__file__).parents[2] / "src" / "c4" / "ui" / "samples" / "sentry.json"
TARGET = {"package": "com.android.settings", "activity": ".Settings"}
RESPONSE = json.dumps(
    [{"index": 0, "action": "tap", "target": {"text": "Network and internet"},
      "source_event_id": None}]
)
PAGE = (
    '<hierarchy><node class="android.widget.FrameLayout" bounds="[0,0][800,800]">'
    '<node class="android.widget.TextView" text="Network &amp; internet" clickable="true" '
    'enabled="true" bounds="[20,0][800,80]" />'
    '<node class="android.widget.TextView" text="Display" clickable="true" '
    'enabled="true" bounds="[20,80][800,160]" /></node></hierarchy>'
)


class FakeLLM:
    model = "fake"

    def __init__(self, source_event_id: str) -> None:
        self.prompts: list[str] = []
        self.response = RESPONSE.replace("null", json.dumps(source_event_id))

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


class FakeExecution:
    """Records executions; fails the first run with a locator failure, passes reruns."""

    def __init__(self, page: Path | None = None) -> None:
        self.page = page
        self.scripts: list[str] = []

    def execute(self, synthesis, *, runs_dir="runs", run_id=None, **_):
        self.scripts.append(synthesis.script)
        run_id = run_id or "run-1"
        first = len(self.scripts) == 1 and self.page is not None
        failure = FailureInfo(
            step_index=0, action="tap", kind=FailureKind.LOCATOR_NOT_FOUND,
            page_source_path=str(self.page),
        ) if first else None
        return ExecutionResult(
            run_id=run_id, journey_id=synthesis.journey_id,
            status=ExecutionStatus.FAILED if first else ExecutionStatus.PASSED,
            started_at=datetime.now(timezone.utc), elapsed_seconds=0.0, failure=failure,
        )


def _setup(tmp_path):
    config = tmp_path / "target.json"
    config.write_text(json.dumps(TARGET), encoding="utf-8")
    return str(config)


def _verdict(verdict_id: str, session_id: str | None) -> dict:
    return C3Verdict(
        schema_version="1.0", verdict_id=verdict_id, session_id=session_id,
        has_gui_defect=True, defect_type="Component Overlap", confidence=0.9,
        evidence={"note": "overlap on settings"},
    ).model_dump(mode="json")


def _journey(controller, tmp_path):
    views = controller.create_journeys(str(SAMPLE), "sentry", str(tmp_path / "journeys"))
    assert views[0].error is None
    return views[0]


def test_journey_view_shows_origin_and_stale_syntheses_are_cleared(tmp_path) -> None:
    controller = C4DemoController(llm=FakeLLM(None))
    view = _journey(controller, tmp_path)
    assert (view.source, view.session_id, view.source_file) == ("sentry", view.session_id, str(SAMPLE))
    controller.syntheses["stale"] = object()
    _journey(controller, tmp_path)
    assert controller.syntheses == {}


def test_create_journeys_rejects_missing_empty_and_incompatible_inputs(tmp_path) -> None:
    controller = C4DemoController()
    assert "existing telemetry file" in controller.create_journeys("", "sentry", str(tmp_path))[0].error
    empty = tmp_path / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    assert controller.create_journeys(str(empty), "sentry", str(tmp_path))[0].error
    noerror = tmp_path / "noerror.json"
    noerror.write_text(json.dumps({"event_id": "x", "timestamp": "2026-01-01T00:00:00Z",
        "breadcrumbs": [{"timestamp": "2026-01-01T00:00:00Z", "category": "ui.click", "data": {"text": "A"}}]}),
        encoding="utf-8")
    assert controller.create_journeys(str(noerror), "sentry", str(tmp_path))[0].error


def test_c3_verdict_reaches_synthesis_prompt_for_matching_session(tmp_path) -> None:
    llm = FakeLLM(None)
    controller = C4DemoController(llm=llm, c3_inbox=tmp_path / "inbox")
    view = _journey(controller, tmp_path)
    controller.receive_inspection(_verdict("v-match", view.session_id), tmp_path / "inbox")
    controller.receive_inspection(_verdict("v-other", "unrelated-session"), tmp_path / "inbox")

    test = controller.generate_test(view.id, "m", "http://x", True, _setup(tmp_path))

    assert (test.status, test.c3_status, test.c3_verdict_id) == ("generated", "used", "v-match")
    assert "C3 evidence:" in llm.prompts[0] and "component_overlap" in llm.prompts[0]


def test_c3_explicit_choice_wins_and_unrelated_verdicts_are_never_attached(tmp_path) -> None:
    llm = FakeLLM(None)
    controller = C4DemoController(llm=llm, c3_inbox=tmp_path / "inbox")
    view = _journey(controller, tmp_path)
    controller.receive_inspection(_verdict("v-live", "mvp_abc123"), tmp_path / "inbox")
    config = _setup(tmp_path)

    auto = controller.generate_test(view.id, "m", "http://x", True, config)
    assert auto.c3_status == "no_evidence" and "C3 evidence:" not in llm.prompts[0]

    chosen = controller.generate_test(view.id, "m", "http://x", True, config, "v-live")
    assert chosen.c3_verdict_id == "v-live" and "C3 evidence:" in llm.prompts[1]

    missing = controller.generate_test(view.id, "m", "http://x", True, config, "nope")
    assert missing.c3_status == "unavailable" and "not found" in (missing.error or "")

    off = controller.generate_test(view.id, "m", "http://x", False, config, "v-live")
    assert off.c3_status == "not_requested" and "C3 evidence:" not in llm.prompts[-1]


def test_inbox_client_skips_corrupt_files(tmp_path) -> None:
    inbox = tmp_path / "inbox"
    C4DemoController().receive_inspection(_verdict("v1", "s1"), inbox)
    (inbox / "junk.json").write_text("{not json", encoding="utf-8")
    client = InboxC3Client(inbox)
    assert client.get_verdict("s1", None).verdict_id == "v1" and client.last_status == "used"


def test_run_test_uses_ui_model_and_c3_settings_when_nothing_was_generated(tmp_path) -> None:
    llm = FakeLLM(None)
    execution = FakeExecution()
    controller = C4DemoController(llm=llm, execution_service=execution, c3_inbox=tmp_path / "inbox")
    view = _journey(controller, tmp_path)
    controller.receive_inspection(_verdict("v1", view.session_id), tmp_path / "inbox")

    run = controller.run_test(view.id, _setup(tmp_path), str(tmp_path / "runs"), use_c3=True)

    assert run.status == "passed" and "C3 evidence:" in llm.prompts[0]
    assert execution.scripts and run.synthesis_result.c3_status == "used"


def test_run_test_reports_unexecutable_synthesis_instead_of_running(tmp_path) -> None:
    llm = FakeLLM(None)
    llm.response = "not json"
    execution = FakeExecution()
    controller = C4DemoController(llm=llm, execution_service=execution)
    view = _journey(controller, tmp_path)
    run = controller.run_test(view.id, _setup(tmp_path), str(tmp_path / "runs"))
    assert run.status == "error" and not execution.scripts


def test_heal_distinguishes_suggestion_from_verified_repair(tmp_path) -> None:
    page = tmp_path / "page.xml"
    page.write_text(PAGE, encoding="utf-8")
    execution = FakeExecution(page)
    controller = C4DemoController(llm=FakeLLM(None), execution_service=execution)
    view = _journey(controller, tmp_path)
    run = controller.run_test(view.id, _setup(tmp_path), str(tmp_path / "runs"))
    assert run.status == "failed" and run.failure_kind == "locator_not_found"

    suggested = controller.heal_last_failure(run, "lexical", 0.1)
    assert suggested.status == "healed" and not suggested.verified
    assert suggested.rerun_status == "not_run" and len(execution.scripts) == 1

    verified = controller.heal_last_failure(
        run, "lexical", 0.1, verify=True, config_path=_setup(tmp_path))
    assert verified.verified and verified.rerun_status == "passed_after_healing"
    assert len(execution.scripts) == 2 and "Network &amp; internet" not in execution.scripts[1]
    assert "Network & internet" in execution.scripts[1]
    repo = tmp_path / "runs" / "repository" / "auto-sentry-c4-demo-1-0_c4-demo-1_error"
    assert (repo / "versions.json").exists() and verified.versions


def test_heal_respects_threshold_and_refuses_non_locator_failures(tmp_path) -> None:
    page = tmp_path / "page.xml"
    page.write_text(PAGE, encoding="utf-8")
    controller = C4DemoController(llm=FakeLLM(None), execution_service=FakeExecution(page))
    view = _journey(controller, tmp_path)
    run = controller.run_test(view.id, _setup(tmp_path), str(tmp_path / "runs"))

    strict = controller.heal_last_failure(run, "lexical", 1.0, verify=True, config_path=_setup(tmp_path))
    assert not strict.verified and strict.status != "healed"

    run.execution_result.failure.kind = FailureKind.INFRASTRUCTURE
    other = controller.heal_last_failure(run, "lexical", 0.1)
    assert other.status == "not_applicable" and "locator" in other.error
