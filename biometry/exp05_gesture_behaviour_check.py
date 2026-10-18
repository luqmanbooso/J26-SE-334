"""EXP-05 — Gesture & behaviour realism check (offline).

EXP-03 validated the tap samplers against published touch data. The gesture
synthesizer and the two new timing behaviours (hesitation gaps, rage bursts)
arrived after it, with unit tests but no distribution-level validation. This
experiment supplies that, entirely offline and seeded.

It is deliberately NOT a published-number fit: no open dataset of stressed
curved-swipe trajectories exists on disk to fit against, so claiming one would
be dishonest. Instead it checks two things that ARE checkable:

  1. STRUCTURE — the generated motion reproduces the qualitative shape human
     movement is known to have: a minimum-jerk speed profile (slow-fast-slow,
     peak mid-path) rather than the constant speed a robot would produce, and a
     path that bows off the straight chord instead of following it.

  2. STRESS MONOTONICITY — every behaviour the design says should intensify with
     stress actually does, and all of it collapses to baseline at alpha = 0.
     That last check is the coupling pillar of CLAIM-01 restated for the newest
     modules: one term moves everything, or nothing.

Writes figures and a machine-readable summary to results/exp-05/.
"""
import json
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402

from models.coupling import StressCoupling  # noqa: E402
from models.gesture import GestureDistortionSynthesizer  # noqa: E402
from models.timing import TimingModel  # noqa: E402

OUT = "results/exp-05"
PX_PER_MM = 16.0
SEED = 2026
STRESS_LEVELS = [0.05, 0.45, 0.90]          # calm, impatient, frustrated
N = 4000
# A horizontal swipe, long enough that curvature and tremor are resolvable.
X1, Y1, X2, Y2 = 200, 1000, 900, 1000


def _synth(stress, n=N, seed=SEED, alpha=2.5):
    g = GestureDistortionSynthesizer(
        px_per_mm=PX_PER_MM, coupling=StressCoupling(alpha=alpha),
        rng=np.random.default_rng(seed))
    return [g.synthesize(X1, Y1, X2, Y2, stress) for _ in range(n)]


def _chord_deviation(path):
    (sx, sy), (ex, ey) = path[0][:2], path[-1][:2]
    length = math.hypot(ex - sx, ey - sy)
    if length < 1e-9:
        return 0.0
    return max(abs((ex - sx) * (sy - y) - (sx - x) * (ey - sy)) / length
               for x, y, _ in path[1:-1])


def _speed_profile(path):
    """Per-segment speed as a fraction of path progress; for the min-jerk check."""
    speeds = []
    for a, b in zip(path, path[1:]):
        dt = (b[2] - a[2]) or 1e-9
        speeds.append(math.hypot(b[0] - a[0], b[1] - a[1]) / dt)
    return speeds


# --- A. structure: min-jerk speed profile + curvature ----------------------

def check_structure():
    runs = _synth(0.05)                      # structure is clearest when calm
    # Speed profile: average the per-segment speed across runs, normalise.
    profiles = np.array([_speed_profile(r["path"]) for r in runs])
    mean_profile = profiles.mean(axis=0)
    peak_idx = int(np.argmax(mean_profile))
    n_seg = len(mean_profile)
    peak_frac = peak_idx / (n_seg - 1)
    # Min-jerk is symmetric with the peak at the midpoint; ends are slowest.
    ends_slower_than_peak = (mean_profile[0] < mean_profile[peak_idx]
                             and mean_profile[-1] < mean_profile[peak_idx])
    # Curvature: the path must leave the chord.
    deviations = [_chord_deviation(r["path"]) for r in runs]

    return {
        "n_segments": n_seg,
        "speed_peak_fraction": round(peak_frac, 3),      # ~0.5 for min-jerk
        "speed_peak_near_middle": 0.35 <= peak_frac <= 0.65,
        "ends_slower_than_peak": bool(ends_slower_than_peak),
        "mean_chord_deviation_px": round(float(np.mean(deviations)), 2),
        "paths_bow_off_chord": float(np.mean(deviations)) > 1.0,
        "_mean_profile": [round(float(v), 4) for v in mean_profile],
    }


# --- B. stress monotonicity: gesture behaviours ----------------------------

def check_gesture_stress():
    out = {}
    dev, dur, early = {}, {}, {}
    for s in STRESS_LEVELS:
        runs = _synth(s)
        dev[s] = float(np.median([_chord_deviation(r["path"]) for r in runs]))
        full = [r for r in runs if not r["released_early"]]
        dur[s] = float(np.median([r["duration_s"] for r in full])) if full else None
        early[s] = float(np.mean([r["released_early"] for r in runs]))
    lo, hi = STRESS_LEVELS[0], STRESS_LEVELS[-1]
    return {
        "median_deviation_px": {str(s): round(dev[s], 2) for s in STRESS_LEVELS},
        "deviation_rises_with_stress": dev[hi] > dev[lo],
        "median_duration_s": {str(s): round(dur[s], 4) for s in STRESS_LEVELS},
        "duration_shortens_with_stress": dur[hi] < dur[lo],
        "early_release_rate": {str(s): round(early[s], 4) for s in STRESS_LEVELS},
        "early_release_rises_with_stress": early[hi] > early[lo],
    }


# --- C. stress monotonicity: timing behaviours -----------------------------

