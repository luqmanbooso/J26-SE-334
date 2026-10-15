"""EXP-03 — Realism check: do the samplers reproduce published distributions?

Runs entirely offline. Compares the engine's generated distributions against the
values reported in the source papers, which are transcribed with provenance in
data/bi2013_published.csv.

Three checks, one per modelled phenomenon:

  A. Spread vs target width   — against Bi, Li & Zhai (2013), 2D results.
     Their table gives sigma_observed per target width with sigma_absolute held
     at 1.50 mm. The engine must reproduce that curve, and must do so with the
     sub-linear growth their data shows rather than a linear one.

  B. Ellipse orientation      — against Ma et al. (2021).
     Their claim is structural: the major axis of the touch distribution lies
     along the finger's movement direction, the minor axis perpendicular to it.
     Verified by fitting the covariance of generated points and recovering the
     principal axis angle.

  C. Inter-action delay shape — right-skewed, never symmetric, at every stress
     level. A Gaussian cannot express the long tail human timing has.

Writes figures and a machine-readable summary to results/exp-03/.
"""
import csv
import json
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy import optimize, stats  # noqa: E402

from models.spatial import RotationalSpatialModel  # noqa: E402
from models.timing import TimingModel  # noqa: E402

OUT = "results/exp-03"
PX_PER_MM = 16.0
SEED = 2026


