import os
import json
import matplotlib.pyplot as plt
import numpy as np

def generate_charts(results_path="results/experiment_results.json", output_dir="results"):
    if not os.path.exists(results_path):
        print(f"[-] Results file {results_path} not found.")
        return

    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(output_dir, exist_ok=True)

    # Prepare labels and data
    raw_keys = list(data.keys())
    labels = [
        "1. Baseline\nNominal",
        "2. Network\nDegradation",
        "3. Hardware\nStarvation",
        "4. Interruption\nBurst",
        "5. Compound\nMulti-Factor"
    ]

    mean_rtt = [data[k]["mean_latency_ms"] for k in raw_keys]
    p95_rtt = [data[k]["p95_latency_ms"] for k in raw_keys]
    mean_fps = [data[k]["mean_fps"] for k in raw_keys]
    fail_rates = [data[k]["failure_rate_pct"] for k in raw_keys]
    jank_drops = [data[k]["jank_frame_drop_pct"] for k in raw_keys]

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # -------------------------------------------------------------------------
    # FIGURE 1: Dual-Axis Latency vs Render Frame Rate (FPS)
    # -------------------------------------------------------------------------
    fig, ax1 = plt.subplots(figsize=(9, 5), dpi=300)

    color_rtt = "#e11d48"  # rose-red
    color_fps = "#0284c7"  # sky-blue

    x = np.arange(len(labels))
    width = 0.35

    rects1 = ax1.bar(x - width/2, mean_rtt, width, label="Mean RTT Latency (ms)", color=color_rtt, alpha=0.88, edgecolor="black", linewidth=0.8)
    ax1.set_ylabel("Round Trip Time Latency (ms)", color=color_rtt, fontsize=12, fontweight="bold")
    ax1.tick_params(axis="y", labelcolor=color_rtt)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=10, fontweight="bold")
    ax1.set_title("Fig 1: Impact of Environmental Perturbations on Mobile Latency & Framerate", fontsize=13, fontweight="bold", pad=14)

    # Secondary Axis for FPS
    ax2 = ax1.twinx()
    rects2 = ax2.plot(x, mean_fps, color=color_fps, marker="o", linewidth=2.5, markersize=8, label="Mean UI Framerate (FPS)")
    ax2.set_ylabel("UI Render Framerate (FPS)", color=color_fps, fontsize=12, fontweight="bold")
    ax2.tick_params(axis="y", labelcolor=color_fps)
    ax2.set_ylim(0, 65)

    # Data value labels on bars
    for rect in rects1:
        h = rect.get_height()
        ax1.annotate(f"{h:.0f}ms",
                    xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8, fontweight="bold")

    fig.tight_layout()
    fig1_path = os.path.join(output_dir, "fig1_latency_and_framerate.png")
    fig.savefig(fig1_path)
    plt.close(fig)
    print(f"[+] Saved Figure 1 to: {fig1_path}")

    # -------------------------------------------------------------------------
    # FIGURE 2: Failure & Defect Exposure Rate (%)
    # -------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=300)

    colors = ["#10b981", "#f59e0b", "#f97316", "#ef4444", "#881337"]
    bars = ax.bar(labels, fail_rates, color=colors, width=0.55, edgecolor="black", linewidth=0.8)

    ax.set_ylabel("Application Failure Rate (%)", fontsize=12, fontweight="bold")
    ax.set_title("Fig 2: Defect Exposure Rate Under Compound vs Single-Factor Chaos", fontsize=13, fontweight="bold", pad=14)
    ax.set_ylim(0, 65)

    for bar in bars:
        h = bar.get_height()
        ax.annotate(f"{h:.1f}%",
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=10, fontweight="bold")

    fig.tight_layout()
    fig2_path = os.path.join(output_dir, "fig2_failure_rate_comparison.png")
    fig.savefig(fig2_path)
    plt.close(fig)
    print(f"[+] Saved Figure 2 to: {fig2_path}")

    # -------------------------------------------------------------------------
    # FIGURE 3: Jank & Dropped Frames Percentage
    # -------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=300)

    bars_jank = ax.bar(labels, jank_drops, color="#a855f7", width=0.55, alpha=0.88, edgecolor="black", linewidth=0.8)
    ax.set_ylabel("UI Jank / Dropped Frames (%)", fontsize=12, fontweight="bold")
    ax.set_title("Fig 3: Non-Crash GUI Degradation: Frame Drop Probability", fontsize=13, fontweight="bold", pad=14)
    ax.set_ylim(0, 75)

    for bar in bars_jank:
        h = bar.get_height()
        ax.annotate(f"{h:.1f}%",
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=10, fontweight="bold")

    fig.tight_layout()
    fig3_path = os.path.join(output_dir, "fig3_jank_frame_drop.png")
    fig.savefig(fig3_path)
    plt.close(fig)
    print(f"[+] Saved Figure 3 to: {fig3_path}")

if __name__ == "__main__":
    generate_charts()
