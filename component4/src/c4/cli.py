"""Command-line entry point for Component 4."""

from __future__ import annotations

import argparse
import sys

from c4.config import load_target_config
from c4.execution import ExecutionService
from c4.pipeline import Pipeline
from c4.synthesis.qwen_client import OllamaQwenClient


def build_parser() -> argparse.ArgumentParser:
    """Build the Component 4 argument parser."""
    parser = argparse.ArgumentParser(prog="c4")
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--config", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--telemetry", required=True)
    run.add_argument("--config", required=True)
    run.add_argument("--runs-dir", required=True)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--no-c3", action="store_true")
    run.add_argument("--limit", type=int)
    run.add_argument("--model", default="qwen3:8b")
    run.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the selected command and return a process exit code."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        target = load_target_config(args.config)
        if args.command == "preflight":
            report = ExecutionService(target=target).preflight()
            print(report.model_dump_json(indent=2))
            return 0 if not report.problems else 1
        llm = OllamaQwenClient(base_url=args.ollama_url, model=args.model)
        records = Pipeline(
            llm,
            target,
            use_c3=not args.no_c3,
        ).run(
            args.telemetry,
            args.runs_dir,
            dry_run=args.dry_run,
            limit=args.limit,
        )
        failed = any(
            record.status == "synthesis_failed"
            or (
                record.execution is not None
                and getattr(record.execution, "status", None) != "passed"
            )
            for record in records
        )
        return 1 if failed else 0
    except (OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2
