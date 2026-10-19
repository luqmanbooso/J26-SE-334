"""Parse UIAutomator hierarchy dumps into tappable targets.

Pure parsing, no device. This is what lets the engine run against *real* screen
layouts with nothing attached: a saved dump gives real element positions and,
more importantly, the real spread of element sizes, which is what exercises the
FFitts width dependence. A synthetic rectangle does not.
"""
import glob
import hashlib
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


def _as_root(source):
    """A dump — path, raw XML, or an ElementTree root — as a root Element."""
    if isinstance(source, ET.Element):
        return source
    if isinstance(source, (str, os.PathLike)) and os.path.exists(source):
        return ET.parse(source).getroot()
    return ET.fromstring(source)


def structural_signature(source, grid=8, drop_packages=("com.android.systemui",)):
    """A digest of a screen's *structure*, stable across volatile content.

    Keys each node by class, resource-id, clickability and grid-snapped bounds,
    and deliberately ignores text / content-desc (a clock, a counter, the
    selected row) so the same logical screen hashes the same on every visit.
    System chrome (status/navigation bars) is dropped so it cannot perturb the
    identity. This is the identity the explorer's visited/exhausted cache is
    keyed on: the coarser it is, the more aggressively structurally-identical
    screens (a list-detail page template) collapse to one — which, for
    exhausting an app rather than its data, is the point. For strict,
    every-pixel change detection use `full_signature` instead.
    """
    root = _as_root(source)
    g = grid if grid and grid > 0 else 1
    rows = []
    for node in root.iter("node"):
        if node.get("package", "") in drop_packages:
            continue
        try:
            x1, y1, x2, y2 = parse_bounds(node.get("bounds"))
        except ValueError:
            x1 = y1 = x2 = y2 = 0
        rows.append("{}|{}|{}|{},{},{},{}".format(
            node.get("class", ""), node.get("resource-id", ""),
            node.get("clickable", ""), x1 // g, y1 // g, x2 // g, y2 // g))
    rows.sort()   # order-independent: a reflow that only reorders is the same screen
    return hashlib.sha1("\n".join(rows).encode("utf-8")).hexdigest()


def full_signature(source):
    """A digest of the *entire* screen XML — strict change detection.

    Any moved pixel of text or a blinking cursor changes it, so as a screen
    *identity* it over-counts and makes every revisit look new; that is why
    `structural_signature` is the explorer's default. Kept for `--signature
    full` and parity with `latency_probe.hierarchy_signature`.
    """
    root = _as_root(source)
    return hashlib.sha1(ET.tostring(root, encoding="unicode").encode("utf-8")).hexdigest()


def frame_signature(source, drop_packages=("com.android.systemui",)):
    """A screen's *frame* identity: its set of interactive controls, ignoring
    content and layout.

    Hashes the distinct `(class, resource-id)` of every clickable node, dropping
    system chrome. Two states of one screen that differ only in content — a
    filter chip reselecting a list, a tab swapping a fragment — carry the same
    controls, so they share a frame and the explorer taps all the chips/tabs in
    place instead of descending into each as a "new screen". A genuinely
    different screen, with a different control set, gets a different frame.

    The trade-off is deliberate and the opposite of `structural_signature`: this
    collapses content states of one screen into one identity (what you want to
    exhaust an app's *controls*), at the risk of collapsing two screens whose
    interactive controls happen to be identical. Use `structural_signature` (via
    --signature structural) when every content state should be its own screen.
    """
    root = _as_root(source)
    controls = set()
    for node in root.iter("node"):
        if node.get("package", "") in drop_packages:
            continue
        if node.get("clickable") == "true":
            controls.add((node.get("class", ""), node.get("resource-id", "")))
    rows = sorted("{}|{}".format(cls, rid) for cls, rid in controls)
    return hashlib.sha1("\n".join(rows).encode("utf-8")).hexdigest()


def parse_hierarchy(source):
    """Parse a dump — a path, raw XML, or an ElementTree root — into UiElements."""
    root = _as_root(source)
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
