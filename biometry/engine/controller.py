"""The adaptive loop.

This is the component that makes the engine adaptive rather than merely noisy.
Existing tools choose *which* action to perform based on feedback; none changes
*how* the action is physically performed in response to how the app is behaving.
That is the gap this closes.

One action is: read the current stress, distort the touch by it, dispatch it,
measure how the app reacted, convert that into provocation, and feed it back
into the cognitive chain. The next action is therefore shaped by what the app
just did.
"""
import json
import time
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ActionRecord:
    """One action and the app's reaction to it.

    Field names follow the IF-C2-to-Store contract so the timeline can be
    persisted without translation.
    """

    t_ms: float
    target_element_id: str
    x: float
    y: float
    hit_flag: bool
    error_px: float
    delay_s: float
    stress_s: float
    cognitive_state: str
    ui_delay_ms: float
    responded: bool
    provocation: float


@dataclass
class StressTimeline:
    """The run's record: what was done, what state it was done in, what came back."""

    run_id: str
    persona_id: str = "default"
    records: list = field(default_factory=list)

    def append(self, record):
        self.records.append(record)

    def to_dict(self):
        return {
            "run_id": self.run_id,
            "persona_id": self.persona_id,
            "records": [asdict(r) for r in self.records],
        }

    def write_json(self, path):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
        return path


class AdaptiveFeedbackController:
    """
    Runs the closed loop over a sequence of targets.

    `dispatch(x, y, pre_delay)` performs the touch — an ADB bridge in
    production, a recording stub in tests. `probe` measures the reaction;
    `cognitive` converts it into the next stress value. Swapping `cognitive`
    for StaticStress turns the whole thing back into an open-loop noise
    generator, which is exactly the ablation.
    """

    def __init__(self, simulator, cognitive, probe, dispatch,
                 clock=time.monotonic, run_id="run", persona_id="default"):
        self.simulator = simulator
        self.cognitive = cognitive
        self.probe = probe
        self.dispatch = dispatch
        self.clock = clock
        self.timeline = StressTimeline(run_id=run_id, persona_id=persona_id)
        self._started = None
        self._previous_point = None

    def act(self, target):
        """Perform one action against `target` and fold the app's reaction back in."""
        if self._started is None:
            self._started = self.clock()

        stress = self.cognitive.stress
        prev_x, prev_y = self._previous_point or (None, None)
        tap = self.simulator.simulate_tap(
            target["x"], target["y"], target["width"], target["height"],
            stress, prev_x=prev_x, prev_y=prev_y,
        )

        before = self.probe.read_signature()
        self.dispatch(tap["actual"]["x"], tap["actual"]["y"], tap["delay"])
        observation = self.probe.observe(before=before)
        provocation = self.probe.provocation(observation)

        state_before = getattr(self.cognitive, "state", None)
        self.cognitive.update(provocation)

        record = ActionRecord(
            t_ms=(self.clock() - self._started) * 1000.0,
            target_element_id=target.get("id", ""),
            x=tap["actual"]["x"],
            y=tap["actual"]["y"],
            hit_flag=tap["is_hit"],
            error_px=tap["error_distance"],
            delay_s=tap["delay"],
            stress_s=stress,
            cognitive_state=state_before.value if state_before is not None else "static",
            ui_delay_ms=observation.ui_delay_ms,
            responded=observation.changed,
            provocation=provocation,
        )
        self.timeline.append(record)
        self._previous_point = (tap["actual"]["x"], tap["actual"]["y"])
        return record

    def run(self, targets):
        """Perform one action per target in order; return the timeline."""
        for target in targets:
            self.act(target)
        return self.timeline
