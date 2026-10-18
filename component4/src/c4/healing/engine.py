"""Pure locator healing engine."""

from __future__ import annotations

import time

from c4.healing.changes import detect_changes
from c4.healing.hierarchy import (
    HierarchyParseError,
    UiHierarchy,
    UiNode,
    node_to_descriptor,
    parse_hierarchy,
)
from c4.healing.models import (
    CandidateScore,
    ElementDescriptor,
    HealingConfig,
    HealingDecision,
    HealingStatus,
)
from c4.healing.narrowing import StructuralNarrower
from c4.healing.policy import build_unique_locator, decide
from c4.healing.script_ast import StepNotFoundError, extract_step, rewrite_step_locator
from c4.healing.semantic import Embedder, LexicalEmbedder, SentenceBertEmbedder, rank


class HealingEngine:
    """Rank and safely rewrite a failed locator without device access."""

    def __init__(self, config: HealingConfig | None = None, embedder: Embedder | None = None) -> None:
        self.config = config or HealingConfig()
        self.embedder = embedder or (
            SentenceBertEmbedder(self.config.sbert_model)
            if self.config.embedder == "sbert"
            else LexicalEmbedder()
        )

    def heal(
        self,
        script_source: str,
        step_index: int,
        new_hierarchy_xml: str,
        baseline: ElementDescriptor | None = None,
        journey_context: dict[str, object] | None = None,
        baseline_hierarchy_xml: str | None = None,
    ) -> HealingDecision:
        """Return a safe healing decision and rewritten script when accepted."""
        started = time.perf_counter()
        base = dict(
            step_index=step_index,
            action=None,
            original_locator={},
            embedder=self.embedder.name,
            threshold=self.config.confidence_threshold,
        )
        try:
            step = extract_step(script_source, step_index)
            base["action"] = step.action
            base["original_locator"] = {"by": _normalize_strategy(step.by), "value": step.value}
            descriptor = baseline or _fallback_descriptor(step.by, step.value, journey_context)
            hierarchy = parse_hierarchy(new_hierarchy_xml)
            excluded: frozenset[int] = frozenset()
            r6_applied = False
            if baseline_hierarchy_xml:
                baseline_hierarchy = parse_hierarchy(baseline_hierarchy_xml)
                changes = detect_changes(baseline_hierarchy, hierarchy)
                excluded = changes.unchanged
                r6_applied = True
                if baseline is None:
                    old_nodes = baseline_hierarchy.find_by_locator(
                        _hierarchy_strategy(step.by), _hierarchy_value(step.by, step.value)
                    )
                    if old_nodes:
                        descriptor = node_to_descriptor(old_nodes[0], baseline_hierarchy)
            candidates, rule_counts = StructuralNarrower(self.config).narrow(
                hierarchy, descriptor, step.action, excluded
            )
            if not candidates:
                return self._finish(base, HealingStatus.REFUSED_NO_CANDIDATES, started, reason="No structurally compatible candidates remain.", rule_counts=rule_counts, r6_applied=r6_applied)
            limited = _cap_candidates(candidates, self.config.max_candidates_ranked)
            ranked = rank(
                descriptor.semantic_text(),
                [(node.index, node_to_descriptor(node, hierarchy).semantic_text()) for node in limited],
                self.embedder,
            )
            node_by_index = {node.index: node for node in limited}
            top = [
                CandidateScore(
                    node_index=index,
                    descriptor=node_to_descriptor(node_by_index[index], hierarchy),
                    score=score,
                    locator_preview=_locator_preview(node_by_index[index], hierarchy),
                )
                for index, score in ranked[: self.config.top_k_reported]
            ]
            policy, confidence, margin = decide(ranked, self.config)
            base.update(
                candidates_total=len(hierarchy.nodes),
                candidates_after_narrowing=len(candidates),
                candidates_ranked=len(ranked),
                top_candidates=top,
                confidence=confidence,
                margin=margin,
                rule_counts=rule_counts,
                r6_applied=r6_applied,
            )
            if policy != "accept":
                status = HealingStatus(policy)
                return self._finish(base, status, started, reason=f"Healing refused by {policy.replace('_', ' ')} policy.", rule_counts=rule_counts, r6_applied=r6_applied)
            node = next(item for item in candidates if item.index == ranked[0][0])
            locator = build_unique_locator(node, hierarchy)
            if locator is None:
                return self._finish(base, HealingStatus.REFUSED_NOT_UNIQUE, started, reason="No unique locator exists for the top candidate.", rule_counts=rule_counts, r6_applied=r6_applied)
            healed_by, healed_value = locator
            healed_script = rewrite_step_locator(
                script_source, step_index, _appium_by_to_ast(healed_by), healed_value, "semantic match"
            )
            base["healed_locator"] = {"by": _normalize_strategy(healed_by), "value": healed_value}
            base["healed_script"] = healed_script
            return self._finish(base, HealingStatus.HEALED, started)
        except (HierarchyParseError, StepNotFoundError) as error:
            return self._finish(base, HealingStatus.NOT_APPLICABLE, started, reason=str(error))

    def _finish(self, values: dict[str, object], status: HealingStatus, started: float, reason: str | None = None, rule_counts: dict[str, int] | None = None, r6_applied: bool | None = None) -> HealingDecision:
        values["status"] = status
        values["latency_ms"] = (time.perf_counter() - started) * 1000
        if reason:
            values["reason"] = reason
        if rule_counts is not None:
            values["rule_counts"] = rule_counts
        if r6_applied is not None:
            values["r6_applied"] = r6_applied
        return HealingDecision.model_validate(values)


