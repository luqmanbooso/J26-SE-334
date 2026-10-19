"""
Synthetic Defect Mutation Engine for Mobile UI Screens.
Grounded in OwlEye (ICSE 2020), Nighthawk (ASE 2022), and CLAIM-01.
Applies deterministic DOM and visual mutations to clean paired Rico screens,
producing ground-truth bounding boxes [ymin, xmin, ymax, xmax] in [0, 1000].
"""

import json
import random
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Union
from PIL import Image, ImageDraw, ImageFont

from local_vision_oracle.schemas import DefectType, Verdict


@dataclass
class UINode:
    """Flattened leaf UI widget from view hierarchy."""
    class_name: str
    resource_id: Optional[str]
    bounds: Tuple[int, int, int, int]  # [x1, y1, x2, y2]
    text: Optional[str]
    clickable: bool

    @property
    def width(self) -> int:
        return self.bounds[2] - self.bounds[0]

    @property
    def height(self) -> int:
        return self.bounds[3] - self.bounds[1]

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)


@dataclass
class MutationResult:
    """Artifact emitted by synthetic mutation."""
    screen_id: str
    image: Image.Image
    defect_type: DefectType
    bounding_box: List[int]  # [ymin, xmin, ymax, xmax] in [0, 1000]
    affected_element_id: Optional[str]
    explanation: str
    mutated_hierarchy: Dict[str, Any]

    def to_verdict(self) -> Verdict:
        return Verdict(
            has_defect=True,
            defect_type=self.defect_type,
            confidence=1.0,
            bounding_box=self.bounding_box,
            affected_element_id=self.affected_element_id,
            explanation=self.explanation,
        )


