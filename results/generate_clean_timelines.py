import os
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

STATE_COLOUR = {
    "calm": "#10b981",
    "impatient": "#f59e0b",
    "frustrated": "#ef4444",
    "static": "#64748b",
}

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "results", "exp-02", "mon-joint-session")
OUT_DIR = os.path.join(ROOT_DIR, "results")
os.makedirs(OUT_DIR, exist_ok=True)

def plot_clean_timeline(json_file, out_png, title):
    json_path = os.path.join(SRC_DIR, json_file)
    if not os.path.exists(json_path):
        print(f"Skipping {json_file}: not found")
        return
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    records = data.get("records", [])
    if not records:
        return

    steps = list(range(len(records)))
    stress = [r.get("stress_s", 0.0) for r in records]
    delays = [r.get("ui_delay_ms", 20.0) for r in records]

    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(11, 8), gridspec_kw={"height_ratios": [1, 1.25]}
    )
    fig.patch.set_facecolor("#ffffff")
    top.set_facecolor("#f8fafc")
    bottom.set_facecolor("#f8fafc")

    for i, r in enumerate(records):
        st = r.get("cognitive_state", "calm")
        top.axvspan(i - 0.5, i + 0.5, color=STATE_COLOUR.get(st, "#94a3b8"), alpha=0.15, linewidth=0)

    top.plot(steps, stress, color="#2563eb", linewidth=2.2, label="Cognitive Stress ($S_{\\text{cog}}$)", zorder=3)
    top.set_ylim(-0.02, 1.05)
    top.set_ylabel("Cognitive Stress ($S_{\\text{cog}}$)", color="#1e3a8a", fontsize=10, fontweight="bold")
    top.set_xlabel("Action Sequence (#)", fontsize=10, fontweight="bold")
    top.grid(alpha=0.3, linestyle="--")

    response = top.twinx()
    response.plot(steps, delays, color="#7c3aed", linewidth=1.4, alpha=0.8, label="UI Response Latency (ms)")
    response.set_ylabel("UI Response Latency (ms)", color="#7c3aed", fontsize=10, fontweight="bold")
    response.tick_params(axis="y", colors="#7c3aed")

    handles = [
        plt.Line2D([], [], color="#2563eb", lw=2.2, label="Cognitive Stress ($S_{\\text{cog}}$)"),
        plt.Line2D([], [], color="#7c3aed", lw=1.4, label="UI Response (ms)"),
        patches.Patch(color="#10b981", alpha=0.3, label="Calm State"),
        patches.Patch(color="#f59e0b", alpha=0.3, label="Impatient State"),
        patches.Patch(color="#ef4444", alpha=0.3, label="Frustrated (Stalled)"),
    ]
    top.legend(handles=handles, loc="upper left", fontsize=8, ncol=3)
    top.set_title(title, fontsize=11, fontweight="bold", color="#0f172a")

    # Bottom panel: touch distribution
    target = {"x": 540, "y": 1150, "width": 260, "height": 70}
    half_w, half_h = target["width"] / 2.0, target["height"] / 2.0
    bottom.add_patch(patches.Rectangle(
        (target["x"] - half_w, target["y"] - half_h), target["width"], target["height"],
        linewidth=1.8, edgecolor="#2563eb", facecolor="#eff6ff", alpha=0.7, zorder=1
    ))
    bottom.text(target["x"], target["y"], "TARGET COMPONENT (260×70 px)", ha="center", va="center", color="#1e40af", fontsize=8, fontweight="bold")
    bottom.plot(target["x"], target["y"], "k+", markersize=14, markeredgewidth=1.8, zorder=3)

    scatter = bottom.scatter(
        [r["x"] for r in records], [r["y"] for r in records],
        c=stress, cmap="plasma", vmin=0, vmax=1,
        s=34, alpha=0.85, zorder=4, edgecolors="#1e293b", linewidths=0.6
    )

    misses = [r for r in records if not r.get("hit_flag", True)]
    if misses:
        bottom.scatter(
            [r["x"] for r in misses], [r["y"] for r in misses],
            facecolors="none", edgecolors="#dc2626", s=85, linewidths=1.6,
            zorder=5, label=f"Missed Target ({len(misses)})"
        )
        bottom.legend(loc="upper right", fontsize=8)

    cbar = fig.colorbar(scatter, ax=bottom, orientation="vertical", pad=0.02)
    cbar.set_label("Cognitive Stress ($S_{\\text{cog}}$)", fontsize=9, fontweight="bold")
    bottom.set_xlabel("Device X Position (px)", fontsize=9, fontweight="bold")
    bottom.set_ylabel("Device Y Position (px)", fontsize=9, fontweight="bold")
    bottom.set_title("On-Device Biometric Touch Coordinates & Motor Tremor Dispersions", fontsize=10, fontweight="bold", color="#0f172a")
    bottom.grid(alpha=0.3, linestyle="--")

    fig.tight_layout()
    target_out = os.path.join(OUT_DIR, out_png)
    fig.savefig(target_out, dpi=160)
    plt.close(fig)
    print(f"Generated clean timeline: {target_out}")

