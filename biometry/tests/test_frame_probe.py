"""The frame-statistics probe.

Replaces hierarchy-change timing, which real hardware showed to be unusable:
a uiautomator dump costs ~2.4 s on a mid-range phone against ~44 ms for
dumpsys gfxinfo, so the old instrument was twenty times coarser than the
latency it was trying to measure.
"""
import pytest

from bridge.frame_probe import FrameObservation, FrameProbe, FrameStats

GFXINFO = """
Applications Graphics Acceleration Info:
Total frames rendered: 1162
Janky frames: 57 (4.91%)
Janky frames (legacy): 50 (4.30%)
50th percentile: 11ms
90th percentile: 14ms
95th percentile: 17ms
99th percentile: 73ms
Number Missed Vsync: 20
Number High input latency: 780
Number Slow UI thread: 26
"""


class FakeDevice:
    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = 0

    def shell(self, *args):
        self.calls += 1
        return self.texts[min(self.calls - 1, len(self.texts) - 1)]


class FakeClock:
    def __init__(self): self.now = 0.0
    def __call__(self):
        self.now += 0.01
        return self.now


def probe(texts, **kw):
    return FrameProbe(FakeDevice(texts), "com.example", clock=FakeClock(), **kw)


# --- parsing ----------------------------------------------------------------

def test_parses_the_platform_counters():
    s = FrameStats.parse(GFXINFO)
    assert (s.total_frames, s.janky_frames, s.high_input_latency) == (1162, 57, 780)
    assert (s.p50_ms, s.p90_ms, s.p95_ms, s.p99_ms) == (11.0, 14.0, 17.0, 73.0)


@pytest.mark.parametrize("text", ["", None, "no counters here"])
def test_unparseable_output_yields_zeros_rather_than_raising(text):
    assert FrameStats.parse(text).total_frames == 0


# --- differencing -----------------------------------------------------------

def window(frames, janky, p95=17):
    return (GFXINFO.replace("Total frames rendered: 1162", f"Total frames rendered: {frames}")
                   .replace("Janky frames: 57", f"Janky frames: {janky}")
                   .replace("95th percentile: 17ms", f"95th percentile: {p95}ms"))


def test_a_reading_describes_only_its_own_window():
    """Counters are read with reset, so no differencing is needed."""
    o = probe([window(20, 3)]).observe()
    assert o.frames == 20 and o.janky == 3
    assert o.jank_pct == pytest.approx(0.15)


def test_the_window_is_opened_by_resetting():
    d = FakeDevice([GFXINFO])
    FrameProbe(d, "com.example", clock=FakeClock()).read_signature()
    assert d.calls == 1          # the reset read happened and was discarded


def test_no_frames_rendered_is_a_stall():
    o = probe([window(0, 0)]).observe()
    assert o.stalled and o.frames == 0


def test_a_jank_ratio_from_too_few_frames_is_not_trusted():
    """One janky frame out of two is not a 50% jank rate; it is no sample."""
    o = probe([window(2, 1)]).observe()
    assert o.frames == 2 and o.janky == 1
    assert o.jank_pct == 0.0


def test_jank_is_assessed_once_enough_frames_have_rendered():
    o = probe([window(20, 5)]).observe()
    assert o.jank_pct == pytest.approx(0.25)


# --- provocation ------------------------------------------------------------

def test_a_stalled_app_is_maximally_provoking():
    p = probe([GFXINFO])
    assert p.provocation(FrameObservation(0, 0, 0.0, 17.0, 0, 0.1, 0.05, True)) == 1.0


def test_smooth_rendering_does_not_provoke():
    p = probe([GFXINFO])
    assert p.provocation(FrameObservation(60, 0, 0.0, 16.0, 0, 0.1, 0.05, False)) == 0.0


def test_slow_frames_provoke_in_proportion():
    p = probe([GFXINFO])
    rising = [p.provocation(FrameObservation(60, 0, 0.0, ms, 0, 0.1, 0.05, False))
              for ms in (16.7, 80, 150, 250, 400)]
    assert rising == sorted(rising)
    assert rising[0] == 0.0 and rising[-1] == 1.0


def test_jank_provokes_even_when_percentiles_look_fine():
    """A burst of dropped frames matters even if p95 is unremarkable."""
    p = probe([GFXINFO])
    assert p.provocation(FrameObservation(20, 5, 0.25, 16.0, 0, 0.1, 0.05, False)) == 1.0


@pytest.mark.parametrize("p95,jank", [(16.0, 0.0), (100.0, 0.05), (500.0, 0.9)])
def test_provocation_is_always_a_valid_stress_input(p95, jank):
    p = probe([GFXINFO])
    v = p.provocation(FrameObservation(40, int(40 * jank), jank, p95, 0, 0.1, 0.05, False))
    assert 0.0 <= v <= 1.0


def test_the_read_cost_is_recorded():
    assert probe([GFXINFO]).observe().read_cost_s > 0


def test_percentiles_describe_the_window_not_the_process():
    """A slow window must be visible. Lifetime percentiles barely move; that is
    the bug reading with reset exists to avoid."""
    assert probe([window(11, 3, p95=93)]).observe().p95_ms == 93.0


def test_the_empty_histogram_sentinel_is_not_reported_as_a_latency():
    """With no frames rendered, gfxinfo fills every percentile with 4950 ms.
    That is an empty-set marker, not something anyone measured."""
    o = probe([window(0, 0, p95=4950)]).observe()
    assert o.stalled
    assert o.ui_delay_ms is None
    assert o.p95_ms == 4950.0          # raw reading preserved
    assert probe([GFXINFO]).provocation(o) == 1.0


def test_a_real_frame_time_is_still_reported():
    assert probe([window(20, 1, p95=93)]).observe().ui_delay_ms == 93.0
