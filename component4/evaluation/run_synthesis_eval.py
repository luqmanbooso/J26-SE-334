"""Evaluate Component 4 synthesis quality, replay, and stability."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from c4.config import TargetAppConfig, load_target_config
from c4.execution.models import ExecutionResult, FailureKind
from c4.execution.service import ExecutionService
from c4.ingestion.loader import TelemetryIngestionService
from c4.schemas import EventSource, FailureJourney
from c4.sessionization.service import SessionizationService
from c4.synthesis.service import SynthesisResult, SynthesisService
from c4.synthesis.qwen_client import OllamaQwenClient


CSV_FIELDS = (
    "journey_id",
    "reproducible_flag",
    "synthesis_status",
    "attempts",
    "steps_count",
    "grounded_steps_ratio",
    "script_compiles",
    "llm_seconds",
    "execution_status",
    "failure_kind",
    "failed_step_index",
    "execution_seconds",
)


def collect_journeys(
    telemetry_dir: str | Path,
    *,
    limit: int | None = None,
) -> list[FailureJourney]:
    """Load and sessionize all JSON telemetry files in deterministic order."""
    ingestion = TelemetryIngestionService()
    sessionization = SessionizationService()
    journeys: list[FailureJourney] = []
    paths = sorted(
        path
        for path in Path(telemetry_dir).iterdir()
        if path.is_file() and path.suffix.lower() in {".json", ".jsonl"}
    )
    for path in paths:
        journeys.extend(
            sessionization.process(
                ingestion.parse_file(path, EventSource.SENTRY)
            )
        )
    journeys.sort(key=lambda item: (item.failure.timestamp, item.journey_id))
    return journeys[:limit] if limit is not None else journeys


def evaluate(
    journeys: list[FailureJourney],
    synthesis: SynthesisService,
    execution: ExecutionService | None = None,
    *,
    runs_dir: str | Path = "runs",
    repeats: int = 1,
) -> list[dict[str, Any]]:
    """Evaluate each journey repeatedly and return CSV-shaped rows."""
    if repeats < 1:
        raise ValueError("repeats must be at least one")
    root = Path(runs_dir)
    root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for journey in journeys:
        for repeat in range(1, repeats + 1):
            result = synthesis.synthesize(journey)
            execution_result = None
            if execution is not None and result.status == "generated":
                execution_result = execution.execute(
                    result,
                    runs_dir=root,
                    run_id=f"{_safe_name(journey.journey_id)}-r{repeat}",
                )
            rows.append(_row(journey, result, execution_result))
    return rows


def build_summary(
    rows: list[dict[str, Any]],
    *,
    model: str | None = None,
    prompt_version: str | None = None,
    repeats: int = 1,
) -> dict[str, Any]:
    """Compute deterministic aggregate evaluation metrics."""
    reproducible = [
        row for row in rows if _as_bool(row.get("reproducible_flag", False))
    ]
    generated = [
        row for row in reproducible if row.get("synthesis_status") == "generated"
    ]
    first_success = [
        row for row in generated if row["attempts"] == 1
    ]
    grounded_values = [row["grounded_steps_ratio"] for row in generated]
    valid_scripts = [row for row in generated if row["script_compiles"]]
    executed = [row for row in generated if row.get("execution_status")]
    first_passed = [
        row
        for row in executed
        if _as_bool(row.get("_first_execution_passed", row["execution_status"] == "passed"))
    ]
    failure_kinds = Counter(
        row["failure_kind"] for row in executed if row.get("failure_kind")
    )
    grouped: dict[str, list[tuple[str, ...]]] = defaultdict(list)
    for row in rows:
        signature = row.get("_step_signature", row.get("step_signature", ()))
        grouped[row["journey_id"]].append(tuple(signature))
    stability_groups = [
        len(set(signatures)) == 1
        for signatures in grouped.values()
        if len(signatures) == repeats
    ]
    latencies = [float(row.get("llm_seconds", 0.0)) for row in rows]
    return {
        "execution_success_rate": _rate(len(first_passed), len(executed)),
        "failure_kind_distribution": dict(sorted(failure_kinds.items())),
        "first_attempt_success_rate": _rate(len(first_success), len(reproducible)),
        "generation_success_rate": _rate(len(generated), len(reproducible)),
        "grounded_step_rate": (
            sum(grounded_values) / len(grounded_values)
            if grounded_values
            else 0.0
        ),
        "llm_latency_p50_seconds": _percentile(latencies, 0.50),
        "llm_latency_p95_seconds": _percentile(latencies, 0.95),
        "mean_attempts": (
            statistics.fmean(row["attempts"] for row in rows) if rows else 0.0
        ),
        "model": model,
        "prompt_version": prompt_version,
        "replay_success_rate": _rate(
            sum(
                row.get("execution_status") == "passed"
                and row.get("failure_kind")
                != FailureKind.LOCATOR_NOT_FOUND.value
                for row in executed
            ),
            len(executed),
        ),
        "script_valid_rate": _rate(len(valid_scripts), len(generated)),
        "stability": (
            sum(stability_groups) / len(stability_groups)
            if stability_groups
            else 0.0
        ),
        "repeats": repeats,
    }


def write_outputs(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    runs_dir: str | Path,
) -> None:
    """Write CSV, JSON, and explanatory Markdown evaluation outputs."""
    root = Path(runs_dir)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "results.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows({field: row[field] for field in CSV_FIELDS} for row in rows)
    (root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Component 4 Synthesis Evaluation",
        "",
        "Failure reproduction of the original crash cannot be measured on telemetry that has no real app bug.",
        "This evaluation reports replay_success_rate instead: whether the synthesized script replayed successfully.",
        "",
        "```json",
        json.dumps(summary, indent=2, sort_keys=True),
        "```",
        "",
    ]
    (root / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Run the synthesis evaluation command."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        target = load_target_config(args.config)
        journeys = collect_journeys(args.telemetry_dir, limit=args.limit)
        llm = OllamaQwenClient(base_url=args.ollama_url, model=args.model)
        synthesis = SynthesisService(llm, target=target, use_c3=not args.no_c3)
        execution = (
            ExecutionService(target=target) if args.execute else None
        )
        rows = evaluate(
            journeys,
            synthesis,
            execution,
            runs_dir=args.runs_dir,
            repeats=args.repeats,
        )
        model = getattr(llm, "model", args.model)
        prompt_version = synthesis.prompt_builder.prompt_version
        summary = build_summary(
            rows,
            model=model,
            prompt_version=prompt_version,
            repeats=args.repeats,
        )
        write_outputs(rows, summary, args.runs_dir)
        return 0
    except (OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m evaluation.run_synthesis_eval")
    parser.add_argument("--telemetry-dir", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--runs-dir", required=True)
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--execute", dest="execute", action="store_true", default=True)
    parser.add_argument("--no-execute", dest="execute", action="store_false")
    parser.add_argument("--no-c3", action="store_true")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--limit", type=int)
    return parser


def _row(
    journey: FailureJourney,
    result: SynthesisResult,
    execution: ExecutionResult | None,
) -> dict[str, Any]:
    steps = result.steps
    grounded = sum(bool(step.metadata.get("grounded")) for step in steps)
    compiles = False
    if result.script is not None:
        try:
            compile(result.script, "<evaluation>", "exec")
        except SyntaxError:
            compiles = False
        else:
            compiles = True
    failure = execution.failure if execution else None
    return {
        "journey_id": journey.journey_id,
        "reproducible_flag": journey.metadata.get("reproducible", True) is not False,
        "synthesis_status": result.status,
        "attempts": len(result.attempts),
        "steps_count": len(steps),
        "grounded_steps_ratio": grounded / len(steps) if steps else 0.0,
        "script_compiles": compiles,
        "llm_seconds": result.elapsed_seconds,
        "execution_status": execution.status.value if execution else "",
        "failure_kind": failure.kind.value if failure else "",
        "failed_step_index": failure.step_index if failure else "",
        "execution_seconds": execution.elapsed_seconds if execution else 0.0,
        "_step_signature": [
            (
                step.action,
                tuple(sorted(step.target.items())),
                step.value,
            )
            for step in steps
        ],
        "_first_execution_passed": bool(
            execution
            and execution.attempts
            and execution.attempts[0].status.value == "passed"
        ),
    }


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _percentile(values: list[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() or character in "._-" else "_" for character in value).strip("._") or "journey"


if __name__ == "__main__":
    raise SystemExit(main())
