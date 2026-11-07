"""Release-to-release healing: pair selection, app targets, and the whole flow with a real healer."""

from datetime import datetime, timezone
from pathlib import Path

from c4.config import TargetAppConfig
from c4.execution.models import ExecutionResult, ExecutionStatus, FailureInfo, FailureKind
from c4.healing.baseline import BaselineStore
from c4.healing.semantic import LexicalEmbedder
from c4.synthesis.service import SynthesisResult
from evaluation.release_healing import apk_target, run_pair, select_pairs, summarize

FIXTURES = Path(__file__).parents[1] / "fixtures" / "healing"
OLD = (FIXTURES / "settings_home_real.xml").read_text(encoding="utf-8")
NEW = OLD.replace("Wi-Fi", "Wi-Fi settings")
BASE = TargetAppConfig(package="base", activity=".Main", udid="emulator-5554", adb_path="adb")
SCRIPT = (
    "from appium.webdriver.common.appiumby import AppiumBy\n\n\n"
    "def step_0(driver) -> None:\n"
    "    _snapshot(driver, 0)\n"
    "    driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text(\"Wi-Fi\")').click()\n"
)


def _trace(number, package, commit, steps=3):
    return {"trace_id": f"andror2-{number}", "app_package": package, "app_version": commit,
            "app_apk": f"apks/{number}.apk", "steps": [{"action": "tap"}] * steps}


def test_apk_target_installs_the_apk_and_names_only_the_package() -> None:
    target = apk_target(BASE, "org.example", Path("a/7.apk"))

    capabilities = target.capabilities()
    assert (target.package, target.activity, target.apk_path) == ("org.example", None, None)
    assert "appActivity" not in capabilities and "app" not in capabilities
    assert capabilities["appPackage"] == "org.example" and target.udid == "emulator-5554"
    assert target.setup_commands[0] == ["shell", "pm uninstall org.example >/dev/null 2>&1; true"]
    assert target.setup_commands[1] == ["install", "-r", "-d", "-g", str(Path("a/7.apk"))]


def test_identical_scripts_result_for_both_releases_because_only_setup_differs() -> None:
    first = apk_target(BASE, "org.example", Path("a/7.apk")).capabilities()
    second = apk_target(BASE, "org.example", Path("a/9.apk")).capabilities()
    assert first == second


def test_pairs_use_a_short_source_and_other_releases_of_the_same_app() -> None:
    traces = [
        _trace(1, "app.a", "c1", steps=6), _trace(2, "app.a", "c2", steps=3), _trace(3, "app.a", "c2", steps=4),
        _trace(4, "app.a", "c3"), _trace(5, "app.a", "c4"),
        _trace(6, "app.b", "d1"), _trace(7, "app.b", "d1"),
        _trace(8, "app.c", "e1", steps=3), _trace(9, "app.c", "e2", steps=3),
        _trace(10, "app.d", "f1", steps=1), _trace(11, "app.d", "f2", steps=20),
    ]
    compatible = {str(n): "ok" for n in range(1, 12)}
    compatible["9"] = "install failed: INSTALL_FAILED_DEPRECATED_SDK_VERSION"

    pairs = select_pairs(traces, compatible, per_app=2)

    assert [(s["trace_id"], t["trace_id"]) for s, t in pairs] == [
        ("andror2-2", "andror2-1"), ("andror2-2", "andror2-4"),
    ]
    assert all(s["app_version"] != t["app_version"] for s, t in pairs)


def test_pairs_need_two_runnable_releases_and_a_source_of_usable_length() -> None:
    traces = [
        _trace(1, "app.a", "c1"), _trace(2, "app.a", "c2", steps=20),
        _trace(3, "app.b", "d1"), _trace(4, "app.b", "d2"),
        _trace(5, "app.c", "e1", steps=20), _trace(6, "app.c", "e2", steps=20),
    ]
    compatible = {"1": "ok", "2": "ok", "3": "ok", "4": "launch failed: x", "5": "ok", "6": "ok"}

    pairs = select_pairs(traces, compatible)

    # app.a: a short source and a long target is fine; app.b has one runnable release; app.c has no short source
    assert [(s["trace_id"], t["trace_id"]) for s, t in pairs] == [("andror2-1", "andror2-2")]


class _Synthesis:
    def __init__(self):
        self.target = None

    def synthesize(self, journey):
        return SynthesisResult(journey_id="j", status="generated", steps=[{"index": 0, "action": "tap", "target": {"text": "Wi-Fi"}}], script=SCRIPT, attempts=[],
                               c3_used=False, prompt_version="t", model=None, elapsed_seconds=0.0)


class _Execution:
    """Releases are told apart by their install command, like the real runs."""

    runs = []

    def __init__(self, target):
        self.target = target

    def execute(self, synthesis, *, runs_dir, run_id, capture_baseline=False, **_):
        release = "old" if self.target.setup_commands[1][-1].endswith("old.apk") else "new"
        run_dir = Path(runs_dir) / run_id
        (run_dir / "baseline").mkdir(parents=True, exist_ok=True)
        (run_dir / "baseline" / "step_0.xml").write_text(OLD if release == "old" else NEW, encoding="utf-8")
        (run_dir / "synthesized_test.py").write_text(synthesis.script, encoding="utf-8")
        passed = release == "old" or "Wi-Fi settings" in synthesis.script
        failure = None
        if not passed:
            (run_dir / "page_source.xml").write_text(NEW, encoding="utf-8")
            failure = FailureInfo(step_index=0, action="tap", kind=FailureKind.LOCATOR_NOT_FOUND,
                                  page_source_path=str(run_dir / "page_source.xml"))
        self.runs.append((release, run_id))
        return ExecutionResult(run_id=run_id, journey_id="j", status=ExecutionStatus.PASSED if passed else ExecutionStatus.FAILED,
                               started_at=datetime.now(timezone.utc), elapsed_seconds=0.0, failure=failure)


