"""End-to-end Component 4 pipeline through execution."""

from __future__ import annotations

import json
import re
import struct
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from c4.c3_interface.client import C3Client
from c4.c3_interface.live_client import C3LiveClient
from c4.c3_interface.contract import C3Verdict
from c4.c3_interface.normalize import normalize_verdict
from c4.config import TargetAppConfig
from c4.execution.service import ExecutionService
from c4.execution.models import ExecutionResult, FailureKind
from c4.healing.baseline import BaselineStore
from c4.healing.service import HealingOutcome, HealingService
from c4.ingestion.loader import TelemetryIngestionService
from c4.schemas import EventSource, FailureJourney, journey_to_document
from c4.journeys.export import load_hint_rules
from c4.sessionization.service import SessionizationService
from c4.synthesis.service import SynthesisResult, SynthesisService


class PipelineRecord(BaseModel):
    """One journey's synthesis and optional execution record."""

    journey_id: str
    status: Literal[
        "skipped_not_reproducible",
        "synthesis_failed",
        "dry_run",
        "executed",
        "healed",
        "heal_refused",
        "error",
    ]
    synthesis: SynthesisResult | None = None
    execution: ExecutionResult | None = None
    healing: HealingOutcome | None = None
    c3_status: Literal[
        "not_requested", "used", "unavailable", "invalid", "no_evidence"
    ] = "not_requested"
    c3_verdict: C3Verdict | None = None
    journey_file: str | None = None


