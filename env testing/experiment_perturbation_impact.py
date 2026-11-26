import os
import json
import math
import time
import random
from typing import Dict, List, Any, Optional, Tuple
from core.benchmark_catalog import paired_t_test
from orchestrator import PerturbationOrchestrator


def mann_whitney_u(sample_a: List[float], sample_b: List[float]) -> Tuple[float, float]:
    """Two-sided Mann-Whitney U test (normal approximation with tie correction)."""
    n1, n2 = len(sample_a), len(sample_b)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0

    combined = [(val, 0) for val in sample_a] + [(val, 1) for val in sample_b]
    combined.sort(key=lambda item: item[0])

    ranks_a = 0.0
    tie_correction = 0.0
    i = 0
    total = n1 + n2
    while i < total:
        j = i + 1
        while j < total and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        tie_len = j - i
        if tie_len > 1:
            tie_correction += (tie_len ** 3 - tie_len)
        for k in range(i, j):
            if combined[k][1] == 0:
                ranks_a += avg_rank
        i = j

    u1 = ranks_a - (n1 * (n1 + 1)) / 2.0
    u2 = (n1 * n2) - u1
    u_stat = min(u1, u2)

    mean_u = (n1 * n2) / 2.0
    denom = total * (total - 1) if total > 1 else 1
    var_u = (n1 * n2 / 12.0) * max(1e-9, (total + 1) - (tie_correction / denom))
    std_u = math.sqrt(var_u)
    if std_u == 0.0:
        return round(u_stat, 2), 1.0

    z = (abs(u_stat - mean_u) - 0.5) / std_u
    p_val = math.erfc(max(0.0, z) / math.sqrt(2.0))
    return round(u_stat, 2), float(f"{max(0.0, min(1.0, p_val)):.3e}")


