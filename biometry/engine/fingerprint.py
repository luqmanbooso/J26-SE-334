"""Cheap perceptual fingerprint of a screen, for fast replay verification.

An average-hash (aHash) of a downscaled grayscale screenshot: robust to small
content changes (a clock, one list item) but distinct across different screens.
Comparing two fingerprints is a Hamming distance over the bit string — a few
microseconds, versus the ~2.5 s `uiautomator dump` the mapper used to identify a
screen. Replay uses it to confirm it is still on the screen the compiled plan
expects before it trusts a saved tap coordinate, without paying for a full dump.
"""
from __future__ import annotations

HASH_SIDE = 16                 # 16x16 = a 256-bit hash (64 hex chars)
DEFAULT_MAX_DISTANCE = 28      # bits that may differ and still be "the same screen"


def ahash(image, side: int = HASH_SIDE) -> str:
    """Average-hash a PIL image to a hex string. Returns "" if it cannot."""
    try:
        grey = image.convert("L").resize((side, side))
        px = list(grey.tobytes())          # one byte per pixel in 'L' mode
        if not px:
            return ""
        avg = sum(px) / len(px)
        bits = "".join("1" if p >= avg else "0" for p in px)
        return "{:0{}x}".format(int(bits, 2), side * side // 4)
    except Exception:
        return ""


def distance(a: str, b: str) -> int:
    """Hamming distance between two hex fingerprints; huge when incomparable."""
    if not a or not b or len(a) != len(b):
        return 10 ** 9
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except ValueError:
        return 10 ** 9


def matches(a: str, b: str, max_distance: int = DEFAULT_MAX_DISTANCE) -> bool:
    """True when two fingerprints are close enough to be the same screen."""
    return distance(a, b) <= max_distance
