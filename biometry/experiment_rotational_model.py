import os
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from simulation.simulator import BiometricSimulator


def main():
    os.makedirs("results", exist_ok=True)
    simulator = BiometricSimulator(base_sigma=10.0, base_time=0.25)
    
    target = {"x": 500, "y": 800, "width": 160, "height": 70}
    test_angles_deg = [45, 90, 135]
    stress_level = 0.8
    iterations = 800

    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharex=True, sharey=True)

    for idx, deg in enumerate(test_angles_deg):
        ax = axes[idx]
        theta_rad = math.radians(deg)
        
        touches_x = []
        touches_y = []
        misses = 0

        for _ in range(iterations):
            res = simulator.simulate_tap(
                target["x"], target["y"], target["width"], target["height"],
                stress=stress_level, angle=theta_rad
            )
            touches_x.append(res["actual"]["x"])
            touches_y.append(res["actual"]["y"])
            if not res["is_hit"]:
                misses += 1

        # Draw Target Bounds
        rect = patches.Rectangle(
            (target["x"] - target["width"] / 2.0, target["y"] - target["height"] / 2.0),
            target["width"], target["height"],
            linewidth=2, edgecolor="#2c3e50", facecolor="#ecf0f1", alpha=0.6, label="Target"
        )
        ax.add_patch(rect)
        ax.plot(target["x"], target["y"], "k+", markersize=14, markeredgewidth=2)

        # Plot Touch Ellipse Points
        ax.scatter(touches_x, touches_y, alpha=0.35, color="#e74c3c", s=18, label="Touch Points")

        # Draw Approach Direction Vector Arrow
        arrow_len = 80
        ax.arrow(
            target["x"] - arrow_len * math.cos(theta_rad),
            target["y"] - arrow_len * math.sin(theta_rad),
            arrow_len * math.cos(theta_rad) * 0.85,
            arrow_len * math.sin(theta_rad) * 0.85,
            head_width=10, head_length=12, fc="#2980b9", ec="#2980b9", linewidth=2.5, label="Approach Angle (θ)"
        )

        miss_rate = round((misses / iterations) * 100, 1)
        ax.set_title(f"Approach θ = {deg}° (Stress = {stress_level})\nMiss Rate: {miss_rate}%", fontsize=12)
        ax.set_xlabel("X (pixels)")
        ax.set_ylabel("Y (pixels)")
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper right")

    plt.suptitle("Rotational Dual Gaussian Model (Ma et al., UIST '21) Distribution", fontsize=14)
    plt.tight_layout()
    
    out_path = "results/rotational_dual_gaussian_distribution.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"[Success] Rotational Dual Gaussian experiment plot exported to: {out_path}")


if __name__ == "__main__":
    main()