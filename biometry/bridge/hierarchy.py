"""Parse UIAutomator hierarchy dumps into tappable targets.

Pure parsing, no device. This is what lets the engine run against *real* screen
layouts with nothing attached: a saved dump gives real element positions and,
more importantly, the real spread of element sizes, which is what exercises the
FFitts width dependence. A synthetic rectangle does not.
"""
import glob
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

BOUNDS = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def parse_bounds(bounds):
    """'[x1,y1][x2,y2]' -> (x1, y1, x2, y2)."""
    match = BOUNDS.match(bounds or "")
    if not match:
        raise ValueError(f"malformed bounds: {bounds!r}")
    return tuple(int(g) for g in match.groups())


@dataclass(frozen=True)
class UiElement:
    """One node of a screen, reduced to what the engine needs to aim at it."""

    element_id: str
    x: float
    y: float
    width: float
    height: float
    text: str
    resource_id: str
    clickable: bool

    @property
    def area(self):
        return self.width * self.height

    def as_target(self):
        """The shape BiometricSimulator and the controller expect."""
        return {"id": self.element_id, "x": self.x, "y": self.y,
                "width": self.width, "height": self.height}


def _element(node):
    x1, y1, x2, y2 = parse_bounds(node.get("bounds"))
    width, height = x2 - x1, y2 - y1
    text = (node.get("text") or "").strip()
    desc = (node.get("content-desc") or "").strip()
    resource_id = node.get("resource-id") or ""
    label = text or desc or resource_id.rsplit("/", 1)[-1] or "unnamed"
    return UiElement(
        element_id=label,
        x=x1 + width / 2.0,
        y=y1 + height / 2.0,
        width=float(width),
        height=float(height),
        text=text,
        resource_id=resource_id,
        clickable=node.get("clickable") == "true",
    )


def parse_hierarchy(source):
    """Parse a dump — a path, raw XML, or an ElementTree root — into UiElements."""
    if isinstance(source, ET.Element):
        root = source
    elif isinstance(source, (str, os.PathLike)) and os.path.exists(source):
        root = ET.parse(source).getroot()
    else:
        root = ET.fromstring(source)
    out = []
    for node in root.iter("node"):
        try:
            out.append(_element(node))
        except ValueError:
            continue  # a node without usable bounds is not a target
    return out


def tappable_targets(elements, min_side=20.0, max_side=900.0):
    """Clickable elements of a plausible size to aim at.

    Containers spanning most of the screen are clickable but are not what a user
    aims at, and zero-area nodes cannot be hit at all.
    """
    return [e for e in elements
            if e.clickable
            and min_side <= min(e.width, e.height)
            and max(e.width, e.height) <= max_side]


def load_corpus(directory, pattern="*.xml"):
    """{screen name -> tappable targets} for every dump in a directory."""
    corpus = {}
    for path in sorted(glob.glob(os.path.join(directory, pattern))):
        name = os.path.splitext(os.path.basename(path))[0]
        corpus[name] = tappable_targets(parse_hierarchy(path))
    return corpus
