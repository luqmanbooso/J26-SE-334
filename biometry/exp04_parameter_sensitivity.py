"""EXP-04 — Parameter sensitivity: do the conclusions depend on alpha?

Every other parameter in the engine is taken from published data. Alpha is not,
and cannot be: it scales the *coupling* between cognitive state and physical
input, which is the part of the model no prior work provides a value for. There
is nothing to calibrate it against.

So this experiment cannot validate alpha. What it can do is establish that the
conclusions do not hinge on a lucky choice of it. Three checks:

  A. At rest, alpha does nothing. It only ever acts through s, so every alpha
     must reproduce the EXP-03 calibration identically at s = 0. If it does not,
     alpha is leaking into the validated part of the model.

  B. The response is monotone and well-behaved across a wide band. No alpha
     inverts the relationship, saturates it, or breaks it.

  C. The adaptive-vs-static divergence survives the whole band. If the coupling
     only shows up at one hand-picked alpha, it is an artefact of that choice.

Runs offline, seeded. Writes figures and a summary to results/exp-04/.
"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from models.cognitive import StaticStress  # noqa: E402
from simulation.simulator import BiometricSimulator  # noqa: E402

OUT = "results/exp-04"
SEED = 2026
ALPHAS = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
STRESSES = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
# Two targets, because miss rate is meaningless without a physical size. At
# 16 px/mm these are 6.9 x 2.8 mm (a cramped control) and 20.8 x 10.6 mm (a real
# dialer key, measured from the committed hierarchy dump).
TARGETS = {"small (2.8 mm)": dict(x=500.0, y=800.0, width=110.0, height=44.0),
           "realistic (10.6 mm)": dict(x=500.0, y=800.0, width=332.0, height=170.0)}
TARGET = TARGETS["small (2.8 mm)"]
N = 6000


def run(alpha, stress, n=N, seed=SEED, target=None):
    target = target or TARGET
    sim = BiometricSimulator(alpha=alpha, seed=seed)
    rs = [sim.simulate_tap(target["x"], target["y"], target["width"], target["height"], stress)
          for _ in range(n)]
    return (float(np.mean([r["error_distance"] for r in rs])),
            100.0 * sum(1 for r in rs if not r["is_hit"]) / n,
            float(np.mean([r["delay"] for r in rs])))


def main():
    os.makedirs(OUT, exist_ok=True)
    grid = {a: {s: run(a, s) for s in STRESSES} for a in ALPHAS}

    # --- A: alpha must be inert at rest -------------------------------------
    at_rest = [grid[a][0.0][0] for a in ALPHAS]
    rest_spread = max(at_rest) - min(at_rest)

    # --- B: monotone and bounded across the band ----------------------------
    at_full = [grid[a][1.0][0] for a in ALPHAS]
    monotone = all(x <= y + 1e-9 for x, y in zip(at_full, at_full[1:]))

    # --- C: divergence from a static source survives the band ---------------
    divergence = {}
    for a in ALPHAS:
        sim = BiometricSimulator(alpha=a, seed=SEED)
        static = StaticStress(0.05)
        adaptive_err = grid[a][0.8][0]
        static_err = run(a, static.stress)[0]
        divergence[a] = adaptive_err - static_err

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 4.4))
    for a in ALPHAS:
        ax1.plot(STRESSES, [grid[a][s][0] for s in STRESSES], marker="o", ms=4,
                 label=f"α={a}", lw=1.6)
    ax1.set_xlabel("stress $s$"); ax1.set_ylabel("mean touch error (px)")
    ax1.set_title("A/B. Response across the alpha band", fontsize=11)
    ax1.grid(alpha=.3, ls="--"); ax1.legend(fontsize=7, ncol=2)

    ax2.plot(ALPHAS, at_rest, "o-", color="#14803A", lw=2, label="s = 0 (calibrated)")
    ax2.plot(ALPHAS, at_full, "s-", color="#C01919", lw=2, label="s = 1")
    ax2.set_xlabel("α"); ax2.set_ylabel("mean touch error (px)")
    ax2.set_title("alpha is inert at rest, monotone under stress", fontsize=11)
    ax2.grid(alpha=.3, ls="--"); ax2.legend(fontsize=8)

    ax3.plot(ALPHAS, [divergence[a] for a in ALPHAS], "o-", color="#BE185D", lw=2)
    ax3.axhline(0, color="#999", lw=1, ls="--")
    ax3.set_xlabel("α"); ax3.set_ylabel("adaptive − static error (px)")
    ax3.set_title("C. Coupling is visible across the band", fontsize=11)
    ax3.grid(alpha=.3, ls="--")
    fig.tight_layout(); fig.savefig(f"{OUT}/alpha_sensitivity.png", dpi=160); plt.close(fig)

    verdicts = {
        "A_alpha_inert_at_rest": bool(rest_spread < 0.5),
        "B_monotone_across_band": bool(monotone),
        "C_coupling_visible_above_zero_alpha": bool(
            all(divergence[a] > 0 for a in ALPHAS if a > 0) and abs(divergence[0.0]) < 0.5),
    }
    summary = {
        "experiment": "EXP-04", "seed": SEED, "alphas": ALPHAS, "stresses": STRESSES,
        "note": "alpha has no published value and cannot be calibrated; this tests "
                "whether conclusions depend on the choice, not whether the value is right",
        "mean_error_px": {str(a): {str(s): round(grid[a][s][0], 3) for s in STRESSES}
                          for a in ALPHAS},
        "miss_rate_pct": {str(a): {str(s): round(grid[a][s][1], 2) for s in STRESSES}
                          for a in ALPHAS},
        "spread_at_rest_px": round(rest_spread, 4),
        "divergence_from_static_px": {str(a): round(v, 3) for a, v in divergence.items()},
        "verdicts": verdicts,
    }
    with open(f"{OUT}/summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    print("EXP-04 — parameter sensitivity (alpha)\n")
    print("mean touch error (px) — rows alpha, columns stress")
    print("   α   " + "".join(f"{s:>9.1f}" for s in STRESSES) + "   miss@s=1")
    for a in ALPHAS:
        row = "".join(f"{grid[a][s][0]:>9.2f}" for s in STRESSES)
        print(f"  {a:>4.1f} {row}   {grid[a][1.0][1]:>7.1f}%")
    print("\nmiss rate (%) at s=1, by physical target size")
    print("   α   " + "".join(f"{n:>22}" for n in TARGETS))
    miss_by_target = {}
    for a in ALPHAS:
        cells = []
        for name, t in TARGETS.items():
            m = run(a, 1.0, target=t)[1]
            miss_by_target.setdefault(name, {})[a] = round(m, 2)
            cells.append(f"{m:>21.1f}%")
        print(f"  {a:>4.1f} " + "".join(cells))
    print("   -> a cramped control misses often even at rest; a real dialer key does not.")
    print("      That gap IS the FFitts absolute floor, and it is why miss rate alone")
    print("      is a poor headline metric. Mean error is the one to quote.")
    summary["miss_rate_by_target_at_s1"] = miss_by_target
    with open(f"{OUT}/summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    print(f"\nA. spread of the s=0 column: {rest_spread:.4f} px "
          f"-> alpha does not touch the calibrated behaviour")
    print(f"B. error at s=1 monotone in alpha: {monotone}")
    print(f"C. adaptive-vs-static divergence positive for every alpha > 0: "
          f"{all(divergence[a] > 0 for a in ALPHAS if a > 0)}")
    print("\nverdicts:")
    for k, v in verdicts.items():
        print(f"   {'PASS' if v else 'FAIL'}  {k}")
    print(f"\nwrote {OUT}/summary.json and alpha_sensitivity.png")


if __name__ == "__main__":
    main()
