"""
Deterministic AST View Hierarchy Pruner & Coordinate Normalizer.
Grounded in METHOD-AST-Hierarchy-Pruner, RDR-0002, and EXP-02.
"""

import os
import re
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Union, Tuple
from pathlib import Path


@dataclass
class PrunedNode:
    """
    Compact representation of an interactive or textual UI element.
    """
    element_id: str = ""
    class_name: str = ""
    text: str = ""
    content_desc: str = ""
    bounds: Optional[List[int]] = None  # [ymin, xmin, ymax, xmax] normalized to [0, 1000]
    clickable: bool = False
    scrollable: bool = False
    raw_bounds: Optional[List[int]] = None  # [x1, y1, x2, y2]
    bbox: Optional[List[int]] = None
    depth: int = 0

    def __post_init__(self):
        if self.bounds is None and self.bbox is not None:
            self.bounds = self.bbox
        elif self.bounds is None:
            self.bounds = [0, 0, 0, 0]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_prompt_string(self) -> str:
        """
        Token-dense string representation for VLM prompt injection.
        """
        parts = []
        short_class = self.class_name.split(".")[-1]
        parts.append(f"<{short_class}")
        if self.element_id:
            clean_id = self.element_id.split("/")[-1]
            parts.append(f'id="{clean_id}"')
        if self.text:
            clean_text = self.text.strip().replace('"', "'")
            if len(clean_text) > 40:
                clean_text = clean_text[:37] + "..."
            parts.append(f'text="{clean_text}"')
        if self.content_desc and self.content_desc != self.text:
            clean_desc = self.content_desc.strip().replace('"', "'")
            parts.append(f'desc="{clean_desc}"')
        parts.append(f"bounds={self.bounds}")
        if self.clickable:
            parts.append("clickable")
        return " ".join(parts) + " />"


