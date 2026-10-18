"""Measure app responsiveness from the device's own rendering statistics.

The first probe timed the gap between dispatching an action and the UI
hierarchy changing. On real hardware that turned out to be unusable: a
`uiautomator dump` costs about 2.4 seconds on a mid-range phone, while a
calculator tap responds in roughly 50 ms. The instrument was twenty times
coarser than the thing it measured, and every sample came back either "changed
on the first read" or "timed out". The contention flag caught it, which is how
we know.

`dumpsys gfxinfo` costs about 58 ms on the same device — close to the bare ADB
round trip of 28 ms — and reports what the platform itself measured: how many
frames were rendered, how many were janky, and the frame-time distribution.
That is both cheaper and more direct than inferring latency from screen
changes, so it is the primary probe. LatencyProbe remains for cases where
gfxinfo is unavailable.

The counters are read with `reset`, which zeroes them as it prints. Without
that the percentiles are lifetime figures and barely move: a first live run
showed p95 varying only between 17 ms and 19 ms across forty actions, because
it was describing the whole process rather than the action just performed.
Reading with reset makes every figure describe exactly one window — the same
run then showed windows of 19 ms, 20 ms and 93 ms.

Jank is only assessed once enough frames have rendered. A window holding two
frames, one of them janky, is not a 50% jank rate; it is no sample at all, and
treating it as one made the first run's stress curve noise.

When nothing rendered at all, gfxinfo fills every percentile with 4950 ms — the
top histogram bucket, used as an empty-set sentinel rather than a measurement.
A stalled window therefore reports no frame time at all. The stall itself is
the signal; 4950 ms is not a number anyone measured.
"""
import re
import time
from dataclasses import dataclass

TOTAL = re.compile(r"Total frames rendered:\s*(\d+)")
JANKY = re.compile(r"Janky frames:\s*(\d+)\s*\(([\d.]+)%\)")
PCTL = re.compile(r"(\d+)th percentile:\s*(\d+)ms")
HIGH_INPUT = re.compile(r"Number High input latency:\s*(\d+)")


@dataclass(frozen=True)
class FrameStats:
    """One reading of the platform's rendering counters."""

    total_frames: int = 0
    janky_frames: int = 0
    high_input_latency: int = 0
    p50_ms: float = 0.0
    p90_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0

    @classmethod
    def parse(cls, text):
        pct = {int(k): float(v) for k, v in PCTL.findall(text or "")}
        janky = JANKY.search(text or "")
        total = TOTAL.search(text or "")
        high = HIGH_INPUT.search(text or "")
        return cls(
            total_frames=int(total.group(1)) if total else 0,
            janky_frames=int(janky.group(1)) if janky else 0,
            high_input_latency=int(high.group(1)) if high else 0,
            p50_ms=pct.get(50, 0.0), p90_ms=pct.get(90, 0.0),
            p95_ms=pct.get(95, 0.0), p99_ms=pct.get(99, 0.0),
        )


@dataclass(frozen=True)
class FrameObservation:
    """What rendering did across one action."""

    frames: int
    janky: int
    jank_pct: float
    p95_ms: float
    high_input_delta: int
    elapsed_s: float
    read_cost_s: float
    stalled: bool          # no frames rendered at all — the app did not react

    #: gfxinfo fills every percentile with this when the histogram is empty.
    EMPTY_HISTOGRAM_SENTINEL_MS = 4950.0

    @property
    def ui_delay_ms(self):
        """Worst-case frame time in the window, or None when nothing rendered.

        A stalled window has no frame times. Reporting the sentinel as a latency
        would put a figure nobody measured into the results.
        """
        if self.stalled or self.p95_ms >= self.EMPTY_HISTOGRAM_SENTINEL_MS:
            return None
        return self.p95_ms

    # The controller treats every probe alike, so these mirror LatencyProbe.
    @property
    def changed(self):
        """The app rendered something: it reacted."""
        return not self.stalled

    @property
    def consecutive_unchanged(self):
        return 0

    @property
    def contended(self):
        """A read costing more than ~150 ms is competing for the device, and the
        window it describes is wider than the action it is meant to cover."""
        return self.read_cost_s > 0.150


class FrameProbe:
    """Responsiveness from `dumpsys gfxinfo`, sampled around each action."""

    def __init__(self, device, package, clock=time.monotonic,
                 smooth_ms=16.7, intolerable_ms=250.0, jank_tolerance=0.20):
        # smooth_ms:       one frame at 60 Hz; at or below this nothing is wrong.
        # intolerable_ms:  a frame this slow is a visible stutter.
        # jank_tolerance:  proportion of janky frames treated as fully provoking.
        self.device = device
        self.package = package
        self.clock = clock
        self.smooth_ms = smooth_ms
        self.intolerable_ms = intolerable_ms
        self.jank_tolerance = jank_tolerance
        self._consecutive_stalls = 0

    MIN_FRAMES_FOR_JANK = 8     # below this a jank ratio is noise, not a rate

    def read_signature(self):
        """Open a measurement window: zero the counters and discard the reading."""
        self.snapshot()
        return None

    def snapshot(self):
        """Read the counters and zero them. Returns (FrameStats, read cost).

        `reset` makes each reading describe only the window since the previous
        one, which is what the percentiles have to mean for a per-action figure.
        """
        start = self.clock()
        text = self.device.shell("dumpsys", "gfxinfo", self.package, "reset")
        return FrameStats.parse(text), self.clock() - start

    def observe(self, before=None):     # noqa: ARG002 - window opened by reset
        """Describe the window that `read_signature` opened."""
        started = self.clock()
        window, cost = self.snapshot()
        frames, janky = window.total_frames, window.janky_frames
        stalled = frames == 0
        self._consecutive_stalls = self._consecutive_stalls + 1 if stalled else 0
        return FrameObservation(
            frames=frames, janky=janky,
            jank_pct=(janky / frames) if frames >= self.MIN_FRAMES_FOR_JANK else 0.0,
            p95_ms=window.p95_ms,
            high_input_delta=window.high_input_latency,
            elapsed_s=self.clock() - started, read_cost_s=cost, stalled=stalled,
        )

    def provocation(self, observation):
        """Map rendering behaviour onto the [0,1] the cognitive layer expects."""
        if observation.stalled:
            return 1.0                      # nothing rendered: the app is not reacting
        span = self.intolerable_ms - self.smooth_ms
        frame_ms = observation.ui_delay_ms
        if frame_ms is None:            # no frame times in this window
            return float(min(1.0, observation.jank_pct / self.jank_tolerance))
        slowness = (frame_ms - self.smooth_ms) / span
        jank = observation.jank_pct / self.jank_tolerance
        return float(min(1.0, max(0.0, max(slowness, jank))))
