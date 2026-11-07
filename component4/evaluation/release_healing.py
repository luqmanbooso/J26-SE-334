"""Heal a test across two real releases of the same app.

A test is generated for a journey recorded against one release, run on that release
(capturing a baseline), then run unchanged on a different real release of the same app.
A locator failure on the newer release is healed against the older release's screen.

Both releases run the identical script: the app is installed by a setup command, so
the script names only the package and its baseline stays valid for the second release.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from c4.config import TargetAppConfig, load_target_config
from c4.execution.models import ExecutionStatus, FailureKind
from c4.execution.service import ExecutionService
from c4.healing.baseline import BaselineStore
from c4.healing.engine import HealingEngine
from c4.healing.models import HealingConfig
from c4.healing.semantic import LexicalEmbedder
from c4.healing.service import HealingService
from c4.store.repository import TestRepository

COMPATIBILITY_DIALOG = "DeprecatedTargetSdkVersionDialog"
SYSTEM_PREFIXES = ("com.android.", "android:", "android.")

CSV_FIELDS = (
    "pair", "package", "source", "source_commit", "target", "target_commit", "steps", "system_steps_removed",
    "source_status", "source_failure", "target_status", "target_failure", "failed_step",
    "heal_status", "healed_locator", "heal_baseline", "heal_without_baseline", "final_status",
)


def prepare_device(adb: str, serial: str | None) -> None:
    """Stop Android 15 from showing its older-version compatibility dialog on every launch.

    That dialog covers the app and hides every element, so no test could run on those apps.
    The property lasts until the emulator restarts.
    """
    command = [adb, *(["-s", serial] if serial else []), "shell", "setprop", "debug.wm.disable_deprecated_target_sdk_dialog", "1"]
    subprocess.run(command, capture_output=True, text=True, timeout=60)


def apk_target(base: TargetAppConfig, package: str, apk: Path) -> TargetAppConfig:
    """Target that installs ``apk`` fresh before each run and launches ``package``."""
    return base.model_copy(update={
        "package": package, "activity": None, "apk_path": None, "wait_activity": "*",
        "setup_commands": [
            ["shell", f"pm uninstall {package} >/dev/null 2>&1; true"],
            ["install", "-r", "-d", "-g", str(apk)],
        ],
    })


def survey_apk(adb: str, serial: str | None, package: str, apk: Path, settle_seconds: float = 6.0) -> str:
    """Install and launch one APK; return ``ok`` or the reason it cannot be used."""
    base = [adb, *(["-s", serial] if serial else [])]

    def run(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
        return subprocess.run([*base, *args], capture_output=True, text=True, timeout=timeout)

    run("shell", f"pm uninstall {package} >/dev/null 2>&1; true")
    installed = run("install", "-r", "-d", "-g", str(apk), timeout=240)
    if installed.returncode != 0 or "Success" not in installed.stdout:
        text = (installed.stdout + installed.stderr).replace("\n", " ")
        marker = next((word for word in text.replace("[", " ").replace("]", " ").replace(":", " ").split()
                       if word.startswith("INSTALL_")), None)
        return f"install failed: {marker or text[:80]}"
    run("shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
    time.sleep(settle_seconds)
    running = run("shell", f"pidof {package}").stdout.strip()
    focus = run("shell", "dumpsys window | grep mCurrentFocus", timeout=30).stdout
    run("shell", f"pm uninstall {package} >/dev/null 2>&1; true")
    if not running:
        return "launch failed: process not running after launch"
    if COMPATIBILITY_DIALOG in focus:
        return "blocked: Android shows an older-version compatibility dialog on every launch"
    return "ok"


def without_system_steps(journey: Any, package: str) -> tuple[Any, int]:
    """Drop events that tap the Android system (permission dialogs), which are not part of the app.

    The app is installed with permissions pre-granted, so such dialogs never appear, and their
    ids differ between Android versions.
    """
    kept = [
        event for event in journey.events
        if not _targets_system(event.locator.get("resource_id", ""), package)
    ]
    return journey.model_copy(update={"events": kept}), len(journey.events) - len(kept)


def _targets_system(resource_id: str, package: str) -> bool:
    return bool(resource_id) and not resource_id.startswith(package) and resource_id.startswith(SYSTEM_PREFIXES)


def select_pairs(
    traces: list[dict[str, Any]],
    compatible: dict[str, str],
    *,
    max_steps: int = 8,
    min_steps: int = 2,
    per_app: int = 2,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Pick, per app, one short source test and other releases of the same app to run it on."""
    usable = [t for t in traces if compatible.get(t["trace_id"].removeprefix("andror2-")) == "ok" and t.get("app_package")]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trace in usable:
        groups[trace["app_package"]].append(trace)
    pairs = []
    for package in sorted(groups):
        group = sorted(groups[package], key=lambda t: _number(t["trace_id"]))
        sources = [t for t in group if min_steps <= len(t["steps"]) <= max_steps]
        for source in sorted(sources, key=lambda t: (len(t["steps"]), _number(t["trace_id"]))):
            seen = {source["app_version"]}
            targets = []
            for other in group:
                if other["app_version"] not in seen:
                    seen.add(other["app_version"])
                    targets.append(other)
            if targets:
                pairs.extend((source, target) for target in targets[:per_app])
                break
    return pairs


