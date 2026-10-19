"""Command-line entry point for Component 4."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from c4.config import load_target_config
from c4.execution import ExecutionService
from c4.pipeline import Pipeline
from c4.synthesis.qwen_client import OllamaQwenClient
from c4.healing import HealingConfig, HealingEngine, HealingService
from c4.healing.baseline import BaselineStore
from c4.healing.semantic import LexicalEmbedder
from c4.store.repository import TestRepository


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
    run.add_argument("--heal", action="store_true")
    run.add_argument("--capture-baseline", action="store_true")
    run.add_argument("--baseline-dir")
    run.add_argument("--repo-dir")
    run.add_argument("--embedder", choices=("sbert", "lexical"), default="sbert")
    run.add_argument("--heal-threshold", type=float, default=0.5)
    run.add_argument("--max-heal-rounds", type=int, default=3)
    heal = subparsers.add_parser("heal")
    heal.add_argument("--script", required=True)
    heal.add_argument("--step", required=True, type=int)
    heal.add_argument("--new-hierarchy", required=True)
    heal.add_argument("--baseline-hierarchy")
    heal.add_argument("--embedder", choices=("sbert", "lexical"), default="sbert")
    heal.add_argument("--out")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the selected command and return a process exit code."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "heal":
            script = Path(args.script).read_text(encoding="utf-8")
            new_hierarchy = Path(args.new_hierarchy).read_text(encoding="utf-8")
            baseline_hierarchy = (
                Path(args.baseline_hierarchy).read_text(encoding="utf-8")
                if args.baseline_hierarchy
                else None
            )
            config = HealingConfig(embedder=args.embedder)
            decision = HealingEngine(
                config,
                embedder=LexicalEmbedder() if args.embedder == "lexical" else None,
            ).heal(
                script,
                args.step,
                new_hierarchy,
                baseline_hierarchy_xml=baseline_hierarchy,
            )
            output = decision.model_dump_json(indent=2)
            if args.out:
                Path(args.out).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 0 if decision.status.value == "healed" else 1
        target = load_target_config(args.config)
        if args.command == "preflight":
            report = ExecutionService(target=target).preflight()
            print(report.model_dump_json(indent=2))
            return 0 if not report.problems else 1
        healer = None
        if getattr(args, "heal", False):
            heal_config = HealingConfig(
                embedder=args.embedder,
                confidence_threshold=args.heal_threshold,
                max_heal_rounds=args.max_heal_rounds,
            )
            healer = HealingService(
                HealingEngine(
                    heal_config,
                    embedder=LexicalEmbedder() if args.embedder == "lexical" else None,
                ),
                ExecutionService(target=target),
                BaselineStore(Path(args.baseline_dir or Path(args.runs_dir) / "baselines")),
                TestRepository(Path(args.repo_dir or Path(args.runs_dir) / "repository")),
                heal_config,
            )
        llm = OllamaQwenClient(base_url=args.ollama_url, model=args.model)
        records = Pipeline(
            llm,
            target,
            use_c3=not args.no_c3,
            healer=healer,
        ).run(
            args.telemetry,
            args.runs_dir,
            dry_run=args.dry_run,
            limit=args.limit,
            capture_baseline=args.capture_baseline,
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
    except (OSError, ValueError, TypeError, ImportError) as error:
        print(str(error), file=sys.stderr)
        return 2
