import math
from models.spatial import RotationalSpatialModel
from models.timing import TimingModel


class BiometricSimulator:

    def __init__(self, base_sigma=6.0, base_time=0.3):
        self.spatial_model = RotationalSpatialModel(base_sigma=base_sigma)
        self.timing_model = TimingModel(base_time=base_time)

    def simulate_tap(self, target_x, target_y, width, height, stress, prev_x=None, prev_y=None, angle=None):
        actual_x, actual_y, theta = self.spatial_model.generate_touch(
            target_x=target_x,
            target_y=target_y,
            stress=stress,
            prev_x=prev_x,
            prev_y=prev_y,
            angle=angle
        )

        delay = self.timing_model.generate_delay(stress)

        # Calculate Euclidean error distance
        error_distance = math.sqrt(
            (actual_x - target_x) ** 2 + (actual_y - target_y) ** 2
        )

        # Hit-box verification
        half_w = width / 2.0
        half_h = height / 2.0
        is_hit = (
            (target_x - half_w <= actual_x <= target_x + half_w) and
            (target_y - half_h <= actual_y <= target_y + half_h)
        )

        return {
            "target": {"x": target_x, "y": target_y, "width": width, "height": height},
            "actual": {"x": round(actual_x, 2), "y": round(actual_y, 2)},
            "approach_angle_deg": round(math.degrees(theta), 2),
            "error_distance": round(error_distance, 2),
            "is_hit": is_hit,
            "stress": stress,
            "delay": round(delay, 4),
        }