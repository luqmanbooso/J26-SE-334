import math
import random


class RotationalSpatialModel:
    """
    Implements the Rotational Dual Gaussian Touch Endpoint Distribution Model
    (Ma et al., UIST '21) conditioned on modeled cognitive stress.
    """

    def __init__(self, base_sigma=6.0, aspect_ratio=0.45):
        self.base_sigma = base_sigma
        self.aspect_ratio = aspect_ratio  # Ratio of minor axis to major axis

    def calculate_approach_angle(self, prev_x, prev_y, target_x, target_y):
        """Calculates the angle theta (in radians) of the approach vector."""
        dx = target_x - prev_x
        dy = target_y - prev_y
        if dx == 0 and dy == 0:
            return random.uniform(0, 2 * math.pi)  # Random resting drift
        return math.atan2(dy, dx)

    def generate_touch(self, target_x, target_y, stress, prev_x=None, prev_y=None, angle=None):
        """
        Generates anisotropic touch coordinates rotated along the trajectory angle.
        """
        # Determine approach angle
        if angle is not None:
            theta = angle
        elif prev_x is not None and prev_y is not None:
            theta = self.calculate_approach_angle(prev_x, prev_y, target_x, target_y)
        else:
            # Default to bottom-right thumb reach (approx. 45 degrees / pi/4 radians)
            theta = math.pi / 4.0

        # Major axis variance (movement direction) and minor axis variance (lateral)
        sigma_u = self.base_sigma * (1.0 + (stress * 2.5))
        sigma_v = (self.base_sigma * self.aspect_ratio) * (1.0 + (stress * 1.2))

        # Sample from 2D Gaussian in local coordinate frame (u, v)
        delta_u = random.gauss(0, sigma_u)
        delta_v = random.gauss(0, sigma_v)

        # Apply 2D Rotation Matrix R(theta)
        dx = delta_u * math.cos(theta) - delta_v * math.sin(theta)
        dy = delta_u * math.sin(theta) + delta_v * math.cos(theta)

        actual_x = target_x + dx
        actual_y = target_y + dy

        return actual_x, actual_y, theta