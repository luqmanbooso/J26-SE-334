"""One hierarchy-to-text format for both fine-tuning and inference.

A fusion adapter only works if the layout text it reads at inference is produced
by exactly the same rules as during training. Rico training data stores view
hierarchies as JSON (``activity.root``); live devices produce UIAutomator XML.
Both are reduced here to the same element list and serialised by
``format_hierarchy``.

Rules (identical for both sources):
* Only visible, on-screen elements with non-zero area.
* Keep an element if it has text or a description, is clickable or scrollable,
  or is a leaf (no children). Leaves keep image views and placeholders, which is
  what a "missing component" defect contradicts.
* Bounds are normalised to the hierarchy's own root bounds (not the screenshot
  pixel size, which may be downscaled), as [ymin, xmin, ymax, xmax] in 0-1000,
  the same space as the model's bounding boxes.
* Elements are sorted top-to-bottom, left-to-right and capped at ``max_nodes``
  so the prompt stays inside the training length limit.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

FORMAT_VERSION = "c3-hierarchy-text-v1-compact"
DEFAULT_MAX_NODES = 20  # p95 = 523 tokens on Rico; keeps image + prompt + answer under cutoff_len 1024
_BOUNDS = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


@dataclass
class LayoutElement:
    class_name: str
    element_id: str
    text: str
    clickable: bool
    scrollable: bool
    bounds: List[int]  # [ymin, xmin, ymax, xmax] in 0-1000

    def to_line(self) -> str:
        """Compact line, e.g. ``Button#sign_in "Sign In" [841,0,907,1000] click``."""
        line = self.class_name.split(".")[-1] or "View"
        if self.element_id:
            line += "#" + self.element_id.split("/")[-1]
        if self.text:
            text = " ".join(self.text.split()).replace('"', "'")
            line += ' "' + (text[:27] + "..." if len(text) > 30 else text) + '"'
        line += " [" + ",".join(str(v) for v in self.bounds) + "]"
        if self.clickable:
            line += " click"
        if self.scrollable:
            line += " scroll"
        return line


def _normalise(x1: float, y1: float, x2: float, y2: float, w: float, h: float) -> List[int]:
    clamp = lambda v: int(max(0, min(1000, round(v))))  # noqa: E731
    return [clamp(y1 / h * 1000), clamp(x1 / w * 1000), clamp(y2 / h * 1000), clamp(x2 / w * 1000)]


def _keep(text: str, clickable: bool, scrollable: bool, is_leaf: bool) -> bool:
    return bool(text) or clickable or scrollable or is_leaf


def _valid(x1: float, y1: float, x2: float, y2: float, w: float, h: float) -> bool:
    return x2 > x1 and y2 > y1 and x1 < w and y1 < h and x2 > 0 and y2 > 0


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        value = next((v for v in value if v), "")
    return str(value or "").strip()


def _rico_class(node: Dict[str, Any]) -> str:
    """Rico apps are often obfuscated (class "q", "ab"); use the first framework ancestor then."""
    cls = str(node.get("class") or "View")
    if "." in cls and not re.search(r"\.[a-z]{1,2}$", cls):
        return cls
    for anc in node.get("ancestors") or []:
        if isinstance(anc, str) and anc.startswith(("android.", "androidx.")):
            return anc
    return cls


RICO_DEVICE = (1440, 2560)  # Nexus 6P; Rico screenshots are this screen downscaled (1080x1920, 540x960)


def rico_screen_size(data: Dict[str, Any]) -> tuple:
    """Pixel size of the screen a Rico hierarchy's bounds refer to.

    The root view is often 1440x2392 (navigation bar excluded) while the screenshot
    covers the full 1440x2560 screen, so root bounds must not be used for scaling.
    Verified visually: bounds * (image_width / 1440) align with the screenshot.
    """
    root = (data.get("activity") or {}).get("root") or data.get("root") or data
    rb = root.get("bounds") or [0, 0, 1, 1]
    if rb[2] - rb[0] == RICO_DEVICE[0]:
        return RICO_DEVICE
    return max(1, rb[2] - rb[0]), max(1, rb[3] - rb[1])


def elements_from_rico(data: Union[Dict[str, Any], str, Path]) -> List[LayoutElement]:
    """Elements from a Rico view-hierarchy JSON (dict, JSON string or file path)."""
    if isinstance(data, (str, Path)) and Path(str(data)).exists():
        data = json.loads(Path(str(data)).read_text(encoding="utf-8"))
    elif isinstance(data, str):
        data = json.loads(data)
    root = (data.get("activity") or {}).get("root") or data.get("root") or data
    rb = root.get("bounds") or [0, 0, 0, 0]
    w, h = rico_screen_size(data)
    out: List[LayoutElement] = []

    def visit(node: Dict[str, Any]) -> None:
        if node.get("visibility", "visible") != "visible" or node.get("visible-to-user") is False:
            return
        children = [c for c in (node.get("children") or []) if isinstance(c, dict)]
        b = node.get("bounds") or [0, 0, 0, 0]
        if len(b) == 4 and _valid(b[0] - rb[0], b[1] - rb[1], b[2] - rb[0], b[3] - rb[1], w, h):
            text = _first_text(node.get("text")) or _first_text(node.get("content-desc"))
            clickable = bool(node.get("clickable"))
            scrollable = bool(node.get("scrollable-vertical") or node.get("scrollable-horizontal"))
            if _keep(text, clickable, scrollable, not children):
                out.append(LayoutElement(
                    class_name=_rico_class(node),
                    element_id=str(node.get("resource-id") or ""),
                    text=text, clickable=clickable, scrollable=scrollable,
                    bounds=_normalise(b[0] - rb[0], b[1] - rb[1], b[2] - rb[0], b[3] - rb[1], w, h)))
        for child in children:
            visit(child)

    visit(root)
    return out


