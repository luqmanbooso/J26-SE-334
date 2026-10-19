"""Run the deterministic offline Component 4 healing evaluation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

from c4.healing.models import HealingConfig
from c4.healing.hierarchy import parse_hierarchy
from c4.healing.semantic import LexicalEmbedder, SentenceBertEmbedder

from .baselines import ExactLocatorOnly, Proposed, SemanticOnly, StructureOnly
from .datasets import load_hierarchies, load_release_pairs
from .metrics import aggregate, classify
from .scenario_builder import Scenario, build_scenarios, write_scenarios
from .threshold_sweep import run_threshold_sweep


METHODS = (
    ExactLocatorOnly,
    StructureOnly,
    SemanticOnly,
)


def run(
    hierarchies: str | Path,
    out: str | Path,
    *,
    seed: int = 42,
    targets_per_screen: int = 3,
    embedder_name: str = "sbert",
    release_manifest: str | Path | None = None,
) -> dict[str, object]:
    """Run all baselines and write the evaluation artifacts."""
    if targets_per_screen < 1:
        raise ValueError("targets-per-screen must be at least one")
    embedder = (
        LexicalEmbedder()
        if embedder_name == "lexical"
        else SentenceBertEmbedder(HealingConfig().sbert_model)
    )
    config = HealingConfig(embedder=embedder_name)
    skipped: dict[str, dict[str, int]] = {}
    scenarios = build_scenarios(
        load_hierarchies(hierarchies),
        seed,
        targets_per_screen,
        skip_report=skipped,
    )
    output = Path(out)
    output.mkdir(parents=True, exist_ok=True)
    write_scenarios(output / "scenarios.jsonl", scenarios)
    methods = [
        ExactLocatorOnly(),
        StructureOnly(config),
        SemanticOnly(config, embedder),
        Proposed(config, embedder, True),
        Proposed(config, embedder, False),
    ]
    results = {
        method.name: [method.solve(item, item.old_xml, item.new_xml) for item in scenarios]
        for method in methods
    }
    _write_results(output / "results.csv", scenarios, results)
    summary = aggregate(scenarios, results, seed)
    (output / "summary.json").write_text(
        json.dumps(
            {
                "methods": summary,
                "change_classes": _change_class_summary(scenarios, results),
                "skipped": skipped,
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    (output / "summary.md").write_text(
        _markdown_summary(summary, scenarios, results, skipped),
        encoding="utf-8",
    )
    run_threshold_sweep(scenarios, embedder, output / "threshold_sweep.csv", seed=seed)
    info = {
        "seed": seed,
        "embedder": embedder.name,
        "model": getattr(config, "sbert_model", None) if embedder.name == "sbert" else None,
        "threshold": config.confidence_threshold,
        "ambiguity_margin": config.ambiguity_margin,
        "config_hash": hashlib.sha256(config.model_dump_json().encode()).hexdigest(),
        "python": platform.python_version(),
        "package_versions": _versions(),
        "scenario_count": len(scenarios),
        "in_scope_count": sum(item.in_scope for item in scenarios),
        "out_of_scope_count": sum(not item.in_scope for item in scenarios),
        "skipped": skipped,
    }
    (output / "run_info.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if release_manifest:
        pairs = load_release_pairs(release_manifest)
        with (output / "summary.md").open("a", encoding="utf-8") as stream:
            stream.write("\n## Hand-labelled release pairs\n\n")
            stream.write("| Name | Method | Status | Expected new | Selected node |\n|---|---|---|---|---:|\n")
            for pair in pairs:
                pair_scenario = _release_pair_scenario(pair)
                outcome = Proposed(config, embedder, True).solve(
                    pair_scenario, pair_scenario.old_xml, pair_scenario.new_xml
                )
                stream.write(
                    f"| {pair['name']} | B3_proposed_with_baseline | {outcome.status} | "
                    f"{pair['expected_new']} | {outcome.node_index} |\n"
                )
    return summary


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and return an exit code."""
    parser = argparse.ArgumentParser(prog="python -m evaluation.run_healing_eval")
    parser.add_argument("--hierarchies", default="evaluation/samples")
    parser.add_argument("--release-manifest")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--targets-per-screen", type=int, default=3)
    parser.add_argument("--embedder", choices=("sbert", "lexical"), default="sbert")
    parser.add_argument("--out", required=True)
    try:
        args = parser.parse_args(argv)
        run(args.hierarchies, args.out, seed=args.seed, targets_per_screen=args.targets_per_screen,
            embedder_name=args.embedder, release_manifest=args.release_manifest)
        return 0
    except (OSError, ValueError, ImportError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2


def _write_results(path: Path, scenarios: list[Scenario], results) -> None:
    fields = ["scenario_id", "change_class", "in_scope", "expected_status", "method",
              "status", "node_index", "classification", "latency_ms",
              "candidates_total", "candidates_after_narrowing", "embedder"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for method, outcomes in results.items():
            for scenario, outcome in zip(scenarios, outcomes):
                writer.writerow({
                    "scenario_id": scenario.scenario_id,
                    "change_class": scenario.change_class,
                    "in_scope": scenario.in_scope,
                    "expected_status": scenario.expected_status,
                    "method": method,
                    "status": outcome.status,
                    "node_index": outcome.node_index,
                    "classification": classify(scenario, outcome),
                    "latency_ms": f"{outcome.latency_ms:.6f}",
                    "candidates_total": outcome.candidates_total,
                    "candidates_after_narrowing": outcome.candidates_after_narrowing,
                    "embedder": outcome.embedder,
                })


def _change_class_summary(scenarios, results):
    output = {}
    for change_class in sorted({item.change_class for item in scenarios}):
        selected = [index for index, item in enumerate(scenarios) if item.change_class == change_class]
        output[change_class] = {}
        for method, outcomes in results.items():
            labels = [classify(scenarios[index], outcomes[index]) for index in selected]
            output[change_class][method] = dict(__import__("collections").Counter(labels))
    return output


def _markdown_summary(summary, scenarios, results, skipped=None) -> str:
    lines = ["# Healing evaluation summary", "", "## Methods", "",
             "| Method | Accuracy | False repair | Safe refusal | Missed heal |",
             "|---|---:|---:|---:|---:|"]
    for method, values in summary.items():
        if method == "B0_exact_locator_only":
            lines.append(
                f"| {method} | n/a (never attempts to heal) | 0.0000 | "
                f"n/a (never attempts to heal) | n/a (never attempts to heal) |"
            )
            continue
        lines.append(
            f"| {method} | {values['healing_accuracy']:.4f} | {values['false_repair_rate']:.4f} | "
            f"{values['safe_refusal_rate']:.4f} | {values['missed_heal_rate']:.4f} |"
        )
    if skipped:
        lines.extend(["", "## Skipped scenarios", "", "| Change class | Reason | Count |", "|---|---|---:|"])
        for change_class in sorted(skipped):
            for reason, count in sorted(skipped[change_class].items()):
                lines.append(f"| {change_class} | {reason} | {count} |")
    lines.extend([
        "", "## Change classes", "",
        "| Change class | Method | Correct heal | False repair | Safe refusal | Missed heal |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for change_class in sorted({item.change_class for item in scenarios}):
        selected = [
            index for index, item in enumerate(scenarios)
            if item.change_class == change_class
        ]
        for method, outcomes in results.items():
            counts = {
                label: sum(
                    classify(scenarios[index], outcomes[index]) == label
                    for index in selected
                )
                for label in ("correct_heal", "false_repair", "safe_refusal", "missed_heal")
            }
            lines.append(
                f"| {change_class} | {method} | {counts['correct_heal']} | "
                f"{counts['false_repair']} | {counts['safe_refusal']} | "
                f"{counts['missed_heal']} |"
            )
    return "\n".join(lines) + "\n"


def _versions() -> dict[str, str]:
    result = {}
    for name in ("heart-component4", "pydantic", "libcst"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return result


def _release_pair_scenario(pair: dict[str, object]) -> Scenario:
    """Convert one manifest entry into the common scenario representation."""
    old_xml = Path(str(pair["old_xml_path"])).read_text(encoding="utf-8")
    new_xml = Path(str(pair["new_xml_path"])).read_text(encoding="utf-8")
    locator = pair["script_locator"]
    if not isinstance(locator, dict) or not {"by", "value"}.issubset(locator):
        raise ValueError("release script_locator must contain by and value")
    by = str(locator["by"])
    value = str(locator["value"])
    constant = {
        "id": "ID",
        "accessibility id": "ACCESSIBILITY_ID",
        "accessibility_id": "ACCESSIBILITY_ID",
        "-android uiautomator": "ANDROID_UIAUTOMATOR",
        "android_uiautomator": "ANDROID_UIAUTOMATOR",
        "xpath": "XPATH",
    }.get(by, by)
    script = (
        "from appium.webdriver.common.appiumby import AppiumBy\n\n"
        "def step_0(driver):\n"
        f"    driver.find_element(AppiumBy.{constant}, {value!r}).click()\n"
    )
    old = parse_hierarchy(old_xml)
    old_nodes = old.find_by_locator(_release_strategy(by), value)
    if not old_nodes:
        raise ValueError(f"release locator does not match old hierarchy: {pair['name']}")
    expected = pair["expected_new"]
    expected_index = None
    if isinstance(expected, dict):
        new = parse_hierarchy(new_xml)
        if "resource_id" in expected:
            matches = [node for node in new.nodes if node.resource_id == expected["resource_id"]]
        elif "text" in expected:
            matches = [node for node in new.nodes if node.text == expected["text"]]
        else:
            matches = []
        if len(matches) == 1:
            expected_index = matches[0].index
    return Scenario(
        str(pair["name"]), str(pair["name"]), old_xml, new_xml, script, 0,
        by, value, old_nodes[0].index, "release_pair", expected is not None,
        "heal" if expected is not None else "refuse", expected_index,
    )


def _release_strategy(by: str) -> str:
    return {
        "ID": "id", "id": "id",
        "ACCESSIBILITY_ID": "accessibility id", "accessibility_id": "accessibility id",
        "accessibility id": "accessibility id",
        "ANDROID_UIAUTOMATOR": "-android uiautomator",
        "android_uiautomator": "-android uiautomator",
        "-android uiautomator": "-android uiautomator",
        "XPATH": "xpath", "xpath": "xpath",
    }.get(by, by)


if __name__ == "__main__":
    raise SystemExit(main())
