"""Canonical action vocabulary used by flow extraction."""

from __future__ import annotations

from enum import Enum


class CanonicalAction(str, Enum):
    """Normalized interaction categories."""

    TAP = "tap"
    INPUT = "input"
    NAVIGATE = "navigate"
    SCROLL = "scroll"
    BACK = "back"
    UNKNOWN = "unknown"


ACTION_ALIASES: dict[str, CanonicalAction] = {
    "ui.click": CanonicalAction.TAP,
    "click": CanonicalAction.TAP,
    "tap": CanonicalAction.TAP,
    "press": CanonicalAction.TAP,
    "touch": CanonicalAction.TAP,
    "ui.input": CanonicalAction.INPUT,
    "input": CanonicalAction.INPUT,
    "text_input": CanonicalAction.INPUT,
    "type": CanonicalAction.INPUT,
    "enter_text": CanonicalAction.INPUT,
    "set_text": CanonicalAction.INPUT,
    "navigation": CanonicalAction.NAVIGATE,
    "navigate": CanonicalAction.NAVIGATE,
    "screen_view": CanonicalAction.NAVIGATE,
    "open_screen": CanonicalAction.NAVIGATE,
    "scroll": CanonicalAction.SCROLL,
    "swipe": CanonicalAction.SCROLL,
    "fling": CanonicalAction.SCROLL,
    "back": CanonicalAction.BACK,
    "ui.back": CanonicalAction.BACK,
    "navigate_back": CanonicalAction.BACK,
}

REPRODUCIBLE_ACTIONS = frozenset(
    action for action in CanonicalAction if action is not CanonicalAction.UNKNOWN
)


def canonicalize_action(raw: str | None) -> CanonicalAction:
    """Map a provider action label to the canonical action vocabulary."""
    if raw is None:
        return CanonicalAction.UNKNOWN
    return ACTION_ALIASES.get(raw.strip().lower(), CanonicalAction.UNKNOWN)
