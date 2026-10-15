"""Figures for a stress timeline.

One plotting path serves three outputs: the live view during a run, the figures
in the run report, and the figures in the thesis. Nothing here is specific to
any of them, so none of it is duplicated.
"""
import matplotlib

matplotlib.use("Agg")  # overridden by the live view when a display exists

import matplotlib.patches as patches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

STATE_COLOUR = {
    "calm": "#14803A",
    "impatient": "#B45309",
    "frustrated": "#C01919",
    "static": "#5b6b7c",
}


def plot_timeline(timeline, target, title=None, path=None):
    """Two panels: stress against time with the app's response, and where the taps landed."""
    records = timeline.records
    if not records:
        raise ValueError("timeline is empty")

    steps = range(len(records))
    stress = [r.stress_s for r in records]
    delays = [r.ui_delay_ms for r in records]

    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(11, 8), gridspec_kw={"height_ratios": [1, 1.25]}
    )

    # --- stress over time, banded by cognitive state ---
    for i, r in enumerate(records):
        top.axvspan(i - 0.5, i + 0.5, color=STATE_COLOUR.get(r.cognitive_state, "#999"),
                    alpha=0.13, linewidth=0)
    top.plot(steps, stress, color="#0E7C86", linewidth=2.2, label="stress $s$", zorder=3)
    top.set_ylim(0, 1.02)
    top.set_ylabel("stress $s$")
    top.set_xlabel("action")
    top.grid(alpha=0.25, linestyle="--")

    response = top.twinx()
    response.plot(steps, delays, color="#6D28D9", linewidth=1.1,
                  alpha=0.75, label="UI response (ms)")
    response.set_ylabel("UI response (ms)", color="#6D28D9")
    response.tick_params(axis="y", colors="#6D28D9")

    handles = [plt.Line2D([], [], color="#0E7C86", lw=2.2, label="stress $s$"),
               plt.Line2D([], [], color="#6D28D9", lw=1.1, label="UI response (ms)")]
    handles += [patches.Patch(color=c, alpha=0.3, label=n)
                for n, c in STATE_COLOUR.items()
                if any(r.cognitive_state == n for r in records)]
    top.legend(handles=handles, loc="upper left", fontsize=8, ncol=2)
    top.set_title(title or "Cognitive state and input distortion over a run", fontsize=12)

    # --- where the taps landed ---
    half_w, half_h = target["width"] / 2.0, target["height"] / 2.0
    bottom.add_patch(patches.Rectangle(
        (target["x"] - half_w, target["y"] - half_h), target["width"], target["height"],
        linewidth=1.6, edgecolor="#2c3e50", facecolor="#ecf0f1", alpha=0.65, zorder=1))
    scatter = bottom.scatter([r.x for r in records], [r.y for r in records],
                             c=stress, cmap="viridis", vmin=0, vmax=1,
                             s=26, alpha=0.8, zorder=2, edgecolors="none")
    bottom.plot(target["x"], target["y"], "k+", markersize=13, markeredgewidth=1.8, zorder=3)
    misses = [r for r in records if not r.hit_flag]
    if misses:
        bottom.scatter([r.x for r in misses], [r.y for r in misses],
                       facecolors="none", edgecolors="#C01919", s=70, linewidths=1.1,
                       zorder=4, label=f"missed the target ({len(misses)})")
        bottom.legend(loc="upper right", fontsize=8)
    fig.colorbar(scatter, ax=bottom, label="stress $s$ at the moment of the tap")
    bottom.set_xlabel("x (px)")
    bottom.set_ylabel("y (px)")
    bottom.set_aspect("equal", adjustable="datalim")
    bottom.grid(alpha=0.25, linestyle="--")

    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=160)
        plt.close(fig)
        return path
    return fig


def plot_comparison(timelines, target, path=None):
    """Stress traces from several runs on one axis — the ablation figure."""
    fig, ax = plt.subplots(figsize=(11, 4.2))
    for label, timeline in timelines.items():
        ax.plot(range(len(timeline.records)),
                [r.stress_s for r in timeline.records], linewidth=2.0, label=label)
    ax.set_xlabel("action")
    ax.set_ylabel("stress $s$")
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.25, linestyle="--")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title("Same app, same seed, same targets — only the stress source differs",
                 fontsize=12)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=160)
        plt.close(fig)
        return path
    return fig
