"""Stress-conditioned gesture distortion.

A human swipe is not a straight line swept at constant speed. The finger bows
away from the chord, trembles around its own path, accelerates out of the
press and brakes into the release — and under frustration it sometimes lets
go before the gesture is finished. Each of those distortions is produced
here, and every one of them scales through the same single coupling term the
tap models use, so one alpha still moves the whole engine.

The output is a timed path — ordered (x, y, t_ms) points — which is what the
IF-C2-to-Driver contract calls an ordered motion event sequence once it has
been compiled by engine.events.
"""
import math

import numpy as np

from models.coupling import StressCoupling


def _min_jerk(tau):
    """Position fraction at time fraction tau under a minimum-jerk profile.

    The standard model of reaching movements: slow out of the press, fastest
    mid-path, slow into the release. Constant speed is the robot tell this
    removes.
    """
    return 10 * tau ** 3 - 15 * tau ** 4 + 6 * tau ** 5


class GestureDistortionSynthesizer:
    """Produces one distorted, timed swipe/drag path.

    Shares the spatial model's calibration (the absolute finger-imprecision
    floor, in mm) and the engine's single coupling and Generator, so gesture
    runs are reproducible from the same seed as tap runs.
    """

    # Relative sensitivities — weights on the one shared alpha.
    SENSITIVITY_BOW = 1.00      # how far the path bows off the chord
    SENSITIVITY_TREMOR = 0.90   # per-point shake around the bowed path
    SENSITIVITY_RELEASE = 1.00  # chance the drag is let go early
    SENSITIVITY_SPEED = 0.60    # duration shortens with haste (same weight as taps)

    BOW_SIGMA_FRACTION = 0.04       # bow spread as a fraction of chord length, at rest
    TREMOR_MM = 0.25                # per-point lateral shake at rest
    P_EARLY_RELEASE_BASE = 0.03     # chance per drag at rest
    EARLY_RELEASE_SPAN = (0.55, 0.90)  # where along the path an early release lands
    BASE_DURATION_S = 0.30          # median swipe duration at rest
    DURATION_SHAPE = 0.15           # log-space spread of the duration
    N_POINTS = 24                   # samples along the path

    def __init__(self, sigma_absolute_mm=1.50, px_per_mm=16.0,
                 coupling=None, rng=None):
        self.sigma_absolute_mm = sigma_absolute_mm
        self.px_per_mm = px_per_mm
        self.coupling = coupling if coupling is not None else StressCoupling()
        self.rng = rng if rng is not None else np.random.default_rng()

    def _endpoint(self, x, y, stress):
        """Scatter a free-space endpoint by the absolute imprecision floor.

        Swipe endpoints have no widget to aim at, so the FFitts relative term
        does not apply — only the finger's absolute floor does.
        """
        sigma = (self.sigma_absolute_mm * self.px_per_mm
                 * self.coupling.factor(stress, self.SENSITIVITY_TREMOR))
        return (x + self.rng.normal(0.0, sigma),
                y + self.rng.normal(0.0, sigma))

    def synthesize(self, x1, y1, x2, y2, stress, duration_s=None):
        """Return one distorted swipe from (x1,y1) to (x2,y2) as a timed path.

        The dict carries `path` as ordered (x, y, t_ms) tuples plus the
        distortions applied, so a timeline record can say not only where the
        finger went but which behaviours fired.
        """
        sx, sy = self._endpoint(x1, y1, stress)
        ex, ey = self._endpoint(x2, y2, stress)

        chord = math.hypot(ex - sx, ey - sy)
        if chord < 1e-9:
            raise ValueError("degenerate gesture: start and end coincide")
        ux, uy = (ex - sx) / chord, (ey - sy) / chord   # along the chord
        nx, ny = -uy, ux                                # perpendicular to it

        # One bowed control point: a quadratic Bezier whose apex is drawn from
        # a zero-mean normal, so the path curves a different way each time.
        bow = self.rng.normal(
            0.0, chord * self.BOW_SIGMA_FRACTION
            * self.coupling.factor(stress, self.SENSITIVITY_BOW))
        cx = (sx + ex) / 2.0 + nx * bow
        cy = (sy + ey) / 2.0 + ny * bow

        # Early release truncates the parameter range before sampling.
        p_release = min(1.0, self.P_EARLY_RELEASE_BASE
                        * self.coupling.factor(stress, self.SENSITIVITY_RELEASE))
        released_early = bool(self.rng.random() < p_release)
        lo, hi = self.EARLY_RELEASE_SPAN
        release_fraction = float(self.rng.uniform(lo, hi)) if released_early else 1.0

        if duration_s is None:
            median = (self.BASE_DURATION_S
                      / self.coupling.factor(stress, self.SENSITIVITY_SPEED))
            duration_s = float(self.rng.lognormal(
                mean=math.log(median), sigma=self.DURATION_SHAPE))
        duration_s *= release_fraction  # a cut-short drag also ends sooner

        tremor_px = (self.TREMOR_MM * self.px_per_mm
                     * self.coupling.factor(stress, self.SENSITIVITY_TREMOR))

        path = []
        for i in range(self.N_POINTS):
            tau = i / (self.N_POINTS - 1)
            s = _min_jerk(tau) * release_fraction
            # Quadratic Bezier point at parameter s.
            px = (1 - s) ** 2 * sx + 2 * (1 - s) * s * cx + s ** 2 * ex
            py = (1 - s) ** 2 * sy + 2 * (1 - s) * s * cy + s ** 2 * ey
            # Tremor shakes every interior point laterally; the press point is
            # where the finger actually landed, so it stays put.
            if 0 < i < self.N_POINTS - 1:
                shake = self.rng.normal(0.0, tremor_px)
                px += nx * shake
                py += ny * shake
            path.append((round(px, 2), round(py, 2), round(tau * duration_s * 1000.0, 2)))

        return {
            "path": path,
            "start": (round(sx, 2), round(sy, 2)),
            "end": path[-1][:2],
            "intended_end": (x2, y2),
            "duration_s": round(duration_s, 4),
            "released_early": released_early,
            "release_fraction": round(release_fraction, 4),
            "bow_px": round(bow, 2),
            "stress": stress,
        }
