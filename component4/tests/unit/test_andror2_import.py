"""AndroR2 UiAutomator scripts convert into traces that keep their meaning and report what was lost."""

import json

from c4.ingestion import TelemetryIngestionService
from c4.schemas import EventSource
from c4.sessionization import SessionizationService
from c4.sessionization.config import SessionizationConfig
from evaluation.andror2_import import SCRIPT_DIR, convert_dataset, convert_script, main
from evaluation.run_synthesis_eval import collect_journeys

JAVA = '''
public class Script7 {
    private static final String PACKAGE_NAME
            = "org.example.notes";
    private static final String EMAIL_TO_BE_TYPED = "user@example.org";

    @Before
    public void startActivityFromHomeScreen() {
        uiDevice.pressHome();
    }

    @Test
    public void performGUIActionsAndAssertions() throws Exception {
        // Setup GUI actions
        // Press allow button
        mDevice.findObject(new UiSelector().className("android.widget.Button").instance(1)).click();
        // Bug-specific GUI actions
        //Click next
        mDevice.findObject(new UiSelector().resourceId("org.example.notes:id/next")).click();
        //Click next
        mDevice.findObject(new UiSelector().resourceId("org.example.notes:id/next")).click();
        // Open "Save (all)"
        mDevice.findObject(new UiSelector().text("Save (all)")).click();
        mDevice.findObject(new UiSelector().resourceId("org.example.notes:id/row").index(8)).click();
        mDevice.findObject(new UiSelector().description("More options")).click();
        mDevice.findObject(new UiSelector().clickable(true)).click();
        mDevice.findObject(new UiSelector().className("android.widget.LinearLayout").index(6)).click();
        // Type email
        mDevice.findObject(new UiSelector().text("Email")).setText(EMAIL_TO_BE_TYPED);
        mDevice.findObject(new UiSelector().text("Body")).setText("hello; world");
        mDevice.findObject(new UiSelector().text("Body")).setText(unknownVariable);
        mDevice.click(540,897);
        mDevice.swipe(100, 1000, 1000, 1000, 10);
        mDevice.pressBack();
        mDevice.pressRecentApps();
        TimeUnit.MILLISECONDS.sleep(1000);
        startActivityFromHomeScreen();
        mDevice.findObject(By.text("odd")).click();
        // Assertions
        assertTrue(mDevice.findObject(new UiSelector().className("android.widget.Switch")).isChecked());
    }
}
'''
METADATA = {"id": "7", "commit_id": "abc123", "android_os": "9", "failure_type": "crash",
            "github_issue": "https://github.com/o/r/issues/7", "gui_actions": 20}


def _steps(trace):
    return [(s["action"], {k: s[k] for k in ("text", "resource_id", "content_desc", "xpath") if k in s}) for s in trace["steps"]]


def test_script_steps_keep_order_locators_values_and_phases() -> None:
    trace = convert_script(JAVA, METADATA)

    assert trace["trace_id"] == "andror2-7" and trace["app_package"] == "org.example.notes"
    assert trace["app_version"] == "abc123" and trace["os_version"] == "9"
    assert _steps(trace) == [
        ("tap", {"xpath": "(//android.widget.Button)[2]"}),
        ("tap", {"resource_id": "org.example.notes:id/next"}),
        ("tap", {"resource_id": "org.example.notes:id/next"}),
        ("tap", {"text": "Save (all)"}),
        ("tap", {"resource_id": "org.example.notes:id/row"}),
        ("tap", {"content_desc": "More options"}),
        ("tap", {"xpath": "(//*[@clickable='true'])[1]"}),
        ("input", {"text": "Email"}),
        ("input", {"text": "Body"}),
        ("scroll", {}),
        ("back", {}),
    ]
    steps = trace["steps"]
    assert [s["phase"] for s in steps[:2]] == ["setup", "bug"] and steps[1]["name"] == "Click next"
    assert steps[7]["value"] == "user@example.org" and steps[8]["value"] == "hello; world"
    assert steps[4]["approximate_locator"] is True and "approximate_locator" not in steps[1]
    assert all(s["synthetic_time"] for s in steps)
    assert steps[0]["timestamp"] == "2000-01-01T00:00:00Z" and steps[10]["timestamp"] == "2000-01-01T00:00:10Z"


