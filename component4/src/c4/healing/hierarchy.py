"""Pure Android UI hierarchy parsing and locator lookup."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from c4.healing.models import ElementDescriptor


class HierarchyParseError(ValueError):
    """Raised when a UI hierarchy is malformed."""


@dataclass(frozen=True)
class UiNode:
    """One node in document order."""

    index: int
    tag: str
    class_name: str | None
    resource_id: str | None
    text: str | None
    content_desc: str | None
    package: str | None
    bounds: tuple[int, int, int, int] | None
    clickable: bool
    enabled: bool
    focusable: bool
    checkable: bool
    password: bool
    parent_index: int | None
    ancestors: tuple[str, ...]


@dataclass(frozen=True)
class UiHierarchy:
    """Immutable parsed hierarchy."""

    nodes: tuple[UiNode, ...]

    def find_by_locator(self, by: str, value: str) -> list[UiNode]:
        """Find nodes using common Appium locator forms."""
        if by == "id":
            return [
                node
                for node in self.nodes
                if node.resource_id == value
                or (node.resource_id or "").rsplit(":id/", 1)[-1] == value
            ]
        if by in {"accessibility id", "accessibility_id"}:
            return [node for node in self.nodes if node.content_desc == value]
        if by in {"-android uiautomator", "android_uiautomator"}:
            match = re.fullmatch(r'new UiSelector\(\)\.text\("((?:\\.|[^"])*)"\)', value)
            if match:
                text = bytes(match.group(1), "utf-8").decode("unicode_escape")
                return [node for node in self.nodes if node.text == text]
        if by == "xpath":
            match = re.fullmatch(
                r"//([A-Za-z0-9_.-]+)\[@([A-Za-z0-9_-]+)=(['\"])(.*?)\3\]",
                value,
            )
            if match:
                tag, attribute, _, expected = match.groups()
                return [
                    node
                    for node in self.nodes
                    if node.tag == tag
                    and _node_attribute(node, attribute) == expected
                ]
        return []

    def count_matches(self, by: str, value: str) -> int:
        """Count locator matches in this hierarchy."""
        return len(self.find_by_locator(by, value))


def parse_hierarchy(xml_text: str) -> UiHierarchy:
    """Parse Appium or uiautomator XML into immutable nodes."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as error:
        raise HierarchyParseError("Malformed UI hierarchy XML") from error
    nodes: list[UiNode] = []

    def visit(element: ET.Element, parent: UiNode | None, ancestor_names: tuple[str, ...]) -> None:
        index = len(nodes)
        class_name = element.attrib.get("class") or element.tag
        node = UiNode(
            index=index,
            tag=element.tag,
            class_name=class_name,
            resource_id=_first(element, "resource-id", "resource_id"),
            text=_first(element, "text"),
            content_desc=_first(element, "content-desc", "content_desc"),
            package=_first(element, "package"),
            bounds=_parse_bounds(element.attrib.get("bounds")),
            clickable=_bool(element.attrib.get("clickable")),
            enabled=element.attrib.get("enabled", "true").lower() == "true",
            focusable=_bool(element.attrib.get("focusable")),
            checkable=_bool(element.attrib.get("checkable")),
            password=_bool(element.attrib.get("password")),
            parent_index=parent.index if parent else None,
            ancestors=ancestor_names,
        )
        nodes.append(node)
        names = ancestor_names + tuple(
            value for value in (node.resource_id, node.class_name) if value
        )
        for child in element:
            visit(child, node, names)

    visit(root, None, ())
    return UiHierarchy(tuple(nodes))


def node_to_descriptor(node: UiNode, hierarchy: UiHierarchy | None = None) -> ElementDescriptor:
    """Convert a node into a semantic/structural descriptor."""
    sibling_texts: list[str] = []
    if hierarchy is not None and node.parent_index is not None:
        sibling_texts = [
            sibling.text
            for sibling in hierarchy.nodes
            if sibling.parent_index == node.parent_index
            and sibling.index != node.index
            and sibling.text
        ]
    return ElementDescriptor(
        resource_id=node.resource_id,
        text=node.text,
        content_desc=node.content_desc,
        class_name=node.class_name,
        package=node.package,
        bounds=node.bounds,
        clickable=node.clickable,
        ancestors=list(node.ancestors),
        sibling_texts=sibling_texts,
    )


def _first(element: ET.Element, *names: str) -> str | None:
    for name in names:
        value = element.attrib.get(name)
        if value:
            return value
    return None


def _bool(value: str | None) -> bool:
    return (value or "false").lower() == "true"


def _parse_bounds(value: str | None) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", value)
    return tuple(int(item) for item in match.groups()) if match else None


def _node_attribute(node: UiNode, attribute: str) -> str | None:
    return {
        "resource-id": node.resource_id,
        "resource_id": node.resource_id,
        "text": node.text,
        "content-desc": node.content_desc,
        "package": node.package,
        "class": node.class_name,
    }.get(attribute)
