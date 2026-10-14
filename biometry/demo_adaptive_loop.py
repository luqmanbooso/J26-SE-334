"""Run the adaptive loop against a simulated degrading app and plot the result.

Needs no device. This is the offline demonstration path and the fallback if
hardware fails: the app under test is replaced by a stub whose responsiveness we
script, everything else is the real engine.
"""
import os

import numpy as np

from bridge.latency_probe import LatencyProbe
from engine.controller import AdaptiveFeedbackController
from engine.visualise import plot_comparison, plot_timeline
from models.cognitive import CognitiveStateModel, StaticStress
from simulation.simulator import BiometricSimulator

TARGET = {"id": "btn_submit", "x": 500.0, "y": 800.0, "width": 110.0, "height": 44.0}
ACTIONS = 120


class DegradingApp:
    """Responsive, then progressively slower, then recovering — a load spike."""

    def __init__(self, actions):
        self.actions = actions
        self.action = 0
        self._polls = 0
        self._epoch = 0

    def lag_polls(self):
        phase = self.action / self.actions
        if phase < 0.25:
            return 1
        if phase < 0.70:
            return int(1 + 24 * (phase - 0.25) / 0.45)
        return 1

    def signature(self):
        self._polls += 1
        if self._polls > self.lag_polls():
            self._epoch += 1
            self._polls = 0
        return f"screen-{self._epoch}"


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def run(stress_source, seed=2026):
    app = DegradingApp(ACTIONS)
    clock = Clock()
    probe = LatencyProbe(app.signature, clock=clock, sleep=clock.sleep,
                         poll_interval=0.05, timeout=1.6)
    controller = AdaptiveFeedbackController(
        simulator=BiometricSimulator(sigma_absolute=8.0, seed=seed),
        cognitive=stress_source,
        probe=probe,
        dispatch=lambda x, y, d: None,
        clock=clock,
        run_id="demo-adaptive",
    )
    for _ in range(ACTIONS):
        app.action += 1
        controller.act(TARGET)
    return controller.timeline


def main():
    os.makedirs("results", exist_ok=True)

    adaptive = run(CognitiveStateModel(rng=np.random.default_rng(2026)))
    static = run(StaticStress(0.05))

    hits = sum(1 for r in adaptive.records if r.hit_flag)
    print(f"adaptive run: {len(adaptive.records)} actions, "
          f"{len(adaptive.records) - hits} missed the target")
    print(f"  stress {adaptive.records[0].stress_s:.2f} -> "
          f"{max(r.stress_s for r in adaptive.records):.2f} (peak)")
    static_hits = sum(1 for r in static.records if r.hit_flag)
    print(f"static run:   {len(static.records)} actions, "
          f"{len(static.records) - static_hits} missed the target")

    plot_timeline(adaptive, TARGET, path="results/adaptive_loop_timeline.png",
                  title="Adaptive loop: app latency drives cognitive state drives input error")
    plot_comparison({"adaptive (feedback on)": adaptive,
                     "static (feedback off)": static},
                    TARGET, path="results/adaptive_vs_static.png")
    print("\nwrote results/adaptive_loop_timeline.png")
    print("wrote results/adaptive_vs_static.png")
    adaptive.write_json("results/adaptive_loop_timeline.json")
    print("wrote results/adaptive_loop_timeline.json")


if __name__ == "__main__":
    main()
