"""Healing confidence and locator uniqueness policy."""

from __future__ import annotations

from c4.healing.hierarchy import UiHierarchy, UiNode
from c4.healing.models import HealingConfig


def build_unique_locator(node: UiNode, hierarchy: UiHierarchy) -> tuple[str, str] | None:
    """Choose the first unique supported locator in priority order."""
    options = [
        ("id", node.resource_id),
        ("accessibility id", node.content_desc),
        ("-android uiautomator", _text_selector(node.text)),
    ]
    for by, value in options:
        if value and hierarchy.count_matches(by, value) == 1:
            return by, value
    return None


def decide(
    ranked: list[tuple[int, float]],
    config: HealingConfig,
) -> tuple[str, float | None, float | None]:
    """Return policy status, confidence, and top-two margin."""
    if not ranked:
        return "refused_no_candidates", None, None
    best = ranked[0][1]
    second = ranked[1][1] if len(ranked) > 1 else None
    margin = best - second if second is not None else None
    if best < config.confidence_threshold:
        return "refused_low_confidence", best, margin
    if second is not None and second >= config.confidence_threshold and margin < config.ambiguity_margin:
        return "refused_ambiguous", best, margin
    return "accept", best, margin


def _text_selector(text: str | None) -> str | None:
    if not text:
        return None
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'new UiSelector().text("{escaped}")'