class Pipeline:
    """Chain ingestion, sessionization, synthesis, and execution."""

    def __init__(
        self,
        llm: object,
        target: TargetAppConfig,
        *,
        ingestion: TelemetryIngestionService | None = None,
        sessionization: SessionizationService | None = None,
        synthesis: SynthesisService | None = None,
        execution: ExecutionService | None = None,
        c3_client: C3Client | None = None,
        use_c3: bool = True,
        healer: HealingService | None = None,
        c3_strict: bool = False,
    ) -> None:
        self.target = target
        self.ingestion = ingestion or TelemetryIngestionService()
        self.sessionization = sessionization or SessionizationService()
        if use_c3 and c3_client is None:
            c3_client = C3LiveClient()
        self.synthesis = synthesis or SynthesisService(
            llm,
            target=target,
            c3_client=c3_client,
            use_c3=use_c3,
            c3_strict=c3_strict,
        )
        self.execution = execution or ExecutionService(target=target)
        self.healer = healer
        self.c3_client = c3_client
        self.c3_strict = c3_strict

    def run(
        self,
        telemetry_path: str | Path,
        runs_dir: str | Path,
        *,
        source: EventSource | str = EventSource.SENTRY,
        dry_run: bool = False,
        limit: int | None = None,
        capture_baseline: bool = False,
    ) -> list[PipelineRecord]:
        """Run all journeys from a provider telemetry file."""
        events = self.ingestion.parse_file(telemetry_path, source)
        journeys = self.sessionization.process(events)
        return self.run_journeys(
            journeys,
            runs_dir,
            dry_run=dry_run,
            limit=limit,
            capture_baseline=capture_baseline,
        )

    def run_journeys(
        self,
        journeys: list[FailureJourney],
        runs_dir: str | Path,
        *,
        dry_run: bool = False,
        limit: int | None = None,
        capture_baseline: bool = False,
    ) -> list[PipelineRecord]:
        """Run already-created journeys without repeating ingestion."""
        if limit is not None:
            journeys = journeys[:limit]
        root = Path(runs_dir)
        root.mkdir(parents=True, exist_ok=True)
        records: list[PipelineRecord] = []
        for journey in journeys:
            safe_id = _safe_name(journey.journey_id)
            journey_dir = root / safe_id
            journey_dir.mkdir(parents=True, exist_ok=True)
            journey_file = _write_journey_file(journey, journey_dir)
            result = self.synthesis.synthesize(journey)
            if result.status == "skipped_not_reproducible":
                records.append(
                    PipelineRecord(
                        journey_id=journey.journey_id,
                        status="skipped_not_reproducible",
                        synthesis=result,
                        c3_status=result.c3_status,
                        c3_verdict=result.c3_verdict,
                        journey_file=journey_file,
                    )
                )
                continue
            if result.status != "generated":
                records.append(
                    PipelineRecord(
                        journey_id=journey.journey_id,
                        status="error" if result.status == "error" else "synthesis_failed",
                        synthesis=result,
                        c3_status=result.c3_status,
                        c3_verdict=result.c3_verdict,
                        journey_file=journey_file,
                    )
                )
                continue
            if dry_run:
                (journey_dir / "synthesized_test.py").write_text(
                    result.script or "", encoding="utf-8"
                )
                records.append(
                    PipelineRecord(
                        journey_id=journey.journey_id,
                        status="dry_run",
                        synthesis=result,
                        c3_status=result.c3_status,
                        c3_verdict=result.c3_verdict,
                        journey_file=journey_file,
                    )
                )
                continue
            execution = self.execution.execute(
                result,
                runs_dir=root,
                run_id=safe_id,
                capture_baseline=capture_baseline,
            )
            healing = None
            record_status = "executed"
            c3_verdict = result.c3_verdict
            c3_status = result.c3_status
            if execution.failure is not None:
                handoff = self._c3_execution_handoff(
                    journey, execution, root / safe_id
                )
                if handoff is not None:
                    c3_verdict, c3_status = handoff
                    if self.c3_strict and c3_status in {"unavailable", "invalid"}:
                        record_status = "error"
            if (
                self.healer is not None
                and execution.failure is not None
                and execution.failure.kind is FailureKind.LOCATOR_NOT_FOUND
            ):
                baseline_store = getattr(self.healer, "baseline_store", None)
                if isinstance(baseline_store, BaselineStore):
                    baseline_store.save_from_run(safe_id, root / safe_id)
                healing = self.healer.heal_and_rerun(
                    result, execution, root / safe_id, safe_id
                )
                record_status = (
                    "healed"
                    if healing.final_status == "passed_after_healing"
                    else "heal_refused"
                )
            records.append(
                PipelineRecord(
                    journey_id=journey.journey_id,
                    status=record_status,
                    synthesis=result,
                    execution=execution,
                    healing=healing,
                    c3_status=c3_status,
                    c3_verdict=c3_verdict,
                    journey_file=journey_file,
                )
            )
        (root / "pipeline_report.json").write_text(
            json.dumps(
                [record.model_dump(mode="json") for record in records],
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return records

    def _c3_execution_handoff(
        self,
        journey,
        execution,
        run_dir: Path,
    ) -> tuple[C3Verdict, str] | None:
        """Send captured failure artifacts to C3 without using device commands."""
        client = self.c3_client or getattr(self.synthesis, "c3_client", None)
        failure = execution.failure
        if client is None or failure is None:
            return None
        hierarchy_path = run_dir / "page_source.xml"
        screenshot_path = run_dir / "screenshot.png"
        if not hierarchy_path.is_file() or not screenshot_path.is_file():
            return None
        try:
            width, height = _png_dimensions(screenshot_path)
            verdict = client.get_verdict(
                journey.session_id,
                journey.failure,
                journey,
                hierarchy_xml=hierarchy_path.read_text(encoding="utf-8"),
                screenshot_path=str(screenshot_path),
                screenshot_width=width,
                screenshot_height=height,
            )
        except Exception:
            return None
        status = getattr(client, "last_status", "used")
        (run_dir / "c3_verdict.json").write_text(
            json.dumps(verdict.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return normalize_verdict(verdict), status


def _safe_name(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return sanitized or "journey"


def _write_journey_file(journey: FailureJourney, run_dir: Path) -> str | None:
    """Persist a versioned journey document for a real journey."""
    if not isinstance(journey, FailureJourney):
        return None
    path = run_dir / "journey.json"
    path.write_text(
        json.dumps(
            journey_to_document(journey, load_hint_rules()).model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return str(path)


def _png_dimensions(path: Path) -> tuple[int, int]:
    """Read PNG dimensions from its fixed header without image dependencies."""
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"invalid PNG file: {path}")
    return struct.unpack(">II", header[16:24])
