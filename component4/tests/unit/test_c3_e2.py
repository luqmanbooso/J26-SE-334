from __future__ import annotations

import struct
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from c4.c3_interface import C3LiveClient, C3Verdict
from c4.c3_interface.normalize import normalize_defect_type, normalize_verdict
from c4.execution.models import ExecutionResult, ExecutionStatus, FailureInfo, FailureKind
from c4.pipeline import Pipeline
from c4.synthesis.service import SynthesisResult
from c4.schemas import EventKind, EventSource, NormalizedEvent
from c4.pipeline import _png_dimensions


def _failure() -> NormalizedEvent:
    return NormalizedEvent(
        event_id="failure",
        session_id="session",
        source=EventSource.SENTRY,
        kind=EventKind.ERROR,
        timestamp=datetime.now(timezone.utc),
        name="failure",
    )


def test_defect_normalization_table_and_original_metadata() -> None:
    values = {
        "component overlap": "component_overlap",
        "TEXT-TRUNCATION": "text_truncation",
        "missing_component": "missing_component",
        "unrendered asset": "unrendered_asset",
        "functional-incongruence": "functional_incongruence",
        "frozen state": "frozen_state",
        "other defect": "other_defect",
        "not-a-real-defect": "other_defect",
    }
    assert {value: normalize_defect_type(value) for value in values} == values
    verdict = C3Verdict(
        schema_version="1",
        verdict_id="v",
        has_gui_defect=True,
        defect_type="TEXT-TRUNCATION",
        confidence=0.8,
    )
    normalized = normalize_verdict(verdict)
    assert normalized.defect_type == "text_truncation"
    assert normalized.metadata["original_defect_type"] == "TEXT-TRUNCATION"
    assert normalized.evidence["original_defect_type"] == "TEXT-TRUNCATION"


def test_png_dimensions_reads_header_without_image_dependency(tmp_path) -> None:
    path = tmp_path / "image.png"
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" +
        struct.pack(">II", 1080, 2400) + b"\x08\x06\x00\x00\x00"
    )
    assert _png_dimensions(path) == (1080, 2400)


def test_offline_live_client_records_unavailable_status() -> None:
    client = C3LiveClient(
        mode="http",
        base_url="http://127.0.0.1:1",
        timeout_s=0.01,
    )
    verdict = client.get_verdict(
        "session",
        _failure(),
        hierarchy_xml="<hierarchy />",
        screenshot_path="missing.png",
    )
    assert verdict.has_gui_defect is False
    assert client.last_status == "unavailable"


def test_pipeline_hands_execution_artifacts_to_c3(tmp_path) -> None:
    failure = _failure()
    journey = SimpleNamespace(
        journey_id="journey",
        session_id="session",
        failure=failure,
    )
    script = "def step_0(driver):\n    driver.back()\n"
    synthesis = SynthesisResult(
        journey_id="journey",
        status="generated",
        steps=[],
        script=script,
        attempts=[],
        c3_used=False,
        prompt_version="v1",
        model=None,
        elapsed_seconds=0.0,
    )

    class Ingestion:
        def parse_file(self, *args):
            return ["event"]

    class Sessionization:
        def process(self, events):
            return [journey]

    class Synthesis:
        c3_client = None

        def synthesize(self, value):
            return synthesis

    class Execution:
        def execute(self, result, *, runs_dir, run_id, capture_baseline=False):
            run = Path(runs_dir) / run_id
            run.mkdir(parents=True, exist_ok=True)
            (run / "page_source.xml").write_text("<hierarchy />")
            (run / "screenshot.png").write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR"
                + struct.pack(">II", 20, 30) + b"\x08\x06\x00\x00\x00"
            )
            return ExecutionResult(
                run_id=run_id,
                journey_id="journey",
                status=ExecutionStatus.FAILED,
                started_at="2026-01-01T00:00:00Z",
                elapsed_seconds=0.1,
                failure=FailureInfo(
                    kind=FailureKind.LOCATOR_NOT_FOUND,
                    step_index=0,
                ),
            )

    class C3:
        last_status = "used"

        def get_verdict(self, session_id, failure_event, journey, **kwargs):
            assert kwargs["hierarchy_xml"] == "<hierarchy />"
            assert kwargs["screenshot_width"] == 20
            assert kwargs["screenshot_height"] == 30
            return C3Verdict(
                schema_version="1",
                verdict_id="handoff",
                session_id=session_id,
                has_gui_defect=False,
                confidence=0.0,
            )

    records = Pipeline(
        object(),
        SimpleNamespace(),
        ingestion=Ingestion(),
        sessionization=Sessionization(),
        synthesis=Synthesis(),
        execution=Execution(),
        c3_client=C3(),
        use_c3=False,
    ).run("ignored.json", tmp_path / "runs")

    assert records[0].c3_status == "used"
    assert records[0].c3_verdict is not None
    assert (tmp_path / "runs" / "journey" / "c3_verdict.json").is_file()
