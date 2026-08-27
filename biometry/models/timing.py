import random


class TimingModel:

    def __init__(self, base_time=0.3):
        self.base_time = base_time

    def generate_delay(self, stress):

        variation = 0.05 + (stress * 0.15)

        delay = random.gauss(
            self.base_time,
            variation
        )

        return max(0.05, delay) 