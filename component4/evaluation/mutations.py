"""Deterministic UI hierarchy mutations used by the healing evaluation."""

from __future__ import annotations

import copy
import random
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Mutation:
    """One mutated hierarchy and its evaluation ground truth."""

    new_xml: str
    change_class: str
    in_scope: bool
    expected_status: str
    expected_node_index_in_new: int | None


def _tree(xml_text: str) -> tuple[ET.Element, list[ET.Element]]:
    root = ET.fromstring(xml_text)
    nodes: list[ET.Element] = []

    def visit(element: ET.Element) -> None:
        nodes.append(element)
        for child in element:
            visit(child)

    visit(root)
    return root, nodes


def _render(root: ET.Element) -> str:
    return ET.tostring(root, encoding="unicode")


def _target(xml_text: str, index: int) -> tuple[ET.Element, list[ET.Element]]:
    root, nodes = _tree(xml_text)
    if index < 0 or index >= len(nodes):
        raise IndexError("target_node_index is outside the hierarchy")
    return root, nodes


def _parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    parents: dict[ET.Element, ET.Element] = {}

    def visit(parent: ET.Element) -> None:
        for child in parent:
            parents[child] = parent
            visit(child)

    visit(root)
    return parents


def _bounds(value: str | None) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    try:
        left_top, right_bottom = value.split("][")
        left, top = left_top.removeprefix("[").split(",")
        right, bottom = right_bottom.removesuffix("]").split(",")
        return int(left), int(top), int(right), int(bottom)
    except (ValueError, AttributeError):
        return None


def _set_bounds(element: ET.Element, offset: int) -> None:
    current = _bounds(element.attrib.get("bounds"))
    if current is None:
        return
    left, top, right, bottom = current
    element.set("bounds", f"[{left + offset},{top + offset}][{right + offset},{bottom + offset}]")


def _shift_target_and_siblings(
    root: ET.Element,
    target: ET.Element,
    offset: int,
    *,
    include_target: bool = True,
) -> None:
    parents = _parent_map(root)
    parent = parents.get(target)
    siblings = list(parent) if parent is not None else []
    if include_target and target not in siblings:
        siblings.append(target)
    for sibling in siblings:
        _set_bounds(sibling, offset)


def _index_for(root: ET.Element, target: ET.Element) -> int | None:
    _, nodes = _tree(_render(root))
    for index, node in enumerate(nodes):
        if node is target:
            return index
        if node.attrib == target.attrib and node.tag == target.tag:
            return index
    return None


def _mutation(
    root: ET.Element,
    target: ET.Element | None,
    change_class: str,
    in_scope: bool,
    expected_status: str,
    expected_index: int | None = None,
) -> Mutation:
    return Mutation(
        _render(root),
        change_class,
        in_scope,
        expected_status,
        expected_index if expected_index is not None else (
            _index_for(root, target) if target is not None else None
        ),
    )


def _offset(rng: random.Random) -> int:
    return rng.randint(20, 120)


def rename_id(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation | None:
    """Append ``_v2`` to a target resource-id and shift its sibling row."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    if not target.attrib.get("resource-id"):
        return None
    target.set("resource-id", target.attrib["resource-id"] + "_v2")
    _shift_target_and_siblings(root, target, _offset(rng))
    return _mutation(root, target, "rename_id", True, "heal")


def change_text(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation | None:
    """Rewrite a target text value using a deterministic replacement table."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    old = target.attrib.get("text")
    if not old:
        return None
    table = {"SIM cards": "SIMs", "Wi-Fi": "WiFi", "Bluetooth": "Bluetooth settings"}
    if old in table:
        new = table[old]
    elif " " in old:
        words = old.split()
        new = " ".join(words[:-1]) if rng.random() < 0.5 else old + " item"
    else:
        new = old + " item"
    target.set("text", new)
    _shift_target_and_siblings(root, target, _offset(rng))
    return _mutation(root, target, "change_text", True, "heal")


def change_content_desc(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation | None:
    """Change a target content description while preserving its node."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    old = target.attrib.get("content-desc")
    if not old:
        return None
    target.set("content-desc", old + " button")
    _shift_target_and_siblings(root, target, _offset(rng))
    return _mutation(root, target, "change_content_desc", True, "heal")


def move_node(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation | None:
    """Move a target to another layout parent and shift the affected rows."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    parents = _parent_map(root)
    old_parent = parents.get(target)
    if old_parent is None:
        return None
    containers = [
        node for node in nodes
        if node is not target
        and node is not old_parent
        and "Layout" in node.attrib.get("class", "")
    ]
    if not containers:
        return None
    old_parent.remove(target)
    new_parent = containers[rng.randrange(len(containers))]
    new_parent.append(target)
    _shift_target_and_siblings(root, target, _offset(rng))
    return _mutation(root, target, "move_node", True, "heal")


def remove_id_keep_text(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation | None:
    """Clear only a target resource-id and preserve its visible text."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    if not target.attrib.get("resource-id"):
        return None
    target.attrib.pop("resource-id")
    _shift_target_and_siblings(root, target, _offset(rng))
    return _mutation(root, target, "remove_id_keep_text", True, "heal")


def class_change_within_family(
    xml_text: str,
    target_node_index: int,
    rng: random.Random,
) -> Mutation | None:
    """Swap Button/ImageButton or EditText/AutoCompleteTextView only."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    class_name = target.attrib.get("class", "")
    pairs = {
        "android.widget.Button": "android.widget.ImageButton",
        "android.widget.ImageButton": "android.widget.Button",
        "android.widget.EditText": "android.widget.AutoCompleteTextView",
        "android.widget.AutoCompleteTextView": "android.widget.EditText",
    }
    if class_name not in pairs:
        return None
    target.set("class", pairs[class_name])
    _shift_target_and_siblings(root, target, _offset(rng))
    return _mutation(root, target, "class_change_within_family", True, "heal")


def remove_node(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation | None:
    """Delete a target node; this is an out-of-scope mutation."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    parents = _parent_map(root)
    parent = parents.get(target)
    if parent is None:
        return None
    parent.remove(target)
    offset = _offset(rng)
    for sibling in list(parent):
        _set_bounds(sibling, offset)
    return _mutation(root, None, "remove_node", False, "refuse", None)


def ambiguous_lookalike(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation | None:
    """Rename a target id and add a near-identical same-text sibling."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    parents = _parent_map(root)
    parent = parents.get(target)
    if parent is None:
        return None
    target.set("resource-id", (target.attrib.get("resource-id") or "target") + "_v2")
    duplicate = copy.deepcopy(target)
    duplicate.attrib.pop("resource-id", None)
    parent.append(duplicate)
    _shift_target_and_siblings(root, target, _offset(rng))
    _set_bounds(duplicate, _offset(rng))
    return _mutation(root, target, "ambiguous_lookalike", False, "refuse")


def class_change_cross_family(
    xml_text: str,
    target_node_index: int,
    rng: random.Random,
) -> Mutation | None:
    """Change a Button to TextView; other target classes are skipped."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    if target.attrib.get("class") != "android.widget.Button":
        return None
    target.set("class", "android.widget.TextView")
    _shift_target_and_siblings(root, target, _offset(rng))
    return _mutation(root, target, "class_change_cross_family", False, "refuse")


MUTATIONS: tuple[Callable[[str, int, random.Random], Mutation | None], ...] = (
    rename_id,
    change_text,
    change_content_desc,
    move_node,
    remove_id_keep_text,
    class_change_within_family,
    remove_node,
    ambiguous_lookalike,
    class_change_cross_family,
)
