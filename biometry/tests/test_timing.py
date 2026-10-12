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


# --- hesitation gaps ---------------------------------------------------------

def gaps(stress, n=20000, seed=7):
    t = TimingModel(rng=np.random.default_rng(seed))
    return np.array([t.hesitation_gap(stress) for _ in range(n)])


def test_most_actions_have_no_hesitation():
    g = gaps(0.0)
    assert (g == 0.0).mean() > 0.9


def test_hesitation_probability_rises_with_stress():
    assert (gaps(0.9) > 0).mean() > 1.5 * (gaps(0.0) > 0).mean()


def test_a_hesitation_reads_as_a_pause_not_a_slow_action():
    """The gap median sits well above the resting delay median."""
    g = gaps(0.9)
    assert np.median(g[g > 0]) > 2.0 * np.median(delays(0.0))


# --- rage bursts -------------------------------------------------------------

def bursts(stress, n=20000, seed=7):
    t = TimingModel(rng=np.random.default_rng(seed))
    return [t.rage_burst(stress) for _ in range(n)]


def test_rage_bursts_are_rare_at_rest():
    b = bursts(0.0)
    assert np.mean([len(x) > 0 for x in b]) < 0.05


def test_rage_burst_probability_rises_with_stress():
    calm = np.mean([len(x) > 0 for x in bursts(0.0)])
    frustrated = np.mean([len(x) > 0 for x in bursts(0.9)])
    assert frustrated > 2.0 * calm


def test_burst_gaps_read_as_pounding():
    """Inside a burst the taps are fast — but never below the coalescing floor."""
    for b in bursts(1.0):
        for gap in b:
            lo, hi = TimingModel.RAGE_GAP_S
            assert lo <= gap <= hi


def test_bursts_are_bounded():
    assert max(len(b) for b in bursts(1.0)) <= TimingModel.RAGE_MAX_EXTRA
