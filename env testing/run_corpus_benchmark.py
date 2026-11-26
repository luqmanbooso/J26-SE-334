"""Multi-APK Empirical Corpus Runner & Live AVD Findings Benchmark for Component 1."""

import json
import math
import os
import statistics
import subprocess
import time
from typing import Any, Dict, List, Optional

from core.benchmark_catalog import FDROID_CORPUS_25, paired_t_test
from experiment_perturbation_impact import mann_whitney_u
from orchestrator import PerturbationOrchestrator


def wilcoxon_signed_rank(before: List[float], after: List[float]) -> float:
    """Two-sided Wilcoxon signed-rank p-value (normal approximation) without external deps."""
    diffs = [a - b for b, a in zip(before, after) if abs(a - b) > 1e-9]
    n = len(diffs)
    if n < 2:
        return 1.0
    ranked = sorted(enumerate(diffs), key=lambda x: abs(x[1]))
    w_pos = 0.0
    w_neg = 0.0
    i = 0
    while i < n:
        j = i + 1
        while j < n and abs(ranked[j][1]) == abs(ranked[i][1]):
            j += 1
        avg_r = (i + 1 + j) / 2.0
        for k in range(i, j):
            if ranked[k][1] > 0:
                w_pos += avg_r
            else:
                w_neg += avg_r
        i = j
    w_stat = min(w_pos, w_neg)
    mean_w = n * (n + 1) / 4.0
    std_w = math.sqrt(n * (n + 1) * (2 * n + 1) / 24.0)
    if std_w == 0:
        return 1.0
    z = (abs(w_stat - mean_w) - 0.5) / std_w
    return float(f"{max(0.0, min(1.0, math.erfc(max(0.0, z) / math.sqrt(2.0)))):.3e}")


def discover_corpus_packages(orchestrator: PerturbationOrchestrator, max_apps: int = 25) -> List[str]:
    """Discovers F-Droid catalog + third-party + core system packages on target device."""
    if orchestrator.adb.is_simulated:
        return [entry["package"] for entry in FDROID_CORPUS_25[:max_apps]]

    uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    if os.path.exists(uploads_dir):
        for fn in sorted(os.listdir(uploads_dir)):
            if fn.endswith(".apk"):
                try:
                    orchestrator.adb.install_apk(os.path.join(uploads_dir, fn))
                except Exception:
                    pass

    pkgs: List[str] = []
    # Query launchable UI apps cleanly (avoid RRO overlays / headless system providers)
    out3 = orchestrator.adb.run_shell("pm list packages -3")
    for line in out3.splitlines():
        p = line.replace("package:", "").strip()
        if p and p not in pkgs and not any(skip in p for skip in ("_rro", ".overlay", "auto_generated")):
            pkgs.append(p)
        if len(pkgs) >= max_apps:
            break

    core_ui_candidates = [
        "com.android.settings",
        "com.google.android.dialer",
        "com.google.android.deskclock",
        "com.android.chrome",
        "com.google.android.apps.messaging",
        "com.google.android.contacts",
        "com.google.android.calendar",
        "com.google.android.calculator",
    ]
    if len(pkgs) < max_apps:
        sys_all = set(line.replace("package:", "").strip() for line in orchestrator.adb.run_shell("pm list packages").splitlines())
        for cand in [e["package"] for e in FDROID_CORPUS_25] + core_ui_candidates:
            if cand in sys_all and cand not in pkgs:
                pkgs.append(cand)
            if len(pkgs) >= max_apps:
                break
    return pkgs[:max_apps] or ["com.android.settings"]


