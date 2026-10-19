"""Deterministic UI hierarchy mutations used by the healing evaluation."""

from __future__ import annotations

import copy
import random
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable

from c4.healing.hierarchy import parse_hierarchy


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


def _index_for(root: ET.Element, target: ET.Element) -> int | None:
    _, nodes = _tree(_render(root))
    target_attrs = target.attrib
    target_class = target_attrs.get("class")
    target_text = target_attrs.get("text")
    for index, node in enumerate(nodes):
        if (
            node.attrib.get("class") == target_class
            and node.attrib.get("text") == target_text
            and node.attrib.get("resource-id") == target_attrs.get("resource-id")
            and node.attrib.get("content-desc") == target_attrs.get("content-desc")
        ):
            return index
    return None


def _target(xml_text: str, index: int) -> tuple[ET.Element, list[ET.Element]]:
    root, nodes = _tree(xml_text)
    if index < 0 or index >= len(nodes):
        raise IndexError("target_node_index is outside the hierarchy")
    return root, nodes


def _mutation(
    root: ET.Element,
    target: ET.Element,
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
        expected_index if expected_index is not None else _index_for(root, target),
    )


def rename_id(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation:
    """Append ``_v2`` to the target resource-id, leaving all other attributes."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    value = target.attrib.get("resource-id")
    if not value:
        raise ValueError("rename_id requires a resource-id")
    target.set("resource-id", value + ("_v2" if rng.random() >= 0 else "_v2"))
    return _mutation(root, target, "rename_id", True, "heal")


def change_text(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation:
    """Apply a deterministic common text rewrite or add/remove one word."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    old = target.attrib.get("text", "")
    table = {"SIM cards": "SIMs", "Wi-Fi": "WiFi", "Bluetooth": "Bluetooth settings"}
    if old in table:
        new = table[old]
    elif " " in old:
        words = old.split()
        new = " ".join(words[:-1]) if rng.random() < 0.5 else old + " item"
    else:
        new = old + " item"
    target.set("text", new)
    return _mutation(root, target, "change_text", True, "heal")


def change_content_desc(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation:
    """Change the target content description while preserving its node."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    old = target.attrib.get("content-desc") or target.attrib.get("text") or "element"
    target.set("content-desc", old + (" button" if rng.random() >= 0 else " button"))
    return _mutation(root, target, "change_content_desc", True, "heal")


def move_node(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation:
    """Move the target under another container without changing its attributes."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    parents: dict[ET.Element, ET.Element] = {}

    def collect(parent: ET.Element) -> None:
        for child in parent:
            parents[child] = parent
            collect(child)

    collect(root)
    old_parent = parents.get(target)
    containers = [
        node for node in nodes
        if node is not target and node is not old_parent and len(node) >= 0
        and ("Layout" in node.attrib.get("class", "") or node.tag == "hierarchy")
    ]
    if old_parent is None or not containers:
        raise ValueError("move_node requires a re-parentable target and container")
    new_parent = containers[rng.randrange(len(containers))]
    old_parent.remove(target)
    new_parent.append(target)
    return _mutation(root, target, "move_node", True, "heal")


def remove_id_keep_text(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation:
    """Clear only the target resource-id and preserve visible text."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    target.attrib.pop("resource-id", None)
    return _mutation(root, target, "remove_id_keep_text", True, "heal")


def class_change_within_family(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation:
    """Swap Button and ImageButton, preserving the button family."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    target.set(
        "class",
        "android.widget.ImageButton"
        if target.attrib.get("class", "").endswith("Button")
        and not target.attrib.get("class", "").endswith("ImageButton")
        else "android.widget.Button",
    )
    return _mutation(root, target, "class_change_within_family", True, "heal")


def remove_node(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation:
    """Delete the target node from its parent; this is out of scope."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    parent = next((item for item in nodes if target in list(item)), None)
    if parent is None:
        raise ValueError("cannot remove the hierarchy root")
    parent.remove(target)
    return _mutation(root, target, "remove_node", False, "refuse", None)


def ambiguous_lookalike(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation:
    """Rename the target id and add a same-text near-duplicate sibling."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    target.attrib["resource-id"] = (target.attrib.get("resource-id") or "target") + "_v2"
    parent = next((item for item in nodes if target in list(item)), None)
    if parent is None:
        raise ValueError("target must have a parent")
    duplicate = copy.deepcopy(target)
    duplicate.attrib.pop("resource-id", None)
    parent.append(duplicate)
    return _mutation(root, target, "ambiguous_lookalike", False, "refuse")


def class_change_cross_family(xml_text: str, target_node_index: int, rng: random.Random) -> Mutation:
    """Change a Button target into a TextView, crossing the widget family."""
    root, nodes = _target(xml_text, target_node_index)
    target = nodes[target_node_index]
    target.set("class", "android.widget.TextView")
    return _mutation(root, target, "class_change_cross_family", False, "refuse")


MUTATIONS: tuple[Callable[[str, int, random.Random], Mutation], ...] = (
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

