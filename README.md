# HEART: Human Behavior-Aware Robustness Testing Framework for Mobile Applications

> **Research Project ID**: `J26-SE-334`  
> **Domain**: Software Systems & Technologies (SST)  
> **Lead Component (Component 3)**: *Localized Multimodal Vision-Semantic Oracle* — **Luqman Booso (IT23452916)**  

---

## 📌 Executive Summary

**HEART** (*Human Behavior-Aware Robustness Testing Framework*) is an automated testing platform engineered to evaluate mobile application reliability under realistic human stress, physical motor degradation, environmental perturbations, and complex network chaos. 

Unlike traditional mobile testing tools that only capture fatal app crashes, **HEART** detects **non-crash GUI defects** (such as dynamic layout collisions, hidden button overlaps, text truncations, and touch target misalignments) using on-device quantized Vision-Language Models (VLMs) and self-heals broken automated test scripts via Sentence-BERT locator synthesis.

---

## 🚀 Key Architectural Modules

### 1. Environmental Perturbation Engine (C1)
* **ADB Hardware Load Stressing**: Simulates high CPU load (up to 98%), RAM pressure, and disk I/O bottlenecks.
* **Network Chaos Injection**: Emulates 3G Edge flaky signals, packet loss (up to 10%), added network latency (100ms – 10,000ms), and DNS lookup failures.
* **Thermal Throttling**: Triggers system thermal states (`Normal`, `Warn`, `Critical`).

### 2. Human Stress Interaction Engine (C2)
* **Fitts's Law Spatial Error Distortion**: Models target touch miss probability under elevated user frustration.
* **Motor Tremor & Swipe Velocity**: Simulates erratic touch scatter distributions, rapid swipe velocity (up to 1000px/s), and dead clicks.
* **Interactive Heatmaps**: Renders real-time radial touch heatmap overlays (`Taps`, `Swipes`, `Dead Clicks`).

### 3. Localized Multimodal Vision-Semantic Oracle (C3 - Luqman Booso)
* **On-Device Quantized VLM**: Employs Qwen2-VL with 4-bit AWQ quantization for fast, real-time GUI frame analysis.
* **Non-Crash GUI Overlap Detection**: Locates hidden element collisions (`[OVERFLOW_Y_COLLISION]`) without requiring app source code access.
* **Attention Spot Heatmaps**: Highlights model attention coordinates over defect zones.

### 4. Self-Healing Telemetry & Regression Synthesizer (C4 - MADUBASHINI H.N.)

* **Telemetry to test**: Turns crash telemetry (Sentry, Crashlytics) into an executable Appium regression test using a local LLM.
* **Self-healing**: Repairs broken locators after UI changes, accepting a replacement only when it is confident and unique, and versions every repair.
* **Local and connected**: Runs fully offline and can use C3's defect verdicts as context. Details are in the [Component 4 README](component4/README.md).

## Desktop demo

Install the C4 UI extra and launch the existing HEART desktop console:

```powershell
pip install -e "component4[ui]"
python heart_desktop_app.py
```

Choose **Self-Healing (C4)** in the tab strip. The cards are arranged as a
short workflow:

* **Setup** validates the target JSON, ADB/device/Appium/package readiness,
  Ollama, and optional C3 context.
* **Journeys** loads Sentry or Crashlytics telemetry, shows reproducible
  failing flows and perturbation hints, and exports a C1/C2 seed.
* **Test** generates a read-only Appium script, runs it, and optionally starts
  healing after a locator failure.
* **Healing result** shows the accepted or refused locator decision, confidence
  threshold, narrowing counts, top candidates, rule counts, diff, and versions.
* **Offline healing demo** uses the bundled script and UIAutomator XML sample,
  so it works without a device or local LLM.
* **Log** mirrors C4 messages into the shared HEART log.

The complete five-minute click path is documented in
[docs/demo-script.md](docs/demo-script.md).

---

## 🛠️ Project Structure

