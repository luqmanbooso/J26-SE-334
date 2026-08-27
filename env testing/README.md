# Component 1: Context-Aware Environmental Perturbation Engine

**Student:** G.L.S. Chanlaka (IT23151260)  
**Research Project:** J26-SE-334 — Human Behavior-Aware Robustness Testing Framework for Mobile Applications

---

## Overview

Modern mobile apps experience unpredictable real-world environmental variations—such as sudden network degradation, thermal throttling, memory pressure, battery drops, and background interruptions. Traditional mobile testing suites execute inside sanitized, static environments, failing to capture environment-induced edge cases and non-crash functional degradations.

The **Context-Aware Environmental Perturbation Engine** systematically orchestrates and injects synchronized environmental stressors into the test loop based on runtime state and semantic test steps, outputting structured perturbation event logs correlated to application failures.

---

## Key Features & Capabilities

- **Network Perturbations:** Simulates network variability (WiFi $\leftrightarrow$ Mobile Data transitions, latency spikes, packet loss, bandwidth throttling).
- **Device Stress Injection:** Induces CPU load spikes, low-memory pressure conditions, battery state transitions, and thermal throttling profiles.
- **Interruption Simulation:** Injects incoming calls, SMS messages, push notifications, and app backgrounding/resume cycles.
- **Dynamic Orchestration & Scheduling:** Correlates perturbation timing with semantic test steps and performance signals (frame drops, latency).
- **Telemetry & Event Correlation:** Emits timestamped perturbation event logs (`perturbation_event_log.json`) to trace exact environmental triggers behind application failures.

---

## Directory Structure

```text
env testing/
├── core/
│   ├── base.py                   # Base perturbation stressor abstraction
│   ├── scheduler.py              # Perturbation event scheduler and dispatch loop
│   └── event_logger.py           # Timestamped perturbation logger
├── stressors/
│   ├── network_stressor.py       # Network throttling and handover simulation
│   ├── system_stressor.py        # CPU, RAM, battery, and thermal perturbation
│   └── interruption_stressor.py  # Call, notification, and lifecycle interruptions
├── orchestrator.py               # Orchestrator coordinating multi-factor stress loops
├── run_live_suite.py             # Live execution suite runner against test device/emulator
├── perturbation_event_log.json   # Output perturbation audit log
└── requirements.txt              # Component dependencies
```

---

## Prerequisites & Installation

1. **Prerequisites:**
   - Python 3.10+
   - Android SDK Platform-Tools (`adb` configured in system PATH)
   - Connected physical Android device or active Android emulator

2. **Setup:**
   ```bash
   cd "env testing"
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

---

## Usage

Run the test suite with coordinated environmental stress injection:

```bash
python run_live_suite.py
```

Inspect output logs:
- `perturbation_event_log.json` contains full event trace including timestamps, target stress type, parameters injected, and execution context.