def test_unconvertible_ui_actions_are_reported_and_non_actions_are_ignored() -> None:
    dropped = convert_script(JAVA, METADATA)["conversion"]["dropped"]

    assert sorted(item["reason"] for item in dropped) == sorted([
        "selector has no text, id, description, or instance-only form",
        "typed value is not a string literal or constant",
        "coordinate tap",
        "pressRecentApps has no C4 action",
        "startActivityFromHomeScreen has no C4 action",
        "findObject argument is not a UiSelector chain",
    ])
    assert not any("sleep" in item["statement"] or "assert" in item["statement"] for item in dropped)


def test_repeated_identical_steps_survive_sessionization() -> None:
    trace = convert_script(JAVA, METADATA)
    events = TelemetryIngestionService().parse(trace, EventSource.TRACE)
    journey = SessionizationService(SessionizationConfig(max_actions=30)).process(events)[0]

    assert [e.locator.get("resource_id") for e in journey.events[1:3]] == ["org.example.notes:id/next"] * 2
    assert len(journey.events) == len(trace["steps"])
    assert journey.metadata["source"] == "trace" and journey.failure.name == "andror2.crash"


def test_evaluation_keeps_early_steps_of_long_traces(tmp_path) -> None:
    (tmp_path / "traces.jsonl").write_text(json.dumps(convert_script(JAVA, METADATA)) + "\n", encoding="utf-8")

    default = collect_journeys(tmp_path, source="trace")[0]
    kept = collect_journeys(tmp_path, source="trace", max_actions=30)[0]

    assert default.metadata["truncated"] is True and len(default.events) == 10
    assert kept.metadata["truncated"] is False and len(kept.events) == 11


def _dataset(tmp_path, reports):
    (tmp_path / "metadata").mkdir(parents=True)
    script_dir = tmp_path / SCRIPT_DIR
    script_dir.mkdir(parents=True)
    for report_id, (metadata, java) in reports.items():
        (tmp_path / "metadata" / f"{report_id}.json").write_text(
            repr(metadata) if isinstance(metadata, dict) else metadata, encoding="utf-8")
        if java is not None:
            (script_dir / f"Script{report_id}.java").write_text(java, encoding="utf-8")
    return tmp_path


def test_dataset_conversion_filters_failure_types_and_reports_coverage(tmp_path) -> None:
    root = _dataset(tmp_path, {
        "7": (METADATA, JAVA),
        "8": ({**METADATA, "id": "8", "failure_type": "output"}, JAVA),
        "9": ({**METADATA, "id": "9"}, None),
        "10": ("not a dict at all (", JAVA),
        "11": ({**METADATA, "id": "11"}, "public class Script11 { @Test public void t() { } }"),
    })

    traces, report = convert_dataset(root)

    assert [t["trace_id"] for t in traces] == ["andror2-7"]
    assert report["scripts_read"] == 2 and report["traces_written"] == 1 and report["fully_converted"] == 0
    assert report["steps_converted"] == 11 and report["steps_dropped"] == 6
    assert report["skipped"] == {
        "8": "failure_type 'output' not selected", "9": "script file not found",
        "10": "metadata is not a readable dict", "11": "no convertible steps",
    }
    both, _ = convert_dataset(root, failure_types=("crash", "output"))
    assert [t["trace_id"] for t in both] == ["andror2-7", "andror2-8"]
    complete, complete_report = convert_dataset(root, only_complete=True)
    assert complete == [] and complete_report["skipped"]["7"] == "has statements that cannot be converted"


def test_command_line_writes_traces_and_report_and_rejects_a_wrong_folder(tmp_path, capsys) -> None:
    root = _dataset(tmp_path / "andror2", {"7": (METADATA, JAVA)})
    out = tmp_path / "out"

    assert main(["--dataset", str(root), "--out", str(out)]) == 0
    traces = [json.loads(line) for line in (out / "traces.jsonl").read_text(encoding="utf-8").splitlines()]
    assert traces[0]["trace_id"] == "andror2-7"
    assert json.loads((out / "conversion_report.json").read_text(encoding="utf-8"))["traces_written"] == 1

    assert main(["--dataset", str(tmp_path / "missing"), "--out", str(out)]) == 2
    assert "metadata directory" in capsys.readouterr().err
