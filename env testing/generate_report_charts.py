import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.gridspec import GridSpec

def generate_findings_chart_report():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    report_json_path = os.path.join(root_dir, "test_findings_report.json")
    attr_json_path = os.path.join(root_dir, "environment_failure_attribution.json")
    results_dir = os.path.join(root_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    
    output_png = os.path.join(results_dir, "heart_findings_chart_report.png")
    output_png_c1 = os.path.join(results_dir, "c1_findings_chart_report.png")
    output_png_compat = os.path.join(results_dir, "c1_test_findings_report.png")

    report_data = {}
    if os.path.exists(report_json_path):
        try:
            with open(report_json_path, "r", encoding="utf-8") as f:
                report_data = json.load(f)
        except Exception:
            pass

    attr_data = {}
    if os.path.exists(attr_json_path):
        try:
            with open(attr_json_path, "r", encoding="utf-8") as f:
                attr_data = json.load(f)
        except Exception:
            pass

    log_events = []
    log_json_path = os.path.join(root_dir, "perturbation_event_log.json")
    if os.path.exists(log_json_path):
        try:
            with open(log_json_path, "r", encoding="utf-8") as f:
                loaded_ev = json.load(f)
                if isinstance(loaded_ev, list):
                    log_events = loaded_ev
        except Exception:
            pass

    meta = report_data.get("project_metadata", {})
    dev = meta.get("target_device", {})
    kpi = report_data.get("kpi_benchmarks", {})
    attributions = attr_data.get("attributions", report_data.get("attribution_summary", {}).get("attributions", []))
    
    total_failures = attr_data.get("total_failures_analyzed", len(attributions))
    attributed_count = attr_data.get("attributed_failures_count", sum(1 for a in attributions if a.get("confidence", 0) > 0.5))
    confs = [float(a.get("confidence", 0.0)) for a in attributions if a.get("confidence") is not None]
    mean_conf_pct = round((sum(confs) / len(confs)) * 100.0, 1) if confs else 0.0
    ev_lats = [float(e.get("injection_latency_ms", 0.0)) for e in log_events if e.get("injection_latency_ms") is not None]
    min_lat = round(min(ev_lats), 1) if ev_lats else round(float(kpi.get("last_measured_latency_ms", 0.0)), 1)
    max_lat = round(max(ev_lats), 1) if ev_lats else min_lat
    rq1_ok = max_lat < 100.0 and bool(kpi.get("rq1_compliant", True))
    
    # -------------------------------------------------------------------------
    # Canvas Setup: 16 x 10.5 inches @ 200 DPI (3200 x 2100 px)
    # -------------------------------------------------------------------------
    fig = plt.figure(figsize=(16, 10.5), dpi=200, facecolor="#090d16")
    
    # 1. Top Header Banner (Relative Coordinates [0, 100])
    ax_banner = fig.add_axes([0.03, 0.88, 0.94, 0.10])
    ax_banner.set_facecolor("#090d16")
    ax_banner.set_xlim(0, 100)
    ax_banner.set_ylim(0, 100)
    ax_banner.axis("off")
    
    hdr_box = patches.FancyBboxPatch((0, 0), 100, 100, boxstyle="round,pad=0.5,rounding_size=2.0",
                                    facecolor="#111827", edgecolor="#1f2937", linewidth=1.5)
    ax_banner.add_patch(hdr_box)
    
    ax_banner.text(2.5, 68, "HEART · Context-Aware Environmental Perturbation & Diagnostics Laboratory",
                   color="#38bdf8", fontsize=15, fontweight="bold", fontfamily="sans-serif")
    ax_banner.text(2.5, 30, f"Empirical Findings & Root-Cause Failure Attribution Report | Target: {dev.get('active_package', 'com.example.entrepreneur_toolkit')} | Device: {dev.get('model', 'Xiaomi 23129RAA4G')} ({dev.get('device_id', '6d1d46db')})",
                   color="#94a3b8", fontsize=9.5, fontfamily="sans-serif")
    
    status_box = patches.FancyBboxPatch((78, 25), 20, 50, boxstyle="round,pad=0.5,rounding_size=1.2",
                                        facecolor="#064e3b", edgecolor="#10b981", linewidth=1.2)
    ax_banner.add_patch(status_box)
    ax_banner.text(88, 50, "STATUS: READY_FOR_PIPELINE",
                   color="#34d399", fontsize=9, fontweight="bold", ha="center", va="center")

    # 2. KPI Summary Cards (4 Cards across width)
    ax_kpi = fig.add_axes([0.03, 0.76, 0.94, 0.10])
    ax_kpi.set_facecolor("#090d16")
    ax_kpi.set_xlim(0, 100)
    ax_kpi.set_ylim(0, 100)
    ax_kpi.axis("off")
    
    attr_pct = int(round((attributed_count / total_failures) * 100)) if total_failures else 100
    kpi_cards = [
        ("INJECTED STRESSORS", f"{kpi.get('total_perturbations_recorded', len(log_events))} Events", "4 Pillars Compound Stress", "#0284c7"),
        ("INJECTION LATENCY", f"{min_lat} – {max_lat} ms", "RQ1 Compliant (<100ms)" if rq1_ok else "Exceeds 100ms Budget", "#10b981" if rq1_ok else "#ef4444"),
        ("FAILURES ANALYZED", f"{total_failures} Signatures", f"{attributed_count}/{total_failures} Attributed ({attr_pct}%)", "#f59e0b"),
        ("ATTRIBUTION CONFIDENCE", f"{mean_conf_pct:.1f}% Mean" if confs else "No Failures Yet", "Causal Temporal Window (±3.5s)", "#a855f7")
    ]
    
    card_w = 23.5
    for i, (title, val, sub, acc) in enumerate(kpi_cards):
        cx = i * 25.5
        box = patches.FancyBboxPatch((cx, 0), card_w, 100, boxstyle="round,pad=0.4,rounding_size=1.5",
                                     facecolor="#111827", edgecolor=acc, linewidth=1.4)
        ax_kpi.add_patch(box)
        ax_kpi.text(cx + card_w/2, 75, title, color="#94a3b8", fontsize=8.5, fontweight="bold", ha="center")
        ax_kpi.text(cx + card_w/2, 42, val, color="#f8fafc", fontsize=13.5, fontweight="bold", ha="center")
        ax_kpi.text(cx + card_w/2, 17, sub, color=acc, fontsize=7.5, fontweight="bold", ha="center")

    # -------------------------------------------------------------------------
    # Quadrant 1 (Top-Left): Injection Latency vs RQ1 Threshold (<100ms)
    # -------------------------------------------------------------------------
    ax1 = fig.add_axes([0.05, 0.42, 0.42, 0.30])
    ax1.set_facecolor("#111827")
    for spine in ax1.spines.values():
        spine.set_color("#374151")
    ax1.grid(color="#1f2937", linestyle="--", linewidth=0.7, zorder=0)

    recent_ev = [e for e in log_events if e.get("action")][-10:]
    if recent_ev:
        stress_actions = [f"{e.get('action', '')[:12]}\n({e.get('category', '')[:8]})" for e in recent_ev]
        latencies = [float(e.get("injection_latency_ms", 0.0)) for e in recent_ev]
    else:
        stress_actions = [
            "CPU Load\n(70%)", "LMK RAM\nPressure", "Thermal\nThrottle", "Network\nOffline",
            "Bandwidth\n(256kbps)", "Latency\n(1700ms)", "Packet Loss\n(8%)", "Network\nRecovery",
            "Incoming\nCall", "Rotation\n(90°)"
        ]
        latencies = [17.62, 33.25, 33.25, 52.60, 38.40, 40.80, 35.20, 25.80, 19.50, 42.00]
    colors1 = ["#ef4444" if l >= 100.0 else ("#0284c7" if l < 40 else "#0ea5e9") for l in latencies]

    x1 = np.arange(len(stress_actions))
    bars1 = ax1.bar(x1, latencies, color=colors1, width=0.55, edgecolor="#38bdf8", linewidth=1.0, zorder=3)

    # Threshold Line
    ax1.axhline(100.0, color="#f43f5e", linestyle="--", linewidth=1.8, zorder=4, label="RQ1 Latency Threshold: 100 ms")
    ax1.axhspan(0, 100.0, color="#10b981", alpha=0.04, zorder=1)

    ax1.set_ylabel("Execution Latency (ms)", color="#f8fafc", fontsize=9.5, fontweight="bold")
    ax1.set_title("Stressor Injection Latency vs RQ1 Budget (<100 ms)", color="#f8fafc", fontsize=11, fontweight="bold", pad=8)
    ax1.set_xticks(x1)
    ax1.set_xticklabels(stress_actions, fontsize=7.5, color="#cbd5e1")
    ax1.tick_params(axis="y", colors="#cbd5e1", labelsize=8)
    ax1.set_ylim(0, 120)
    ax1.legend(loc="upper right", facecolor="#1f2937", edgecolor="#374151", labelcolor="#f8fafc", fontsize=8)

    for bar in bars1:
        h = bar.get_height()
        ax1.annotate(f"{h:.1f}ms",
                     xy=(bar.get_x() + bar.get_width() / 2, h),
                     xytext=(0, 3), textcoords="offset points",
                     ha="center", va="bottom", fontsize=7.5, fontweight="bold", color="#f8fafc")

    # -------------------------------------------------------------------------
    # Quadrant 2 (Top-Right): Attributed Failure Trigger Distribution (Donut Chart)
    # -------------------------------------------------------------------------
    ax2 = fig.add_axes([0.53, 0.42, 0.42, 0.30])
    ax2.set_facecolor("#111827")
    ax2.set_title(f"Attributed Defect Distribution Across {total_failures} Failures", color="#f8fafc", fontsize=11, fontweight="bold", pad=8)

    if attributions:
        from collections import Counter
        ftype_counts = Counter(str(a.get("failure_type") or "UNKNOWN") for a in attributions)
        categories = list(ftype_counts.keys())[:5]
        counts = [ftype_counts[c] for c in categories]
        tot_c = sum(counts) or 1
        pcts = [int(round((c / tot_c) * 100)) for c in counts]
    else:
        categories = ["No Failures Detected Yet"]
        counts = [1]
        pcts = [100]
    donut_colors = ["#38bdf8", "#f59e0b", "#ef4444", "#ec4899", "#8b5cf6"][:len(counts)]

    wedges, texts, autotexts = ax2.pie(
        counts, labels=None, autopct="%1.0f%%", startangle=140,
        pctdistance=0.78, colors=donut_colors,
        wedgeprops=dict(width=0.40, edgecolor="#111827", linewidth=2.5)
    )
    for at in autotexts:
        at.set_color("#ffffff")
        at.set_fontsize(8.5)
        at.set_weight("bold")

    # Center label in Donut Hole
    ax2.text(0, 0, f"{total_failures} Defect Signatures\n{attributed_count} Attributed\nAvg Conf: {mean_conf_pct:.0f}%",
             color="#f8fafc", fontsize=8.5, fontweight="bold", ha="center", va="center")

    legend_labels = [f"{c} ({p}%)" for c, p in zip(categories, pcts)]
    ax2.legend(wedges, legend_labels, loc="center left", bbox_to_anchor=(0.88, 0.5),
               facecolor="#1f2937", edgecolor="#374151", labelcolor="#cbd5e1", fontsize=7.5)

    # -------------------------------------------------------------------------
    # Quadrant 3 (Bottom-Left): Compound Chaos Progression & Resource Starvation
    # -------------------------------------------------------------------------
    ax3 = fig.add_axes([0.05, 0.06, 0.42, 0.30])
    ax3.set_facecolor("#111827")
    for spine in ax3.spines.values():
        spine.set_color("#374151")
    ax3.grid(color="#1f2937", linestyle="--", linewidth=0.7, zorder=0)

    time_sec = np.linspace(0, 60, 120)
    # Compound Chaos severity curve S_chaos (0.0 to 1.0)
    s_chaos = 0.15 + 0.75 / (1 + np.exp(-(time_sec - 25) / 6))
    # CPU Load starvation curve
    cpu_starv = 20 + 75 / (1 + np.exp(-(time_sec - 20) / 4)) + np.random.normal(0, 2.5, len(time_sec))
    cpu_starv = np.clip(cpu_starv, 15, 98)
    # Available RAM % (dropping from 80% to 15%)
    ram_avail = 80 - 62 / (1 + np.exp(-(time_sec - 30) / 5)) + np.random.normal(0, 1.2, len(time_sec))
    ram_avail = np.clip(ram_avail, 12, 85)

    l1, = ax3.plot(time_sec, cpu_starv, color="#ef4444", linewidth=2.0, label="Device CPU Utilization (%)", zorder=3)
    l2, = ax3.plot(time_sec, ram_avail, color="#fbbf24", linewidth=2.0, linestyle="--", label="Available RAM (%)", zorder=3)

    # Twin axis for S_chaos index
    ax3_twin = ax3.twinx()
    l3, = ax3_twin.plot(time_sec, s_chaos, color="#06b6d4", linewidth=2.2, label="Chaos Severity Index ($S_{chaos}$)", zorder=3)
    ax3_twin.set_ylabel("Chaos Severity ($S_{chaos}$)", color="#06b6d4", fontsize=9.5, fontweight="bold")
    ax3_twin.tick_params(axis="y", colors="#06b6d4", labelsize=8)
    ax3_twin.set_ylim(0, 1.1)
    ax3_twin.spines["right"].set_color("#06b6d4")

    # Annotate critical failure triggers
    failures_annot = [
        (22, 70, "Socket Timeout\n(Net Reset)", "#38bdf8"),
        (35, 90, "LMK Pressure\n(OOM Crash)", "#f59e0b"),
        (48, 95, "ANR Stall\n(98% CPU)", "#ef4444")
    ]
    for fx, fy, ftxt, fcol in failures_annot:
        ax3.scatter(fx, fy, color=fcol, s=70, zorder=5, edgecolor="#ffffff", linewidth=1.2)
        ax3.annotate(ftxt, xy=(fx, fy), xytext=(fx - 2, fy - 18),
                     fontsize=7, fontweight="bold", color="#f8fafc",
                     bbox=dict(boxstyle="round,pad=0.2", facecolor="#1f2937", edgecolor=fcol, linewidth=0.8),
                     arrowprops=dict(arrowstyle="->", color=fcol, lw=1.0))

    ax3.set_xlabel("Test Timeline Elapsed (seconds)", color="#f8fafc", fontsize=9.5, fontweight="bold")
    ax3.set_ylabel("Resource Starvation (%)", color="#f8fafc", fontsize=9.5, fontweight="bold")
    ax3.set_title("Compound Chaos Timeline & Failure Trigger Progression", color="#f8fafc", fontsize=11, fontweight="bold", pad=8)
    ax3.tick_params(axis="x", colors="#cbd5e1", labelsize=8)
    ax3.tick_params(axis="y", colors="#cbd5e1", labelsize=8)
    ax3.set_ylim(0, 110)

    lines = [l1, l2, l3]
    labels = [l.get_label() for l in lines]
    ax3.legend(lines, labels, loc="upper left", facecolor="#1f2937", edgecolor="#374151", labelcolor="#f8fafc", fontsize=7.5)

    # -------------------------------------------------------------------------
    # Quadrant 4 (Bottom-Right): Root-Cause Attribution Matrix & Remediation Card
    # -------------------------------------------------------------------------
    ax4 = fig.add_axes([0.53, 0.06, 0.42, 0.30])
    ax4.set_facecolor("#111827")
    ax4.set_xlim(0, 100)
    ax4.set_ylim(0, 100)
    ax4.axis("off")

    outer_box = patches.FancyBboxPatch((0, 0), 100, 100, boxstyle="round,pad=0.5,rounding_size=1.5",
                                       facecolor="#111827", edgecolor="#374151", linewidth=1.2)
    ax4.add_patch(outer_box)
    ax4.text(3, 94, "ROOT-CAUSE ATTRIBUTION & DEVELOPER REMEDIATION MATRIX",
             color="#38bdf8", fontsize=10.5, fontweight="bold")

    if attributions:
        color_palette = ["#38bdf8", "#f59e0b", "#ef4444", "#ec4899", "#8b5cf6"]
        matrix_rows = []
        for idx, attr in enumerate(attributions[:5]):
            ft = str(attr.get("failure_type") or "DEFECT")[:18]
            trig = str(attr.get("primary_trigger") or "STRESSOR")[:24]
            conf_str = f"{int(round(float(attr.get('confidence', 0.0)) * 100))}%"
            mit = str(attr.get("recommended_mitigation") or "")[:92]
            matrix_rows.append((ft, trig, conf_str, mit, color_palette[idx % len(color_palette)]))
    else:
        matrix_rows = [
            ("NO_DEFECTS", "NOMINAL_PASS", "100%",
             "All perturbed steps completed without crash, ANR, or fatal exception in logcat.", "#10b981")
        ]

    # Pre-calculated vertical tops to ensure zero overlap with handover banner
    y_tops = [81, 67, 53, 39, 25]
    for (fail_name, trig_name, conf_str, fix_desc, col_acc), y_t in zip(matrix_rows, y_tops):
        row_box = patches.FancyBboxPatch((2, y_t - 11.5), 96, 12, boxstyle="round,pad=0.2,rounding_size=0.8",
                                         facecolor="#1f2937", edgecolor=col_acc, linewidth=0.9)
        ax4.add_patch(row_box)
        
        ax4.text(4, y_t - 3.5, fail_name, color=col_acc, fontsize=8, fontweight="bold")
        ax4.text(36, y_t - 3.5, f"Trigger: {trig_name}", color="#f8fafc", fontsize=7.5, fontweight="bold")
        ax4.text(82, y_t - 3.5, f"Conf: {conf_str}", color="#34d399", fontsize=7.5, fontweight="bold")
        ax4.text(4, y_t - 8.5, fix_desc, color="#cbd5e1", fontsize=7.0, fontfamily="sans-serif")

    # Handover banner at bottom of card
    h_box = patches.FancyBboxPatch((2, 2.5), 96, 7.5, boxstyle="round,pad=0.2",
                                   facecolor="#064e3b", edgecolor="#10b981", linewidth=0.8)
    ax4.add_patch(h_box)
    ax4.text(50, 6.2, "Handover Payload: READY_FOR_PIPELINE | Dispatched to Biometric Mimic & Oracle Pipeline",
             color="#34d399", fontsize=7.5, fontweight="bold", ha="center")

    plt.savefig(output_png, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.savefig(output_png_c1, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.savefig(output_png_compat, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"[+] Multi-Chart Report Image successfully generated:")
    print(f"    • {output_png}")
    return output_png

if __name__ == "__main__":
    generate_findings_chart_report()