def plot_clean_analysis():
    json_path = os.path.join(SRC_DIR, "analysis.json")
    if not os.path.exists(json_path):
        return
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    arms = data.get("arms", {})
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(11, 7.5), gridspec_kw={"height_ratios": [1, 1]})
    fig.patch.set_facecolor("#ffffff")
    top.set_facecolor("#f8fafc")
    bottom.set_facecolor("#f8fafc")

    colours = {"noise-only": "#64748b", "static-stress": "#d97706", "full-adaptive": "#2563eb"}
    labels = {
        "noise-only": "Baseline Floor (Decoupled)",
        "static-stress": "Static Stress (Open-Loop)",
        "full-adaptive": "Closed-Loop Adaptive (Coupled)"
    }

    for name in ["noise-only", "static-stress", "full-adaptive"]:
        arm_json = os.path.join(SRC_DIR, f"{name}_timeline.json")
        if os.path.exists(arm_json):
            with open(arm_json, "r", encoding="utf-8") as f:
                r_data = json.load(f)
            s_series = [r["stress_s"] for r in r_data.get("records", [])]
            top.plot(range(len(s_series)), s_series, label=labels.get(name, name),
                     color=colours.get(name, "#2563eb"), linewidth=2.4)

    top.set_ylabel("Cognitive Stress ($S_{\\text{cog}}$)", fontsize=10, fontweight="bold")
    top.set_xlabel("Action Number (#)", fontsize=10, fontweight="bold")
    top.set_ylim(-0.02, 1.05)
    top.legend(loc="upper left", fontsize=8.5)
    top.grid(alpha=0.3, linestyle="--")
    top.set_title("Cross-Arm Coupling Separation Analysis: Closed-Loop Dynamics vs Baselines", fontsize=11, fontweight="bold", color="#0f172a")

    arm_names = ["noise-only", "static-stress", "full-adaptive"]
    display_names = ["Noise Floor", "Static Stress", "Closed-Loop Adaptive"]
    miss_rates = [arms.get(n, {}).get("miss_rate", 0.0) * 100 for n in arm_names]
    mean_stresses = [arms.get(n, {}).get("mean_stress", 0.0) for n in arm_names]

    x = [0, 1, 2]
    w = 0.32
    b1 = bottom.bar([xi - w/2 for xi in x], miss_rates, width=w, label="Target Miss Rate (%)", color="#ef4444")
    b2 = bottom.bar([xi + w/2 for xi in x], [ms * 100 for ms in mean_stresses], width=w, label="Mean Stress Scale (×100)", color="#2563eb")
    bottom.set_xticks(x)
    bottom.set_xticklabels(display_names, fontsize=9.5, fontweight="bold")
    bottom.set_ylabel("Metric Benchmark (%)", fontsize=10, fontweight="bold")
    bottom.legend(loc="upper left", fontsize=8.5)
    bottom.grid(alpha=0.3, linestyle="--", axis="y")
    bottom.set_title("Empirical Statistical Separation: Miss Rates and Cumulative Stress Levels", fontsize=10, fontweight="bold", color="#0f172a")

    fig.tight_layout()
    target_out = os.path.join(OUT_DIR, "heart_coupling_analysis.png")
    fig.savefig(target_out, dpi=160)
    plt.close(fig)
    print(f"Generated clean analysis: {target_out}")

