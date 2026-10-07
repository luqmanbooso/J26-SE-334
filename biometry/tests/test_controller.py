"""The adaptive loop, end to end, with no device attached.

The loop is the contribution, so these assert that the app's behaviour actually
reaches the next action's distortion — not merely that the parts run.
"""
import json

import numpy as np
import pytest

from bridge.latency_probe import LatencyProbe
from engine.controller import AdaptiveFeedbackController
from models.cognitive import CognitiveState, CognitiveStateModel, StaticStress
from simulation.simulator import BiometricSimulator

TARGET = {"id": "btn_submit", "x": 500.0, "y": 800.0, "width": 160.0, "height": 70.0}


class FakeApp:
    """A screen whose responsiveness we control. `lag_polls` is how many polls
    pass before it reacts; None means it never does."""

    def __init__(self, lag_polls=1):
        self.lag_polls = lag_polls
        self._reads = 0
        self._epoch = 0

    def signature(self):
        self._reads += 1
        if self.lag_polls is not None and self._reads > self.lag_polls:
            self._epoch += 1
            self._reads = 0
        return f"screen-{self._epoch}"


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def build(lag_polls=1, cognitive=None, seed=5):
    app = FakeApp(lag_polls)
    clock = FakeClock()
    probe = LatencyProbe(app.signature, clock=clock, sleep=clock.sleep,
                         poll_interval=0.05, timeout=1.0)
    taps = []
    controller = AdaptiveFeedbackController(
        simulator=BiometricSimulator(sigma_absolute=8.0, seed=seed),
        cognitive=cognitive if cognitive is not None
        else CognitiveStateModel(rng=np.random.default_rng(seed)),
        probe=probe,
        dispatch=lambda x, y, d: taps.append((x, y, d)),
        clock=clock,
    )
    return controller, app, taps


# --- the loop runs ----------------------------------------------------------

def test_one_action_produces_one_record_and_one_tap():
    c, _, taps = build()
    record = c.act(TARGET)
    assert len(taps) == 1 and len(c.timeline.records) == 1
    assert record.target_element_id == "btn_submit"


def test_the_dispatched_point_is_the_distorted_one():
    c, _, taps = build()
    record = c.act(TARGET)
    assert taps[0][0] == record.x and taps[0][1] == record.y
    assert (record.x, record.y) != (TARGET["x"], TARGET["y"])


def test_run_walks_every_target():
    c, _, taps = build()
    timeline = c.run([TARGET] * 6)
    assert len(taps) == 6 and len(timeline.records) == 6


# --- the loop is actually closed -------------------------------------------

def test_an_unresponsive_app_drives_stress_up():
    """The whole point: the app misbehaving changes how the next tap is performed."""
    c, _, _ = build(lag_polls=None)
    c.run([TARGET] * 40)
    assert c.timeline.records[-1].stress_s > c.timeline.records[0].stress_s + 0.4
    assert c.cognitive.state is CognitiveState.FRUSTRATED


def test_a_responsive_app_leaves_the_user_calm():
    c, _, _ = build(lag_polls=1)
    c.run([TARGET] * 40)
    assert c.cognitive.state is CognitiveState.CALM
    assert c.timeline.records[-1].stress_s < 0.15


def test_rising_stress_widens_the_touch_error():
    """Stress must reach the distortion, not just the log."""
    c, _, _ = build(lag_polls=None)
    c.run([TARGET] * 60)
    early = [r.error_px for r in c.timeline.records[:10]]
    late = [r.error_px for r in c.timeline.records[-10:]]
    assert np.mean(late) > np.mean(early)


def test_an_unresponsive_app_is_recorded_as_unresponsive():
    c, _, _ = build(lag_polls=None)
    c.act(TARGET)
    r = c.timeline.records[0]
    assert not r.responded and r.provocation == 1.0


# --- the ablation is a substitution, not a code path ------------------------

def test_a_static_source_ignores_the_app_entirely():
    c, _, _ = build(lag_polls=None, cognitive=StaticStress(0.2))
    c.run([TARGET] * 40)
    assert {r.stress_s for r in c.timeline.records} == {0.2}
    assert {r.cognitive_state for r in c.timeline.records} == {"static"}


def test_adaptive_and_static_diverge_on_the_same_app():
    adaptive, _, _ = build(lag_polls=None)
    static, _, _ = build(lag_polls=None, cognitive=StaticStress(0.05))
    adaptive.run([TARGET] * 50)
    static.run([TARGET] * 50)
    assert adaptive.timeline.records[-1].stress_s > static.timeline.records[-1].stress_s


# --- the timeline is persistable -------------------------------------------

def test_the_timeline_serialises_to_the_store_contract(tmp_path):
    c, _, _ = build(lag_polls=None)
    c.run([TARGET] * 3)
    path = c.timeline.write_json(tmp_path / "timeline.json")
    data = json.loads(path.read_text())
    assert data["run_id"] == "run" and len(data["records"]) == 3
    assert set(data["records"][0]) >= {
        "t_ms", "target_element_id", "x", "y", "hit_flag",
        "stress_s", "cognitive_state", "ui_delay_ms", "provocation",
    }


def test_timestamps_increase_monotonically():
    c, _, _ = build(lag_polls=2)
    c.run([TARGET] * 10)
    stamps = [r.t_ms for r in c.timeline.records]
    assert stamps == sorted(stamps)
