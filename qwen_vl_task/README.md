# Component 3: Localized Multimodal Vision-Semantic Oracle

**Student:** M.L. Booso (IT23452916)  
**Research Project:** J26-SE-334 — Human Behavior-Aware Robustness Testing Framework for Mobile Applications

---

## Overview

Traditional mobile test assertions rely on hardcoded assertions and crash logs, completely missing non-crash functional GUI bugs—such as overlapping text widgets, obscured buttons, frozen loading indicators, and truncated content. While cloud-hosted Vision-Language Models (e.g. GPT-4o) can detect visual anomalies, they incur substantial latency, operational costs, and privacy risks.

The **Localized Multimodal Vision-Semantic Oracle** deploys compact, quantized Vision-Language Models (e.g., **Qwen2-VL** 2B/7B quantized to 4-bit / 8-bit) to perform zero-cloud, real-time visual bug verification by jointly inspecting UI screenshots and view hierarchy XML data.

---

## Key Features & Capabilities

- **On-Device Vision-Language Model:** Optimized Qwen2-VL inference locally using 4-bit / 8-bit quantization (AWQ / GPTQ / bitsandbytes).
- **Joint Multimodal Analysis:** Combines visual screen captures with Android accessibility view hierarchies (`window_dump.xml`) to eliminate visual false positives.
- **Non-Crash Defect Detection:** Identifies UI overlaps, occlusion, frozen states, layout distortions, and missing essential widgets.
- **Privacy-Preserving & Cost-Effective:** Operates entirely localized without streaming confidential app screenshots to external cloud providers.

---

## Directory Structure

```text
qwen_vl_task/
├── .venv/                # Local virtual environment
├── qwen_task.ipynb       # Interactive notebook for Qwen2-VL loading, quantization, and UI bug detection
└── README.md             # Component documentation
```

---

## Prerequisites & Installation

1. **Prerequisites:**
   - Python 3.10+
   - CUDA-compatible GPU (recommended for quantized local VLM inference) or CPU support
   - Jupyter Lab / VS Code Jupyter extension

2. **Setup:**
   ```bash
   cd qwen_vl_task
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   pip install torch torchvision transformers accelerate bitsandbytes pillow jupyter
   ```

---

## Usage

1. Open `qwen_task.ipynb` in VS Code or Jupyter:
   ```bash
   jupyter notebook qwen_task.ipynb
   ```
2. Run the cells to:
   - Load the quantized Qwen2-VL model.
   - Pass UI screenshots alongside accessibility trees.
   - Run inference to inspect non-crash functional bug classifications and visual bounding box anomaly assessments.
