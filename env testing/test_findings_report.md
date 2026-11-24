# HEART Environmental Mobile Testing — Findings & Root-Cause Attribution Report

**Generated:** 2026-11-01T10:41:05Z  
**Target Package:** `codes.swistak.batterymonitor`  
**Target Device:** Pixel_9_Pro (`emulator-5554`) — Virtual AVD

## 1. Executive Summary & Pipeline Latency Benchmarks

- **Total Perturbation Events Injected:** 17
- **Last Action Latency:** 827.89 ms
- **Pipeline Latency Compliance (<100ms):** ⚠️ WARN
- **Total Failures Analyzed:** 1
- **High-Confidence Attributions:** 1

## Visual Findings Dashboard & Empirical Charts

![HEART Empirical Findings Dashboard](results/heart_findings_chart_report.png)

## 2. Root-Cause Failure Attribution Matrix

| Failure ID | Type | Primary Environmental Trigger | Confidence | Impacted Module / Package |
|---|---|---|---|---|
| `EVAL_1793529665511` | `TIMEOUT` | `PACKET_LOSS_SIMULATED` | 94% | `codes.swistak.batterymonitor` |


## 3. Detailed Root-Cause Analysis & Actionable Mitigations

### 1. Failure `EVAL_1793529665511` (TIMEOUT)
- **Primary Stressor:** `PACKET_LOSS_SIMULATED` (Confidence: 94%)
- **Compound Stress Factors:** SYSTEM_POWER:BATTERY_PRESSURE, SYSTEM_CPU:CPU_LOAD_INJECTED, SYSTEM_CPU:CPU_LOAD_INJECTED, NETWORK_THROTTLE:BANDWIDTH_PROFILE_SET, NETWORK_THROTTLE:BANDWIDTH_PROFILE_SET, NETWORK:STATE_TRANSITION, NETWORK:NETWORK_RESET_NOMINAL, NETWORK_LATENCY:LATENCY_INJECTED, NETWORK_LATENCY:LATENCY_INJECTED, NETWORK_PACKET_LOSS:PACKET_LOSS_SIMULATED, INTERRUPTION_CALL:INCOMING_CALL_RINGING, INTERRUPTION_SMS:SMS_NOTIFICATION_BANNER
- **Root Cause Explanation:** Network failure directly triggered by PACKET_LOSS_SIMULATED (params: {'loss_pct': 40, 'strategy': 'BURST_DROP'}). App failed to recover gracefully.
- **Recommended Developer Mitigation:** Audit error boundaries and add fallback UI indicators during environmental fluctuations.

## 4. Downstream Subsystem Handover Payload

```json
{
  "status": "READY_FOR_PIPELINE",
  "detected_failures": 1,
  "attributed_causes": 1,
  "recommended_mitigations": [
    "Audit error boundaries and add fallback UI indicators during environmental fluctuations."
  ]
}
```