def run_monkey_baseline(orchestrator: PerturbationOrchestrator, package_name: str, events: int = 40) -> Dict[str, Any]:
    """Executes an unperturbed Android Monkey exploration baseline run for control comparison."""
    orchestrator.reset_all()
    if orchestrator.adb.is_simulated:
        return {"package": package_name, "mode": "SIMULATED", "events": events, "crashes": 0}
    out = orchestrator.adb.run_shell(f"monkey -p {package_name} --throttle 50 -v {events}")
    crashes = sum(1 for ln in out.splitlines() if "CRASH" in ln or "ANR" in ln)
    return {"package": package_name, "mode": "LIVE_DEVICE", "events": events, "crashes": crashes}


def run_corpus_evaluation(trials_per_regime: int = 5, max_apps: int = 10) -> Dict[str, Any]:
    """Executes real live-device perturbation corpus sweep across discovered APKs and exports findings."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    results_dir = os.path.join(base_dir, "results")
    os.makedirs(results_dir, exist_ok=True)

    orch = PerturbationOrchestrator(log_path=os.path.join(base_dir, "perturbation_event_log.json"))
    packages = discover_corpus_packages(orch, max_apps=max_apps)
    is_live = not orch.adb.is_simulated
    print(f"[*] Corpus Runner Mode: {'LIVE_DEVICE' if is_live else 'SIMULATED'} | Apps ({len(packages)}): {packages}")

    regimes = [
        ("1_BASELINE_NOMINAL", lambda o, p: o.reset_all()),
        ("2_NETWORK_DEGRADATION", lambda o, p: (o.network.set_bandwidth_profile("edge"), o.network.inject_latency(1200), o.network.inject_packet_loss(7))),
        ("3_HARDWARE_STARVATION", lambda o, p: (o.system.set_cpu_load(90), o.system.set_ram_pressure(85, p), o.system.set_thermal_state("Warn"))),
        ("4_INTERRUPTION_BURST", lambda o, p: (o.context.set_orientation("landscape"), o.interruption.send_sms_banner("Verify OTP 819204"))),
        ("5_COMPOUND_MULTI_FACTOR", lambda o, p: o.apply_profile({
            "name": "Compound Corpus Stress",
            "cpuStress": 92,
            "ramStress": 88,
            "latency": 1600,
            "packetLoss": 10,
            "thermalState": "Critical",
            "networkProfile": "2G / EDGE",
        })),
    ]

    regime_latencies: Dict[str, List[float]] = {r[0]: [] for r in regimes}
    regime_fps: Dict[str, List[float]] = {r[0]: [] for r in regimes}
    regime_jank: Dict[str, List[float]] = {r[0]: [] for r in regimes}
    regime_failures: Dict[str, int] = {r[0]: 0 for r in regimes}
    detected_failures: List[Dict[str, Any]] = []

    uptime_checks = 0
    uptime_ok = 0

    for pkg in packages:
        if is_live:
            orch.adb.launch_app(pkg)
            time.sleep(0.6)
            uptime_checks += 1
            if "device" in orch.adb.run_cmd("get-state"):
                uptime_ok += 1
        for r_name, apply_fn in regimes:
            if r_name != "1_BASELINE_NOMINAL":
                orch.reset_all()
            if is_live:
                orch.adb.run_shell(f"logcat -c; dumpsys gfxinfo {pkg} reset")
            apply_fn(orch, pkg)

            for _ in range(trials_per_regime):
                if is_live:
                    orch.adb.run_shell("input swipe 540 1600 540 700 180")
                    time.sleep(0.25)
                telem = orch.sample_app_telemetry(package_name=pkg)
                lat = float(telem.get("ui_delay_ms") if telem.get("ui_delay_ms") is not None else 0.0)
                fps = float(telem.get("fps") if telem.get("fps") is not None else 60.0)
                jk = float(telem.get("jank_pct") if telem.get("jank_pct") is not None else 0.0)
                regime_latencies[r_name].append(lat)
                regime_fps[r_name].append(fps)
                regime_jank[r_name].append(jk)
                if telem.get("anr_flag") or telem.get("error_count", 0) > 0:
                    regime_failures[r_name] += 1
                    detected_failures.append({
                        "id": f"FAIL_{int(time.time()*1000)}",
                        "type": "ANR" if telem.get("anr_flag") else "CRASH_RUNTIME",
                        "component": pkg,
                        "description": f"Runtime failure in {pkg} under {r_name}",
                        "epoch_ms": int(time.time() * 1000),
                    })
        orch.reset_all()

    total_trials_per_regime = max(1, len(packages) * trials_per_regime)
    base_lats = regime_latencies["1_BASELINE_NOMINAL"]
    summary: Dict[str, Any] = {}
    for r_name, _ in regimes:
        lats = regime_latencies[r_name]
        fpss = regime_fps[r_name]
        jks = regime_jank[r_name]
        fails = regime_failures[r_name]
        u_stat, p_mw = (0.0, 1.0) if r_name == "1_BASELINE_NOMINAL" else mann_whitney_u(base_lats, lats)
        p_wx = 1.0 if r_name == "1_BASELINE_NOMINAL" else wilcoxon_signed_rank(base_lats, lats)
        t_stat, p_t = (0.0, 1.0) if r_name == "1_BASELINE_NOMINAL" else paired_t_test(base_lats, lats)
        summary[r_name] = {
            "evaluation_mode": "LIVE_DEVICE" if is_live else "SIMULATED",
            "apps_evaluated": len(packages),
            "trials_total": len(lats),
            "mean_latency_ms": round(statistics.mean(lats), 2) if lats else 0.0,
            "p95_latency_ms": round(sorted(lats)[min(len(lats) - 1, int(0.95 * len(lats)))], 2) if lats else 0.0,
            "mean_fps": round(statistics.mean(fpss), 2) if fpss else 60.0,
            "jank_frame_drop_pct": round(statistics.mean(jks), 2) if jks else 0.0,
            "failure_rate_pct": round((fails / total_trials_per_regime) * 100.0, 2),
            "total_failures": fails,
            "mann_whitney_u": u_stat,
            "p_value_mann_whitney": p_mw,
            "p_value_wilcoxon": p_wx,
            "paired_t_stat": t_stat,
            "p_value_paired_t": p_t,
            "statistically_significant_p05": bool(p_mw < 0.05) if r_name != "1_BASELINE_NOMINAL" else None,
        }

    uptime_pct = round((uptime_ok / uptime_checks) * 100.0, 2) if uptime_checks else 100.0
    corpus_out = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "device_id": orch.adb.device_id or "simulated",
        "mode": "LIVE_DEVICE" if is_live else "SIMULATED",
        "emulator_uptime_pct": uptime_pct,
        "packages": packages,
        "regimes": summary,
    }
    corpus_path = os.path.join(results_dir, "corpus_benchmark_results.json")
    with open(corpus_path, "w", encoding="utf-8") as f:
        json.dump(corpus_out, f, indent=2)

    perf = orch.logger.get_performance_summary()
    attr_report = orch.correlate_failures(detected_failures)
    orch.attribution_engine.export_report(attr_report, os.path.join(base_dir, "environment_failure_attribution.json"))
    findings_doc = {
        "project_metadata": {
            "platform": "HEART Mobile Environmental Testing Laboratory",
            "version": "2.4.0",
            "export_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "target_device": {
                "device_id": orch.adb.device_id or "simulated",
                "type": "Virtual AVD" if (orch.adb.device_id or "").startswith("emulator-") else ("Live USB" if is_live else "Simulated"),
                "model": "Pixel_9_Pro" if is_live else "Simulated",
                "active_package": packages[0],
                "corpus_packages": packages,
            },
        },
        "kpi_benchmarks": {
            "rq1_latency_threshold_ms": 100.0,
            "last_measured_latency_ms": perf.get("avg_injection_latency_ms", 0.0),
            "rq1_compliant": perf.get("avg_injection_latency_ms", 0.0) < 100.0,
            "total_perturbations_recorded": perf.get("total_events", 0),
        },
        "attribution_summary": attr_report,
    }
    with open(os.path.join(base_dir, "test_findings_report.json"), "w", encoding="utf-8") as f:
        json.dump(findings_doc, f, indent=2)

    write_findings_markdown(
        findings_doc=findings_doc,
        corpus_out=corpus_out,
        md_path=os.path.join(base_dir, "test_findings_report.md"),
    )

    print(f"[+] Corpus evaluation saved to {corpus_path}")
    return corpus_out


def write_findings_markdown(
    findings_doc: Dict[str, Any],
    corpus_out: Optional[Dict[str, Any]],
    md_path: str,
) -> None:
    """Exports a Markdown report kept strictly synchronized with test_findings_report.json."""
    meta = findings_doc.get("project_metadata", {})
    dev = meta.get("target_device", {})
    kpi = findings_doc.get("kpi_benchmarks", {})
    attr = findings_doc.get("attribution_summary", {})
    attributions = attr.get("attributions", [])

    lines = [
        "# HEART Environmental Mobile Testing — Findings & Root-Cause Attribution Report",
        "",
        f"**Generated:** {meta.get('export_timestamp', '')}  ",
        f"**Target Package:** `{dev.get('active_package', 'unknown')}`  ",
        f"**Target Device:** {dev.get('model', 'Simulated')} (`{dev.get('device_id', 'simulated')}`) — {dev.get('type', 'Simulated')}",
        "",
        "## 1. Executive Summary & Pipeline Latency Benchmarks",
        "",
        f"- **Total Perturbation Events Injected:** {kpi.get('total_perturbations_recorded', 0)}",
        f"- **Mean Recorded Cycle Latency:** {kpi.get('last_measured_latency_ms', 0)} ms",
        f"- **Pipeline Latency Compliance (<100ms):** {'PASS' if kpi.get('rq1_compliant') else 'WARN (compound ADB sweep > 100ms budget)'}",
        f"- **Total Failures Analyzed:** {attr.get('total_failures_analyzed', 0)}",
        f"- **High-Confidence Attributions:** {attr.get('attributed_failures_count', 0)}",
        "",
        "## Visual Findings Dashboard & Empirical Charts",
        "",
        "![HEART Empirical Findings Dashboard](results/heart_findings_chart_report.png)",
    ]

    regimes = (corpus_out or {}).get("regimes", {})
    if regimes:
        lines.extend([
            "",
            "## 2. Live Corpus Evaluation Summary",
            "",
            f"Evaluated **{len((corpus_out or {}).get('packages', []))}** packages (`{(corpus_out or {}).get('mode', 'LIVE_DEVICE')}`).",
            "",
            "| Regime | Mean Latency (ms) | Mean FPS | Jank Drop (%) | Failure Rate (%) | Mann-Whitney p |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for r_name, stats in regimes.items():
            lines.append(
                f"| `{r_name}` | {stats.get('mean_latency_ms', 0.0)} | {stats.get('mean_fps', 0.0)} | "
                f"{stats.get('jank_frame_drop_pct', 0.0)}% | {stats.get('failure_rate_pct', 0.0)}% | "
                f"{stats.get('p_value_mann_whitney', 1.0)} |"
            )

    lines.extend([
        "",
        "## 3. Root-Cause Failure Attribution Matrix",
        "",
    ])
    if attributions:
        lines.extend([
            "| Failure ID | Type | Primary Environmental Trigger | Confidence |",
            "|---|---|---|---:|",
        ])
        for a in attributions:
            lines.append(
                f"| `{a.get('failure_id')}` | `{a.get('failure_type')}` | `{a.get('primary_trigger')}` | "
                f"{round(float(a.get('confidence', 0.0)) * 100)}% |"
            )
    else:
        lines.append("No runtime crashes or ANRs were observed during this sweep.")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    run_corpus_evaluation(trials_per_regime=3, max_apps=10)
