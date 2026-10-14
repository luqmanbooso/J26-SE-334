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
