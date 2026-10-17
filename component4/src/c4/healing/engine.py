"""Pure locator healing engine."""

from __future__ import annotations

import time

from c4.healing.hierarchy import HierarchyParseError, node_to_descriptor, parse_hierarchy
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
            base["original_locator"] = {"by": step.by, "value": step.value}
            descriptor = baseline or _fallback_descriptor(step.by, step.value, journey_context)
            hierarchy = parse_hierarchy(new_hierarchy_xml)
            candidates, _ = StructuralNarrower(self.config).narrow(
                hierarchy, descriptor, step.action
            )
            if not candidates:
                return self._finish(base, HealingStatus.REFUSED_NO_CANDIDATES, started, reason="No structurally compatible candidates remain.")
            limited = candidates[: self.config.max_candidates_ranked]
            ranked = rank(
                descriptor.semantic_text(),
                [(node.index, node_to_descriptor(node, hierarchy).semantic_text()) for node in limited],
                self.embedder,
            )
            top = [
                CandidateScore(
                    node_index=index,
                    descriptor=node_to_descriptor(next(node for node in limited if node.index == index), hierarchy),
                    score=score,
                    locator_preview=build_unique_locator(
                        next(node for node in limited if node.index == index), hierarchy
                    )[1]
                    if build_unique_locator(next(node for node in limited if node.index == index), hierarchy)
                    else None,
                )
                for index, score in ranked[:5]
            ]
            policy, confidence, margin = decide(ranked, self.config)
            base.update(
                candidates_total=len(hierarchy.nodes),
                candidates_after_narrowing=len(candidates),
                top_candidates=top,
                confidence=confidence,
                margin=margin,
            )
            if policy != "accept":
                status = HealingStatus(policy)
                return self._finish(base, status, started, reason=f"Healing refused by {policy.replace('_', ' ')} policy.")
            node = next(item for item in candidates if item.index == ranked[0][0])
            locator = build_unique_locator(node, hierarchy)
            if locator is None:
                return self._finish(base, HealingStatus.REFUSED_NOT_UNIQUE, started, reason="No unique locator exists for the top candidate.")
            healed_by, healed_value = locator
            healed_script = rewrite_step_locator(
                script_source, step_index, _appium_by_to_ast(healed_by), healed_value, "semantic match"
            )
            base["healed_locator"] = {"by": healed_by, "value": healed_value}
            base["healed_script"] = healed_script
            return self._finish(base, HealingStatus.HEALED, started)
        except (HierarchyParseError, StepNotFoundError) as error:
            return self._finish(base, HealingStatus.NOT_APPLICABLE, started, reason=str(error))

    def _finish(self, values: dict[str, object], status: HealingStatus, started: float, reason: str | None = None) -> HealingDecision:
        values["status"] = status
        values["latency_ms"] = (time.perf_counter() - started) * 1000
        if reason:
            values["reason"] = reason
        return HealingDecision.model_validate(values)


def _fallback_descriptor(by: str, value: str, context: dict[str, object] | None) -> ElementDescriptor:
    text = value if "text" in by.lower() or "uiautomator" in by.lower() else None
    resource_id = value if by in {"ID", "id"} else None
    context_values = [str(item) for item in (context or {}).values()]
    return ElementDescriptor(
        resource_id=resource_id,
        text=text,
        sibling_texts=context_values,
    )


def _appium_by_to_ast(by: str) -> str:
    return {
        "id": "ID",
        "accessibility id": "ACCESSIBILITY_ID",
        "-android uiautomator": "ANDROID_UIAUTOMATOR",
        "xpath": "XPATH",
    }.get(by, by)
