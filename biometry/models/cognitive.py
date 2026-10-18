"""The cognitive layer: a small Markov state machine that turns evidence of bad
app behaviour into a stress value.

Deliberately a three-state chain with inspectable parameters rather than a
learned policy. A testing tool has to be explainable — when the engine produces
a mis-tap, we need to be able to say which state it was in and why it got there.
"""
import enum

import numpy as np


class CognitiveState(enum.Enum):
    CALM = "calm"
    IMPATIENT = "impatient"
    FRUSTRATED = "frustrated"


# Ordered escalation ladder. Transitions move one rung at a time: a user does
# not go from calm to frustrated without passing through impatience.
LADDER = [CognitiveState.CALM, CognitiveState.IMPATIENT, CognitiveState.FRUSTRATED]

# Stress each state settles towards. Placeholders pending calibration.
TARGET_STRESS = {
    CognitiveState.CALM: 0.05,
    CognitiveState.IMPATIENT: 0.45,
    CognitiveState.FRUSTRATED: 0.90,
}


class StaticStress:
    """A fixed stress level. The non-adaptive source used by the ablation's
    noise-only and static-stress variants, and by the batch experiments."""

    def __init__(self, stress=0.0):
        self.stress = float(np.clip(stress, 0.0, 1.0))
        self.state = None

    def update(self, provocation, dt=1.0):  # noqa: ARG002 - interface parity
        return self.stress


class CognitiveStateModel:
    """
    Markov chain over calm -> impatient -> frustrated, driven by provocation.

    `provocation` in [0,1] summarises how badly the app just behaved — slow
    response, no response, an error. Each update draws one transition: the
    chance of escalating rises with provocation, and the chance of settling
    rises as provocation falls, so the state decays back towards calm once the
    app recovers.

    The emitted stress does not jump when the state does. It eases towards the
    new state's target, because a user who becomes frustrated does not become
    maximally clumsy in the same instant. That easing is what makes the stress
    timeline readable as a curve rather than a staircase.
    """

    def __init__(self, escalate_rate=0.55, settle_rate=0.35, ease=0.25, rng=None):
        # escalate_rate: transition chance at full provocation.
        # settle_rate:   transition chance at zero provocation.
        # ease:          fraction of the gap to the target closed per update.
        self.escalate_rate = escalate_rate
        self.settle_rate = settle_rate
        self.ease = ease
        self.rng = rng if rng is not None else np.random.default_rng()
        self.state = CognitiveState.CALM
        self.stress = TARGET_STRESS[CognitiveState.CALM]

    @property
    def rung(self):
        return LADDER.index(self.state)

    def transition_probabilities(self, provocation):
        """(p_escalate, p_settle) for this provocation, clipped at the ladder ends."""
        provocation = float(np.clip(provocation, 0.0, 1.0))
        p_up = self.escalate_rate * provocation
        p_down = self.settle_rate * (1.0 - provocation)
        if self.rung == len(LADDER) - 1:
            p_up = 0.0
        if self.rung == 0:
            p_down = 0.0
        return p_up, p_down

    def update(self, provocation, dt=1.0):
        """Advance one step and return the current stress."""
        p_up, p_down = self.transition_probabilities(provocation)
        draw = self.rng.random()
        if draw < p_up:
            self.state = LADDER[self.rung + 1]
        elif draw < p_up + p_down:
            self.state = LADDER[self.rung - 1]

        target = TARGET_STRESS[self.state]
        self.stress += (target - self.stress) * min(1.0, self.ease * dt)
        self.stress = float(np.clip(self.stress, 0.0, 1.0))
        return self.stress
