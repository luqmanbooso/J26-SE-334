import os
import json
import statistics
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from models.stress import StressModel
from simulation.simulator import BiometricSimulator


def run_experiment(simulator, stress_level, iterations, target):
    stress_model = StressModel(stress=stress_level)
    current_stress = stress_model.get_stress()
    
    records = []
    for _ in range(iterations):
        res = simulator.simulate_tap(
            target["x"],
            target["y"],
            target["width"],
            target["height"],
            current_stress
        )
        records.append(res)
        
    distances = [r["error_distance"] for r in records]
    delays = [r["delay"] for r in records]
    misses = sum(1 for r in records if not r["is_hit"])
    
    summary = {
        "stress_level": stress_level,
        "iterations": iterations,
        "mean_error_px": round(statistics.mean(distances), 2),
        "std_error_px": round(statistics.stdev(distances), 2),
        "mean_delay_s": round(statistics.mean(delays), 4),
        "std_delay_s": round(statistics.stdev(delays), 4),
        "miss_rate_pct": round((misses / iterations) * 100, 2),
        "raw_records": records
    }
    return summary


def plot_distributions(experiments, target, output_path):
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharex=True, sharey=True)
    colors = ['#2ecc71', '#f39c12', '#e74c3c']
    
    half_w = target["width"] / 2.0
    half_h = target["height"] / 2.0

    for idx, (exp, color) in enumerate(zip(experiments, colors)):
        ax = axes[idx]
        actual_x = [r["actual"]["x"] for r in exp["raw_records"]]
        actual_y = [r["actual"]["y"] for r in exp["raw_records"]]
        
        # Target bounding box
        rect = patches.Rectangle(
            (target["x"] - half_w, target["y"] - half_h),
            target["width"],
            target["height"],
            linewidth=2,
            edgecolor='#2c3e50',
            facecolor='#ecf0f1',
            alpha=0.6,
            label="Target Bounds"
        )
        ax.add_patch(rect)
        
        # Target Center
        ax.plot(target["x"], target["y"], 'k+', markersize=12, markeredgewidth=2, label="Center")
        
        # Scatter actual touch points
        ax.scatter(actual_x, actual_y, alpha=0.35, color=color, s=15, label="Touches")
        
        ax.set_title(
            f"Stress = {exp['stress_level']}\n"
            f"Mean Err: {exp['mean_error_px']}px | Miss: {exp['miss_rate_pct']}%"
        )
        ax.set_xlabel("X (pixels)")
        ax.set_ylabel("Y (pixels)")
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper right")

    plt.suptitle("Biometric Interaction Engine: Touch Distribution vs Stress", fontsize=14)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def main():
    os.makedirs("results", exist_ok=True)

    # UI Element definition (e.g., standard mobile button)
    target = {
        "x": 500,
        "y": 800,
        "width": 160,
        "height": 70
    }

    simulator = BiometricSimulator(base_error=8.0, base_time=0.25)
    stress_conditions = [0.0, 0.5, 1.0]
    iterations = 1000

    print("=" * 65)
    print(f"{'STRESS':<10} | {'MEAN ERR (px)':<15} | {'STD ERR':<10} | {'MISS RATE':<10} | {'MEAN DELAY':<10}")
    print("-" * 65)

    all_experiments = []
    for s in stress_conditions:
        exp = run_experiment(simulator, s, iterations, target)
        all_experiments.append(exp)
        print(f"{exp['stress_level']:<10} | {exp['mean_error_px']:<15} | {exp['std_error_px']:<10} | {exp['miss_rate_pct']}%{'':<5} | {exp['mean_delay_s']}s")

    print("=" * 65)

    # Save summary metrics
    summary_export = [
        {k: v for k, v in exp.items() if k != "raw_records"}
        for exp in all_experiments
    ]
    with open("results/baseline_summary.json", "w") as f:
        json.dump(summary_export, f, indent=4)

    # Export visualization
    plot_path = "results/touch_distribution_baseline.png"
    plot_distributions(all_experiments, target, plot_path)
    print(f"\nBaseline metrics written to: results/baseline_summary.json")
    print(f"Distribution plot saved to:   {plot_path}")


if __name__ == "__main__":
    main()