def run_pair(
    source: dict[str, Any],
    target: dict[str, Any],
    journey: Any,
    *,
    synthesis: Any,
    base: TargetAppConfig,
    apk_root: Path,
    runs_dir: Path,
    embedder_name: str,
    embedder: Any,
    execution_factory: Any = ExecutionService,
) -> dict[str, Any]:
    package = source["app_package"]
    pair = f"{source['trace_id']}->{target['trace_id']}"
    row: dict[str, Any] = {field: "" for field in CSV_FIELDS}
    row.update(pair=pair, package=package, source=source["trace_id"], source_commit=source["app_version"][:8],
               target=target["trace_id"], target_commit=target["app_version"][:8])
    source_target = apk_target(base, package, apk_root / source["app_apk"])
    target_target = apk_target(base, package, apk_root / target["app_apk"])
    journey, removed = without_system_steps(journey, package)
    row["system_steps_removed"] = removed
    synthesis.target = source_target
    result = synthesis.synthesize(journey)
    row["steps"] = len(result.steps)
    if result.status != "generated" or result.script is None:
        row["final_status"] = f"generation {result.status}"
        return row

    first = execution_factory(target=source_target).execute(
        result, runs_dir=runs_dir, run_id=f"{pair}-source".replace(">", ""), capture_baseline=True)
    row["source_status"] = first.status.value
    if first.status is not ExecutionStatus.PASSED:
        row["source_failure"] = _failure_text(first)
        row["final_status"] = "source release does not pass"
        return row
    test_id = pair.replace("->", "_to_")
    store = BaselineStore(runs_dir / "baselines")
    store.save_from_run(test_id, runs_dir / f"{pair}-source".replace(">", ""))

    execution = execution_factory(target=target_target)
    second = execution.execute(result, runs_dir=runs_dir, run_id=f"{pair}-target".replace(">", ""))
    row["target_status"] = second.status.value
    if second.failure is not None:
        row["target_failure"] = second.failure.kind.value
        row["failed_step"] = "" if second.failure.step_index is None else second.failure.step_index
    if second.status is ExecutionStatus.PASSED:
        row["final_status"] = "passes unchanged on the other release"
        return row
    if second.failure is None or second.failure.kind is not FailureKind.LOCATOR_NOT_FOUND:
        row["final_status"] = f"fails, not a locator failure ({row['target_failure'] or second.status.value})"
        return row

    config = HealingConfig(embedder=embedder_name)
    engine = HealingEngine(config, embedder)
    page = Path(second.failure.page_source_path) if second.failure.page_source_path else None
    if page is not None and page.exists():
        blind = engine.heal(result.script, second.failure.step_index or 0, page.read_text(encoding="utf-8"))
        row["heal_without_baseline"] = blind.status.value
    service = HealingService(engine, execution, store, TestRepository(runs_dir / "repository"), config)
    outcome = service.heal_and_rerun(result, second, runs_dir / f"{pair}-target".replace(">", ""), test_id)
    last = outcome.rounds[-1].decision if outcome.rounds else None
    row["heal_status"] = last.status.value if last else ""
    row["healed_locator"] = json.dumps(last.healed_locator) if last and last.healed_locator else ""
    row["heal_baseline"] = "used" if last and last.r6_applied else "not used"
    row["final_status"] = outcome.final_status
    return row


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ran = [r for r in rows if r["source_status"] == "passed"]
    broke = [r for r in ran if r["target_failure"] == FailureKind.LOCATOR_NOT_FOUND.value]
    return {
        "pairs": len(rows),
        "source_passes": len(ran),
        "pass_unchanged": sum(r["final_status"].startswith("passes unchanged") for r in ran),
        "locator_failures": len(broke),
        "other_failures": sum(r["target_status"] not in ("passed", "") and r not in broke for r in ran),
        "healed_and_verified": sum(r["final_status"] == "passed_after_healing" for r in broke),
        "refused": sum(r["final_status"] == "refused" for r in broke),
        "failed_after_healing": sum(r["final_status"] == "failed_after_healing" for r in broke),
        "healed_without_baseline": sum(r["heal_without_baseline"] == "healed" for r in broke),
    }


