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
        ("tap", {"text": "odd"}),
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
    assert kept.metadata["truncated"] is False and len(kept.events) == 12


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
    assert report["steps_converted"] == 12 and report["steps_dropped"] == 5
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


JAVA_LITERALS = '''
public class Script9 {
    @Test
    public void t() throws Exception {
        /* a block comment with a brace { and a quote " */
        char quote = '"';
        char open = '{';
        char close = '}';
        char escaped = '\'';
        mDevice.findObject(new UiSelector().text("First")).click();
        mDevice.findObject(new UiSelector().text("Second")).click();
    }
}
'''


def test_char_literals_and_block_comments_do_not_break_parsing() -> None:
    trace = convert_script(JAVA_LITERALS, {**METADATA, "id": "9"})

    assert [s["text"] for s in trace["steps"]] == ["First", "Second"]
    assert trace["conversion"]["dropped"] == []


def test_coverage_counts_every_script_read_even_when_filtering_incomplete_ones(tmp_path) -> None:
    root = _dataset(tmp_path, {"7": (METADATA, JAVA), "9": ({**METADATA, "id": "9"}, JAVA_LITERALS)})

    traces, report = convert_dataset(root, only_complete=True)

    assert [t["trace_id"] for t in traces] == ["andror2-9"]
    assert report["steps_converted"] == 14 and report["steps_dropped"] == 5
    assert sum(report["dropped_reasons"].values()) == report["steps_dropped"]


JAVA_OBJECTS = '''
public class Script12 {
    private static final String BASIC_SAMPLE_PACKAGE = "org.example.app";
    private static final String NAME = "Ada";

    @Test
    public void t() throws Exception {
        //Click plus
        UiObject2 Plus = mDevice.wait(Until.findObject(By.res(BASIC_SAMPLE_PACKAGE, "fab")), 2000);
        Plus.click();
        //Allow
        UiObject2 Allow = mDevice.wait(Until.findObject(By.res("com.android.packageinstaller", "allow")), 2000);
        Allow.click();
        UiObject2 Back = mDevice.wait(Until.findObject(By.desc( "Navigate up")), 2000);
        Back.click();
        //Type name
        UiObject2 field = mDevice.findObject(By.res("org.example.app:id/name"));
        field.setText(NAME);
        Next = mDevice.wait(Until.findObject(By.text("Next")), 2000);
        Next.clickAndWaitForNewWindow(3000);
        UiObject back = mDevice.findObject(new UiSelector().className("android.widget.ImageButton").instance(0));
        try { back.click();
        } catch (Exception e) { }
        mDevice.wait(Until.findObject(By.text("Done")), 2000).click();
        Plus.click(2000);
        Missing.click();
        UiObject2 gone = mDevice.wait(Until.findObject(By.res(UNKNOWN_CONSTANT, "x")), 2000);
        gone.click();
    }
}
'''


def test_objects_bound_to_variables_and_by_selectors_convert() -> None:
    trace = convert_script(JAVA_OBJECTS, {**METADATA, "id": "12"})

    assert _steps(trace) == [
        ("tap", {"resource_id": "org.example.app:id/fab"}),
        ("tap", {"resource_id": "com.android.packageinstaller:id/allow"}),
        ("tap", {"content_desc": "Navigate up"}),
        ("input", {"resource_id": "org.example.app:id/name"}),
        ("tap", {"text": "Next"}),
        ("tap", {"xpath": "(//android.widget.ImageButton)[1]"}),
        ("tap", {"text": "Done"}),
    ]
    assert trace["steps"][3]["value"] == "Ada"
    assert trace["steps"][0]["name"] == "Click plus"
    assert trace["steps"][0]["selector"] == 'By.res(BASIC_SAMPLE_PACKAGE, "fab")'


def test_variable_uses_that_cannot_be_resolved_are_reported() -> None:
    reasons = [item["reason"] for item in convert_script(JAVA_OBJECTS, {**METADATA, "id": "12"})["conversion"]["dropped"]]

    assert reasons == [
        "click with an argument (long press)",
        "unrecognized UI statement",
        "variable has no resolved locator",
    ]


JAVA_MORE = '''
public class Script13 {
    @Test
    public void t() throws Exception {
        uiDevice.findObject(new UiSelector().className("android.widget.EditText")).legacySetText("t");
        uiDevice.findObject(new UiSelector().scrollable(true)).swipeUp(10);
        UiObject2 Switch = mDevice.findObject(By.res("a:id/sw"));
        if (Switch.isChecked()){ Switch.click();
        }
    }
}
'''


def test_legacy_set_text_selector_swipes_and_conditional_clicks() -> None:
    trace = convert_script(JAVA_MORE, {**METADATA, "id": "13"})

    assert [(s["action"], s.get("value")) for s in trace["steps"]] == [("input", "t"), ("scroll", None)]
    assert trace["steps"][0]["xpath"] == "(//android.widget.EditText)[1]"
    assert [item["reason"] for item in trace["conversion"]["dropped"]] == ["conditional action"]
    typed = convert_script(
        'class S { @Test void t() { mDevice.findObject(new UiSelector().text("Name")).legacySetText("t"); } }',
        METADATA,
    )
    assert [(s["action"], s["value"]) for s in typed["steps"]] == [("input", "t")]
