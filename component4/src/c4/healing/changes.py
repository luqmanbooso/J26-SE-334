"""Deterministic structural change detection between UI hierarchies."""

from __future__ import annotations

from dataclasses import dataclass

from c4.healing.hierarchy import UiHierarchy, UiNode


@dataclass(frozen=True)
class ChangeSet:
    """Nodes classified as unchanged, modified, added, or removed."""

    unchanged: frozenset[int]
    modified: frozenset[int]
    added: frozenset[int]
    removed: frozenset[int]


def detect_changes(old: UiHierarchy, new: UiHierarchy) -> ChangeSet:
    """Compare nodes by resource id, class, and ancestor path."""
    old_by_key = {_identity(node): node for node in old.nodes if _identity(node)}
    new_by_key = {_identity(node): node for node in new.nodes if _identity(node)}
    unchanged: set[int] = set()
    modified: set[int] = set()
    removed: set[int] = {
        node.index for key, node in old_by_key.items() if key not in new_by_key
    }
    added: set[int] = {
        node.index for key, node in new_by_key.items() if key not in old_by_key
    }
    for key, new_node in new_by_key.items():
        old_node = old_by_key.get(key)
        if old_node is None:
            continue
        if (
            old_node.text == new_node.text
            and old_node.content_desc == new_node.content_desc
        ):
            unchanged.add(new_node.index)
        else:
            modified.add(new_node.index)
    return ChangeSet(
        unchanged=frozenset(unchanged),
        modified=frozenset(modified),
        added=frozenset(added),
        removed=frozenset(removed),
    )


def _identity(node: UiNode) -> tuple[str | None, str | None, tuple[str, ...]]:
    return node.resource_id, node.class_name, node.ancestors