def _fallback_descriptor(by: str, value: str, context: dict[str, object] | None) -> ElementDescriptor:
    strategy = by.upper()
    text = None
    content_desc = None
    resource_id = value if strategy == "ID" else None
    if strategy == "ACCESSIBILITY_ID":
        content_desc = value
    elif strategy == "ANDROID_UIAUTOMATOR":
        import re

        match = re.search(
            r"\.(?:text|textContains|description)\(\s*(['\"])(.*?)\1\s*\)",
            value,
        )
        text = match.group(2) if match else None
    context_values = [
        str(context[key])
        for key in ("screen", "name")
        if context and isinstance(context.get(key), str)
    ]
    return ElementDescriptor(
        resource_id=resource_id,
        text=text,
        content_desc=content_desc,
        sibling_texts=context_values,
    )


def _cap_candidates(candidates: list[UiNode], limit: int) -> list[UiNode]:
    """Apply the deterministic safety cap after structural narrowing."""
    if len(candidates) <= limit:
        return candidates
    prioritized = sorted(
        candidates,
        key=lambda node: (not bool(node.text or node.content_desc), node.index),
    )
    return prioritized[:limit]


def _locator_preview(node: UiNode, hierarchy: UiHierarchy) -> str | None:
    locator = build_unique_locator(node, hierarchy)
    return locator[1] if locator else None


def _appium_by_to_ast(by: str) -> str:
    return {
        "id": "ID",
        "accessibility id": "ACCESSIBILITY_ID",
        "-android uiautomator": "ANDROID_UIAUTOMATOR",
        "xpath": "XPATH",
    }.get(by, by)


def _normalize_strategy(by: str) -> str:
    return {
        "id": "ID",
        "ID": "ID",
        "accessibility id": "ACCESSIBILITY_ID",
        "ACCESSIBILITY_ID": "ACCESSIBILITY_ID",
        "-android uiautomator": "ANDROID_UIAUTOMATOR",
        "ANDROID_UIAUTOMATOR": "ANDROID_UIAUTOMATOR",
        "xpath": "XPATH",
        "XPATH": "XPATH",
    }.get(by, by)


def _hierarchy_strategy(by: str) -> str:
    return {
        "ID": "id",
        "ACCESSIBILITY_ID": "accessibility id",
        "ANDROID_UIAUTOMATOR": "-android uiautomator",
        "XPATH": "xpath",
    }.get(by.upper(), by)


def _hierarchy_value(by: str, value: str) -> str:
    return value
