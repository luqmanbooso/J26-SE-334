# Component 1: Context-Aware Environmental Perturbation Engine

**Student:** Chanlaka G.L.S. (IT23151260)  
**Supervisor:** Prof. Dilshan De Silva  
**Co-Supervisor:** Mr. Dinal Senadheera  
**Research Project:** J26-SE-334 — Human Behavior-Aware Robustness Testing Framework for Mobile Applications (HEART)  
**Domain:** Software Systems & Technologies (SST)

---

## Overview

Modern mobile apps operate in highly unpredictable physical environments subject to fluctuating networks, background resource contention, and OS interruptions. Traditional mobile testing suites execute inside sanitized, static environments, failing to capture environment-induced edge cases and non-crash functional degradations.

The **Context-Aware Environmental Perturbation Engine** systematically orchestrates and injects synchronized environmental stressors into the test loop based on runtime state and semantic test steps, outputting structured perturbation event logs correlated to application failures.

### Key Research Novelty & Proposal Targets
1. **Semantic Test-Step Synchronization:** Rather than static context fuzzing, perturbations are injected at semantically critical moments within live test flows (e.g., WiFi $\leftrightarrow$ Mobile Data handover mid-transaction, battery drop during checkout).
2. **Adaptive Performance Feedback Loop:** Dynamically observes runtime performance signals (FPS drops, frame lag, network RTT surges) and adaptively escalates stress conditions.
3. **Environment-to-Failure Attribution Engine:** Correlates high-precision timestamped perturbation event logs with crash, ANR, and non-crash GUI defects to output root-cause attribution reports.
4. **Dual Hardware/Virtual Bridge:** Seamlessly drives physical Android devices/emulators via ADB, or falls back to a high-fidelity Virtual Device Simulator when running in decoupled environments.
5. **Strict Overhead & Latency Thresholds:** Guaranteed injection latency < 100 ms and host system overhead < 15% (avoiding emulator destabilization).
6. **Empirical Defect Exposure Gain:** Achieves >30% increase in defect detection rate on curated F-Droid and Themis benchmark apps.

---

## Architecture & Directory Structure

```text
env testing/
├── core/
│   ├── base.py                         # Base perturbation stressor abstraction (BaseStressor)
│   ├── adb_client.py                   # Hardware ADB bridge & virtual device fallback
│   ├── event_logger.py                 # Telemetry logger with latency (<100ms) & overhead (<15%) tracking
│   ├── profile_parser.py               # YAML & JSON schema validator per Proposal Section 5
│   └── scheduler.py                    # Semantic step hooks & adaptive signal escalation scheduler
├── profiles/                           # Standard YAML environmental stress scenario configurations
│   ├── 3g_network_drop.yaml            # 3G high-latency & packet loss scenario
│   ├── high_cpu_stress.yaml            # CPU starvation profile (up to 92%)
│   ├── thermal_throttling_battery_drain.yaml # Critical thermal state & 3% battery drop
│   ├── aggressive_multitasking_backgrounding.yaml # OS interruptions & call bursts
│   └── compound_multi_factor_chaos.yaml # Compound multi-vector chaos scenario
├── stressors/
│   ├── system_stressor.py              # CPU load (up to 98%), RAM/LMK trim pressure, disk I/O, battery & thermal
│   ├── device_stressor.py              # Backward-compatible alias for system_stressor
│   ├── network_stressor.py             # Bandwidth throttle, latency (Netem), packet loss, DNS fail & handovers
│   ├── interruption_stressor.py        # GSM calls, SMS push banners, app backgrounding, Doze & Standby
│   └── context_stressor.py             # Display orientation, dark theme, accessibility font scale, GPS
├── orchestrator.py                     # Central coordinator uniting all stressors, scheduling & attribution
├── attribution_engine.py               # Environment-induced failure attribution & correlation engine
├── run_live_suite.py                   # 7-stage live execution test suite
├── experiment_perturbation_impact.py   # Empirical evaluation benchmark across 5 stress regimes
├── test_themis_app_chaos.py            # Targeted test runner against Themis benchmark app scenarios
├── generate_research_charts.py         # Publication chart generator (Figures 1, 2, 3)
├── server.py                           # FastAPI REST server bridging engine to React dashboard
├── start_c1_demo.bat                   # One-click presentation launcher
├── tests/                              # Automated Pytest suite (100% green pass)
│   ├── test_stressors.py               # Unit tests for hardware, network, and interruption stressors
│   ├── test_scheduler.py               # Unit tests for semantic hooks & adaptive signals
│   └── test_attribution.py             # Unit tests for failure attribution engine
├── perturbation_event_log.json         # Timestamped perturbation audit log
├── results/
│   ├── experiment_results.json         # Empirical benchmark evaluation metrics
│   ├── fig1_latency_and_framerate.png  # Figure 1: Dual-axis latency vs framerate
│   ├── fig2_failure_rate_comparison.png# Figure 2: Defect exposure rate comparison
│   └── fig3_jank_frame_drop.png        # Figure 3: Non-crash GUI jank frame drop
└── requirements.txt                    # Component dependencies
```

