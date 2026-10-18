"""Deterministic structural change detection between UI hierarchies."""

from __future__ import annotations

from collections import defaultdict
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
    """Compare hierarchy nodes using deterministic one-to-one group matching."""
    old_by_key: dict[tuple[str | None, str | None, tuple[str, ...]], list[UiNode]] = (
        defaultdict(list)
    )
    new_by_key: dict[tuple[str | None, str | None, tuple[str, ...]], list[UiNode]] = (
        defaultdict(list)
    )
    for node in old.nodes:
        old_by_key[_identity(node)].append(node)
    for node in new.nodes:
        new_by_key[_identity(node)].append(node)

    unchanged: set[int] = set()
    modified: set[int] = set()
    added: set[int] = set()
    removed: set[int] = set()
    for key in sorted(set(old_by_key) | set(new_by_key), key=repr):
        old_nodes = old_by_key.get(key, [])
        new_nodes = new_by_key.get(key, [])
        remaining_old = list(old_nodes)
        remaining_new = list(new_nodes)

        for new_node in new_nodes:
            match_index = next(
                (
                    index
                    for index, old_node in enumerate(remaining_old)
                    if _labels_equal(old_node, new_node)
                ),
                None,
            )
            if match_index is not None:
                unchanged.add(new_node.index)
                remaining_old.pop(match_index)
                remaining_new.remove(new_node)

        for old_node, new_node in zip(remaining_old, remaining_new):
            modified.add(new_node.index)
        added.update(node.index for node in remaining_new[len(remaining_old) :])
        removed.update(node.index for node in remaining_old[len(remaining_new) :])

    return ChangeSet(
        unchanged=frozenset(unchanged),
        modified=frozenset(modified),
        added=frozenset(added),
        removed=frozenset(removed),
    )


def _identity(node: UiNode) -> tuple[str | None, str | None, tuple[str, ...]]:
    return node.resource_id, node.class_name, node.ancestors


def _labels_equal(old: UiNode, new: UiNode) -> bool:
    return old.text == new.text and old.content_desc == new.content_desc
