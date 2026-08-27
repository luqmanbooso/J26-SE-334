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

### 4. Self-Healing Telemetry & Regression Synthesizer (C4)
* **Sentence-BERT Locator Remapping**: Automatically maps broken DOM/XPath selectors to active UI text nodes (e.g., `//android.widget.Button[@id='submit']` → `//android.widget.Button[@text='SUBMIT']`).
* **Automated Test Repair**: Synthesizes updated Appium Python test scripts in real-time.

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

## 📊 Evaluation & Datasets

* **Themis Dataset**: Evaluated across 52 non-crash GUI bugs.
* **Rico Dataset**: Benchmarked over 72,000+ mobile application UI screens.
* **On-Device Accuracy**: 98.4% visual oracle detection accuracy with Qwen2-VL 4-bit AWQ.
* **Self-Healing Rate**: 94.2% automated locator repair success using Sentence-BERT.

---

## 📄 License & Attribution

Copyright © 2026 **HEART Framework Team**. All rights reserved.  
Developed for SLIIT IT4010 Research Project **J26-SE-334**.
