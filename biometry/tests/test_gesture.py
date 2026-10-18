"""Gesture distortion: the swipe bows, shakes, hurries and sometimes lets go."""
import math

import numpy as np
import pytest

from models.gesture import GestureDistortionSynthesizer


def synth(seed=3, **kw):
    return GestureDistortionSynthesizer(rng=np.random.default_rng(seed), **kw)


def swipes(stress, n=400, seed=3, **kw):
    g = synth(seed, **kw)
    return [g.synthesize(100, 800, 900, 800, stress) for _ in range(n)]


def test_path_starts_at_the_press_and_ends_at_the_release():
    r = synth().synthesize(100, 800, 900, 800, 0.2)
    assert r["path"][0][:2] == r["start"]
    assert r["path"][-1][:2] == r["end"]


def test_timestamps_are_strictly_increasing_from_zero():
    r = synth().synthesize(100, 800, 900, 800, 0.5)
    times = [t for _, _, t in r["path"]]
    assert times[0] == 0.0
    assert all(b > a for a, b in zip(times, times[1:]))


def test_the_path_is_not_a_straight_line():
    """A ruler-straight swipe is the robot tell; the bow and tremor remove it."""
    r = synth().synthesize(100, 800, 900, 800, 0.5)
    ys = [y for _, y, _ in r["path"]]
    assert max(ys) - min(ys) > 1.0


def test_deviation_from_the_chord_grows_with_stress():
    def worst_deviation(runs):
        out = []
        for r in runs:
            (sx, sy), (ex, ey) = r["path"][0][:2], r["path"][-1][:2]
            length = math.hypot(ex - sx, ey - sy)
            out.append(max(
                abs((ex - sx) * (sy - y) - (sx - x) * (ey - sy)) / length
                for x, y, _ in r["path"][1:-1]))
        return np.median(out)
    assert worst_deviation(swipes(1.0)) > 1.3 * worst_deviation(swipes(0.0))


def test_early_release_is_rare_at_rest_and_rises_with_stress():
    rate = lambda runs: np.mean([r["released_early"] for r in runs])
    assert rate(swipes(0.0, n=2000)) < 0.08
    assert rate(swipes(1.0, n=2000)) > 2.0 * rate(swipes(0.0, n=2000))


def test_an_early_release_stops_short_of_the_target():
    g = synth(seed=1)
    released = [r for _ in range(2000)
                for r in [g.synthesize(100, 800, 900, 800, 1.0)]
                if r["released_early"]]
    assert released, "no early release in 2000 frustrated drags"
    for r in released:
        ex, ey = r["end"]
        ix, iy = r["intended_end"]
        # Stops short along the direction of travel, beyond endpoint scatter.
        assert r["release_fraction"] < 0.95
        assert math.hypot(ex - ix, ey - iy) > 0


def test_stress_shortens_the_swipe():
    dur = lambda runs: np.median([r["duration_s"] for r in runs])
    full = [r for r in swipes(1.0, n=2000) if not r["released_early"]]
    calm = [r for r in swipes(0.0, n=2000) if not r["released_early"]]
    assert dur(full) < dur(calm)


def test_min_jerk_profile_moves_slowest_at_the_ends():
    """Equal time steps cover less ground near press and release than mid-path."""
    r = synth().synthesize(100, 800, 900, 800, 0.0)
    pts = r["path"]
    step = lambda i: math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
    mid = len(pts) // 2
    assert step(0) < step(mid)
    assert step(len(pts) - 2) < step(mid)


def test_same_seed_same_gesture():
    a = synth(seed=9).synthesize(100, 800, 900, 800, 0.7)
    b = synth(seed=9).synthesize(100, 800, 900, 800, 0.7)
    assert a == b


def test_degenerate_gesture_is_rejected():
    g = GestureDistortionSynthesizer(
        sigma_absolute_mm=0.0, rng=np.random.default_rng(0))
    with pytest.raises(ValueError):
        g.synthesize(5, 5, 5, 5, 0.0)
