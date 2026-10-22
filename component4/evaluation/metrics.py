"""Metrics and statistical summaries for healing evaluation."""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from statistics import mean
from typing import Iterable

from .baselines import Outcome
from .scenario_builder import Scenario


def classify(scenario: Scenario, outcome: Outcome) -> str:
    """Classify one method result against scenario ground truth."""
    if scenario.expected_status == "heal":
        if outcome.status == "healed" and outcome.node_index == scenario.expected_node_index_in_new:
            return "correct_heal"
        if outcome.status == "healed":
            return "false_repair"
        return "missed_heal"
    if outcome.status == "refused":
        return "safe_refusal"
    return "false_repair"


def bootstrap_ci(values: list[float], seed: int, samples: int = 1000) -> tuple[float, float]:
    """Return a seeded percentile bootstrap confidence interval."""
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    estimates = [
        mean(rng.choice(values) for _ in values)
        for _ in range(samples)
    ]
    estimates.sort()
    return estimates[int(samples * 0.025)], estimates[int(samples * 0.975)]


def mcnemar_exact(first: list[bool], second: list[bool]) -> float:
    """Return the two-sided exact McNemar p-value for paired correctness."""
    discordant = sum(left != right for left, right in zip(first, second))
    if discordant == 0:
        return 1.0
    smaller = min(sum(left and not right for left, right in zip(first, second)),
                  sum(right and not left for left, right in zip(first, second)))
    tail = sum(math.comb(discordant, index) for index in range(smaller + 1)) / (2**discordant)
    return min(1.0, 2 * tail)


def aggregate(
    scenarios: list[Scenario],
    results: dict[str, list[Outcome]],
    seed: int,
) -> dict[str, dict[str, object]]:
    """Aggregate method metrics and paired comparisons."""
    summary: dict[str, dict[str, object]] = {}
    in_scope = [item.in_scope for item in scenarios]
    for method, outcomes in results.items():
        labels = [classify(scenario, outcome) for scenario, outcome in zip(scenarios, outcomes)]
        correct = sum(label == "correct_heal" for label in labels)
        false = sum(label == "false_repair" for label in labels)
        in_count = sum(in_scope)
        out_count = len(scenarios) - in_count
        accuracy_values = [
            float(label == "correct_heal") for label, scenario in zip(labels, scenarios) if scenario.in_scope
        ]
        false_values = [float(label == "false_repair") for label in labels]
        latencies = sorted(outcome.latency_ms for outcome in outcomes)
        narrowed = [outcome.candidates_after_narrowing for outcome in outcomes]
        total = [outcome.candidates_total for outcome in outcomes]
        summary[method] = {
            "counts": dict(Counter(labels)),
            "healing_accuracy": correct / in_count if in_count else 0.0,
            "false_repair_rate": false / len(scenarios) if scenarios else 0.0,
            "safe_refusal_rate": sum(label == "safe_refusal" for label in labels) / out_count if out_count else 0.0,
            "missed_heal_rate": sum(label == "missed_heal" for label in labels) / in_count if in_count else 0.0,
            "mean_candidates_total": mean(total) if total else 0.0,
            "mean_candidates_after_narrowing": mean(narrowed) if narrowed else 0.0,
            "narrowing_ratio": mean(n / t for n, t in zip(narrowed, total) if t) if total else 0.0,
            "latency_p50_ms": _percentile(latencies, 0.5),
            "latency_p95_ms": _percentile(latencies, 0.95),
            "accuracy_ci_95": bootstrap_ci(accuracy_values, seed),
            "false_repair_ci_95": bootstrap_ci(false_values, seed + 1),
        }
    proposed = results.get("B3_proposed_with_baseline")
    if proposed is not None:
        proposed_correct = [
            classify(scenario, outcome) == "correct_heal"
            for scenario, outcome in zip(scenarios, proposed)
            if scenario.in_scope
        ]
        for method, outcomes in results.items():
            if method == "B3_proposed_with_baseline":
                continue
            other = [
                classify(scenario, outcome) == "correct_heal"
                for scenario, outcome in zip(scenarios, outcomes)
                if scenario.in_scope
            ]
            summary[method]["mcnemar_p_b3_vs_method"] = mcnemar_exact(proposed_correct, other)
    return summary


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    return values[min(len(values) - 1, int((len(values) - 1) * fraction))]

