# Component 2: Human Stress-Aware Input Interaction Engine

**Student:** L.T. Jayawardhana (IT23156760)  
**Research Project:** J26-SE-334 — Human Behavior-Aware Robustness Testing Framework for Mobile Applications

---

## Overview

Existing mobile GUI test automation tools (such as Appium or Monkey) either execute geometrically perfect coordinate taps or inject blind random noise. They fail to reflect realistic human motor behaviors, tremors, finger geometry, or stress-induced cognitive variations (e.g. rage clicking, panic swiping, or tremor during latency).

The **Human Stress-Aware Input Interaction Engine** operationalizes validated human-computer interaction (HCI) models—specifically **FFitts Law** and the **Rotational Dual Gaussian Model**—to generate realistic, biomechanically distorted touch inputs conditioned on dynamic user stress states.

---

## Key Features & Capabilities

### Implemented
- **Rotational Dual Gaussian touch distortion:** samples a touch offset from two Gaussians in the
  movement frame, rotated to the approach angle, so scatter elongates along the direction of travel.
- **Stress-scaled spread:** both axes of that distribution widen as the modelled stress value rises.
- **Inter-action delay sampling:** a per-action delay drawn around a base interval, its variance
  rising with stress.
- **Live device integration:** UIAutomator hierarchy dump, element lookup by text / content-desc /
  resource-id, and coordinate tap injection over ADB.
- **Offline validation harness:** scatter-versus-approach-angle experiment that runs with no device
  attached.

### Designed, not yet implemented
- **Cognitive stress model** — a Markov state machine (calm → impatient → frustrated) driven by app
  behaviour. `models/stress.py` is currently only a clamped scalar, not this model.
- **Adaptive feedback loop** — raising stress in response to measured UI latency, ANR and
  no-response conditions.
- **FFitts target-width dependence** — scatter growing as the target shrinks.
- **Right-skewed delays, hesitation gaps and rage-click bursts.**
- **Gesture distortion** — Bézier-path deviation, shaky swipes, early-release drags.

## Directory Structure

```text
biometry/
├── bridge/
│   └── adb_bridge.py                # ADB interface: hierarchy dump, element lookup, tap injection
├── models/
│   ├── spatial.py                   # RotationalSpatialModel — anisotropic touch scatter
│   ├── timing.py                    # TimingModel — inter-action delay sampling
│   └── stress.py                    # StressModel — scalar stress holder (not the cognitive model)
├── simulation/
│   └── simulator.py                 # BiometricSimulator — composes spatial + timing into one tap
├── experiment_rotational_model.py   # Offline scatter-vs-approach-angle experiment (no device)
├── main.py                          # Batch runner: distributions across stress levels
├── demo_live_calculator.py          # Live demo script against the Android Calculator
├── demo_live_dialer.py              # Live demo script against the Android Dialer
├── demo_live_pixel_detector.py      # Screen capture + clickable-element overlay
└── results/                         # Generated figures and summary metrics
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
   pip install matplotlib pillow
   ```

---

## Usage

### 1. Run Distribution Experiment
Validate the Rotational Dual Gaussian touch endpoints:
```bash
python experiment_rotational_model.py
```

> **Note:** `demo_live_*.py` drive a real device and are demonstrations, not tests. The
> automated suite is in `tests/` and needs no device.


### 2. Run Live Application Tests
Execute stress-conditioned human-like touch inputs on a connected device:
```bash
# Test on Calculator:
python demo_live_calculator.py

# Test on Dialer:
python demo_live_dialer.py

# General test runner:
python main.py
```
