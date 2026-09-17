import numpy as np

from models.coupling import StressCoupling


class TimingModel:
    """Inter-action delay sampling, widening with modelled stress."""

    # Relative sensitivity of timing variability to stress — a weight on the
    # single shared alpha held by StressCoupling, not a separate stress response.
    SENSITIVITY = 1.20

    def __init__(self, base_time=0.3, base_variation=0.05, coupling=None, rng=None):
        self.base_time = base_time
        self.base_variation = base_variation
        self.coupling = coupling if coupling is not None else StressCoupling()
        self.rng = rng if rng is not None else np.random.default_rng()

    def generate_delay(self, stress):
        """Return one pre-action delay in seconds, floored at 50 ms."""
        variation = self.base_variation * self.coupling.factor(stress, self.SENSITIVITY)
        delay = self.rng.normal(self.base_time, variation)
        return max(0.05, delay)
