import numpy as np


class TimingModel:
    """Inter-action delay sampling, widening with modelled stress."""

    def __init__(self, base_time=0.3, rng=None):
        self.base_time = base_time
        self.rng = rng if rng is not None else np.random.default_rng()

    def generate_delay(self, stress):
        """Return one pre-action delay in seconds, floored at 50 ms."""
        variation = 0.05 + (stress * 0.15)
        delay = self.rng.normal(self.base_time, variation)
        return max(0.05, delay)
