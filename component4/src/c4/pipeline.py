"""End-to-end Component 4 pipeline through execution."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from c4.c3_interface.client import C3Client
from c4.config import TargetAppConfig
from c4.execution.service import ExecutionService
from c4.execution.models import ExecutionResult
from c4.ingestion.loader import TelemetryIngestionService
from c4.schemas import EventSource
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
    ]
    synthesis: SynthesisResult | None = None
    execution: ExecutionResult | None = None


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
    ) -> None:
        self.target = target
        self.ingestion = ingestion or TelemetryIngestionService()
        self.sessionization = sessionization or SessionizationService()
        self.synthesis = synthesis or SynthesisService(
            llm,
            target=target,
            c3_client=c3_client,
            use_c3=use_c3,
        )
        self.execution = execution or ExecutionService(target=target)

    def run(
        self,
        telemetry_path: str | Path,
        runs_dir: str | Path,
        *,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> list[PipelineRecord]:
        """Run all journeys from a Sentry telemetry file."""
        events = self.ingestion.parse_file(telemetry_path, EventSource.SENTRY)
        journeys = self.sessionization.process(events)
        if limit is not None:
            journeys = journeys[:limit]
        root = Path(runs_dir)
        root.mkdir(parents=True, exist_ok=True)
        records: list[PipelineRecord] = []
        for journey in journeys:
            result = self.synthesis.synthesize(journey)
            safe_id = _safe_name(journey.journey_id)
            if result.status == "skipped_not_reproducible":
                records.append(
                    PipelineRecord(
                        journey_id=journey.journey_id,
                        status="skipped_not_reproducible",
                        synthesis=result,
                    )
                )
                continue
            if result.status != "generated":
                records.append(
                    PipelineRecord(
                        journey_id=journey.journey_id,
                        status="synthesis_failed",
                        synthesis=result,
                    )
                )
                continue
            if dry_run:
                journey_dir = root / safe_id
                journey_dir.mkdir(parents=True, exist_ok=True)
                (journey_dir / "synthesized_test.py").write_text(
                    result.script or "", encoding="utf-8"
                )
                records.append(
                    PipelineRecord(
                        journey_id=journey.journey_id,
                        status="dry_run",
                        synthesis=result,
                    )
                )
                continue
            execution = self.execution.execute(
                result, runs_dir=root, run_id=safe_id
            )
            records.append(
                PipelineRecord(
                    journey_id=journey.journey_id,
                    status="executed",
                    synthesis=result,
                    execution=execution,
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


def _safe_name(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return sanitized or "journey"
