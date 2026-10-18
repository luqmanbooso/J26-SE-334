import math

import numpy as np

from models.coupling import StressCoupling


class TimingModel:
    """
    Inter-action delay sampling.

    Human inter-action intervals are not symmetric around a mean: most are
    short and clustered, with a long right tail from hesitation and attention
    lapses. A Gaussian cannot represent that, and can also return negative
    values. Delays are therefore drawn from a log-normal, which is positive by
    construction and right-skewed at every stress level.

    Stress does two separate things to timing, and both route through the one
    shared coupling term: the median interval shortens, because a hurried user
    acts sooner, and the spread widens, because a hurried user is less
    consistent. The right tail survives both, so occasional long pauses still
    appear under stress.
    """

    # Relative sensitivities — weights on the single shared alpha, not separate
    # stress responses.
    SENSITIVITY_SPREAD = 1.20  # variability grows with stress
    SENSITIVITY_HASTE = 0.60   # median interval shortens under urgency

    MIN_DELAY = 0.05  # seconds; below this the device coalesces events

    # Hesitation: an occasional long pause before acting — attention lapse,
    # re-reading the screen, second-guessing. Its probability rises with
    # stress through the shared coupling; its length is a multiple of the
    # resting median so it reads as a pause, not a slow action.
    SENSITIVITY_HESITATE = 0.80
    P_HESITATE_BASE = 0.04      # chance per action at rest
    HESITATE_SCALE = 5.0        # median gap = HESITATE_SCALE * base_time
    HESITATE_SHAPE = 0.50       # spread of the gap in log space

    # Rage burst: the frustrated repeat-tap — the same point hit again in
    # quick succession. Rare at rest, and the probability (not the taps
    # themselves) is what stress scales.
    SENSITIVITY_RAGE = 1.00
    P_RAGE_BASE = 0.03          # chance per action at rest
    RAGE_CONTINUE = 0.45        # chance each extra tap is followed by another
    RAGE_MAX_EXTRA = 5          # ceiling on extra taps in one burst
    RAGE_GAP_S = (0.08, 0.16)   # uniform inter-tap gap inside a burst

    def __init__(self, base_time=0.3, shape=0.18, coupling=None, rng=None):
        # base_time: median interval at rest, in seconds.
        # shape: spread of the underlying normal in log space at rest, roughly
        #        the coefficient of variation of the delay. Placeholder pending
        #        calibration in EXP-03.
        self.base_time = base_time
        self.shape = shape
        self.coupling = coupling if coupling is not None else StressCoupling()
        self.rng = rng if rng is not None else np.random.default_rng()

    def generate_delay(self, stress):
        """Return one pre-action delay in seconds, floored at MIN_DELAY."""
        median = self.base_time / self.coupling.factor(stress, self.SENSITIVITY_HASTE)
        sigma_log = self.shape * self.coupling.factor(stress, self.SENSITIVITY_SPREAD)
        delay = self.rng.lognormal(mean=math.log(median), sigma=sigma_log)
        return max(self.MIN_DELAY, delay)

    def hesitation_gap(self, stress):
        """Return an extra pause in seconds, or 0.0 — most actions have none.

        Both the chance of hesitating and (mildly) the resulting gap rise with
        stress, so a frustrated run shows more long stalls, not merely faster
        clicking. This is what keeps haste and hesitation coexisting at high
        stress rather than the distribution simply shifting left.
        """
        p = min(1.0, self.P_HESITATE_BASE
                * self.coupling.factor(stress, self.SENSITIVITY_HESITATE))
        if self.rng.random() >= p:
            return 0.0
        median = self.base_time * self.HESITATE_SCALE
        return self.rng.lognormal(mean=math.log(median), sigma=self.HESITATE_SHAPE)

    def rage_burst(self, stress):
        """Return gaps (seconds) for the extra taps of a rage burst; usually [].

        An empty list means no burst. A non-empty list of length n means the
        action is repeated n more times at the same target, separated by the
        returned gaps — short enough to read as pounding, long enough that the
        device does not coalesce them.
        """
        p = min(1.0, self.P_RAGE_BASE
                * self.coupling.factor(stress, self.SENSITIVITY_RAGE))
        if self.rng.random() >= p:
            return []
        gaps = []
        lo, hi = self.RAGE_GAP_S
        while len(gaps) < self.RAGE_MAX_EXTRA:
            gaps.append(float(self.rng.uniform(lo, hi)))
            if self.rng.random() >= self.RAGE_CONTINUE:
                break
        return gaps