def published(task="2D"):
    rows = []
    with open("data/bi2013_published.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(l for l in fh if not l.startswith("#")):
            if r["task"] == task:
                rows.append({k: (v if k == "task" else float(v)) for k, v in r.items()})
    return rows


# --- A. spread vs target width ---------------------------------------------

def check_spread(rows):
    model = RotationalSpatialModel(px_per_mm=PX_PER_MM, rng=np.random.default_rng(SEED))
    widths = sorted({r["width_mm"] for r in rows})
    obs = {w: np.mean([r["sigma_observed_mm"] for r in rows if r["width_mm"] == w])
           for w in widths}

    analytic, empirical = [], []
    for w in widths:
        px = w * PX_PER_MM
        analytic.append(model.base_sigma(px, px) / PX_PER_MM)
        pts = [model.generate_touch(0.0, 0.0, px, px, 0.0, angle=0.0) for _ in range(20000)]
        d = np.hypot([p[0] for p in pts], [p[1] for p in pts])
        empirical.append(float(np.sqrt(np.mean(d ** 2) / 2) / PX_PER_MM))  # SDxy

    pub = [obs[w] for w in widths]
    err = [abs(a - p) for a, p in zip(analytic, pub)]
    ss_res = sum((a - p) ** 2 for a, p in zip(analytic, pub))
    ss_tot = sum((p - np.mean(pub)) ** 2 for p in pub)

    # does the published data support a linear law or a sub-linear one?
    W = np.array([r["width_mm"] for r in rows])
    SR = np.array([r["sigma_relative_mm"] for r in rows])
    fits = {}
    for name, f, p0 in [("linear", lambda w, k: k * w, [0.2]),
                        ("sqrt", lambda w, k: k * np.sqrt(w), [0.5]),
                        ("power", lambda w, k, n: k * w ** n, [0.5, 0.5])]:
        p, _ = optimize.curve_fit(f, W, SR, p0=p0, maxfev=20000)
        res = np.sum((SR - f(W, *p)) ** 2)
        fits[name] = {"params": [round(float(v), 4) for v in p],
                      "sse": round(float(res), 5),
                      "r2": round(float(1 - res / np.sum((SR - SR.mean()) ** 2)), 4)}

    fig, ax = plt.subplots(figsize=(7.6, 5))
    ax.plot(widths, pub, "o-", color="#C01919", lw=2, ms=9, label="published (Bi et al. 2013, 2D)")
    ax.plot(widths, analytic, "s--", color="#0E7C86", lw=2, ms=8, label="engine, analytic")
    ax.plot(widths, empirical, "^:", color="#1168BD", lw=1.8, ms=8, label="engine, 20k samples")
    ax.set_xlabel("target width W (mm)")
    ax.set_ylabel(r"endpoint deviation $\sigma$ (mm)")
    ax.set_title("A. Spread vs target width", fontsize=12)
    ax.grid(alpha=.3, ls="--"); ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(f"{OUT}/A_spread_vs_width.png", dpi=160); plt.close(fig)

    return {"widths_mm": widths, "published_mm": [round(v, 3) for v in pub],
            "engine_analytic_mm": [round(v, 3) for v in analytic],
            "engine_sampled_mm": [round(v, 3) for v in empirical],
            "max_abs_error_mm": round(max(err), 4),
            "mean_abs_error_mm": round(float(np.mean(err)), 4),
            "r2_against_published": round(float(1 - ss_res / ss_tot), 4),
            "scaling_law_fits": fits}


# --- B. ellipse orientation --------------------------------------------------

def check_orientation():
    model = RotationalSpatialModel(px_per_mm=PX_PER_MM, rng=np.random.default_rng(SEED + 1))
    angles = [0, 30, 45, 60, 90, 120, 135, 150]
    recovered, aspects = [], []
    for deg in angles:
        th = math.radians(deg)
        pts = [model.generate_touch(0., 0., 110., 110., 0.6, angle=th) for _ in range(12000)]
        xy = np.vstack([[p[0] for p in pts], [p[1] for p in pts]])
        vals, vecs = np.linalg.eigh(np.cov(xy))
        major = vecs[:, -1]
        recovered.append(math.degrees(math.atan2(major[1], major[0]) % math.pi))
        aspects.append(float(np.sqrt(vals[0] / vals[-1])))
    dev = [min(abs(r - a), 180 - abs(r - a)) for r, a in zip(recovered, angles)]

    fig, (l, r) = plt.subplots(1, 2, figsize=(11, 4.4))
    l.plot([0, 180], [0, 180], "--", color="#999", lw=1, label="perfect alignment")
    l.plot(angles, recovered, "o", color="#0E7C86", ms=9, label="recovered major axis")
    l.set_xlabel("movement direction θ (deg)"); l.set_ylabel("fitted major axis (deg)")
    l.set_title("B. Ellipse tracks the movement direction", fontsize=11)
    l.grid(alpha=.3, ls="--"); l.legend(fontsize=9)
    r.bar(range(len(angles)), dev, color="#1168BD", alpha=.8)
    r.set_xticks(range(len(angles))); r.set_xticklabels(angles)
    r.axhline(2.0, color="#C01919", ls="--", lw=1.2, label="2° tolerance")
    r.set_xlabel("θ (deg)"); r.set_ylabel("deviation (deg)")
    r.set_title("Orientation error", fontsize=11); r.grid(alpha=.3, ls="--", axis="y")
    r.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(f"{OUT}/B_ellipse_orientation.png", dpi=160); plt.close(fig)

    return {"angles_deg": angles,
            "recovered_deg": [round(v, 2) for v in recovered],
            "max_deviation_deg": round(max(dev), 3),
            "mean_aspect_minor_over_major": round(float(np.mean(aspects)), 3)}


# --- C. delay distribution shape --------------------------------------------

def check_delays():
    levels = [0.0, 0.25, 0.5, 0.75, 1.0]
    out, samples = [], {}
    for s in levels:
        t = TimingModel(rng=np.random.default_rng(SEED + 2))
        d = np.array([t.generate_delay(s) for _ in range(40000)])
        samples[s] = d
        out.append({"stress": s, "median_s": round(float(np.median(d)), 4),
                    "sd_s": round(float(d.std()), 4),
                    "skew": round(float(stats.skew(d)), 3),
                    "p95_over_median": round(float(np.percentile(d, 95) / np.median(d)), 3),
                    "min_s": round(float(d.min()), 4)})

    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    for s in levels:
        ax.hist(samples[s], bins=120, density=True, histtype="step", lw=1.7,
                label=f"s = {s:.2f} (skew {stats.skew(samples[s]):.2f})")
    ax.set_xlim(0, 0.8); ax.set_xlabel("inter-action delay (s)"); ax.set_ylabel("density")
    ax.set_title("C. Delays are right-skewed at every stress level", fontsize=12)
    ax.grid(alpha=.3, ls="--"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(f"{OUT}/C_delay_distribution.png", dpi=160); plt.close(fig)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = published("2D")
    a, b, c = check_spread(rows), check_orientation(), check_delays()

    verdicts = {
        "A_spread_vs_width": bool(a["max_abs_error_mm"] < 0.10),
        "B_ellipse_orientation": bool(b["max_deviation_deg"] < 2.0),
        "C_delay_right_skewed": bool(all(r["skew"] > 0.3 for r in c)),
    }
    summary = {"experiment": "EXP-03", "seed": SEED, "px_per_mm": PX_PER_MM,
               "baseline_source": "Bi, Li & Zhai, CHI 2013, Tables 1 and 3; "
                                  "Ma et al., UIST 2021 (structural claim)",
               "A_spread_vs_width": a, "B_ellipse_orientation": b,
               "C_delay_shape": c, "verdicts": verdicts}
    with open(f"{OUT}/summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    print("EXP-03 — realism check\n")
    print("A. spread vs target width, against Bi et al. 2013 (2D)")
    print(f"   {'W mm':>6} {'published':>10} {'engine':>8} {'sampled':>8}")
    for w, p, an, em in zip(a["widths_mm"], a["published_mm"],
                            a["engine_analytic_mm"], a["engine_sampled_mm"]):
        print(f"   {w:>6.1f} {p:>10.3f} {an:>8.3f} {em:>8.3f}")
    print(f"   max abs error {a['max_abs_error_mm']} mm | R^2 {a['r2_against_published']}")
    print("   scaling law fitted to their sigma_relative:")
    for k, v in a["scaling_law_fits"].items():
        print(f"     {k:<7} R^2 {v['r2']:>7}  params {v['params']}")
    print(f"\nB. ellipse orientation: max deviation {b['max_deviation_deg']}° "
          f"over {len(b['angles_deg'])} angles")
    print(f"\nC. delay shape")
    print(f"   {'stress':>7} {'median':>8} {'sd':>7} {'skew':>6} {'p95/med':>8}")
    for r in c:
        print(f"   {r['stress']:>7.2f} {r['median_s']:>8.3f} {r['sd_s']:>7.3f} "
              f"{r['skew']:>6.2f} {r['p95_over_median']:>8.2f}")
    print("\nverdicts:")
    for k, v in verdicts.items():
        print(f"   {'PASS' if v else 'FAIL'}  {k}")
    print(f"\nwrote {OUT}/summary.json and three figures")


if __name__ == "__main__":
    main()