def plot_live_pipeline_timeline(records, out_png="heart_pipeline_live_timeline.png", out_json="heart_pipeline_live_timeline.json", title=None):
    if not records:
        return None
    
    if out_json:
        json_path = os.path.join(OUT_DIR, out_json)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"pipeline_run_timestamp": json_path, "records_count": len(records), "records": records}, f, indent=2)

    steps = list(range(1, len(records) + 1))
    stress = [r.get("stress_s", 0.0) for r in records]
    delays = [r.get("ui_delay_ms", 25.0) for r in records]

    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(11, 8.2), gridspec_kw={"height_ratios": [1, 1.2]}
    )
    fig.patch.set_facecolor("#ffffff")
    top.set_facecolor("#f8fafc")
    bottom.set_facecolor("#f8fafc")

    for i, r in enumerate(records):
        s_val = r.get("stress_s", 0.0)
        st = "calm" if s_val < 0.25 else ("impatient" if s_val < 0.70 else "frustrated")
        top.axvspan(i + 0.5, i + 1.5, color=STATE_COLOUR.get(st, "#94a3b8"), alpha=0.18, linewidth=0)

    top.plot(steps, stress, color="#2563eb", linewidth=2.4, marker="o", markersize=5, label="Cognitive Stress ($S_{\\text{cog}}$)", zorder=3)
    top.set_ylim(-0.02, 1.05)
    top.set_ylabel("Cognitive Stress ($S_{\\text{cog}}$)", color="#1e3a8a", fontsize=10, fontweight="bold")
    top.set_xlabel("Pipeline Step Sequence (#)", fontsize=10, fontweight="bold")
    top.grid(alpha=0.3, linestyle="--")

    response = top.twinx()
    response.plot(steps, delays, color="#7c3aed", linewidth=1.8, marker="s", markersize=4, alpha=0.85, label="UI Response / Frame Latency (ms)")
    response.set_ylabel("UI Response Latency (ms)", color="#7c3aed", fontsize=10, fontweight="bold")
    response.tick_params(axis="y", colors="#7c3aed")

    handles = [
        plt.Line2D([], [], color="#2563eb", lw=2.4, marker="o", label="Cognitive Stress ($S_{\\mathrm{cog}}$)"),
        plt.Line2D([], [], color="#7c3aed", lw=1.8, marker="s", label="UI Response Latency (ms)"),
        patches.Patch(color="#10b981", alpha=0.3, label="Calm State (< 0.25)"),
        patches.Patch(color="#f59e0b", alpha=0.3, label="Impatient State (0.25 - 0.70)"),
        patches.Patch(color="#ef4444", alpha=0.3, label="Frustrated State (>= 0.70)"),
    ]
    top.legend(handles=handles, loc="upper left", fontsize=8, ncol=3)
    plot_title = title or "Autonomous E2E Pipeline: Multi-Factor Chaos & Biometric Stress Trajectory"
    top.set_title(plot_title, fontsize=11, fontweight="bold", color="#0f172a")

    # Bottom panel: Component-relative dispersion scatter
    target_w, target_h = 240.0, 60.0
    half_w, half_h = target_w / 2.0, target_h / 2.0
    bottom.add_patch(patches.Rectangle(
        (-half_w, -half_h), target_w, target_h,
        linewidth=1.8, edgecolor="#2563eb", facecolor="#eff6ff", alpha=0.7, zorder=1
    ))
    bottom.text(0, 0, f"TARGET INTERACTIVE WIDGET ({int(target_w)}×{int(target_h)} px)", ha="center", va="center", color="#1e40af", fontsize=8, fontweight="bold")
    bottom.plot(0, 0, "k+", markersize=14, markeredgewidth=1.8, zorder=3)

    dx_list = []
    dy_list = []
    for r in records:
        dx = r.get("x", 0) - r.get("target_x", r.get("x", 0))
        dy = r.get("y", 0) - r.get("target_y", r.get("y", 0))
        dx_list.append(dx)
        dy_list.append(dy)

    scatter = bottom.scatter(
        dx_list, dy_list,
        c=stress, cmap="plasma", vmin=0, vmax=1,
        s=48, alpha=0.88, zorder=4, edgecolors="#1e293b", linewidths=0.8
    )

    miss_indices = [i for i, r in enumerate(records) if not r.get("hit_flag", True)]
    if miss_indices:
        bottom.scatter(
            [dx_list[i] for i in miss_indices], [dy_list[i] for i in miss_indices],
            facecolors="none", edgecolors="#dc2626", s=110, linewidths=1.8,
            zorder=5, label=f"Missed Target ({len(miss_indices)} Misses)"
        )
        bottom.legend(loc="upper right", fontsize=8.5)

    cbar = fig.colorbar(scatter, ax=bottom, orientation="vertical", pad=0.02)
    cbar.set_label("Cognitive Stress ($S_{\\text{cog}}$)", fontsize=9, fontweight="bold")
    bottom.set_xlabel("Relative Offset X from Widget Center (px)", fontsize=9, fontweight="bold")
    bottom.set_ylabel("Relative Offset Y from Widget Center (px)", fontsize=9, fontweight="bold")
    bottom.set_title("On-Device Biometric Touch Dispersion Relative to Target Widgets Across Traversal", fontsize=10, fontweight="bold", color="#0f172a")
    bottom.grid(alpha=0.3, linestyle="--")

    max_dist = max([max(abs(dx), abs(dy)) for dx, dy in zip(dx_list, dy_list)] + [150])
    limit = max(160, max_dist + 20)
    bottom.set_xlim(-limit, limit)
    bottom.set_ylim(-limit, limit)

    fig.tight_layout()
    target_out = os.path.join(OUT_DIR, out_png)
    fig.savefig(target_out, dpi=160)
    plt.close(fig)
    print(f"Generated live pipeline timeline: {target_out}")
    return target_out

if __name__ == "__main__":
    plot_clean_timeline("noise-only_timeline.json", "heart_noise_floor_timeline.png",
                        "HEART Baseline Touch Imprecision Floor Timeline (No Adaptation)")
    plot_clean_timeline("full-adaptive_timeline.json", "heart_adaptive_timeline.png",
                        "HEART Closed-Loop Adaptive Multi-Factor Chaos Timeline (Coupled Degradation)")
    plot_clean_timeline("static-stress_timeline.json", "heart_static_stress_timeline.png",
                        "HEART Open-Loop Static-Stress Reference Timeline (Fixed Degradation)")
    plot_clean_analysis()

