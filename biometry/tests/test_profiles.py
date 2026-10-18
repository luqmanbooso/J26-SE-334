"""Behaviour profiles: parameters only, same engine, reproducible from (profile, seed)."""
import numpy as np
import pytest

from models.cognitive import CognitiveStateModel
from models.profiles import PROFILES, build_engine, get_profile
from simulation.simulator import BiometricSimulator


def test_the_required_personas_exist():
    for name in ("calm", "rushed", "tremor", "default"):
        assert name in PROFILES


def test_unknown_profile_fails_loudly_with_the_options():
    with pytest.raises(ValueError, match="calm"):
        get_profile("sleepy")


def test_build_returns_the_engine_pair():
    sim, cog = build_engine("default", seed=1)
    assert isinstance(sim, BiometricSimulator)
    assert isinstance(cog, CognitiveStateModel)


def test_rushed_acts_faster_than_calm():
    fast, _ = build_engine("rushed", seed=5)
    slow, _ = build_engine("calm", seed=5)
    f = np.median([fast.timing_model.generate_delay(0.0) for _ in range(5000)])
    s = np.median([slow.timing_model.generate_delay(0.0) for _ in range(5000)])
    assert f < 0.6 * s


def test_tremor_raises_the_absolute_floor_only():
    trem, _ = build_engine("tremor", seed=5)
    base, _ = build_engine("default", seed=5)
    assert trem.spatial_model.sigma_absolute_mm > base.spatial_model.sigma_absolute_mm
    assert trem.timing_model.base_time == base.timing_model.base_time


def test_temperament_reaches_the_cognitive_model():
    _, rushed = build_engine("rushed", seed=5)
    _, calm = build_engine("calm", seed=5)
    assert rushed.escalate_rate > calm.escalate_rate
    assert rushed.settle_rate < calm.settle_rate


def test_same_profile_and_seed_reproduce_the_run():
    a, _ = build_engine("rushed", seed=42)
    b, _ = build_engine("rushed", seed=42)
    ta = a.simulate_tap(100, 100, 48, 48, 0.5)
    tb = b.simulate_tap(100, 100, 48, 48, 0.5)
    assert ta == tb
    sa = a.simulate_swipe(100, 800, 900, 800, 0.5)
    sb = b.simulate_swipe(100, 800, 900, 800, 0.5)
    assert sa == sb


def test_profiles_never_add_code_paths():
    """A persona is a parameter bundle; zero alpha must still give the ablation."""
    from dataclasses import replace
    sim, _ = build_engine(replace(get_profile("rushed"), alpha=0.0), seed=3)
    assert sim.coupling.factor(1.0) == 1.0
