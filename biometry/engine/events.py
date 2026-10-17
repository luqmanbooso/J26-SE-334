"""Compile distorted actions into ordered motion events.

This is the producer side of the IF-C2-to-Driver contract: every action the
engine performs is expressible as a time-ordered DOWN / MOVE* / UP sequence of
coordinates — never an element reference, never `element.click()`. A driver
that can replay raw motion events can replay exactly what the engine did,
distortions included.
"""
from dataclasses import asdict, dataclass

DOWN = "down"
MOVE = "move"
UP = "up"

# A human press is not instantaneous: finger contact dwells before lift-off.
DEFAULT_PRESS_MS = 65.0


@dataclass(frozen=True)
class MotionEvent:
    kind: str    # down | move | up
    x: float
    y: float
    t_ms: float  # relative to the gesture's own DOWN


def compile_tap(x, y, press_ms=DEFAULT_PRESS_MS):
    """A tap is the degenerate gesture: DOWN, dwell, UP at the same point."""
    return [
        MotionEvent(DOWN, x, y, 0.0),
        MotionEvent(UP, x, y, press_ms),
    ]


def compile_path(path):
    """Turn a timed path — ordered (x, y, t_ms) points — into motion events.

    The first point is the press, the last the release, everything between a
    MOVE. Timestamps must be non-decreasing; the synthesizer guarantees that,
    and this guards against a caller who hand-builds a path that is not.
    """
    if len(path) < 2:
        raise ValueError("a gesture path needs at least a press and a release")
    times = [p[2] for p in path]
    if any(b < a for a, b in zip(times, times[1:])):
        raise ValueError("path timestamps must be non-decreasing")

    events = [MotionEvent(DOWN, path[0][0], path[0][1], path[0][2])]
    events += [MotionEvent(MOVE, x, y, t) for x, y, t in path[1:-1]]
    events.append(MotionEvent(UP, path[-1][0], path[-1][1], path[-1][2]))
    return events


def events_to_dicts(events):
    """Serialisable form of an event sequence, for the driver payload."""
    return [asdict(e) for e in events]
