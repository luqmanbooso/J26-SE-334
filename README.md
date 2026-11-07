# HEART: Human Behavior-Aware Robustness Testing Framework for Mobile Applications

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-blue.svg?style=flat)](https://github.com/TomSchimansky/CustomTkinter)
[![Android ADB](https://img.shields.io/badge/Android-ADB%20%7C%20QEMU-3DDC84.svg?style=flat&logo=android&logoColor=white)](https://developer.android.com/tools/adb)
[![HuggingFace LoRA](https://img.shields.io/badge/VLM-Qwen2--VL--2B--Instruct-FFD21E.svg?style=flat&logo=huggingface&logoColor=black)](https://huggingface.co/)
[![CI/CD Pipeline](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF.svg?style=flat&logo=githubactions&logoColor=white)](.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Research Project ID**: `J26-SE-334`  
> **Institution**: Faculty of Computing, Sri Lanka Institute of Information Technology (SLIIT)  
> **Domain**: Software Systems & Technologies (SST) / Mobile Software Engineering  
> **Academic Year**: 2026  

---

## 📌 Executive Summary

**HEART** (**H**uman B**e**havior-**A**ware **R**obustness **T**esting) is an enterprise-grade automated testing and fault-injection platform designed to stress-test Android mobile applications under authentic real-world conditions. 

Traditional mobile test suites only detect fatal binary crashes (`SIGSEGV`, uncaught exceptions) in ideal lab environments. In the real world, mobile applications suffer non-crash UI/UX failures: layout truncations, overlapping buttons, unresponsive taps under high CPU/memory load, and network flakiness.

**HEART unifies four complementary research pillars into a single test harness:**
1. **Context-Aware Environmental Perturbation**: Dynamic hardware and network chaos injection via ADB and Linux kernel stressors.
2. **Stress-Aware Interaction & Motor Degradation**: Fitts's Law-driven motor tremor, erratic touch scatter, and rapid swipe velocity mimicking stressed end-users.
3. **Localized Multimodal Vision-Semantic Oracle**: Air-gapped, edge-quantized Vision-Language Model (`Qwen2-VL-2B`) with domain LoRA adapters detecting non-crash GUI defects without access to source code.
4. **Self-Healing Telemetry & Regression Synthesizer**: Automated Appium test script synthesis from crash telemetry and Sentence-BERT semantic locator repair.

---

## 🏛️ The Four Research Pillars & Team

| Component | Research Focus | Lead Researcher | Student ID |
|---|---|---|---|
| **C1** | **Context-Aware Environmental Perturbation Engine** | G. L. S. Chanlaka | `IT23151260` |
| **C2** | **Stress-Aware Interaction & Motor Degradation Engine** | L. T. Jayawardhana | `IT23156760` |
| **C3** | **Localized Multimodal Vision-Semantic Oracle** | M. L. Booso | `IT23452916` |
| **C4** | **Self-Healing Telemetry & Regression Synthesizer** | H. N. Madubashini | `IT23192300` |

---

## 🔬 System Architecture

```
                                  +---------------------------------------+
                                  |       HEART Studio Desktop App        |
                                  |         (heart_desktop_app.py)        |
                                  +---------------------------------------+
                                        |                           |
                  +---------------------+                           +---------------------+
                  |                                                                       |
                  v                                                                       v
   +------------------------------+                                        +------------------------------+
   |   C1: Environmental Engine   |                                        |    C2: Interaction Engine    |
   | - Network Latency & Flakiness|                                        | - Biometric Motor Tremor     |
   | - CPU Throttling / RAM Load  |                                        | - Fitts's Law Spatial Error  |
   | - Battery / Thermal / Calls  |                                        | - Rapid Swipe & Dead Clicks  |
   | - FastAPI Server (Port 8001) |                                        | - Real-Time Touch Heatmaps   |
   +------------------------------+                                        +------------------------------+
                  |                                                                       |
                  +--------------------------------+--------------------------------------+
                                                   |
                                                   v
                                 +-----------------------------------+
                                 |  Target Android Device / Emulator |
                                 |  - High-Speed Console TCP (5554)  |
                                 |  - Persistent ADB Shell Daemon    |
                                 +-----------------------------------+
                                                   |
                  +--------------------------------+--------------------------------------+
                  |                                                                       |
                  v                                                                       v
   +------------------------------+                                        +------------------------------+
   |   C3: Vision-Semantic Oracle |                                        |     C4: Self-Healing Test    |
   | - Qwen2-VL-2B-Instruct + LoRA|                                        | - Telemetry-to-Test Pipeline |
   | - Non-Crash Defect Detection |                                        | - Sentry/Crashlytics Parser  |
   | - Layout Overlaps & Clipping |                                        | - Sentence-BERT Locator Heal |
   | - FastAPI Server (Port 8003) |                                        | - Appium Python Synthesizer  |
   +------------------------------+                                        +------------------------------+
```

---

## ⚙️ Component Deep-Dive

### 1. Component 1: Context-Aware Environmental Perturbation Engine (`C1`)
- **Direct Hardware & Kernel Stressors**:
  - **Network Chaos**: Traffic Control (`tc-netem`) latency emulation (100 ms – 10,000 ms), packet loss (0% – 50%), jitter, bandwidth constraints (Edge 2G, Flaky 3G, LTE throttled), and DNS failure injection.
  - **CPU & Memory Throttling**: Multi-threaded CPU starvation loops up to 98% utilization and Linux Low-Memory-Killer (LMK) memory pressure simulation.
  - **System Events & Interruptions**: Incoming phone calls, SMS broadcasts, low battery warnings (1% – 100%), and thermal throttling states (`Normal`, `Warning`, `Critical`).
- **High-Speed Screen Mirror & Interactive Fullscreen Engine**:
  - Direct TCP connection to emulator console socket (`127.0.0.1:5554`) delivering sub-100ms screencaps with zero subprocess spawning overhead.
  - Dedicated worker thread streaming at 25 FPS without UI freeze.
  - Resizable pop-out window with `F11` borderless True Fullscreen mode, on-screen Android navigation buttons (`PWR`, `VOL+`, `VOL-`, `BACK`, `HOME`, `RECENTS`), and real-time touch coordinate translation.
- **REST Microservice**: FastAPI server on `http://127.0.0.1:8001` with automated double-slash normalization middleware and live Swagger documentation.

### 2. Component 2: Stress-Aware Interaction Engine (`C2`)
- **Biomechanical Touch Modeling**: Implements modified Fitts's Law spatial dispersion models to emulate degraded user motor control under cognitive and physical stress.
- **Dynamic Interaction Anomalies**: Simulates micro-tremors, touch jitter, overshoot/undershoot spatial errors, rapid swipe velocity (>1000 px/s), and high-frequency dead clicks.
- **Visual Feedback**: Real-time radial ripples, displacement vectors, and contact point heatmaps overlaid directly onto the live mirror.

### 3. Component 3: Localized Multimodal Vision-Semantic Oracle (`C3`)
- **Quantized Vision-Language Model**: Edge-deployable `Qwen2-VL-2B-Instruct` with domain-specific LoRA adapters (`models/c3_lora_final`) trained on mobile GUI defect datasets.
- **Non-Crash Defect Localization**: Pinpoints visual bugs that bypass crash handlers, including `[OVERFLOW_Y_COLLISION]`, component overlapping, illegible font truncations, and missing assets.
- **Air-Gapped REST Engine**: FastAPI service running locally on port 8003 (`/health/live`, `/health/ready`, `/inspect`).

### 4. Component 4: Self-Healing Telemetry & Regression Synthesizer (`C4`)
- **Crash Telemetry Ingestion**: Ingests real-world crash logs (Sentry, Firebase Crashlytics) and reproduces failures deterministically as executable Appium Python scripts.
- **Semantic Locator Self-Healing**: Leverages Sentence-BERT embeddings to repair broken UI selectors when UI elements move, mutate, or are refactored across application versions.
- **Closed-Loop Verification**: Validates healed locators against live Android UI hierarchy dumps (`uiautomator dump`) before committing test updates.

---

## 📂 Repository Directory Layout

```
J26-SE-334/
├── heart_desktop_app.py        # Master unified desktop application (all 4 components)
├── heart_desktop.py            # Unified application launcher script
├── start_c1_demo_recording.bat # Automated 1-click launcher for AVD + Backend + Studio
├── run_heart_desktop_exe.bat   # Windows executable standalone runner
│
├── env testing/                # Component 1 Backend Engine
│   ├── server.py               # FastAPI REST microservice (Port 8001)
│   ├── orchestrator.py         # Multi-factor perturbation orchestrator
│   ├── attribution_engine.py   # Causal failure attribution engine
│   ├── stressors/              # Modular hardware and network stressors
│   │   ├── network_stressor.py
│   │   ├── cpu_stressor.py
│   │   ├── battery_stressor.py
│   │   ├── thermal_stressor.py
│   │   └── interruption_stressor.py
│   ├── profiles/               # Standardized YAML compound perturbation profiles
│   │   ├── compound_multi_factor_chaos.yaml
│   │   ├── 3g_network_drop.yaml
│   │   ├── high_thermal_throttling.yaml
│   │   └── heavy_cpu_starvation.yaml
│   └── results/                # Evaluation reports, JSON event logs, and charts
│
├── biometry/                   # Component 2 Biometric Simulation
│   ├── biometric_simulator.py  # Fitts's law and Gaussian touch tremor engine
│   └── run_simulated_exp02.py  # Biometric stress experiment executor
│
├── vision_oracle/              # Component 3 Vision-Semantic Oracle
│   ├── server.py               # FastAPI VLM service (Port 8003)
│   └── inspector.py            # Multimodal defect localization logic
│
├── component4/                 # Component 4 Self-Healing Engine
│   ├── healing_pipeline.py     # End-to-end telemetry to test pipeline
│   ├── locator_healer.py       # Sentence-BERT semantic locator synthesizer
│   └── rerun_service.py        # Automated test verification runner
│
├── platform-tools/             # Embedded Android ADB and Fastboot binaries
├── postman/                    # Exported Postman API Collections & Environments
├── models/                     # Vision-Language Model weights & LoRA adapters
│   └── c3_lora_final/          # Committed LoRA adapter weights (adapter_model.safetensors)
├── .github/workflows/          # CI/CD Automated testing and syntax audit pipelines
│   └── ci.yml
└── tests/                      # Automated test suite (unit, integration, regression)
```

---

## 🚀 Quickstart & Execution Guide

### 1. Prerequisites
- **Operating System**: Windows 10/11, Ubuntu 22.04 LTS, or macOS 13+
- **Python**: `3.10` or higher (`3.11` / `3.13` supported)
- **Android SDK & Emulator**: Android Studio installed with an active AVD (e.g., `Pixel_9_Pro` running API 34+ with GPU acceleration enabled)
- **Hardware**: Dedicated GPU recommended (NVIDIA RTX 3050+ with 4GB+ VRAM for VLM inference)

### 2. Environment Setup

```powershell
# Clone the repository
git clone https://github.com/luqmanbooso/J26-SE-334.git
cd J26-SE-334

# Create and activate Python virtual environment
python -m venv venv
.\venv\Scripts\activate   # On Linux/macOS: source venv/bin/activate

# Install core dependencies
pip install --upgrade pip
pip install -r requirements.txt   # Or install custom-tkinter, fastapi, uvicorn, pillow, pyyaml
```

---

### 3. Launching the Interactive Desktop Studio

Launch the unified HEART Diagnostics Studio (representing C1, C2, C3, and C4 with live hardware telemetry, high-speed AVD mirroring, and fullscreen controls):
```powershell
python heart_desktop_app.py
# Or via entrypoint launcher:
python heart_desktop.py
# Or via 1-click batch launcher (boots AVD, starts FastAPI backend, and opens Studio):
.\start_c1_demo_recording.bat
```

---

### 4. Running the Backend Services

#### C1 Perturbation Engine (Port 8001)
```powershell
cd "env testing"
python server.py
```
- **Service URL**: `http://127.0.0.1:8001`
- **Interactive Swagger Docs**: `http://127.0.0.1:8001/docs`
- **Health / Status Check**: `http://127.0.0.1:8001/api/status`

#### C3 Vision Oracle (Port 8003)
Download base `Qwen2-VL-2B-Instruct` model if running for the first time:
```powershell
python scripts/download_base_model.py
python -m vision_oracle.server
```
- **Service URL**: `http://127.0.0.1:8003`
- **Health Check**: `http://127.0.0.1:8003/health/live`

---

## 📡 REST API Reference (Component 1)

The C1 microservice exposes clean REST endpoints for remote test automation, CI/CD pipelines, and Postman execution.

### 1. System Status
- **Method**: `GET`
- **Endpoint**: `/api/status` (or `//api/status` via normalization middleware)
- **Response**:
```json
{
  "status": "READY",
  "device_connected": true,
  "device_id": "emulator-5554",
  "active_perturbations": [],
  "timestamp": 1729851600.0
}
```

### 2. Apply Perturbation
- **Method**: `POST`
- **Endpoint**: `/api/perturbation/apply`
- **Request Body**:
```json
{
  "stressor_type": "network",
  "parameters": {
    "latency_ms": 1200,
    "packet_loss_pct": 5.0,
    "bandwidth_profile": "flaky_3g"
  }
}
```
- **Response**:
```json
{
  "status": "SUCCESS",
  "applied": "network",
  "parameters": {
    "latency_ms": 1200,
    "packet_loss_pct": 5.0,
    "bandwidth_profile": "flaky_3g"
  },
  "timestamp": 1729851605.12
}
```

### 3. Reset Perturbations
- **Method**: `POST`
- **Endpoint**: `/api/perturbation/reset`
- **Response**:
```json
{
  "status": "SUCCESS",
  "message": "All active hardware and network perturbations cleared."
}
```

### 4. Causal Failure Attribution
- **Method**: `POST`
- **Endpoint**: `/api/attribution/analyze`
- **Request Body**:
```json
{
  "failure_timestamp": 1729851604.5,
  "failure_type": "ANR_OR_CRASH",
  "causality_window_sec": 3.5
}
```

---

## 🧪 Testing & CI/CD Pipeline

The project enforces quality and test validation through GitHub Actions:
- **Linting & Syntax**: `flake8` audit and `py_compile` across all Python entry points.
- **Unit & Integration Tests**: 57 automated tests covering network chaos injection, stressor resets, and failure attribution algorithms.
- **RQ1 Empirical Verification**: Validates statistical significance of non-crash defect discovery under compound environmental chaos.

Run tests locally:
```powershell
pytest "env testing" -v
pytest tests/ -v
```

---

## 📦 Postman Collections

Pre-configured Postman collections are included in `postman/`:
1. Import `postman/HEART_C1_Perturbation_Engine.postman_collection.json`.
2. Set `baseUrl` variable to `http://127.0.0.1:8001`.
3. Execute the collection:
   - `GET /api/status`
   - `POST /api/perturbation/apply`
   - `POST /api/attribution/analyze`
   - `POST /api/perturbation/reset`

---

## 📄 License & Academic Attribution

Copyright © 2026 **HEART Framework Team**. All rights reserved.  
Developed under the **SLIIT Faculty of Computing** for Research Project **J26-SE-334**.
