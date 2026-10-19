from __future__ import annotations

import json
import random

from c4.healing.models import HealingConfig
from c4.healing.semantic import LexicalEmbedder
from evaluation.baselines import ExactLocatorOnly, Proposed, SemanticOnly, StructureOnly
from evaluation.metrics import aggregate, bootstrap_ci, classify, mcnemar_exact
from evaluation.mutations import (
    MUTATIONS,
    ambiguous_lookalike,
    class_change_cross_family,
    remove_node,
)
from evaluation.run_healing_eval import run
from evaluation.scenario_builder import build_scenarios


SAMPLE = """<hierarchy>
<node class="android.widget.LinearLayout" enabled="true" bounds="[0,0][500,500]">
<node class="android.widget.Button" resource-id="app:id/pay" text="Pay" clickable="true" enabled="true" bounds="[0,0][100,80]" />
</node></hierarchy>"""


def test_mutations_are_seeded_and_out_of_scope_classes_refuse() -> None:
    for mutation in MUTATIONS:
        try:
            first = mutation(SAMPLE, 2, random.Random(7))
            second = mutation(SAMPLE, 2, random.Random(7))
        except ValueError:
            continue
        assert first == second
        assert first.new_xml != SAMPLE
    assert remove_node(SAMPLE, 2, random.Random(1)).expected_status == "refuse"
    assert ambiguous_lookalike(SAMPLE, 2, random.Random(1)).expected_status == "refuse"
    assert class_change_cross_family(SAMPLE, 2, random.Random(1)).expected_status == "refuse"


def test_metrics_and_statistics_are_deterministic() -> None:
    scenarios = build_scenarios([("sample.xml", SAMPLE)], 42, 1)
    selected = [item for item in scenarios if item.change_class in {"rename_id", "remove_node"}]
    outcomes = [
        type("Outcome", (), {
            "status": "healed" if item.in_scope else "refused",
            "node_index": item.expected_node_index_in_new,
            "latency_ms": 1.0,
            "candidates_total": 3,
            "candidates_after_narrowing": 1,
            "embedder": "lexical",
        })()
        for item in selected
    ]
    assert all(classify(item, outcome) in {"correct_heal", "safe_refusal"} for item, outcome in zip(selected, outcomes))
    summary = aggregate(selected, {"method": outcomes}, 42)
    assert summary["method"]["counts"]["correct_heal"] >= 1
    assert bootstrap_ci([0.0, 1.0], 42) == bootstrap_ci([0.0, 1.0], 42)
    assert mcnemar_exact([True, False, True], [True, True, False]) == 1.0


def test_baselines_return_common_outcome_shape() -> None:
    scenarios = build_scenarios([("sample.xml", SAMPLE)], 1, 1)
    scenario = next(item for item in scenarios if item.change_class == "rename_id")
    config = HealingConfig(embedder="lexical")
    embedder = LexicalEmbedder()
    methods = [
        ExactLocatorOnly(),
        StructureOnly(config),
        SemanticOnly(config, embedder),
        Proposed(config, embedder, True),
        Proposed(config, embedder, False),
    ]
    for method in methods:
        outcome = method.solve(scenario, scenario.old_xml, scenario.new_xml)
        assert outcome.status in {"healed", "refused"}
        assert outcome.candidates_total >= 0
        assert outcome.candidates_after_narrowing >= 0


def test_end_to_end_smoke_is_reproducible(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    run("evaluation/samples", first, seed=42, targets_per_screen=3, embedder_name="lexical")
    run("evaluation/samples", second, seed=42, targets_per_screen=3, embedder_name="lexical")
    expected = {
        "scenarios.jsonl", "results.csv", "summary.json", "summary.md",
        "threshold_sweep.csv", "run_info.json",
    }
    assert {path.name for path in first.iterdir()} == expected
    for name in expected:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    payload = json.loads((first / "summary.json").read_text(encoding="utf-8"))
    assert set(payload["methods"]) == {
        "B0_exact_locator_only", "B1_structure_only", "B2_semantic_only",
        "B3_proposed_with_baseline", "B4_proposed_telemetry_only",
    }