def elements_from_uiautomator(xml: Union[str, Path]) -> List[LayoutElement]:
    """Elements from a UIAutomator ``dump`` XML (string or file path)."""
    if isinstance(xml, Path) or (isinstance(xml, str) and not xml.lstrip().startswith("<") and Path(xml).exists()):
        xml = Path(str(xml)).read_text(encoding="utf-8")
    try:
        root = ET.fromstring(xml.strip())
    except ET.ParseError:
        return []
    nodes = [n for n in root.iter() if "bounds" in n.attrib]
    if not nodes:
        return []
    boxes = [tuple(map(int, m.groups())) for n in nodes if (m := _BOUNDS.match(n.attrib["bounds"]))]
    if not boxes:
        return []
    w = max(1, max(b[2] for b in boxes))
    h = max(1, max(b[3] for b in boxes))
    out: List[LayoutElement] = []
    for node in nodes:
        a = node.attrib
        m = _BOUNDS.match(a.get("bounds", ""))
        if not m or a.get("visible-to-user", "true").lower() == "false":
            continue
        x1, y1, x2, y2 = map(int, m.groups())
        if not _valid(x1, y1, x2, y2, w, h):
            continue
        is_leaf = not any("bounds" in c.attrib for c in node)
        text = (a.get("text") or "").strip() or (a.get("content-desc") or "").strip()
        clickable = a.get("clickable", "false").lower() == "true"
        scrollable = a.get("scrollable", "false").lower() == "true"
        if _keep(text, clickable, scrollable, is_leaf):
            out.append(LayoutElement(class_name=a.get("class", "View"), element_id=a.get("resource-id", ""),
                                     text=text, clickable=clickable, scrollable=scrollable,
                                     bounds=_normalise(x1, y1, x2, y2, w, h)))
    return out


def format_hierarchy(elements: List[LayoutElement], max_nodes: int = DEFAULT_MAX_NODES) -> str:
    """Serialise elements in reading order; empty string when there is nothing to show."""
    ordered = sorted(elements, key=lambda e: (e.bounds[0], e.bounds[1], e.bounds[2], e.bounds[3]))
    lines = [e.to_line() for e in ordered[:max_nodes]]
    if len(ordered) > max_nodes:
        lines.append(f"... {len(ordered) - max_nodes} more elements omitted")
    return "\n".join(lines)


def hierarchy_text(source: Optional[Union[str, Path, Dict[str, Any]]], max_nodes: int = DEFAULT_MAX_NODES) -> Optional[str]:
    """Auto-detect Rico JSON or UIAutomator XML and return prompt text, or None."""
    if source is None:
        return None
    if isinstance(source, dict):
        elements = elements_from_rico(source)
    else:
        raw = Path(str(source)).read_text(encoding="utf-8") if isinstance(source, Path) else str(source)
        if not raw.strip():
            return None
        if raw.lstrip().startswith("<"):
            elements = elements_from_uiautomator(raw)
        elif raw.lstrip().startswith("{"):
            elements = elements_from_rico(json.loads(raw))
        elif Path(raw).exists():
            return hierarchy_text(Path(raw), max_nodes)
        else:
            return None
    text = format_hierarchy(elements, max_nodes)
    return text or None


def parse_elements(source: Optional[Union[str, Path, Dict[str, Any]]]) -> List[LayoutElement]:
    """All visible elements (no cap) from Rico JSON or UIAutomator XML; [] if unreadable."""
    if source is None:
        return []
    try:
        if isinstance(source, dict):
            return elements_from_rico(source)
        raw = Path(str(source)).read_text(encoding="utf-8") if isinstance(source, Path) else str(source)
        if raw.lstrip().startswith("<"):
            return elements_from_uiautomator(raw)
        if raw.lstrip().startswith("{"):
            return elements_from_rico(json.loads(raw))
    except (ValueError, OSError):
        return []
    return []


def _iou(a: List[int], b: List[int]) -> float:
    ya, xa, yb, xb = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, yb - ya) * max(0, xb - xa)
    area = lambda r: max(0, r[2] - r[0]) * max(0, r[3] - r[1])  # noqa: E731
    union = area(a) + area(b) - inter
    return inter / union if union else 0.0


def resolve_element(box_yxyx_1000: List[int], elements: List[LayoutElement], min_iou: float = 0.1):
    """The layout element a predicted defect region most plausibly refers to, or None.

    Prefers elements whose centre lies inside the region (best IoU among them); otherwise
    the element with the highest IoU if it reaches ``min_iou``. Returns (element, iou).
    """
    if not box_yxyx_1000 or not elements:
        return None, 0.0
    y1, x1, y2, x2 = box_yxyx_1000
    inside = [e for e in elements
              if y1 <= (e.bounds[0] + e.bounds[2]) / 2 <= y2 and x1 <= (e.bounds[1] + e.bounds[3]) / 2 <= x2
              and (e.bounds[2] - e.bounds[0]) * (e.bounds[3] - e.bounds[1]) < 900_000]  # skip full-screen containers
    pool = inside or elements
    best = max(pool, key=lambda e: _iou(box_yxyx_1000, e.bounds))
    score = _iou(box_yxyx_1000, best.bounds)
    if not inside and score < min_iou:
        return None, score
    return best, score


def element_reference(e: LayoutElement) -> str:
    """resource-id when present, else class plus visible text."""
    if e.element_id:
        return e.element_id
    short = e.class_name.split(".")[-1]
    return f'{short}:"{e.text[:30]}"' if e.text else short