---

## Features & Capabilities

| Module | Perturbation Capabilities | Mechanism / Commands |
|---|---|---|
| **Hardware Starvation** | CPU load spikes (10% - 98%), RAM pressure / LMK, Disk I/O saturation, Battery level & thermal throttling | `sh stress loops`, `am send-trim-memory`, `dd bs=1M`, `dumpsys battery` |
| **Network Chaos** | 2G/EDGE/LTE bandwidth throttling, RTT latency (100ms - 10,000ms), packet loss (0% - 25%), DNS failure, WiFi $\leftrightarrow$ Cellular handovers | `network speed`, `network delay`, `cmd connectivity airplane-mode`, `svc wifi/data` |
| **Interruptions** | Ringing/accepting/declining incoming calls, SMS heads-up notifications, App backgrounding & resume, Doze mode & App Standby | `gsm call/cancel`, `sms send`, `input keyevent 3/5/6`, `dumpsys deviceidle force-idle` |
| **Context Fuzzing** | Portrait/Landscape/Reverse rotation, System dark mode, Accessibility font scaling (1.0x - 1.35x), GPS location shifts | `settings put user_rotation`, `cmd uimode night`, `settings put font_scale`, `geo fix` |
| **Dynamic Scheduler** | Hooks perturbations to semantic steps (`MID_TRANSACTION`, `ASYNC_WAIT`) and escalates stress on FPS drop | `PerturbationScheduler` with runtime signal thresholds |
| **Failure Attribution** | Correlates failure occurrences with proximate stressors within causal time windows | `EnvironmentAttributionEngine` generating confidence scores |

---

## Empirical Evaluation Benchmark Results

Tested across 5 environmental regimes ($N = 30$ trials per condition):

| Condition | Mean RTT Latency | P95 Latency | Mean FPS | Jank / Frame Drop % | Failure Rate % |
|---|---|---|---|---|---|
| **1. Baseline Nominal** | 66.3 ms | 91.3 ms | 58.5 FPS | 2.5% | **0.0%** |
| **2. Network Degradation** | 1,334.4 ms | 1,715.8 ms | 53.4 FPS | 11.0% | **13.3%** |
| **3. Hardware Starvation** | 178.7 ms | 225.3 ms | 31.7 FPS | 47.2% | **16.7%** |
| **4. Interruption Burst** | 112.8 ms | 144.8 ms | 46.1 FPS | 23.2% | **20.0%** |
| **5. Compound Multi-Factor (C1 Novelty)** | **1,816.8 ms** | **2,400.0 ms** | **23.0 FPS** | **61.7%** | **53.3%** |

Full empirical metrics saved in `results/experiment_results.json`.

---

## Execution & Quality Assurance

### 1. Run Automated Unit Test Suite
```bash
cd "env testing"
pytest tests/ -v
# Output: 7 passed in 0.13s (100% pass)
```

### 2. Generate Publication Figures for Research Paper
```bash
python generate_research_charts.py
# Generates high-res 300 DPI figures in results/:
# - results/fig1_latency_and_framerate.png
# - results/fig2_failure_rate_comparison.png
# - results/fig3_jank_frame_drop.png
```

### 3. Run Themis Benchmark Chaos Test Flow
```bash
python test_themis_app_chaos.py
```

### 4. Run Live 7-Stage Perturbation Suite
```bash
python run_live_suite.py
```

### 5. Launch Full Studio (Backend + UI)
Double-click `start_c1_demo.bat` or run:
```bash
python server.py
# (Interactive Swagger docs: http://127.0.0.1:8001/docs)
```
