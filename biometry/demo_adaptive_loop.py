"""Run the adaptive loop against a simulated degrading app and plot the result.

Needs no device. This is the offline demonstration path and the fallback if
hardware fails: the app under test is replaced by a stub whose responsiveness we
script, everything else is the real engine.
"""
import os
from statistics import mean

import numpy as np

from bridge.hierarchy import parse_hierarchy, tappable_targets
from bridge.latency_probe import LatencyProbe
from engine.controller import AdaptiveFeedbackController
from engine.visualise import plot_comparison, plot_timeline
from models.cognitive import CognitiveStateModel, StaticStress
from simulation.simulator import BiometricSimulator

# Real targets from a saved dialer screen, so the run exercises the actual spread
# of element sizes rather than one synthetic rectangle.
TARGETS = [e.as_target() for e in tappable_targets(parse_hierarchy("window_dump.xml"))]
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
    for i in range(ACTIONS):
        app.action += 1
        controller.act(TARGETS[i % len(TARGETS)])
    return controller.timeline


def main():
    os.makedirs("results", exist_ok=True)

    adaptive = run(CognitiveStateModel(rng=np.random.default_rng(2026)))
    static = run(StaticStress(0.05))

    def summarise(name, timeline):
        rs = timeline.records
        calm = [r.error_px for r in rs if r.stress_s < 0.15]
        tense = [r.error_px for r in rs if r.stress_s > 0.60]
        missed = sum(1 for r in rs if not r.hit_flag)
        peak = max(r.stress_s for r in rs)
        print(f"{name:<9} {len(rs)} actions, stress peaks at {peak:.2f}, {missed} missed")
        if calm:
            print(f"          mean error when calm:       {mean(calm):6.1f} px  ({len(calm)} actions)")
        if tense:
            print(f"          mean error when frustrated: {mean(tense):6.1f} px  ({len(tense)} actions)")
            print(f"          -> {mean(tense) / mean(calm):.2f}x wider under stress")
        else:
            print("          never left the calm state")

    summarise("adaptive", adaptive)
    print()
    summarise("static", static)
    print()

    plot_timeline(adaptive, TARGETS[0], path="results/adaptive_loop_timeline.png",
                  title="Adaptive loop: app latency drives cognitive state drives input error")
    plot_comparison({"adaptive (feedback on)": adaptive,
                     "static (feedback off)": static},
                    TARGETS[0], path="results/adaptive_vs_static.png")
    print("\nwrote results/adaptive_loop_timeline.png")
    print("wrote results/adaptive_vs_static.png")
    adaptive.write_json("results/adaptive_loop_timeline.json")
    print("wrote results/adaptive_loop_timeline.json")


if __name__ == "__main__":
    main()