def _journey():
    from c4.schemas import EventKind, EventSource, FailureJourney, NormalizedEvent

    when = datetime(2026, 1, 1, tzinfo=timezone.utc)
    step = NormalizedEvent(event_id="e1", session_id="s", source=EventSource.TRACE, kind=EventKind.ACTION,
                           timestamp=when, name="tap", action="tap", locator={"text": "Wi-Fi"})
    failure = NormalizedEvent(event_id="x", session_id="s", source=EventSource.TRACE, kind=EventKind.ERROR,
                              timestamp=when, name="Crash", error={"type": "Crash"})
    return FailureJourney(journey_id="j", session_id="s", events=[step], failure=failure)


def _run(tmp_path, source="andror2-1", target="andror2-2"):
    _Execution.runs = []
    trace = {"trace_id": source, "app_package": "org.example", "app_version": "c1" * 4,
             "app_apk": "old.apk", "steps": [{}]}
    other = {"trace_id": target, "app_package": "org.example", "app_version": "c2" * 4,
             "app_apk": "new.apk", "steps": [{}]}
    return run_pair(trace, other, journey=_journey(), synthesis=_Synthesis(), base=BASE, apk_root=tmp_path,
                    runs_dir=tmp_path / "runs", embedder_name="lexical", embedder=LexicalEmbedder(),
                    execution_factory=_Execution)


def test_a_locator_that_broke_between_releases_is_healed_against_the_older_screen(tmp_path) -> None:
    row = _run(tmp_path)

    assert row["source_status"] == "passed" and row["target_status"] == "failed"
    assert row["target_failure"] == "locator_not_found" and row["failed_step"] == 0
    assert row["heal_status"] == "healed" and row["heal_baseline"] == "used"
    assert "Wi-Fi settings" in row["healed_locator"] and row["final_status"] == "passed_after_healing"
    assert [release for release, _ in _Execution.runs] == ["old", "new", "new"]
    assert BaselineStore(tmp_path / "runs" / "baselines").load("andror2-1_to_andror2-2", 0, SCRIPT) == OLD


def test_the_blind_attempt_without_the_older_screen_is_recorded_for_comparison(tmp_path) -> None:
    row = _run(tmp_path)
    assert row["heal_without_baseline"] in {"healed", "refused_low_confidence", "refused_no_candidates", "refused_ambiguous"}


def test_summary_counts_each_outcome() -> None:
    def row(source, target_status, failure, final, blind=""):
        return {"source_status": source, "target_status": target_status, "target_failure": failure,
                "final_status": final, "heal_without_baseline": blind}

    rows = [
        row("passed", "passed", "", "passes unchanged on the other release"),
        row("passed", "failed", "locator_not_found", "passed_after_healing", "healed"),
        row("passed", "failed", "locator_not_found", "refused", "refused_low_confidence"),
        row("passed", "failed", "unknown", "fails, not a locator failure (unknown)"),
        row("failed", "", "", "source release does not pass"),
    ]
    summary = summarize(rows)

    assert summary == {
        "pairs": 5, "source_passes": 4, "pass_unchanged": 1, "locator_failures": 2, "other_failures": 1,
        "healed_and_verified": 1, "refused": 1, "failed_after_healing": 0, "healed_without_baseline": 1,
    }


def test_replay_targets_accept_any_activity_so_redirecting_launch_screens_do_not_fail() -> None:
    assert apk_target(BASE, "org.example", Path("a/7.apk")).capabilities()["appWaitActivity"] == "*"


def test_steps_that_tap_the_android_system_are_dropped_and_counted() -> None:
    from datetime import datetime, timezone

    from c4.schemas import EventKind, EventSource, FailureJourney, NormalizedEvent
    from evaluation.release_healing import without_system_steps

    def event(index, **locator):
        return NormalizedEvent(event_id=f"e{index}", session_id="s", source=EventSource.TRACE, kind=EventKind.ACTION,
                               timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), name="tap", action="tap",
                               locator=locator)

    failure = NormalizedEvent(event_id="x", session_id="s", source=EventSource.TRACE, kind=EventKind.ERROR,
                              timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc), name="Crash", error={"type": "Crash"})
    journey = FailureJourney(journey_id="j", session_id="s", failure=failure, events=[
        event(1, resource_id="com.android.permissioncontroller:id/permission_allow_button"),
        event(2, resource_id="android:id/button1"),
        event(3, resource_id="org.example:id/next"),
        event(4, text="Settings"),
        event(5, resource_id="com.android.example.app:id/own"),
    ])

    kept, removed = without_system_steps(journey, "com.android.example.app")

    assert removed == 2
    assert [e.event_id for e in kept.events] == ["e3", "e4", "e5"]


def test_prepare_device_disables_the_compatibility_dialog_on_the_chosen_device(monkeypatch) -> None:
    import subprocess

    from evaluation.release_healing import prepare_device

    calls = []
    monkeypatch.setattr(subprocess, "run", lambda command, **_: calls.append(command))

    prepare_device("adb", "emulator-5554")
    prepare_device("adb", None)

    assert calls[0] == ["adb", "-s", "emulator-5554", "shell", "setprop",
                        "debug.wm.disable_deprecated_target_sdk_dialog", "1"]
    assert calls[1] == ["adb", "shell", "setprop", "debug.wm.disable_deprecated_target_sdk_dialog", "1"]
