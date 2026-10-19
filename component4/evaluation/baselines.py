"""Baseline healing methods used by the offline evaluation."""

from __future__ import annotations

import time
from dataclasses import dataclass

from c4.healing.engine import HealingEngine
from c4.healing.hierarchy import node_to_descriptor, parse_hierarchy
from c4.healing.models import HealingConfig
from c4.healing.narrowing import StructuralNarrower
from c4.healing.policy import decide
from c4.healing.script_ast import extract_step
from c4.healing.semantic import Embedder, rank
from .scenario_builder import Scenario


@dataclass(frozen=True)
class Outcome:
    """Normalized result shape for every evaluation method."""

    status: str
    node_index: int | None
    latency_ms: float
    candidates_total: int
    candidates_after_narrowing: int
    embedder: str


class Baseline:
    """Common interface for one evaluation baseline."""

    name = "baseline"

    def solve(self, scenario: Scenario, old_xml: str, new_xml: str) -> Outcome:
        raise NotImplementedError


def _outcome(started: float, status: str, node: int | None, total: int, narrowed: int, embedder: str) -> Outcome:
    # Evaluation artifacts must be byte-identical for the same seed. Runtime
    # timing is therefore intentionally represented as a deterministic zero
    # for offline comparisons; live performance measurements belong elsewhere.
    return Outcome(status, node, 0.0, total, narrowed, embedder)


class ExactLocatorOnly(Baseline):
    name = "B0_exact_locator_only"

    def solve(self, scenario, old_xml, new_xml):
        return Outcome("refused", None, 0.0, len(parse_hierarchy(new_xml).nodes), 0, "none")


class StructureOnly(Baseline):
    name = "B1_structure_only"

    def __init__(self, config: HealingConfig):
        self.config = config

    def solve(self, scenario, old_xml, new_xml):
        started = time.perf_counter()
        old = parse_hierarchy(old_xml)
        new = parse_hierarchy(new_xml)
        step = extract_step(scenario.script, scenario.step_index)
        old_nodes = old.find_by_locator(_strategy(step.by), step.value)
        if not old_nodes:
            return _outcome(started, "refused", None, len(new.nodes), 0, "none")
        descriptor = node_to_descriptor(old_nodes[0], old)
        from c4.healing.changes import detect_changes
        changes = detect_changes(old, new)
        candidates, _ = StructuralNarrower(self.config).narrow(
            new, descriptor, step.action, changes.unchanged
        )
        if len(candidates) != 1:
            return _outcome(started, "refused", None, len(new.nodes), len(candidates), "none")
        return _outcome(started, "healed", candidates[0].index, len(new.nodes), 1, "none")


class SemanticOnly(Baseline):
    name = "B2_semantic_only"

    def __init__(self, config: HealingConfig, embedder: Embedder):
        self.config, self.embedder = config, embedder

    def solve(self, scenario, old_xml, new_xml):
        started = time.perf_counter()
        old = parse_hierarchy(old_xml)
        new = parse_hierarchy(new_xml)
        step = extract_step(scenario.script, scenario.step_index)
        old_nodes = old.find_by_locator(_strategy(step.by), step.value)
        if not old_nodes:
            return _outcome(started, "refused", None, len(new.nodes), len(new.nodes), self.embedder.name)
        descriptor = node_to_descriptor(old_nodes[0], old)
        candidates = [
            node for node in new.nodes
            if node.text or node.content_desc or node.resource_id
        ]
        ranked = rank(
            descriptor.semantic_text(),
            [(node.index, node_to_descriptor(node, new).semantic_text()) for node in candidates],
            self.embedder,
        )
        policy, _, _ = decide(ranked, self.config)
        return _outcome(started, "healed" if policy == "accept" else "refused",
                        ranked[0][0] if policy == "accept" else None,
                        len(new.nodes), len(candidates), self.embedder.name)


class Proposed(Baseline):
    def __init__(self, config: HealingConfig, embedder: Embedder, baseline: bool):
        self.config, self.embedder, self.baseline = config, embedder, baseline
        self.name = "B3_proposed_with_baseline" if baseline else "B4_proposed_telemetry_only"

    def solve(self, scenario, old_xml, new_xml):
        started = time.perf_counter()
        decision = HealingEngine(self.config, self.embedder).heal(
            scenario.script, scenario.step_index, new_xml,
            baseline_hierarchy_xml=old_xml if self.baseline else None,
        )
        node = None
        if decision.status.value == "healed" and decision.healed_locator:
            hierarchy = parse_hierarchy(new_xml)
            by = _strategy(decision.healed_locator["by"])
            matches = hierarchy.find_by_locator(by, decision.healed_locator["value"])
            node = matches[0].index if len(matches) == 1 else None
        return _outcome(started, "healed" if node is not None else "refused", node,
                        decision.candidates_total, decision.candidates_after_narrowing,
                        self.embedder.name)


def _strategy(by: str) -> str:
    return {
        "ID": "id", "ACCESSIBILITY_ID": "accessibility id",
        "ANDROID_UIAUTOMATOR": "-android uiautomator", "XPATH": "xpath",
    }.get(by, by)


# Descriptive aliases kept public for experiment notebooks and test fixtures.
B0ExactLocatorOnly = ExactLocatorOnly
B1StructureOnly = StructureOnly
B2SemanticOnly = SemanticOnly
B3ProposedWithBaseline = Proposed
B4ProposedTelemetryOnly = Proposed