def check_timing_stress():
    t = TimingModel(rng=np.random.default_rng(SEED))
    hz, rage = {}, {}
    gap_len = {}
    for s in STRESS_LEVELS:
        gaps = [t.hesitation_gap(s) for _ in range(N)]
        hz[s] = float(np.mean([g > 0 for g in gaps]))
        nonzero = [g for g in gaps if g > 0]
        gap_len[s] = float(np.median(nonzero)) if nonzero else 0.0
        bursts = [t.rage_burst(s) for _ in range(N)]
        rage[s] = float(np.mean([len(b) > 0 for b in bursts]))
    base_delay = float(np.median([t.generate_delay(0.05) for _ in range(N)]))
    lo, hi = STRESS_LEVELS[0], STRESS_LEVELS[-1]
    return {
        "hesitation_rate": {str(s): round(hz[s], 4) for s in STRESS_LEVELS},
        "hesitation_rises_with_stress": hz[hi] > hz[lo],
        "median_gap_vs_base_delay": round(gap_len[hi] / base_delay, 1),
        "gap_reads_as_pause": gap_len[hi] > 2.0 * base_delay,
        "rage_rate": {str(s): round(rage[s], 4) for s in STRESS_LEVELS},
        "rage_rises_with_stress": rage[hi] > rage[lo],
    }


# --- D. coupling invariant: alpha = 0 removes all stress response -----------

def check_coupling_off():
    hi = STRESS_LEVELS[-1]
    runs0 = _synth(hi, alpha=0.0)
    runslo = _synth(STRESS_LEVELS[0], alpha=0.0)
    dev_hi = np.median([_chord_deviation(r["path"]) for r in runs0])
    dev_lo = np.median([_chord_deviation(r["path"]) for r in runslo])
    t0 = TimingModel(coupling=StressCoupling(alpha=0.0), rng=np.random.default_rng(SEED))
    hz_hi = np.mean([t0.hesitation_gap(hi) > 0 for _ in range(N)])
    hz_lo = np.mean([t0.hesitation_gap(STRESS_LEVELS[0]) > 0 for _ in range(N)])
    # With alpha=0 the factor is identically 1, so high and low stress must be
    # statistically indistinguishable (allow sampling noise).
    return {
        "deviation_ratio_hi_lo": round(float(dev_hi / dev_lo), 3),
        "hesitation_rate_hi": round(float(hz_hi), 4),
        "hesitation_rate_lo": round(float(hz_lo), 4),
        "stress_response_removed": bool(abs(dev_hi / dev_lo - 1.0) < 0.1
                                        and abs(hz_hi - hz_lo) < 0.02),
    }


def figure(structure, gesture):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    prof = structure["_mean_profile"]
    xs = np.linspace(0, 1, len(prof))
    ax1.plot(xs, prof, color="#0E7C86", linewidth=2, label="generated")
    ax1.axvline(0.5, color="#aaa", linestyle="--", linewidth=1)
    ax1.set_title("A · swipe speed profile (min-jerk = bell, peak mid-path)")
    ax1.set_xlabel("path progress"); ax1.set_ylabel("speed (px/ms)"); ax1.legend()

    levels = [float(s) for s in STRESS_LEVELS]
    dev = [gesture["median_deviation_px"][str(s)] for s in STRESS_LEVELS]
    early = [gesture["early_release_rate"][str(s)] * 100 for s in STRESS_LEVELS]
    ax2.plot(levels, dev, "o-", color="#0E7C86", label="median deviation (px)")
    ax2b = ax2.twinx()
    ax2b.plot(levels, early, "s--", color="#e8a33d", label="early release (%)")
    ax2.set_title("B · gesture distortion rises with stress")
    ax2.set_xlabel("stress $s$"); ax2.set_ylabel("deviation (px)")
    ax2b.set_ylabel("early release (%)")
    ax2.legend(loc="upper left"); ax2b.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(f"{OUT}/exp05_gesture_behaviour.png", dpi=130)


def main():
    os.makedirs(OUT, exist_ok=True)
    structure = check_structure()
    gesture = check_gesture_stress()
    timing = check_timing_stress()
    coupling = check_coupling_off()

    checks = {
        "structure.speed_peak_near_middle": structure["speed_peak_near_middle"],
        "structure.ends_slower_than_peak": structure["ends_slower_than_peak"],
        "structure.paths_bow_off_chord": structure["paths_bow_off_chord"],
        "gesture.deviation_rises_with_stress": gesture["deviation_rises_with_stress"],
        "gesture.duration_shortens_with_stress": gesture["duration_shortens_with_stress"],
        "gesture.early_release_rises_with_stress": gesture["early_release_rises_with_stress"],
        "timing.hesitation_rises_with_stress": timing["hesitation_rises_with_stress"],
        "timing.gap_reads_as_pause": timing["gap_reads_as_pause"],
        "timing.rage_rises_with_stress": timing["rage_rises_with_stress"],
        "coupling.stress_response_removed_at_alpha0": coupling["stress_response_removed"],
    }
    summary = {
        "experiment": "EXP-05 gesture & behaviour realism check",
        "seed": SEED, "n_per_level": N, "stress_levels": STRESS_LEVELS,
        "all_pass": all(checks.values()),
        "checks": checks,
        "structure": {k: v for k, v in structure.items() if not k.startswith("_")},
        "gesture": gesture, "timing": timing, "coupling": coupling,
    }
    with open(f"{OUT}/summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    figure(structure, gesture)

    print(json.dumps({"all_pass": summary["all_pass"], "checks": checks}, indent=2))
    for k, v in checks.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"\nwrote {OUT}/summary.json and {OUT}/exp05_gesture_behaviour.png")


if __name__ == "__main__":
    main()
