import math

import numpy as np

from models.coupling import StressCoupling


class RotationalSpatialModel:
    """
    Rotational Dual Gaussian touch endpoint model, conditioned on modelled
    cognitive stress.

    Touch offsets are sampled in the frame of the approach vector: one axis
    along the direction of movement (u) and one lateral to it (v), with a
    larger spread along u (Ma et al. 2021). The pair is then rotated by the
    approach angle so the scatter ellipse points the way the finger travelled.

    The spread itself follows the FFitts variance decomposition
    (Bi, Li & Zhai 2013): sigma^2_observed = sigma^2_relative + sigma^2_absolute.
    The relative term grows with the size of the target, because a forgiving
    target is aimed at less carefully. The absolute term is a fixed
    finger-imprecision floor that does not shrink with the target — which is
    why small targets are effectively smaller than their nominal bounds.

    Parameters are calibrated against that paper's published 2D results rather
    than invented. Fitting its reported sigma_relative against target width
    (EXP-03) shows the growth is sub-linear: a linear form fits at R^2 = -0.25,
    worse than a horizontal line, while k*sqrt(W) fits at R^2 = 0.94. The
    relative term is therefore sqrt in W, and sigma_absolute defaults to the
    1.50 mm the paper reports for 2D tasks.

    Lengths are handled in millimetres internally, because that is the unit the
    published data is in, and converted to pixels on the way out.
    """

    # Relative sensitivity of each axis to stress. A hurried finger scatters more
    # along the direction of travel than across it. Both are weights on the single
    # shared alpha held by StressCoupling.
    SENSITIVITY_ALONG = 1.00
    SENSITIVITY_LATERAL = 0.48

    def __init__(self, sigma_absolute_mm=1.50, relative_coeff=0.493, px_per_mm=16.0,
                 aspect_ratio=0.45, coupling=None, rng=None):
        # sigma_absolute_mm: finger-imprecision floor. 1.50 mm is the bivariate SDxy
        #   Bi et al. report for 2D finger calibration tasks (their Table 3).
        # relative_coeff:    k in sigma_relative = k * sqrt(W_mm), fitted to the same
        #   table in EXP-03 (k = 0.493, R^2 = 0.94).
        # px_per_mm:         device scale. 16.0 approximates a ~400 ppi phone and
        #   MUST be set per device for the calibration to mean anything.
        self.sigma_absolute_mm = sigma_absolute_mm
        self.relative_coeff = relative_coeff
        self.px_per_mm = px_per_mm
        self.aspect_ratio = aspect_ratio  # minor axis as a fraction of the major
        # Keeps SDxy equal to sigma_base for this aspect ratio (see generate_touch).
        self.ANISOTROPY_NORM = math.sqrt(2.0 / (1.0 + aspect_ratio ** 2))
        self.coupling = coupling if coupling is not None else StressCoupling()
        self.rng = rng if rng is not None else np.random.default_rng()

    def base_sigma(self, width, height):
        """Spread in pixels before stress, from the FFitts decomposition."""
        width_mm = min(width, height) / self.px_per_mm  # the dimension deciding a hit
        sigma_relative_mm = self.relative_coeff * math.sqrt(width_mm)
        sigma_mm = math.hypot(sigma_relative_mm, self.sigma_absolute_mm)
        return sigma_mm * self.px_per_mm

    def calculate_approach_angle(self, prev_x, prev_y, target_x, target_y):
        """Angle theta (radians) of the vector from the previous touch to the target."""
        dx = target_x - prev_x
        dy = target_y - prev_y
        if dx == 0 and dy == 0:
            return self.rng.uniform(0, 2 * math.pi)  # resting drift, no direction
        return math.atan2(dy, dx)

    def generate_touch(self, target_x, target_y, width, height, stress,
                       prev_x=None, prev_y=None, angle=None):
        """Return (x, y, theta) for one touch aimed at (target_x, target_y)."""
        if angle is not None:
            theta = angle
        elif prev_x is not None and prev_y is not None:
            theta = self.calculate_approach_angle(prev_x, prev_y, target_x, target_y)
        else:
            theta = math.pi / 4.0  # default bottom-right thumb reach

        sigma_base = self.base_sigma(width, height)
        # Split sigma_base across the two axes so that the resulting bivariate
        # deviation SDxy = sqrt((sigma_u^2 + sigma_v^2)/2) equals sigma_base.
        # Without this the anisotropy quietly shrinks the delivered spread below
        # the calibrated value — it measured 22.8% low before EXP-03 caught it.
        sigma_u = sigma_base * self.ANISOTROPY_NORM * self.coupling.factor(
            stress, self.SENSITIVITY_ALONG)
        sigma_v = (sigma_base * self.ANISOTROPY_NORM * self.aspect_ratio) * self.coupling.factor(
            stress, self.SENSITIVITY_LATERAL)

        delta_u = self.rng.normal(0.0, sigma_u)
        delta_v = self.rng.normal(0.0, sigma_v)

        # Rotate the (u, v) offset into screen coordinates by R(theta).
        dx = delta_u * math.cos(theta) - delta_v * math.sin(theta)
        dy = delta_u * math.sin(theta) + delta_v * math.cos(theta)

        return target_x + dx, target_y + dy, theta
