"""Baselines must come from an earlier passing run and be tied to their script."""

import json
from datetime import datetime, timezone
from pathlib import Path

from c4.config import TargetAppConfig
from c4.execution.models import ExecutionResult, ExecutionStatus, FailureInfo, FailureKind
from c4.healing.baseline import BaselineStore
from c4.healing.engine import HealingEngine
from c4.healing.models import HealingConfig
from c4.healing.semantic import LexicalEmbedder
from c4.pipeline import Pipeline
from c4.synthesis.service import SynthesisResult
from c4.ui.controller import C4DemoController

FIXTURE = Path(__file__).parents[1] / "fixtures" / "healing" / "settings_home_real.xml"
SCRIPT = (
    "from appium.webdriver.common.appiumby import AppiumBy\n\n\n"
    "def step_0(driver) -> None:\n"
    "    driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text(\"Wi-Fi\")').click()\n"
)
OLD_SCREEN = FIXTURE.read_text(encoding="utf-8")
NEW_SCREEN = OLD_SCREEN.replace("Wi-Fi", "Wi-Fi settings")


def _run_dir(root: Path, name: str, screen: str, script: str = SCRIPT) -> Path:
    run_dir = root / name
    (run_dir / "baseline").mkdir(parents=True)
    (run_dir / "baseline" / "step_0.xml").write_text(screen, encoding="utf-8")
    (run_dir / "synthesized_test.py").write_text(script, encoding="utf-8")
    return run_dir


def test_baseline_taken_from_the_failing_screen_hides_every_change() -> None:
    engine = HealingEngine(HealingConfig(embedder="lexical"), LexicalEmbedder())
    same_screen = engine.heal(SCRIPT, 0, NEW_SCREEN, baseline_hierarchy_xml=NEW_SCREEN)
    previous_release = engine.heal(SCRIPT, 0, NEW_SCREEN, baseline_hierarchy_xml=OLD_SCREEN)

    assert same_screen.status.value == "refused_no_candidates"
    assert previous_release.status.value == "healed"
    assert previous_release.r6_applied and previous_release.candidates_after_narrowing == 1
    assert "Wi-Fi settings" in previous_release.healed_script


def test_baseline_is_returned_only_for_the_script_it_was_captured_from(tmp_path) -> None:
    store = BaselineStore(tmp_path / "baselines")
    store.save_from_run("journey", _run_dir(tmp_path, "run", OLD_SCREEN))

    assert store.load("journey", 0, SCRIPT) == OLD_SCREEN
    assert store.load("journey", 0, SCRIPT.replace("\n", "\r\n")) == OLD_SCREEN
    assert store.load("journey", 0, SCRIPT.replace("Wi-Fi", "Display")) is None
    assert store.load("journey", 0) == OLD_SCREEN
    assert store.load("journey", 1, SCRIPT) is None


def test_baseline_without_an_index_is_not_trusted_for_a_script(tmp_path) -> None:
    store = BaselineStore(tmp_path / "baselines")
    store.save_from_run("journey", _run_dir(tmp_path, "run", OLD_SCREEN))
    (tmp_path / "baselines" / "journey" / "index.json").unlink()
    assert store.load("journey", 0, SCRIPT) is None


class _Ingestion:
    def parse_file(self, path, source):
        return ["event"]


class _Sessionization:
    def process(self, events):
        from types import SimpleNamespace
        return [SimpleNamespace(journey_id="journey")]


class _Synthesis:
    def synthesize(self, journey):
        return SynthesisResult(
            journey_id="journey", status="generated", steps=[], script=SCRIPT, attempts=[],
            c3_used=False, prompt_version="test", model=None, elapsed_seconds=0.0,
        )


class _Execution:
    """Writes the baseline files a real capture run would leave behind."""

    def __init__(self, status: ExecutionStatus, screen: str) -> None:
        self.status = status
        self.screen = screen

    def execute(self, synthesis, *, runs_dir, run_id, capture_baseline=False, **_):
        _run_dir(Path(runs_dir), run_id, self.screen, synthesis.script)
        failed = self.status is ExecutionStatus.FAILED
        return ExecutionResult(
            run_id=run_id, journey_id=synthesis.journey_id, status=self.status,
            started_at=datetime.now(timezone.utc), elapsed_seconds=0.0,
            failure=FailureInfo(kind=FailureKind.LOCATOR_NOT_FOUND) if failed else None,
        )


class _Healer:
    def __init__(self, store: BaselineStore) -> None:
        self.baseline_store = store

    def heal_and_rerun(self, *args, **kwargs):
        from c4.healing.service import HealingOutcome
        return HealingOutcome(final_status="refused")


def _pipeline(execution, healer):
    return Pipeline(
        object(), TargetAppConfig(package="com.example", activity="Main"),
        ingestion=_Ingestion(), sessionization=_Sessionization(), synthesis=_Synthesis(),
        execution=execution, healer=healer, use_c3=False,
    )