class SyntheticMutator:
    """
    Executes programmatic defect injection across clean mobile screens.
    Simulates:
      1. component_overlap
      2. text_truncation
      3. missing_component
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    @staticmethod
    def _extract_leaf_nodes(data: Dict[str, Any]) -> List[UINode]:
        """Traverses Rico JSON hierarchy and returns valid leaf widgets."""
        nodes: List[UINode] = []

        def recurse(node: Dict[str, Any]):
            if not isinstance(node, dict):
                return
            bounds = node.get("bounds", [0, 0, 0, 0])
            children = node.get("children", [])
            class_name = node.get("class", "android.view.View").split(".")[-1]
            resource_id = node.get("resource-id")
            text = node.get("text")
            clickable = bool(node.get("clickable", False))

            if isinstance(bounds, list) and len(bounds) == 4:
                x1, y1, x2, y2 = bounds
                w, h = x2 - x1, y2 - y1
                # OwlEye safety rule: filter out status bar (top 80-120px) and bottom nav bar
                if y1 >= 80 and y2 <= 2450:
                    # Leaf or content-bearing container
                    if (not children or text or clickable) and w > 30 and h > 30:
                        nodes.append(UINode(
                            class_name=class_name,
                            resource_id=resource_id,
                            bounds=(x1, y1, x2, y2),
                            text=text,
                            clickable=clickable,
                        ))

            for child in children:
                if isinstance(child, dict):
                    recurse(child)

        root = data.get("activity", {}).get("root", {})
        if root:
            recurse(root)
        return nodes

    @staticmethod
    def _normalize_box(
        bounds: Tuple[int, int, int, int], 
        img_width: int, 
        img_height: int
    ) -> List[int]:
        """Normalizes pixel [x1, y1, x2, y2] to [ymin, xmin, ymax, xmax] in [0, 1000]."""
        x1, y1, x2, y2 = bounds
        ymin = int(max(0, min(1000, round((y1 / img_height) * 1000))))
        xmin = int(max(0, min(1000, round((x1 / img_width) * 1000))))
        ymax = int(max(0, min(1000, round((y2 / img_height) * 1000))))
        xmax = int(max(0, min(1000, round((x2 / img_width) * 1000))))
        return [ymin, xmin, max(ymin + 1, ymax), max(xmin + 1, xmax)]

    def mutate_component_overlap(
        self,
        image: Image.Image,
        nodes: List[UINode],
        screen_id: str,
        hierarchy_data: Dict[str, Any],
    ) -> Optional[MutationResult]:
        """Shifts Widget B to visually collide and occlude Widget A (VisionDroid 30% overlap rule)."""
        candidates = [n for n in nodes if n.area > 2000]
        if len(candidates) < 2:
            return None

        node_a, node_b = self.rng.sample(candidates, 2)
        w, h = image.size

        # Crop Node B
        bx1, by1, bx2, by2 = node_b.bounds
        bx1, by1 = max(0, bx1), max(0, by1)
        bx2, by2 = min(w, bx2), min(h, by2)
        if bx2 <= bx1 or by2 <= by1:
            return None

        crop_b = image.crop((bx1, by1, bx2, by2))

        # VisionDroid rule: enforce >=30% area collision
        ax1, ay1, ax2, ay2 = node_a.bounds
        overlap_shift_x = int(min(node_a.width, crop_b.width) * 0.4)
        overlap_shift_y = int(min(node_a.height, crop_b.height) * 0.4)
        paste_x = max(0, min(w - crop_b.width, ax1 + overlap_shift_x))
        paste_y = max(0, min(h - crop_b.height, ay1 + overlap_shift_y))

        mutated_img = image.copy()
        mutated_img.paste(crop_b, (paste_x, paste_y))

        # Collision box enclosing Node A and collided portion
        ov_x1 = min(ax1, paste_x)
        ov_y1 = min(ay1, paste_y)
        ov_x2 = max(ax2, paste_x + crop_b.width)
        ov_y2 = max(ay2, paste_y + crop_b.height)

        bbox = self._normalize_box((ov_x1, ov_y1, ov_x2, ov_y2), w, h)
        elem_id = node_a.resource_id or node_a.class_name

        return MutationResult(
            screen_id=f"{screen_id}_mut_overlap",
            image=mutated_img,
            defect_type=DefectType.COMPONENT_OVERLAP,
            bounding_box=bbox,
            affected_element_id=elem_id,
            explanation=f"Component overlap defect: widget {node_b.class_name} occludes {node_a.class_name} ({elem_id}).",
            mutated_hierarchy=hierarchy_data,
        )

    def mutate_text_truncation(
        self,
        image: Image.Image,
        nodes: List[UINode],
        screen_id: str,
        hierarchy_data: Dict[str, Any],
    ) -> Optional[MutationResult]:
        """Crops container and renders clipped text with ellipses '...'."""
        text_nodes = [n for n in nodes if n.text and len(n.text.strip()) > 5 and n.width > 60]
        if not text_nodes:
            return None

        target = self.rng.choice(text_nodes)
        w, h = image.size
        x1, y1, x2, y2 = target.bounds
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return None

        mutated_img = image.copy()
        draw = ImageDraw.Draw(mutated_img)

        # Blank out right 45% of text box using sample corner color
        cut_x = x1 + int(target.width * 0.55)
        sample_pixel = image.getpixel((max(0, x1 - 2), max(0, y1 - 2)))
        draw.rectangle([cut_x, y1, x2, y2], fill=sample_pixel)

        # Draw truncated ellipsis
        draw.text((cut_x - 5, y1 + int(target.height * 0.15)), "...", fill=(180, 50, 50))

        bbox = self._normalize_box((x1, y1, x2, y2), w, h)
        elem_id = target.resource_id or target.class_name

        return MutationResult(
            screen_id=f"{screen_id}_mut_trunc",
            image=mutated_img,
            defect_type=DefectType.TEXT_TRUNCATION,
            bounding_box=bbox,
            affected_element_id=elem_id,
            explanation=f"Text truncation defect: label '{target.text[:15]}...' is clipped by container boundary.",
            mutated_hierarchy=hierarchy_data,
        )

    def mutate_missing_component(
        self,
        image: Image.Image,
        nodes: List[UINode],
        screen_id: str,
        hierarchy_data: Dict[str, Any],
    ) -> Optional[MutationResult]:
        """Replaces an image or button with an unrendered gray placeholder."""
        candidates = [n for n in nodes if n.area > 3000 and n.width > 40 and n.height > 40]
        if not candidates:
            return None

        target = self.rng.choice(candidates)
        w, h = image.size
        x1, y1, x2, y2 = target.bounds
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return None

        mutated_img = image.copy()
        draw = ImageDraw.Draw(mutated_img)

        # Inpaint with blank placeholder box + X stroke
        draw.rectangle([x1, y1, x2, y2], fill=(225, 225, 225), outline=(170, 170, 170), width=2)
        draw.line([x1, y1, x2, y2], fill=(200, 200, 200), width=1)
        draw.line([x1, y2, x2, y1], fill=(200, 200, 200), width=1)

        bbox = self._normalize_box((x1, y1, x2, y2), w, h)
        elem_id = target.resource_id or target.class_name

        return MutationResult(
            screen_id=f"{screen_id}_mut_missing",
            image=mutated_img,
            defect_type=DefectType.MISSING_COMPONENT,
            bounding_box=bbox,
            affected_element_id=elem_id,
            explanation=f"Missing component defect: expected UI element {target.class_name} ({elem_id}) failed to render.",
            mutated_hierarchy=hierarchy_data,
        )

    def mutate_data_binding_null(
        self,
        image: Image.Image,
        nodes: List[UINode],
        screen_id: str,
        hierarchy_data: Dict[str, Any],
    ) -> Optional[MutationResult]:
        """Replaces text content with raw 'null' or 'nullnull' literal (data binding failure)."""
        text_nodes = [n for n in nodes if n.text and len(n.text.strip()) > 2 and n.width > 40 and n.height > 20]
        if not text_nodes:
            return None

        target = self.rng.choice(text_nodes)
        w, h = image.size
        x1, y1, x2, y2 = target.bounds
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return None

        mutated_img = image.copy()
        draw = ImageDraw.Draw(mutated_img)

        try:
            bg_color = image.getpixel((max(0, x1 - 2), max(0, y1 - 2)))
        except Exception:
            bg_color = (255, 255, 255)

        draw.rectangle([x1, y1, x2, y2], fill=bg_color)
        null_str = self.rng.choice(["null", "nullnull", "NULL", "NaN"])
        font_size = max(14, min(36, int((y2 - y1) * 0.7)))
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        draw.text((x1 + 4, y1 + 2), null_str, fill=(120, 120, 120), font=font)

        bbox = self._normalize_box((x1, y1, x2, y2), w, h)
        elem_id = target.resource_id or target.class_name

        return MutationResult(
            screen_id=f"{screen_id}_mut_null",
            image=mutated_img,
            defect_type=DefectType.DATA_BINDING_NULL,
            bounding_box=bbox,
            affected_element_id=elem_id,
            explanation=f"Data binding defect: widget {target.class_name} ({elem_id}) renders unpopulated literal string '{null_str}'.",
            mutated_hierarchy=hierarchy_data,
        )

    def mutate(
        self,
        image_path: Union[str, Path],
        hierarchy_path: Union[str, Path],
        mutation_type: Optional[str] = None,
    ) -> Optional[MutationResult]:
        """Executes a single mutation on a paired screen."""
        img = Image.open(image_path).convert("RGB")
        with open(hierarchy_path, "r", encoding="utf-8") as f:
            h_data = json.load(f)

        nodes = self._extract_leaf_nodes(h_data)
        if not nodes:
            return None

        screen_id = Path(image_path).stem

        # Select mutation across academic taxonomy
        choices = ["overlap", "truncation", "missing", "null"]
        selected = mutation_type or self.rng.choice(choices)

        if selected == "overlap":
            res = self.mutate_component_overlap(img, nodes, screen_id, h_data)
            if res: return res
        elif selected == "truncation":
            res = self.mutate_text_truncation(img, nodes, screen_id, h_data)
            if res: return res
        elif selected == "missing":
            res = self.mutate_missing_component(img, nodes, screen_id, h_data)
            if res: return res
        elif selected == "null":
            res = self.mutate_data_binding_null(img, nodes, screen_id, h_data)
            if res: return res

        # Fallback if preferred choice couldn't find matching nodes
        for fallback in choices:
            if fallback == "overlap":
                res = self.mutate_component_overlap(img, nodes, screen_id, h_data)
            elif fallback == "truncation":
                res = self.mutate_text_truncation(img, nodes, screen_id, h_data)
            elif fallback == "missing":
                res = self.mutate_missing_component(img, nodes, screen_id, h_data)
            elif fallback == "null":
                res = self.mutate_data_binding_null(img, nodes, screen_id, h_data)
            if res:
                return res

        return None