def _failure_text(result: Any) -> str:
    if result.failure is not None:
        return result.failure.kind.value
    return result.error_type or result.status.value


def _number(trace_id: str) -> int:
    tail = trace_id.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 10**9


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluation.release_healing")
    sub = parser.add_subparsers(dest="command", required=True)
    survey = sub.add_parser("survey", help="Install and launch each APK to find the ones the emulator can run")
    survey.add_argument("--traces", required=True)
    survey.add_argument("--apk-root", required=True)
    survey.add_argument("--config", required=True, help="Target config; supplies adb path and device serial")
    survey.add_argument("--out", required=True)
    run = sub.add_parser("run", help="Run the release-to-release healing experiment")
    run.add_argument("--traces", required=True)
    run.add_argument("--apk-root", required=True)
    run.add_argument("--config", required=True)
    run.add_argument("--compat", required=True, help="compat.json written by the survey")
    run.add_argument("--runs-dir", required=True)
    run.add_argument("--embedder", choices=("lexical", "sbert"), default="lexical")
    run.add_argument("--model", default="qwen3:8b")
    run.add_argument("--max-steps", type=int, default=8)
    run.add_argument("--per-app", type=int, default=2)
    run.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    traces = [json.loads(line) for line in Path(args.traces).read_text(encoding="utf-8").splitlines() if line.strip()]
    base = load_target_config(args.config)
    prepare_device(base.adb_path, base.udid)
    if args.command == "survey":
        results: dict[str, str] = {}
        for trace in traces:
            key = trace["trace_id"].removeprefix("andror2-")
            apk = Path(args.apk_root) / trace["app_apk"]
            results[key] = survey_apk(base.adb_path, base.udid, trace["app_package"], apk) if apk.is_file() else "apk missing"
            print(f"{key}: {results[key]}", flush=True)
        Path(args.out).write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 0

    from c4.synthesis.qwen_client import OllamaQwenClient
    from c4.synthesis.service import SynthesisService
    from evaluation.run_synthesis_eval import collect_journeys

    compat = json.loads(Path(args.compat).read_text(encoding="utf-8"))
    pairs = select_pairs(traces, compat, max_steps=args.max_steps, per_app=args.per_app)
    pairs = pairs[: args.limit] if args.limit else pairs
    journeys = {j.session_id: j for j in collect_journeys(Path(args.traces).parent, source="trace", max_actions=30)}
    if args.embedder == "sbert":
        from c4.healing.semantic import SentenceBertEmbedder
        embedder: Any = SentenceBertEmbedder("sentence-transformers/all-MiniLM-L6-v2")
    else:
        embedder = LexicalEmbedder()
    llm = OllamaQwenClient(model=args.model, timeout_seconds=300.0, num_predict=2048)
    synthesis = SynthesisService(llm, target=base, use_c3=False)
    runs_dir = Path(args.runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for source, target in pairs:
        print(f"{source['trace_id']} -> {target['trace_id']}", flush=True)
        rows.append(run_pair(source, target, journeys[source["trace_id"]], synthesis=synthesis, base=base,
                             apk_root=Path(args.apk_root), runs_dir=runs_dir,
                             embedder_name=args.embedder, embedder=embedder))
        print("   ", rows[-1]["final_status"], flush=True)
        _write(runs_dir, rows)  # after every pair, so a long run keeps what it has finished
    print(json.dumps(summarize(rows), indent=2))
    return 0


def _write(runs_dir: Path, rows: list[dict[str, Any]]) -> None:
    with (runs_dir / "results.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (runs_dir / "summary.json").write_text(
        json.dumps(summarize(rows), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
