"""Confidence-threshold sweep for the proposed healing method."""

from __future__ import annotations

import csv
from pathlib import Path

from c4.healing.models import HealingConfig
from .baselines import Proposed
from .scenario_builder import Scenario


def run_threshold_sweep(
    scenarios: list[Scenario],
    embedder,
    output: str | Path,
    *,
    seed: int = 42,
) -> None:
    """Evaluate B3 at thresholds from 0.30 through 0.70."""
    from .metrics import classify

    rows: list[dict[str, object]] = []
    for step in range(9):
        threshold = 0.30 + step * 0.05
        config = HealingConfig(embedder=embedder.name, confidence_threshold=threshold)
        method = Proposed(config, embedder, True)
        outcomes = [method.solve(item, item.old_xml, item.new_xml) for item in scenarios]
        labels = [classify(item, outcome) for item, outcome in zip(scenarios, outcomes)]
        in_scope = sum(item.in_scope for item in scenarios)
        rows.append({
            "threshold": f"{threshold:.2f}",
            "accuracy": sum(label == "correct_heal" for label in labels if True) / in_scope if in_scope else 0.0,
            "false_repair_rate": sum(label == "false_repair" for label in labels) / len(labels) if labels else 0.0,
            "missed_heal_rate": sum(label == "missed_heal" for label in labels) / in_scope if in_scope else 0.0,
        })
    with Path(output).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

