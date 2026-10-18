"""Measure how the app under test responds to an action.

The interface contract with C1 promises latency, frame drops and ANR flags, but
nothing produces them: C1's engine logs the perturbations it applies and never
measures the app's reaction. Rather than block the adaptive loop on a feed that
does not exist, C2 measures the one signal it can obtain by itself and fully
explain — the wall-clock time between dispatching an action and the UI hierarchy
changing, and whether it changed at all.

That is the `ui_delay_ms` field of the agreed contract, obtained from the device
C2 is already driving. C1's perturbation log remains useful as context, but is
no longer on the critical path.
"""
import hashlib
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass


def hierarchy_signature(bridge):
    """A stable digest of the current screen, for change detection."""
    xml = ET.tostring(bridge.dump_ui_hierarchy(), encoding="unicode")
    return hashlib.sha1(xml.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Observation:
    """What the app did in response to one action."""

    ui_delay_s: float
    changed: bool
    consecutive_unchanged: int
    read_cost_s: float = 0.0
    contended: bool = False

    @property
    def ui_delay_ms(self):
        return self.ui_delay_s * 1000.0


class LatencyProbe:
    """
    Times the gap between an action and the screen reacting to it.

    Call `observe()` immediately after dispatching an action. It polls the
    screen signature until it differs from the one captured before the action,
    or until the timeout expires.

    Two things provoke a user, and they are not the same thing: a screen that
    responds slowly, and a screen that does not respond at all. The second is
    worse, and worse again when it repeats — that is the shape of a rage click.

    Measurement is quantised by polling: a change is detected up to one
    `poll_interval` after it actually happened, so the reported delay is an
    upper bound on the true latency and never an underestimate. A shorter
    interval buys precision at the cost of more hierarchy dumps, which are
    themselves slow enough to perturb what is being measured.

    **The measurement assumes C2 is the only thing touching the device.**
    `uiautomator dump` is exclusive and slow, and three components in this
    project open their own independent ADB connections with nothing coordinating
    them. If another component dumps the hierarchy during a run, the time this
    probe measures is contention, not the app responding. Each observation
    therefore carries the cost of its own screen reads and a `contended` flag
    raised when that cost exceeds the poll interval — at which point polling can
    no longer keep up and the delay figure should not be trusted as app latency.
    """

    def __init__(self, read_signature, clock=time.monotonic, sleep=time.sleep,
                 poll_interval=0.05, timeout=2.0,
                 patience_s=0.30, intolerable_s=1.50):
        # patience_s:     below this, a response feels immediate.
        # intolerable_s:  at or above this, a response is as bad as none.
        # Both are placeholders pending calibration.
        self.read_signature = read_signature
        self.clock = clock
        self.sleep = sleep
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.patience_s = patience_s
        self.intolerable_s = intolerable_s
        self._consecutive_unchanged = 0

    def _timed_read(self):
        """Read the screen signature, returning (signature, seconds it took)."""
        start = self.clock()
        signature = self.read_signature()
        return signature, self.clock() - start

    def observe(self, before=None):
        """Block until the screen changes or the timeout expires; return an Observation."""
        if before is None:
            before, _ = self._timed_read()
        started = self.clock()
        worst_read = 0.0
        while True:
            elapsed = self.clock() - started
            signature, cost = self._timed_read()
            worst_read = max(worst_read, cost)
            contended = worst_read > self.poll_interval
            if signature != before:
                self._consecutive_unchanged = 0
                return Observation(elapsed, True, 0, worst_read, contended)
            if elapsed >= self.timeout:
                self._consecutive_unchanged += 1
                return Observation(elapsed, False, self._consecutive_unchanged,
                                   worst_read, contended)
            self.sleep(self.poll_interval)

    def provocation(self, observation):
        """Map an observation onto [0,1] for the cognitive layer."""
        if not observation.changed:
            # No response at all is maximally provoking, and repetition keeps it there.
            return 1.0
        span = self.intolerable_s - self.patience_s
        over = observation.ui_delay_s - self.patience_s
        return float(min(1.0, max(0.0, over / span)))