class HierarchyPruner:
    """
    Parses Android Accessibility XML and Rico JSON view hierarchies,
    collapses structural layout wrappers, normalizes bounding box coordinates to [0, 1000],
    and produces a compact semantic DOM representation.
    """

    @staticmethod
    def detect_overlap_collision(nodes: List[PrunedNode]) -> Tuple[bool, Dict[str, Any]]:
        """
        Detects bounding box layout collisions between interactive/textual AST nodes.
        Calculates intersection area and colliding element identifiers.
        """
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                n1, n2 = nodes[i], nodes[j]
                b1 = n1.raw_bounds or n1.bbox or n1.bounds
                b2 = n2.raw_bounds or n2.bbox or n2.bounds
                if not b1 or not b2 or len(b1) != 4 or len(b2) != 4:
                    continue
                y1_a, x1_a, y2_a, x2_a = b1[0], b1[1], b1[2], b1[3]
                y1_b, x1_b, y2_b, x2_b = b2[0], b2[1], b2[2], b2[3]

                ix1 = max(x1_a, x1_b)
                iy1 = max(y1_a, y1_b)
                ix2 = min(x2_a, x2_b)
                iy2 = min(y2_a, y2_b)

                if ix2 > ix1 and iy2 > iy1:
                    area = (ix2 - ix1) * (iy2 - iy1)
                    return True, {
                        "element_a": n1.element_id,
                        "element_b": n2.element_id,
                        "intersection_area_px": area,
                        "intersection_box": [iy1, ix1, iy2, ix2],
                    }
        return False, {}

    @staticmethod
    def to_prompt_string(nodes: List[PrunedNode]) -> str:
        """Serializes pruned nodes into token-dense string for prompt injection."""
        return "\n".join(node.to_prompt_string() for node in nodes)


    STRUCTURAL_CONTAINERS = {
        "android.widget.FrameLayout",
        "android.widget.LinearLayout",
        "android.widget.RelativeLayout",
        "android.view.ViewGroup",
        "android.view.View",
        "androidx.coordinatorlayout.widget.CoordinatorLayout",
        "androidx.drawerlayout.widget.DrawerLayout",
        "androidx.appcompat.widget.FitWindowsFrameLayout",
        "androidx.appcompat.widget.ContentFrameLayout",
        "androidx.appcompat.widget.ActionBarOverlayLayout",
    }

    BOUNDS_REGEX = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")

    def __init__(
        self,
        screen_width: int = 1080,
        screen_height: int = 2400,
        max_nodes: int = 60,
        collapse_wrappers: bool = True,
    ):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.max_nodes = max_nodes
        self.collapse_wrappers = collapse_wrappers
        self.raw_node_count = 0
        self.pruned_node_count = 0

    def normalize_bounds(self, x1: int, y1: int, x2: int, y2: int) -> List[int]:
        """
        Normalizes pixel coordinates [x1, y1, x2, y2] to [ymin, xmin, ymax, xmax] in [0, 1000].
        """
        w = max(1, self.screen_width)
        h = max(1, self.screen_height)

        ymin = max(0, min(1000, round((y1 / h) * 1000)))
        xmin = max(0, min(1000, round((x1 / w) * 1000)))
        ymax = max(0, min(1000, round((y2 / h) * 1000)))
        xmax = max(0, min(1000, round((x2 / w) * 1000)))

        # Ensure valid orientation
        if ymin > ymax:
            ymin, ymax = ymax, ymin
        if xmin > xmax:
            xmin, xmax = xmax, xmin

        return [ymin, xmin, ymax, xmax]

    def _is_empty_or_zero_area(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        return (x2 - x1) <= 0 or (y2 - y1) <= 0

    def _is_off_screen(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        return (
            x1 >= self.screen_width
            or y1 >= self.screen_height
            or x2 <= 0
            or y2 <= 0
        )

    def prune_xml(
        self,
        xml_source: Union[str, Path, ET.Element],
        screen_width: Optional[int] = None,
        screen_height: Optional[int] = None,
        **kwargs
    ) -> List[PrunedNode]:
        """
        Parses Android Accessibility / UIAutomator XML string or file path.
        """
        if screen_width is not None:
            self.screen_width = screen_width
        if screen_height is not None:
            self.screen_height = screen_height
        self.raw_node_count = 0
        pruned_nodes: List[PrunedNode] = []

        if isinstance(xml_source, (str, Path)) and os.path.exists(str(xml_source)):
            tree = ET.parse(str(xml_source))
            root = tree.getroot()
        elif isinstance(xml_source, str):
            clean_str = xml_source.strip()
            if not clean_str:
                return []
            try:
                root = ET.fromstring(clean_str)
            except ET.ParseError:
                return []
        elif isinstance(xml_source, ET.Element):
            root = xml_source
        else:
            return []

        def traverse(node: ET.Element):
            self.raw_node_count += 1
            attrib = node.attrib
            bounds_str = attrib.get("bounds", "")
            match = self.BOUNDS_REGEX.match(bounds_str)

            x1, y1, x2, y2 = (0, 0, 0, 0)
            valid_geom = False
            if match:
                x1, y1, x2, y2 = map(int, match.groups())
                valid_geom = not self._is_empty_or_zero_area(x1, y1, x2, y2) and not self._is_off_screen(x1, y1, x2, y2)

            class_name = attrib.get("class", "android.view.View")
            text = attrib.get("text", "").strip()
            desc = attrib.get("content-desc", "").strip()
            clickable = attrib.get("clickable", "false").lower() == "true"
            scrollable = attrib.get("scrollable", "false").lower() == "true"
            elem_id = attrib.get("resource-id", "").strip()

            is_wrapper = class_name in self.STRUCTURAL_CONTAINERS and not text and not desc and not clickable

            # Keep node if valid geometry and not an empty wrapper
            if valid_geom and not (self.collapse_wrappers and is_wrapper):
                has_text = bool(text or desc)
                is_interactive = clickable or scrollable
                if has_text or is_interactive or not self.collapse_wrappers:
                    norm_bounds = self.normalize_bounds(x1, y1, x2, y2)
                    pruned_nodes.append(
                        PrunedNode(
                            element_id=elem_id,
                            class_name=class_name,
                            text=text,
                            content_desc=desc,
                            bounds=norm_bounds,
                            clickable=clickable,
                            scrollable=scrollable,
                            raw_bounds=[x1, y1, x2, y2],
                        )
                    )

            for child in node:
                traverse(child)

        traverse(root)

        # Cap at max_nodes to enforce token budget
        if len(pruned_nodes) > self.max_nodes:
            pruned_nodes = pruned_nodes[:self.max_nodes]

        self.pruned_node_count = len(pruned_nodes)
        return pruned_nodes

    def prune_rico_json(self, json_source: Union[str, Path, Dict[str, Any]]) -> List[PrunedNode]:
        """
        Parses Rico dataset JSON hierarchy dictionary or file path.
        """
        self.raw_node_count = 0
        pruned_nodes: List[PrunedNode] = []

        if isinstance(json_source, (str, Path)) and os.path.exists(str(json_source)):
            with open(str(json_source), "r", encoding="utf-8") as f:
                data = json.load(f)
        elif isinstance(json_source, str):
            try:
                data = json.loads(json_source)
            except json.JSONDecodeError:
                return []
        elif isinstance(json_source, dict):
            data = json_source
        else:
            return []

        root = data.get("root", data)

        def traverse(node: Dict[str, Any]):
            self.raw_node_count += 1
            bounds = node.get("bounds", [0, 0, 0, 0])
            if len(bounds) == 4:
                x1, y1, x2, y2 = bounds
            else:
                x1, y1, x2, y2 = (0, 0, 0, 0)

            valid_geom = not self._is_empty_or_zero_area(x1, y1, x2, y2) and not self._is_off_screen(x1, y1, x2, y2)

            class_name = node.get("class", "android.view.View")
            text = (node.get("text") or "").strip()
            desc = (node.get("content-description") or "").strip()
            clickable = bool(node.get("clickable", False))
            scrollable = bool(node.get("scrollable-horizontal", False) or node.get("scrollable-vertical", False))
            elem_id = (node.get("resource-id") or "").strip()

            is_wrapper = class_name in self.STRUCTURAL_CONTAINERS and not text and not desc and not clickable

            if valid_geom and not (self.collapse_wrappers and is_wrapper):
                has_text = bool(text or desc)
                is_interactive = clickable or scrollable
                if has_text or is_interactive or not self.collapse_wrappers:
                    norm_bounds = self.normalize_bounds(x1, y1, x2, y2)
                    pruned_nodes.append(
                        PrunedNode(
                            element_id=elem_id,
                            class_name=class_name,
                            text=text,
                            content_desc=desc,
                            bounds=norm_bounds,
                            clickable=clickable,
                            scrollable=scrollable,
                            raw_bounds=[x1, y1, x2, y2],
                        )
                    )

            for child in node.get("children", []):
                if isinstance(child, dict):
                    traverse(child)

        traverse(root)

        if len(pruned_nodes) > self.max_nodes:
            pruned_nodes = pruned_nodes[:self.max_nodes]

        self.pruned_node_count = len(pruned_nodes)
        return pruned_nodes

    def prune(self, source: Union[str, Path, Dict[str, Any]]) -> List[PrunedNode]:
        """
        Unified entrypoint: auto-detects XML vs JSON and returns pruned nodes.
        """
        if isinstance(source, dict):
            return self.prune_rico_json(source)
        
        path_str = str(source).strip()
        if path_str.endswith(".json") or path_str.startswith("{"):
            return self.prune_rico_json(source)
        else:
            return self.prune_xml(source)

    def get_reduction_stats(self) -> Dict[str, Any]:
        """
        Telemetry: returns raw node count, pruned count, and percentage reduction.
        """
        reduction_pct = 0.0
        if self.raw_node_count > 0:
            reduction_pct = round((1.0 - (self.pruned_node_count / self.raw_node_count)) * 100, 2)
        return {
            "raw_nodes": self.raw_node_count,
            "pruned_nodes": self.pruned_node_count,
            "reduction_pct": reduction_pct,
        }

    def detect_layout_collisions(
        self,
        pruned_nodes: List[PrunedNode],
        min_overlap_ratio: float = 0.15,
    ) -> List[Dict[str, Any]]:
        """
        Deterministically detects bounding box collisions between distinct UI elements
        (e.g., fixed navigation bars occluding scrollable cards/buttons).
        Operates on CPU in <5ms with 0 VRAM footprint (Grounded in CLAIM-01 / RDR-0002).
        """
        collisions = []
        n = len(pruned_nodes)
        for i in range(n):
            node_a = pruned_nodes[i]
            ay1, ax1, ay2, ax2 = node_a.bounds
            area_a = max(1, (ay2 - ay1) * (ax2 - ax1))

            for j in range(i + 1, n):
                node_b = pruned_nodes[j]
                by1, bx1, by2, bx2 = node_b.bounds
                area_b = max(1, (by2 - by1) * (bx2 - bx1))

                # Intersection rectangle
                iy1 = max(ay1, by1)
                ix1 = max(ax1, bx1)
                iy2 = min(ay2, by2)
                ix2 = min(ax2, bx2)

                if iy2 > iy1 and ix2 > ix1:
                    inter_area = (iy2 - iy1) * (ix2 - ix1)
                    min_area = min(area_a, area_b)
                    ratio = inter_area / min_area

                    # If one node almost completely contains the other, likely parent/child wrapper
                    is_contained = (inter_area / min_area) > 0.85 and (area_a > 2 * area_b or area_b > 2 * area_a)

                    if ratio >= min_overlap_ratio and not is_contained:
                        collisions.append({
                            "collision_bbox": [iy1, ix1, iy2, ix2],
                            "element_a_id": node_a.element_id or node_a.class_name,
                            "element_b_id": node_b.element_id or node_b.class_name,
                            "overlap_ratio": round(ratio, 4),
                        })
        return collisions

