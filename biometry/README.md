# Component 2: Human Stress-Aware Input Interaction Engine

**Student:** L.T. Jayawardhana (IT23156760)  
**Research Project:** J26-SE-334 — Human Behavior-Aware Robustness Testing Framework for Mobile Applications

---

## Overview

Existing mobile GUI test automation tools (such as Appium or Monkey) either execute geometrically perfect coordinate taps or inject blind random noise. They fail to reflect realistic human motor behaviors, tremors, finger geometry, or stress-induced cognitive variations (e.g. rage clicking, panic swiping, or tremor during latency).

The **Human Stress-Aware Input Interaction Engine** operationalizes validated human-computer interaction (HCI) models—specifically **FFitts Law** and the **Rotational Dual Gaussian Model**—to generate realistic, biomechanically distorted touch inputs conditioned on dynamic user stress states.

---

## Key Features & Capabilities

- **Cognitive Stress Modeling:** Simulates stress profiles (Calm, Frustration, Urgency, Distraction) adjusting tap frequencies, touch durations, and interaction intervals dynamically.
- **Biomechanical Touch Modeling:**
  - **FFitts Law:** Models movement time, finger tremor, and precision boundaries.
  - **Rotational Dual Gaussian Distribution:** Simulates orientation-elongated touch contact endpoints.
- **Gesture Distortions:** Produces natural shaky swipes, incomplete drag gestures, and Bézier-path deviations.
- **Live Device ADB Integration:** Injects calculated biomechanical touches and gestures directly into attached Android devices via ADB/UIAutomator dumps.
- **Adaptive Escalation:** Dynamically increases distortion and tap aggression when UI latency or repeated tap failures are encountered.

---

## Directory Structure

```text
biometry/
├── bridge/
│   └── adb_bridge.py                # ADB command interface & touch injection bridge
├── models/
│   ├── biomechanical_models.py      # FFitts Law & Rotational Dual Gaussian implementations
│   └── stress_model.py              # Cognitive stress state machines & parameter scaling
├── simulation/
│   └── gesture_engine.py            # Bézier curve generator & distorted gesture synthesis
├── experiment_rotational_model.py   # Statistical validation script for touch distributions
├── test_live_calculator.py          # Live test script against Android Calculator app
├── test_live_dialer.py              # Live test script against Android Dialer app
├── test_live_pixel_detector.py      # Screen extraction & pixel-level hit validation
├── main.py                          # Main runner for biometrical test sessions
└── results/                         # Output evaluation figures and touch coordinate traces
```

---

## Prerequisites & Installation

1. **Prerequisites:**
   - Python 3.10+
   - Android SDK Platform-Tools (`adb` configured in system PATH)
   - Connected physical device or emulator with USB debugging enabled

2. **Setup:**
   ```bash
   cd biometry
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   pip install numpy matplotlib opencv-python
   ```

---

## Usage

### 1. Run Distribution Experiment
Validate the Rotational Dual Gaussian touch endpoints:
```bash
python experiment_rotational_model.py
```

### 2. Run Live Application Tests
Execute stress-conditioned human-like touch inputs on a connected device:
```bash
# Test on Calculator:
python test_live_calculator.py

# Test on Dialer:
python test_live_dialer.py

# General test runner:
python main.py
```
