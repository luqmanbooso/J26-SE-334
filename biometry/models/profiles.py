"""Named behaviour profiles — the IF-Orchestrator-to-C2 surface.

An orchestrator does not want to reason about alphas and log-space shapes; it
wants to say "run this suite as a rushed user". A profile is a named, frozen
bundle of the engine's calibration parameters, and `build_engine` turns one
into the (simulator, cognitive) pair the controller takes.

Profiles change *parameters only*. They never add code paths, so every persona
exercises exactly the same engine and the ablation argument (one alpha, same
draws) survives persona choice.
"""
from dataclasses import dataclass

import numpy as np

from models.cognitive import CognitiveStateModel
from simulation.simulator import BiometricSimulator


@dataclass(frozen=True)
class BehaviorProfile:
    name: str
    description: str
    # Engine-wide stress gain. Zero gives the ablation arm for any persona.
    alpha: float = 2.5
    # Timing: median inter-action interval at rest (seconds).
    base_time: float = 0.30
    # Spatial: the absolute finger-imprecision floor (mm). Raised for motor
    # noise (tremor); target-size effects stay with the FFitts relative term.
    sigma_absolute_mm: float = 1.50
    # Cognitive temperament: how readily this persona escalates and settles.
    escalate_rate: float = 0.55
    settle_rate: float = 0.35


PROFILES = {
    "default": BehaviorProfile(
        name="default",
        description="The engine's published calibration, unmodified."),
    "calm": BehaviorProfile(
        name="calm",
        description="Unhurried and even-tempered: slower cadence, escalates "
                    "reluctantly, settles quickly.",
        base_time=0.40, escalate_rate=0.40, settle_rate=0.50),
    "rushed": BehaviorProfile(
        name="rushed",
        description="In a hurry and easily provoked: fast cadence, escalates "
                    "readily, settles slowly.",
        base_time=0.16, escalate_rate=0.70, settle_rate=0.25),
    "tremor": BehaviorProfile(
        name="tremor",
        description="Reduced motor precision, ordinary temperament: the "
                    "absolute imprecision floor raised, cognition untouched.",
        sigma_absolute_mm=2.40),
}


def get_profile(name):
    """Resolve a profile by name; unknown names fail loudly with the options."""
    try:
        return PROFILES[name]
    except KeyError:
        raise ValueError(
            f"unknown behaviour profile {name!r}; "
            f"available: {', '.join(sorted(PROFILES))}") from None


def build_engine(profile, seed=None, px_per_mm=16.0):
    """Instantiate the engine for a profile: (simulator, cognitive model).

    One SeedSequence spawns both generators, so a (profile, seed) pair fully
    determines a run — the same reproducibility contract the simulator makes
    on its own.
    """
    if isinstance(profile, str):
        profile = get_profile(profile)
    sim_rng, cog_rng = (np.random.default_rng(s)
                        for s in np.random.SeedSequence(seed).spawn(2))
    simulator = BiometricSimulator(
        sigma_absolute_mm=profile.sigma_absolute_mm,
        px_per_mm=px_per_mm,
        base_time=profile.base_time,
        alpha=profile.alpha,
        rng=sim_rng)
    cognitive = CognitiveStateModel(
        escalate_rate=profile.escalate_rate,
        settle_rate=profile.settle_rate,
        rng=cog_rng)
    return simulator, cognitive
