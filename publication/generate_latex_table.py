import json
import os

results_path = os.path.join(os.path.dirname(__file__), "..", "results", "experiment_results.json")
output_tex = os.path.join(os.path.dirname(__file__), "tables", "table_empirical_results.tex")

with open(results_path, "r", encoding="utf-8") as f:
    data = json.load(f)

rows = []
labels = {
    "1_BASELINE_NOMINAL": ("Baseline Nominal", "No perturbation (Wi-Fi, 100% Bat, 0% Throttle)"),
    "2_NETWORK_DEGRADATION": ("Network Degradation", "3G emulation (RTT: 1200ms, Loss: 5%, BW: 1.5Mbps)"),
    "3_HARDWARE_STARVATION": ("Hardware Starvation", "CPU throttle 95%, LMK pressure, 45°C thermal alert"),
    "4_INTERRUPTION_BURST": ("Interruption Burst", "Incoming telephony, SMS, Doze wake transitions"),
    "5_COMPOUND_MULTI_FACTOR": ("Compound Multi-Factor", "Concurrent Network + CPU + Thermal + Telephony"),
}

tex = [
    r"\begin{table*}[t]",
    r"\centering",
    r"\caption{Empirical Resilience Evaluation Across Single vs. Compound Adversarial Scenarios}",
    r"\label{tab:empirical_evaluation}",
    r"\resizebox{0.95\textwidth}{!}{%",
    r"\begin{tabular}{l l r r r r r}",
    r"\hline",
    r"\textbf{Scenario} & \textbf{Perturbation Configuration} & \textbf{Mean Latency (ms)} & \textbf{P95 Latency (ms)} & \textbf{Mean FPS} & \textbf{Jank Drop (\%)} & \textbf{Failure Rate (\%)} \\",
    r"\hline"
]

for key, metrics in data.items():
    name, config = labels.get(key, (key, ""))
    mean_lat = f"{metrics.get('mean_latency_ms', 0):.2f}"
    p95_lat = f"{metrics.get('p95_latency_ms', 0):.2f}"
    fps = f"{metrics.get('mean_fps', 0):.2f}"
    jank = f"{metrics.get('jank_frame_drop_pct', 0):.2f}\\%"
    fail = f"{metrics.get('failure_rate_pct', 0):.1f}\\%"

    if "COMPOUND" in key:
        tex.append(r"\hline")
        tex.append(f"\\textbf{{{name}}} & \\textbf{{{config}}} & \\textbf{{{mean_lat}}} & \\textbf{{{p95_lat}}} & \\textbf{{{fps}}} & \\textbf{{{jank}}} & \\textbf{{{fail}}} \\\\")
    else:
        tex.append(f"{name} & {config} & {mean_lat} & {p95_lat} & {fps} & {jank} & {fail} \\\\")

tex.extend([
    r"\hline",
    r"\end{tabular}",
    r"}",
    r"\end{table*}"
])

with open(output_tex, "w", encoding="utf-8") as f:
    f.write("\n".join(tex) + "\n")

print(f"Generated LaTeX table at: {output_tex}")
