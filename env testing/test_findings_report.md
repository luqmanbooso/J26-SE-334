# HEART Environmental Mobile Testing — Findings & Root-Cause Attribution Report

**Generated:** 2026-11-26T17:02:14Z  
**Target Package:** `codes.swistak.batterymonitor`  
**Target Device:** Pixel_9_Pro (`emulator-5554`) — Virtual AVD

## 1. Executive Summary & Pipeline Latency Benchmarks

- **Total Perturbation Events Injected:** 1280
- **Mean Recorded Cycle Latency:** 733.13 ms
- **Pipeline Latency Compliance (<100ms):** WARN (compound ADB sweep > 100ms budget)
- **Total Failures Analyzed:** 0
- **High-Confidence Attributions:** 0

## Visual Findings Dashboard & Empirical Charts

![HEART Empirical Findings Dashboard](results/heart_findings_chart_report.png)

## 2. Live Corpus Evaluation Summary

Evaluated **20** packages (`LIVE_DEVICE`).

| Regime | Mean Latency (ms) | Mean FPS | Jank Drop (%) | Failure Rate (%) | Mann-Whitney p |
|---|---:|---:|---:|---:|---:|
| `1_BASELINE_NOMINAL` | 1184.05 | 10.17 | 93.81% | 0.0% | 1.0 |
| `2_NETWORK_DEGRADATION` | 3018.67 | 40.44 | 37.74% | 0.0% | 0.02352 |
| `3_HARDWARE_STARVATION` | 3003.55 | 40.77 | 36.6% | 0.0% | 0.03325 |
| `4_INTERRUPTION_BURST` | 1276.1 | 19.15 | 77.18% | 0.0% | 0.02093 |
| `5_COMPOUND_MULTI_FACTOR` | 1816.18 | 26.44 | 64.62% | 0.0% | 0.255 |

## 3. Root-Cause Failure Attribution Matrix

No runtime crashes or ANRs were observed during this sweep.