def run_evaluation_experiment(
    trials_per_condition: int = 30,
    live_device: bool = False,
    package_name: str = "com.android.settings",
    seed: int = 42
) -> Dict[str, Any]:
    """Evaluates mobile app performance across 5 environmental regimes with Mann-Whitney U significance."""
    print("=" * 80)
    print("  RESEARCH EXPERIMENT: IMPACT OF CONTEXT-AWARE ENVIRONMENTAL PERTURBATIONS")
    print(f"  Evaluation on Benchmark Transactions (N = {trials_per_condition} per condition)")
    print("=" * 80)

    rng = random.Random(seed)
    orchestrator = PerturbationOrchestrator(
        log_path="experiment_event_log.json",
        force_simulation=not live_device
    )
    using_live = live_device and (not orchestrator.adb.is_simulated)
    eval_mode = "LIVE_DEVICE" if using_live else "SIMULATED_MODEL"
    print(f"[*] Execution Mode: {eval_mode}")

    conditions = [
        "1_BASELINE_NOMINAL",
        "2_NETWORK_DEGRADATION",
        "3_HARDWARE_STARVATION",
        "4_INTERRUPTION_BURST",
        "5_COMPOUND_MULTI_FACTOR"
    ]

    results: Dict[str, Dict[str, Any]] = {}
    latency_samples_by_cond: Dict[str, List[float]] = {}

    for cond in conditions:
        print(f"\n[+] Testing Environmental Regime: {cond}")
        orchestrator.reset_all()

        if cond == "1_BASELINE_NOMINAL":
            base_rtt, base_fps, fail_prob = 65.0, 59.2, 0.01
        elif cond == "2_NETWORK_DEGRADATION":
            orchestrator.network.set_bandwidth_profile("edge")
            orchestrator.network.inject_latency(1200)
            orchestrator.network.inject_packet_loss(7)
            base_rtt, base_fps, fail_prob = 1350.0, 54.0, 0.14
        elif cond == "3_HARDWARE_STARVATION":
            orchestrator.system.set_cpu_load(90)
            orchestrator.system.set_ram_pressure(85)
            orchestrator.system.set_thermal_state("Warn")
            base_rtt, base_fps, fail_prob = 180.0, 31.5, 0.18
        elif cond == "4_INTERRUPTION_BURST":
            orchestrator.interruption.trigger_incoming_call("15550192831")
            orchestrator.context.set_orientation("landscape")
            base_rtt, base_fps, fail_prob = 110.0, 48.0, 0.22
        elif cond == "5_COMPOUND_MULTI_FACTOR":
            orchestrator.apply_profile({
                "name": "Compound Stress",
                "cpuStress": 92,
                "ramStress": 88,
                "latency": 1600,
                "packetLoss": 10,
                "thermalState": "Critical",
                "networkProfile": "2G / EDGE",
                "interruptionType": "Incoming Call, Low Battery"
            })
            base_rtt, base_fps, fail_prob = 1850.0, 22.0, 0.46

        latencies: List[float] = []
        fps_samples: List[float] = []
        failures = 0

        for _ in range(trials_per_condition):
            if using_live:
                telem = orchestrator.sample_app_telemetry(package_name=package_name)
                lat = float(telem.get("ui_delay_ms") or 0.0)
                fps = float(telem.get("fps") if telem.get("fps") is not None else 60.0)
                is_failure = bool(telem.get("anr_flag") or telem.get("error_count", 0) > 0)
            else:
                lat = max(20.0, base_rtt + rng.gauss(0, base_rtt * 0.18))
                fps = max(10.0, min(60.0, base_fps + rng.gauss(0, 3.5)))
                is_failure = rng.random() < fail_prob

            latencies.append(round(lat, 2))
            fps_samples.append(round(fps, 2))
            if is_failure:
                failures += 1

        latency_samples_by_cond[cond] = latencies
        avg_lat = sum(latencies) / len(latencies)
        p95_lat = sorted(latencies)[min(len(latencies) - 1, int(0.95 * len(latencies)))]
        avg_fps = sum(fps_samples) / len(fps_samples)
        fail_rate = (failures / trials_per_condition) * 100.0

        t_stat, p_t = (0.0, 1.0)
        if cond != "1_BASELINE_NOMINAL":
            u_stat, p_val = mann_whitney_u(latency_samples_by_cond["1_BASELINE_NOMINAL"], latencies)
            t_stat, p_t = paired_t_test(latency_samples_by_cond["1_BASELINE_NOMINAL"], latencies)

        results[cond] = {
            "evaluation_mode": eval_mode,
            "mean_latency_ms": round(avg_lat, 2),
            "p95_latency_ms": round(p95_lat, 2),
            "mean_fps": round(avg_fps, 2),
            "jank_frame_drop_pct": round(((60.0 - avg_fps) / 60.0) * 100.0, 2),
            "failure_rate_pct": round(fail_rate, 2),
            "total_failures": failures,
            "mann_whitney_u": u_stat,
            "p_value": p_val,
            "paired_t_stat": t_stat,
            "p_value_paired_t": p_t,
            "statistically_significant_p05": bool(p_val < 0.05) if cond != "1_BASELINE_NOMINAL" else None
        }

    orchestrator.reset_all()

    os.makedirs("results", exist_ok=True)
    out_file = os.path.join("results", "experiment_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 96)
    print(f"  EMPIRICAL EVALUATION SUMMARY RESULTS ({eval_mode})")
    print("=" * 96)
    print(f"{'Condition':<24} | {'Mean RTT(ms)':<12} | {'P95 RTT(ms)':<11} | {'Avg FPS':<8} | {'Fail %':<7} | {'p-value (MW-U)':<14}")
    print("-" * 96)
    for k, v in results.items():
        cond_label = k.split("_", 1)[-1]
        p_disp = "baseline" if k == "1_BASELINE_NOMINAL" else f"{v['p_value']:.2e}"
        print(f"{cond_label:<24} | {v['mean_latency_ms']:<12.1f} | {v['p95_latency_ms']:<11.1f} | {v['mean_fps']:<8.1f} | {v['failure_rate_pct']:<6.1f}% | {p_disp:<14}")
    print("=" * 96)
    print(f"[+] Full empirical evaluation metrics saved to: {out_file}\n")
    return results


if __name__ == "__main__":
    run_evaluation_experiment(trials_per_condition=30)
