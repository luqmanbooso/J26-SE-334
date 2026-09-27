"""Statistical properties of the spatial sampler.

These assert distribution shape over many samples rather than exact values, so
they describe the model rather than a particular random draw. Every test seeds
its own generator, so failures are reproducible.
"""
import math

import numpy as np
import pytest

from models.coupling import StressCoupling
from models.spatial import RotationalSpatialModel


def sample(model, n, width=160, height=70, stress=0.0, angle=0.0):
    """Return offsets from the target centre as (du_along, dv_across) in the angle frame."""
    out = []
    for _ in range(n):
        x, y, _ = model.generate_touch(500.0, 800.0, width, height, stress, angle=angle)
        dx, dy = x - 500.0, y - 800.0
        out.append((dx * math.cos(angle) + dy * math.sin(angle),
                    -dx * math.sin(angle) + dy * math.cos(angle)))
    return out


def model(seed=1, **kw):
    return RotationalSpatialModel(rng=np.random.default_rng(seed), **kw)


# --- FFitts variance decomposition -----------------------------------------

def test_spread_grows_with_target_size():
    """The relative term scales with the target, so a bigger target is aimed at less carefully."""
    m = model()
    sizes = [(40, 18), (100, 44), (160, 70), (320, 140)]
    spreads = [m.base_sigma(w, h) for w, h in sizes]
    assert spreads == sorted(spreads), spreads
    assert spreads[-1] > 2 * spreads[0]


def test_absolute_floor_survives_a_vanishing_target():
    """Spread never falls below the finger-imprecision floor, however small the target."""
    m = model(sigma_absolute=4.0)
    assert m.base_sigma(1, 1) >= 4.0
    assert m.base_sigma(0, 0) == pytest.approx(4.0)


def test_small_targets_are_effectively_smaller():
    """Miss rate rises as the target shrinks, because the floor does not shrink with it."""
    m = model(seed=3)
    def miss_rate(w, h):
        misses = 0
        for _ in range(4000):
            x, y, _ = m.generate_touch(500.0, 800.0, w, h, 0.0, angle=0.0)
            if abs(x - 500.0) > w / 2 or abs(y - 800.0) > h / 2:
                misses += 1
        return misses / 4000
    assert miss_rate(30, 14) > miss_rate(160, 70)


# --- rotational dual-Gaussian shape ----------------------------------------

def test_scatter_elongates_along_the_approach_direction():
    """Variance along the direction of travel exceeds variance across it."""
    pts = sample(model(seed=5), 6000, stress=0.5, angle=0.0)
    along = np.var([p[0] for p in pts])
    across = np.var([p[1] for p in pts])
    assert along > 2 * across, (along, across)


@pytest.mark.parametrize("deg", [0, 30, 45, 90, 135])
def test_ellipse_major_axis_tracks_the_approach_angle(deg):
    """The scatter ellipse rotates with theta rather than staying screen-aligned."""
    theta = math.radians(deg)
    m = model(seed=7)
    xs, ys = [], []
    for _ in range(6000):
        x, y, _ = m.generate_touch(500.0, 800.0, 160, 70, 0.6, angle=theta)
        xs.append(x - 500.0); ys.append(y - 800.0)
    cov = np.cov(np.vstack([xs, ys]))
    principal = np.linalg.eigh(cov)[1][:, -1]          # eigenvector of the largest eigenvalue
    measured = math.atan2(principal[1], principal[0]) % math.pi
    assert abs(measured - (theta % math.pi)) < math.radians(8)


def test_returned_angle_is_the_requested_angle():
    _, _, theta = model().generate_touch(500.0, 800.0, 160, 70, 0.0, angle=1.1)
    assert theta == pytest.approx(1.1)


def test_approach_angle_is_inferred_from_the_previous_point():
    m = model()
    _, _, theta = m.generate_touch(600.0, 800.0, 160, 70, 0.0, prev_x=500.0, prev_y=800.0)
    assert theta == pytest.approx(0.0, abs=1e-9)  # due east


# --- stress response --------------------------------------------------------

def test_stress_widens_the_scatter():
    calm = np.std([p[0] for p in sample(model(seed=9), 5000, stress=0.0)])
    tense = np.std([p[0] for p in sample(model(seed=9), 5000, stress=1.0)])
    assert tense > 2 * calm, (calm, tense)


def test_alpha_zero_removes_the_stress_response():
    """With the coupling disabled, stress changes nothing — the ablation's noise-only variant."""
    flat = StressCoupling(alpha=0.0)
    calm = np.std([p[0] for p in sample(model(seed=13, coupling=flat), 5000, stress=0.0)])
    tense = np.std([p[0] for p in sample(model(seed=13, coupling=flat), 5000, stress=1.0)])
    assert tense == pytest.approx(calm, rel=0.05)
