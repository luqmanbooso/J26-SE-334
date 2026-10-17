"""Rule-based structural candidate narrowing."""

from __future__ import annotations

from collections import Counter

from c4.healing.hierarchy import UiHierarchy, UiNode
from c4.healing.models import ElementDescriptor


class StructuralNarrower:
    """Filter new hierarchy nodes using baseline structure and action."""

    def __init__(self, config: object | None = None) -> None:
        self.config = config

    def narrow(
        self,
        hierarchy: UiHierarchy,
        descriptor: ElementDescriptor,
        action: str | None,
    ) -> tuple[list[UiNode], dict[str, int]]:
        """Return candidates surviving rules R1 through R5."""
        counts: Counter[str] = Counter()
        result: list[UiNode] = []
        for node in hierarchy.nodes:
            if not node.enabled or not node.bounds or node.bounds[2] <= node.bounds[0] or node.bounds[3] <= node.bounds[1]:
                counts["R1"] += 1
                continue
            if descriptor.package and node.package and node.package != descriptor.package:
                counts["R2"] += 1
                continue
            if not _action_compatible(node, descriptor, action):
                counts["R3"] += 1
                continue
            if descriptor.class_name and not _class_family_compatible(node.class_name, descriptor.class_name):
                counts["R4"] += 1
                continue
            if not (node.text or node.content_desc or node.resource_id):
                counts["R5"] += 1
                continue
            result.append(node)
        return result, dict(counts)


def _action_compatible(node: UiNode, baseline: ElementDescriptor, action: str | None) -> bool:
    if action in {"tap", "navigate"}:
        return node.clickable or node.focusable or _same_family(node.class_name, baseline.class_name)
    if action == "input":
        name = (node.class_name or "").lower()
        return node.clickable or "edit" in name or "textinput" in name or "text" in name
    return True


def _class_family_compatible(candidate: str | None, baseline: str) -> bool:
    return _same_family(candidate, baseline)


def _same_family(candidate: str | None, baseline: str | None) -> bool:
    if not candidate or not baseline:
        return True
    candidate_family = _family(candidate)
    baseline_family = _family(baseline)
    return candidate_family == baseline_family


def _family(value: str) -> str:
    name = value.rsplit(".", 1)[-1].lower()
    if "button" in name:
        return "button"
    if "edit" in name or "textinput" in name:
        return "edit"
    if "text" in name:
        return "text"
    if "image" in name or "icon" in name:
        return "image"
    return name
