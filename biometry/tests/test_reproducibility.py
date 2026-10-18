"""A run must be reproducible from its seed.

The coupling ablation compares engine variants on identical random draws, so a
seeded run is not a convenience here — it is what makes the comparison sound.
"""
from simulation.simulator import BiometricSimulator


def run(seed, stress=0.5, n=40, **kw):
    sim = BiometricSimulator(seed=seed, **kw)
    return [sim.simulate_tap(500, 800, 160, 70, stress) for _ in range(n)]


def test_same_seed_reproduces_the_run():
    assert run(2026) == run(2026)


def test_different_seeds_diverge():
    assert run(1) != run(2)


def test_one_seed_drives_both_modules():
    """Positions and delays both come from the single seeded generator."""
    a, b = run(7), run(7)
    assert [r["actual"] for r in a] == [r["actual"] for r in b]
    assert [r["delay"] for r in a] == [r["delay"] for r in b]


def test_variants_share_draws_when_seeded_alike():
    """Only alpha differs, so any divergence is the coupling and not the noise."""
    noise_only = run(99, alpha=0.0)
    coupled = run(99, alpha=2.5)
    assert noise_only != coupled
    assert len(noise_only) == len(coupled)
