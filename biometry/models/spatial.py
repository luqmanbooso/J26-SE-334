import math

import numpy as np


class RotationalSpatialModel:
    """
    Rotational Dual Gaussian touch endpoint model, conditioned on modelled
    cognitive stress.

    Touch offsets are sampled in the frame of the approach vector: one axis
    along the direction of movement (u) and one lateral to it (v), with a
    larger spread along u. The pair is then rotated by the approach angle so
    the resulting scatter ellipse points the way the finger was travelling.
    """

    def __init__(self, base_sigma=6.0, aspect_ratio=0.45, rng=None):
        self.base_sigma = base_sigma
        self.aspect_ratio = aspect_ratio  # minor axis as a fraction of the major
        self.rng = rng if rng is not None else np.random.default_rng()

    def calculate_approach_angle(self, prev_x, prev_y, target_x, target_y):
        """Angle theta (radians) of the vector from the previous touch to the target."""
        dx = target_x - prev_x
        dy = target_y - prev_y
        if dx == 0 and dy == 0:
            return self.rng.uniform(0, 2 * math.pi)  # resting drift, no direction
        return math.atan2(dy, dx)

    def generate_touch(self, target_x, target_y, stress, prev_x=None, prev_y=None, angle=None):
        """Return (x, y, theta) for one touch aimed at (target_x, target_y)."""
        if angle is not None:
            theta = angle
        elif prev_x is not None and prev_y is not None:
            theta = self.calculate_approach_angle(prev_x, prev_y, target_x, target_y)
        else:
            theta = math.pi / 4.0  # default bottom-right thumb reach

        sigma_u = self.base_sigma * (1.0 + (stress * 2.5))
        sigma_v = (self.base_sigma * self.aspect_ratio) * (1.0 + (stress * 1.2))

        delta_u = self.rng.normal(0.0, sigma_u)
        delta_v = self.rng.normal(0.0, sigma_v)

        # Rotate the (u, v) offset into screen coordinates by R(theta).
        dx = delta_u * math.cos(theta) - delta_v * math.sin(theta)
        dy = delta_u * math.sin(theta) + delta_v * math.cos(theta)

        return target_x + dx, target_y + dy, theta
