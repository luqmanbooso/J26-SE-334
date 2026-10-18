"""The cognitive layer: a Markov chain over calm -> impatient -> frustrated.

Pillar 2 of the claim lives here, so the chain's structural guarantees are
asserted directly, not only its visible behaviour.
"""
import numpy as np
import pytest

from models.cognitive import (
    LADDER,
    TARGET_STRESS,
    CognitiveState,
    CognitiveStateModel,
    StaticStress,
)


def model(seed=3, **kw):
    return CognitiveStateModel(rng=np.random.default_rng(seed), **kw)


def drive(m, provocation, steps):
    return [m.update(provocation) for _ in range(steps)]


# --- behaviour under provocation -------------------------------------------

def test_sustained_provocation_reaches_frustration():
    m = model()
    drive(m, 0.9, 40)
    assert m.state is CognitiveState.FRUSTRATED


def test_removing_provocation_settles_back_to_calm():
    m = model()
    drive(m, 0.9, 40)
    drive(m, 0.0, 60)
    assert m.state is CognitiveState.CALM
    assert m.stress == pytest.approx(TARGET_STRESS[CognitiveState.CALM], abs=0.02)


def test_stress_rises_with_sustained_provocation():
    m = model()
    trace = drive(m, 0.9, 40)
    assert trace[-1] > trace[0] + 0.5


def test_a_calm_app_never_escalates():
    m = model()
    for _ in range(200):
        m.update(0.0)
        assert m.state is CognitiveState.CALM


# --- structural guarantees of the chain ------------------------------------

@pytest.mark.parametrize("provocation", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_transition_probabilities_are_a_valid_distribution(provocation):
    m = model()
    for _ in range(60):
        p_up, p_down = m.transition_probabilities(provocation)
        assert p_up >= 0 and p_down >= 0
        assert p_up + p_down <= 1.0
        m.update(provocation)


def test_the_ladder_is_never_skipped():
    """A user does not go from calm to frustrated without passing through impatience."""
    m = model()
    previous = m.rung
    for _ in range(400):
        m.update(float(np.random.default_rng(previous).random()))
        assert abs(m.rung - previous) <= 1
        previous = m.rung


def test_the_ends_of_the_ladder_are_absorbing_in_one_direction():
    m = model()
    drive(m, 1.0, 50)
    assert m.state is CognitiveState.FRUSTRATED
    assert m.transition_probabilities(1.0)[0] == 0.0  # cannot escalate past the top
    m2 = model()
    assert m2.state is CognitiveState.CALM
    assert m2.transition_probabilities(0.0)[1] == 0.0  # cannot settle below the bottom


@pytest.mark.parametrize("provocation", [0.0, 0.3, 0.7, 1.0])
def test_stress_stays_in_the_unit_interval(provocation):
    m = model()
    for s in drive(m, provocation, 300):
        assert 0.0 <= s <= 1.0


def test_stress_eases_rather_than_jumping():
    """Becoming frustrated does not make a user maximally clumsy in the same instant."""
    m = model(ease=0.25)
    before = m.stress
    m.state = CognitiveState.FRUSTRATED
    after = m.update(0.0)
    assert after < TARGET_STRESS[CognitiveState.FRUSTRATED]
    assert after > before


def test_the_run_is_reproducible_from_a_seed():
    assert drive(model(seed=8), 0.6, 80) == drive(model(seed=8), 0.6, 80)


def test_different_seeds_diverge():
    assert drive(model(seed=1), 0.6, 80) != drive(model(seed=2), 0.6, 80)


def test_ladder_matches_the_declared_stress_targets():
    assert set(LADDER) == set(TARGET_STRESS)
    assert [TARGET_STRESS[s] for s in LADDER] == sorted(TARGET_STRESS[s] for s in LADDER)


# --- the static source the ablation swaps in -------------------------------

def test_static_source_ignores_provocation():
    s = StaticStress(0.4)
    assert s.update(1.0) == 0.4
    assert s.stress == 0.4


@pytest.mark.parametrize("given,expected", [(-1.0, 0.0), (0.5, 0.5), (2.0, 1.0)])
def test_static_source_clips_to_the_unit_interval(given, expected):
    assert StaticStress(given).stress == expected
