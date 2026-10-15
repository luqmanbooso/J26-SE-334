"""Distribution shape of the inter-action delay sampler."""
import numpy as np
import pytest
from scipy import stats

from models.coupling import StressCoupling
from models.timing import TimingModel


def delays(stress, n=20000, seed=11, **kw):
    t = TimingModel(rng=np.random.default_rng(seed), **kw)
    return np.array([t.generate_delay(stress) for _ in range(n)])


@pytest.mark.parametrize("stress", [0.0, 0.5, 1.0])
def test_delays_are_right_skewed(stress):
    """Human inter-action timing has a long right tail; a Gaussian cannot express that."""
    assert stats.skew(delays(stress)) > 0.3


def test_delays_are_never_negative():
    assert delays(1.0).min() > 0


def test_delays_respect_the_floor():
    d = delays(1.0)
    assert d.min() >= TimingModel.MIN_DELAY


def test_stress_shortens_the_median():
    """A hurried user acts sooner."""
    assert np.median(delays(1.0)) < 0.6 * np.median(delays(0.0))


def test_stress_widens_the_spread():
    """A hurried user is also less consistent."""
    assert delays(1.0).std() > 1.5 * delays(0.0).std()


def test_the_right_tail_survives_stress():
    """Hesitation does not disappear under haste: the tail stays far above the median."""
    d = delays(1.0)
    assert np.percentile(d, 95) > 2.5 * np.median(d)


def test_median_tracks_base_time_at_rest():
    assert np.median(delays(0.0, base_time=0.5)) == pytest.approx(0.5, rel=0.05)


def test_alpha_zero_removes_the_stress_response():
    flat = StressCoupling(alpha=0.0)
    calm, tense = delays(0.0, coupling=flat), delays(1.0, coupling=flat)
    assert np.median(tense) == pytest.approx(np.median(calm), rel=0.05)
    assert tense.std() == pytest.approx(calm.std(), rel=0.1)