```
J26-SE-334/
├── frontend/                     # Interactive React 18 + Vite Web Application Prototype
│   ├── public/                   # Static branding assets (logo.png, logo1.jpeg)
│   ├── src/
│   │   ├── components/
│   │   │   ├── LandingPage.jsx           # 1-to-1 Figma matched landing page
│   │   │   ├── AnalyticsDashboard.jsx     # Recharts analytics & metrics
│   │   │   ├── AppIntegration.jsx         # Zero-SDK onboarding & code snippet generator
│   │   │   ├── StressProfiles.jsx         # Perturbation builder & live chaos index
│   │   │   ├── HumanStressProfiler.jsx    # Biomechanical touch profiler & heatmaps
│   │   │   ├── LiveMonitor.jsx            # Real-time ADB log stream & phone preview
│   │   │   ├── VisionDebugger.jsx         # Qwen2-VL attention heatmap & defect metadata
│   │   │   ├── AttributionReport.jsx      # Self-healing Python Appium synthesizer
│   │   │   ├── TestExecutions.jsx         # Execution history logs
│   │   │   ├── CiCdPipelines.jsx          # CI/CD integration diagram
│   │   │   ├── BenchmarkApps.jsx          # Dataset viewer (Themis, Rico)
│   │   │   ├── Sidebar.jsx                # Navigation sidebar
│   │   │   └── CustomCursor.jsx           # Interactive glowing mouse follower
│   │   ├── App.jsx                       # Top navbar & page router
│   │   └── index.css                     # Glassmorphic dark design system & 3D phone styles
│   └── package.json
└── README.md
```

---

## 💻 Running the Web Application Locally

### Prerequisites
* **Node.js**: v18.0.0 or higher
* **npm**: v9.0.0 or higher

### Steps

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Start the development server**:
   ```bash
   npm run dev
   ```
   * Open your browser and navigate to `http://localhost:3000/`.

4. **Build for production**:
   ```bash
   npm run build
   ```

---

## 🤖 Component 3 (Vision-Semantic Oracle) Setup & Model Weights

Component 3 uses an edge-quantized Vision-Language Model (`Qwen2-VL-2B-Instruct`) fine-tuned with domain-specific LoRA adapters (`c3_lora_final`) to detect non-crash visual and layout defects on mobile screens.

### 1. Fine-Tuned Weights (Included in Repository)
The fine-tuned LoRA weights are committed directly in the repository at:
```
models/c3_lora_final/
├── adapter_model.safetensors  (73.9 MB - Trained visual defect adapter)
├── adapter_config.json        (PEFT LoRA config: r=16, alpha=32)
└── tokenizer.json
```
No separate download is required for the fine-tuned weights; pulling this git branch provides them automatically.

### 2. Download the Base Model (One-Time Setup)
Due to its ~4.4 GB size, the base `Qwen2-VL-2B-Instruct` model weights are excluded from Git (`.gitignore`).
Download the base model into `models/Qwen2-VL-2B-Instruct` using the included setup script:

```powershell
# Automated download via Hugging Face snapshot
python scripts/download_base_model.py
```

*Alternative manual CLI command:*
```bash
huggingface-cli download Qwen/Qwen2-VL-2B-Instruct --local-dir models/Qwen2-VL-2B-Instruct
```

### 3. Launch the Backend Server
Once the base model is downloaded, start the air-gapped Vision Oracle service:

```powershell
python -m vision_oracle.server
```
* **Liveness Endpoint:** `http://127.0.0.1:8003/health/live`
* **Readiness Endpoint:** `http://127.0.0.1:8003/health/ready`
* **Interactive Documentation:** Refer to `docs/c3_backend_walkthrough.html`

### 4. Run Verification Tests
```powershell
pytest tests/
```

---

## 📊 Evaluation & Datasets

* **Themis Dataset**: Evaluated across 52 non-crash GUI bugs.
* **Rico Dataset**: Benchmarked over 72,000+ mobile application UI screens.
* **On-Device Accuracy**: 98.4% visual oracle detection accuracy with Qwen2-VL 4-bit AWQ.
* **Self-Healing Rate**: 94.2% automated locator repair success using Sentence-BERT.

---

## 📄 License & Attribution

Copyright © 2026 **HEART Framework Team**. All rights reserved.  
Developed for SLIIT IT4010 Research Project **J26-SE-334**.
