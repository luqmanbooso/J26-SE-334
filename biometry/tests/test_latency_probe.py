"""The probe that replaces C1's unbuilt perf feed.

Driven entirely by injected clock, sleep and screen-reader callables, so the
whole adaptive input path is testable with no device attached (NFR-06).
"""
import pytest

from bridge.latency_probe import LatencyProbe, Observation


class FakeScreen:
    """A screen that changes after a set number of polls, or never."""

    def __init__(self, changes_after=1):
        self.changes_after = changes_after
        self.reads = 0

    def __call__(self):
        self.reads += 1
        if self.changes_after is None or self.reads <= self.changes_after:
            return "screen-a"
        return "screen-b"


class FakeClock:
    def __init__(self, step=0.05):
        self.now = 0.0
        self.step = step

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def probe(screen, **kw):
    clock = FakeClock()
    return LatencyProbe(screen, clock=clock, sleep=clock.sleep, **kw), clock


# --- measurement ------------------------------------------------------------

def test_an_immediate_change_is_detected_within_one_poll():
    p, _ = probe(FakeScreen(changes_after=1), poll_interval=0.05)
    obs = p.observe(before="screen-a")
    assert obs.changed
    assert obs.ui_delay_s == pytest.approx(0.05, abs=1e-9)


def test_a_delayed_change_is_measured():
    p, _ = probe(FakeScreen(changes_after=9), poll_interval=0.05)
    obs = p.observe(before="screen-a")
    assert obs.changed
    assert obs.ui_delay_s == pytest.approx(0.45, abs=1e-6)


@pytest.mark.parametrize("changes_after", [1, 3, 7, 12])
def test_measurement_error_is_bounded_by_the_poll_interval(changes_after):
    """Polling detects a change up to one interval after it happened. The reported
    delay is therefore an upper bound on the true latency, never an underestimate."""
    interval = 0.05
    p, _ = probe(FakeScreen(changes_after=changes_after), poll_interval=interval)
    obs = p.observe(before="screen-a")
    true_change_at = (changes_after - 1) * interval
    assert true_change_at <= obs.ui_delay_s <= true_change_at + interval


def test_ui_delay_is_also_exposed_in_milliseconds():
    assert Observation(0.25, True, 0).ui_delay_ms == 250.0


def test_a_screen_that_never_changes_times_out():
    p, _ = probe(FakeScreen(changes_after=None), timeout=1.0)
    obs = p.observe(before="screen-a")
    assert not obs.changed
    assert obs.ui_delay_s >= 1.0


def test_repeated_no_response_is_counted():
    p, _ = probe(FakeScreen(changes_after=None), timeout=0.2)
    counts = [p.observe(before="screen-a").consecutive_unchanged for _ in range(3)]
    assert counts == [1, 2, 3]


def test_a_response_resets_the_no_response_counter():
    screen = FakeScreen(changes_after=None)
    p, _ = probe(screen, timeout=0.2)
    p.observe(before="screen-a")
    assert p._consecutive_unchanged == 1
    screen.changes_after = 1
    screen.reads = 0
    obs = p.observe(before="screen-a")
    assert obs.changed and obs.consecutive_unchanged == 0


def test_the_probe_reads_the_current_screen_when_no_baseline_is_given():
    p, _ = probe(FakeScreen(changes_after=2))
    assert p.observe().changed


# --- provocation mapping ----------------------------------------------------

def test_a_fast_response_does_not_provoke():
    p, _ = probe(FakeScreen())
    assert p.provocation(Observation(0.05, True, 0)) == 0.0


def test_provocation_rises_with_delay():
    p, _ = probe(FakeScreen())
    rising = [p.provocation(Observation(d, True, 0)) for d in (0.3, 0.6, 0.9, 1.2, 1.5)]
    assert rising == sorted(rising)
    assert rising[0] == 0.0 and rising[-1] == 1.0


def test_provocation_saturates_rather_than_exceeding_one():
    p, _ = probe(FakeScreen())
    assert p.provocation(Observation(30.0, True, 0)) == 1.0


def test_no_response_is_maximally_provoking():
    p, _ = probe(FakeScreen())
    assert p.provocation(Observation(2.0, False, 1)) == 1.0


@pytest.mark.parametrize("delay", [0.0, 0.3, 0.75, 1.5, 10.0])
def test_provocation_is_always_a_valid_stress_input(delay):
    p, _ = probe(FakeScreen())
    assert 0.0 <= p.provocation(Observation(delay, True, 0)) <= 1.0


# --- contention with other components' ADB access ---------------------------

class SlowScreen:
    """A screen whose read is itself expensive — what another component dumping
    the hierarchy concurrently looks like from here."""

    def __init__(self, clock, read_cost, changes_after=None):
        self.clock, self.read_cost = clock, read_cost
        self.changes_after, self.reads = changes_after, 0

    def __call__(self):
        self.reads += 1
        self.clock.now += self.read_cost          # the read itself takes time
        if self.changes_after is not None and self.reads > self.changes_after:
            return "screen-b"
        return "screen-a"


def test_a_cheap_read_is_not_flagged_as_contended():
    clock = FakeClock()
    screen = SlowScreen(clock, read_cost=0.005, changes_after=1)
    p = LatencyProbe(screen, clock=clock, sleep=clock.sleep, poll_interval=0.05)
    obs = p.observe(before="screen-a")
    assert not obs.contended
    assert obs.read_cost_s == pytest.approx(0.005)


def test_an_expensive_read_is_flagged_as_contended():
    """If reading the screen costs more than the poll interval, polling cannot keep
    up and the measured delay is contention rather than app latency."""
    clock = FakeClock()
    screen = SlowScreen(clock, read_cost=0.40, changes_after=1)
    p = LatencyProbe(screen, clock=clock, sleep=clock.sleep, poll_interval=0.05)
    obs = p.observe(before="screen-a")
    assert obs.contended
    assert obs.read_cost_s >= 0.40


def test_contention_is_carried_through_to_the_run_record():
    """The flag has to reach the timeline, or analysis cannot exclude bad samples."""
    from engine.controller import ActionRecord
    assert "contended" in ActionRecord.__dataclass_fields__
