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
import numpy as np
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
      4. data_binding_null
    Node bounds are scaled from hierarchy device pixels to screenshot pixels.
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
    def _dominant_color(image: Image.Image, box: Tuple[int, int, int, int]) -> Tuple[int, int, int]:
        """Most common colour inside the element: its own background, not a neighbour's."""
        crop = image.crop(box).convert("RGB").resize((32, 32))
        quantised = [tuple(v // 16 * 16 + 8 for v in px) for px in crop.getdata()]
        return max(set(quantised), key=quantised.count)

    @staticmethod
    def _ink_extent(image: Image.Image, box: Tuple[int, int, int, int]):
        """Bounding box of the rendered text inside an element, plus its background colour.

        Returns None when the element has no clear text on a plain background (text over a
        photo or gradient cannot be clipped convincingly).
        """
        bg = SyntheticMutator._dominant_color(image, box)
        crop = np.asarray(image.crop(box).convert("RGB")).astype(int)
        if crop.size == 0:
            return None
        diff = np.abs(crop - np.array(bg)).sum(axis=2)
        if (diff < 30).mean() < 0.5:
            return None
        cols = np.where((diff > 120).any(axis=0))[0]
        rows = np.where((diff > 120).any(axis=1))[0]
        if cols.size == 0 or rows.size == 0 or cols[-1] - cols[0] < 40 or rows[-1] - rows[0] < 6:
            return None
        x1, y1 = box[0], box[1]
        return x1 + int(cols[0]), y1 + int(rows[0]), x1 + int(cols[-1]) + 1, y1 + int(rows[-1]) + 1, bg

    @staticmethod
    def _contrast_color(bg: Tuple[int, int, int]) -> Tuple[int, int, int]:
        luminance = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
        return (60, 60, 60) if luminance > 128 else (225, 225, 225)

    @staticmethod
    def _scale_nodes(nodes: List[UINode], sx: float, sy: float) -> List[UINode]:
        """Map device-pixel hierarchy bounds onto screenshot pixels.

        Rico hierarchies use 1440x2560 device pixels while the screenshots are
        downscaled (1080x1920 or 540x960). Before 2026-10-20 the bounds were applied
        unscaled, which painted mutations in the wrong place (often off-screen) and
        produced wrong boxes.
        """
        return [
            UINode(class_name=n.class_name, resource_id=n.resource_id,
                   bounds=(int(round(n.bounds[0] * sx)), int(round(n.bounds[1] * sy)),
                           int(round(n.bounds[2] * sx)), int(round(n.bounds[3] * sy))),
                   text=n.text, clickable=n.clickable)
            for n in nodes
        ]

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
        w, h = image.size
        candidates = [n for n in nodes if n.area > 2000 and n.area < 0.15 * w * h]
        if len(candidates) < 2:
            return None

        node_a, node_b = self.rng.sample(candidates, 2)

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

        w, h = image.size
        # Clipping a small caption changes too few pixels to see at training resolution, so
        # take the candidates with the largest rendered text and pick among the best three.
        scored = []
        for node in text_nodes:
            bx1, by1 = max(0, node.bounds[0]), max(0, node.bounds[1])
            bx2, by2 = min(w, node.bounds[2]), min(h, node.bounds[3])
            if bx2 <= bx1 or by2 <= by1:
                continue
            found = self._ink_extent(image, (bx1, by1, bx2, by2))
            if found:
                scored.append(((found[2] - found[0]) * (found[3] - found[1]), node, found))
        if not scored:
            return None
        scored.sort(key=lambda s: -s[0])
        _, target, ink = self.rng.choice(scored[:3])
        ix1, iy1, ix2, iy2, bg = ink

        mutated_img = image.copy()
        draw = ImageDraw.Draw(mutated_img)

        # Cut inside the rendered text (not the element box, which is usually wider than the text),
        # clear everything to the right of the cut up to the text's end, then draw an ellipsis.
        cut_x = ix1 + int((ix2 - ix1) * self.rng.uniform(0.5, 0.75))
        draw.rectangle([cut_x, iy1, ix2 + 2, iy2], fill=bg)
        if self.rng.random() < 0.7:
            try:
                font = ImageFont.truetype("arial.ttf", max(12, int((iy2 - iy1) * 0.9)))
            except Exception:
                font = ImageFont.load_default()
            draw.text((cut_x, iy1 - int((iy2 - iy1) * 0.1)), "...", fill=self._contrast_color(bg), font=font)

        # The label covers the whole truncated text line, as annotators draw it.
        bbox = self._normalize_box((ix1, iy1, ix2, iy2), w, h)
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

        # Unrendered-widget placeholder in one of the looks real apps show: grey box with a
        # cross, flat grey, a dark box, or a grey box with a blue "?" (missing-resource icon).
        style = self.rng.choice(["cross", "flat", "dark", "question"])
        fill, edge = {"cross": ((225, 225, 225), (170, 170, 170)), "flat": ((210, 210, 210), (210, 210, 210)),
                      "dark": ((70, 70, 70), (50, 50, 50)), "question": ((235, 235, 235), (190, 190, 190))}[style]
        draw.rectangle([x1, y1, x2, y2], fill=fill, outline=edge, width=2)
        if style == "cross":
            draw.line([x1, y1, x2, y2], fill=(200, 200, 200), width=1)
            draw.line([x1, y2, x2, y1], fill=(200, 200, 200), width=1)
        elif style == "question":
            side = max(10, min(x2 - x1, y2 - y1) // 2)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            draw.rectangle([cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2], fill=(50, 110, 200))
            try:
                qfont = ImageFont.truetype("arial.ttf", max(10, side - 2))
            except Exception:
                qfont = ImageFont.load_default()
            draw.text((cx - side // 4, cy - side // 2), "?", fill=(255, 255, 255), font=qfont)

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

        bg_color = self._dominant_color(image, (x1, y1, x2, y2))

        draw.rectangle([x1, y1, x2, y2], fill=bg_color)
        null_str = self.rng.choice(["null", "nullnull", "NULL", "NaN", "undefined", "null null", "{}", "%s", "None"])
        font_size = max(14, min(36, int((y2 - y1) * 0.7)))
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        draw.text((x1 + 4, y1 + 2), null_str, fill=self._contrast_color(bg_color), font=font)

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
        from local_vision_oracle.hierarchy_text import rico_screen_size
        screen_w, screen_h = rico_screen_size(h_data)
        nodes = self._scale_nodes(nodes, img.width / screen_w, img.height / screen_h)

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
