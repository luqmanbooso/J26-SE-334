"""The coupling term: one stress value, one alpha, every distortion module.

This is the mechanism CLAIM-01 rests on, so it is asserted directly rather than
only through its effects.
"""
import numpy as np
import pytest

from models.coupling import StressCoupling
from models.spatial import RotationalSpatialModel
from models.timing import TimingModel
from simulation.simulator import BiometricSimulator


def test_factor_is_one_at_rest():
    assert StressCoupling(alpha=2.5).factor(0.0) == 1.0


def test_factor_grows_linearly_with_stress():
    c = StressCoupling(alpha=2.0)
    assert c.factor(0.5) == pytest.approx(2.0)
    assert c.factor(1.0) == pytest.approx(3.0)


def test_sensitivity_weights_the_same_alpha():
    c = StressCoupling(alpha=2.0)
    assert c.factor(1.0, 0.5) == pytest.approx(2.0)
    assert c.factor(1.0, 2.0) == pytest.approx(5.0)


@pytest.mark.parametrize("bad", [-0.1, 1.1, 5.0])
def test_stress_outside_the_unit_interval_is_rejected(bad):
    with pytest.raises(ValueError):
        StressCoupling().factor(bad)


def test_one_instance_reaches_every_module():
    """The simulator hands the same coupling object to spatial and timing."""
    sim = BiometricSimulator(seed=1)
    assert sim.spatial_model.coupling is sim.coupling
    assert sim.timing_model.coupling is sim.coupling


def test_one_alpha_moves_spatial_and_temporal_together():
    """Raising alpha alone widens both scatter and delay spread — the coupling."""
    def spread(alpha):
        sim = BiometricSimulator(sigma_absolute=8.0, alpha=alpha, seed=4)
        rs = [sim.simulate_tap(500, 800, 160, 70, 1.0) for _ in range(4000)]
        return (np.std([r["error_distance"] for r in rs]),
                np.std([r["delay"] for r in rs]))

    low_space, low_time = spread(0.5)
    high_space, high_time = spread(4.0)
    assert high_space > low_space
    assert high_time > low_time


def test_modules_default_to_their_own_coupling_when_unwired():
    """Constructed alone, a module is still usable — it just owns the default alpha."""
    assert isinstance(RotationalSpatialModel().coupling, StressCoupling)
    assert isinstance(TimingModel().coupling, StressCoupling)