def test_pipeline_saves_baselines_from_passing_runs_and_never_overwrites_with_a_failing_one(tmp_path) -> None:
    store = BaselineStore(tmp_path / "baselines")
    healer = _Healer(store)

    _pipeline(_Execution(ExecutionStatus.PASSED, OLD_SCREEN), healer).run(
        "t.json", tmp_path / "good", capture_baseline=True)
    store_after_pass = store.load("journey", 0, SCRIPT)
    _pipeline(_Execution(ExecutionStatus.FAILED, NEW_SCREEN), healer).run(
        "t.json", tmp_path / "bad", capture_baseline=True)

    assert store_after_pass == OLD_SCREEN
    assert store.load("journey", 0, SCRIPT) == OLD_SCREEN


def test_pipeline_does_not_save_a_baseline_unless_asked(tmp_path) -> None:
    store = BaselineStore(tmp_path / "baselines")
    _pipeline(_Execution(ExecutionStatus.PASSED, OLD_SCREEN), _Healer(store)).run("t.json", tmp_path / "runs")
    assert store.load("journey", 0) is None


SAMPLE = Path(__file__).parents[2] / "src" / "c4" / "ui" / "samples" / "sentry.json"


class _LLM:
    model = "fake"

    def generate(self, prompt):
        return json.dumps([{"index": 0, "action": "tap", "target": {"text": "Network and internet"},
                            "source_event_id": None}])


class _DeviceRuns:
    """A passing run on the old release, then a failing run on the new one."""

    def __init__(self, new_page: Path) -> None:
        self.new_page = new_page
        self.calls = 0

    def execute(self, synthesis, *, runs_dir="runs", run_id=None, capture_baseline=False, **_):
        self.calls += 1
        run_id = run_id or f"run-{self.calls}"
        run_dir = Path(runs_dir) / run_id
        (run_dir / "baseline").mkdir(parents=True, exist_ok=True)
        (run_dir / "baseline" / "step_0.xml").write_text(
            OLD_PAGE if self.calls == 1 else NEW_PAGE, encoding="utf-8")
        (run_dir / "synthesized_test.py").write_text(synthesis.script, encoding="utf-8")
        failing = self.calls == 2
        return ExecutionResult(
            run_id=run_id, journey_id=synthesis.journey_id,
            status=ExecutionStatus.FAILED if failing else ExecutionStatus.PASSED,
            started_at=datetime.now(timezone.utc), elapsed_seconds=0.0,
            failure=FailureInfo(step_index=0, action="tap", kind=FailureKind.LOCATOR_NOT_FOUND,
                                page_source_path=str(self.new_page)) if failing else None,
        )


OLD_PAGE = (
    '<hierarchy><node class="android.widget.FrameLayout" bounds="[0,0][800,800]">'
    '<node class="android.widget.TextView" text="Network and internet" clickable="true" '
    'enabled="true" bounds="[20,0][800,80]" />'
    '<node class="android.widget.TextView" text="Display" clickable="true" '
    'enabled="true" bounds="[20,80][800,160]" /></node></hierarchy>'
)
NEW_PAGE = OLD_PAGE.replace("Network and internet", "Network &amp; internet")


def test_desktop_flow_reuses_the_passing_run_as_baseline_when_healing(tmp_path) -> None:
    config = tmp_path / "target.json"
    config.write_text(json.dumps({"package": "com.android.settings", "activity": ".Settings"}), encoding="utf-8")
    page = tmp_path / "new_page.xml"
    page.write_text(NEW_PAGE, encoding="utf-8")
    controller = C4DemoController(llm=_LLM(), execution_service=_DeviceRuns(page))
    journey = controller.create_journeys(str(SAMPLE), "sentry", str(tmp_path / "journeys"))[0]
    runs = str(tmp_path / "runs")

    first = controller.run_test(journey.id, str(config), runs)
    second = controller.run_test(journey.id, str(config), runs)
    suggestion = controller.heal_last_failure(second, "lexical", 0.1)
    verified = controller.heal_last_failure(second, "lexical", 0.1, verify=True, config_path=str(config))

    assert first.status == "passed" and second.failure_kind == "locator_not_found"
    assert (tmp_path / "runs" / "baselines").is_dir()
    assert suggestion.status == "healed" and suggestion.baseline_used
    assert verified.baseline_used


def test_heal_reports_no_baseline_when_no_earlier_run_passed(tmp_path) -> None:
    config = tmp_path / "target.json"
    config.write_text(json.dumps({"package": "com.android.settings", "activity": ".Settings"}), encoding="utf-8")
    page = tmp_path / "new_page.xml"
    page.write_text(NEW_PAGE, encoding="utf-8")
    runner = _DeviceRuns(page)
    runner.calls = 1
    controller = C4DemoController(llm=_LLM(), execution_service=runner)
    journey = controller.create_journeys(str(SAMPLE), "sentry", str(tmp_path / "journeys"))[0]

    failed = controller.run_test(journey.id, str(config), str(tmp_path / "runs"))
    suggestion = controller.heal_last_failure(failed, "lexical", 0.1)

    assert failed.failure_kind == "locator_not_found"
    assert suggestion.status == "healed" and not suggestion.baseline_used
