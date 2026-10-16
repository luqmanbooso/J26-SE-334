# Component 3: Localized Multimodal Vision-Semantic Oracle

**Student:** M.L. Booso (IT23452916)  
**Research Project:** J26-SE-334 — Human Behavior-Aware Robustness Testing Framework for Mobile Applications (HEART)  
**Research Gap:** `GAP-03` / `CLAIM-01` / `CLAIM-02`  
**Interface Specification:** `IF-C3-to-C4` (JSON Payload Schema)

---

## 1. Overview & Research Contributions

Mobile automated test assertions historically rely on brittle text-matching or non-visual DOM checks that miss non-crash visual GUI defects (widget overlap, missing content, frozen states, text clipping). While cloud-hosted VLMs (e.g. GPT-4o) detect visual defects, they leak sensitive user screen data, add unacceptable network latency (1.5–4.0s), and cost \$0.02–\$0.05 per step.

**Component 3 (Localized Multimodal Vision-Semantic Oracle)** provides a **100% offline, zero-cloud visual defect oracle** running on consumer laptop hardware (RTX 3050 4GB).

### Key Architectural Pillars:
1. **4-Bit NF4 Quantized Qwen2-VL Base + QLoRA Adapter:** Fits under 3.8GB peak VRAM footprint on consumer GPUs.
2. **Universal SAHI Dynamic Slicing:** Solves the mobile viewport downsampling resolution bottleneck ($720 \times 1600 \to 262\text{k pixels}$) by slicing tall viewports ($H \ge 1.25 W$) into native aspect ratio tiles, localizing sub-patch visual occlusions.
3. **Dual-Modality AST Layout Collision Pruning (CLAIM-01):** Evaluates Android accessibility hierarchy XML/JSON in $<5\text{ms}$ on CPU, detecting obvious bounding box occlusions and bypassing GPU inference to meet strict test execution SLAs.
4. **Standardized HEART `IF-C3-to-C4` Verdict:** Emits structured JSON verdicts with bounding boxes normalized to $[0, 1000]$ and comprehensive latency breakdown instrumentation.

---

## 2. Component Architecture

```mermaid
flowchart TD
    Screen["Raw Mobile Screenshot<br/>(e.g., 720x1600 Native)"] --> Pre["Image Preprocessor & SAHI Engine"]
    DOM["Raw View Hierarchy<br/>(window_dump.xml / JSON)"] --> Pruner["Hierarchy AST Pruner<br/>(<5ms Collision Check)"]

    Pruner -->|Layout Collision Found?| FastExit["Immediate Verdict (CLAIM-01)<br/>has_defect: true, <15ms"]
    Pruner -->|No Collision / Missing DOM| Prompt["Fused Prompt Compiler<br/>(ShareGPT Single-Turn)"]

    Pre -->|Global Downsample (262k px)| Prompt
    Prompt --> VLM["4-bit NF4 Quantized Qwen2-VL<br/>+ LoRA Adapter (Local VRAM)"]

    VLM --> Parser["Verdict JSON Parser & Sanitizer"]
    Parser -->|has_defect: true| Verdict["C3 Oracle Verdict (IF-C3-to-C4)"]
    Parser -->|has_defect: false & Tall Viewport| SAHI["SAHI Dynamic Tiling Pass<br/>(Bottom Navigation Slice)"]
    SAHI --> VLM
    FastExit --> Verdict
```

---

## 3. Directory Layout

```text
Component3(local vision oracle)/
├── local_vision_oracle/         # Core Python package
│   ├── engine.py                # OracleEngine & TransformersInferenceBackend
│   ├── preprocessor.py          # ImagePreprocessor & SahiSlice dynamic tiling
│   ├── pruner.py                # HierarchyPruner & Layout collision detector
│   ├── prompt.py                # ShareGPT template prompt builder
│   ├── parser.py                # JSON verdict parser & recovery
│   ├── cli.py                   # Command-line interface (inspect, benchmark, etc.)
│   ├── schemas.py               # Pydantic data models & defect types
│   ├── evaluator.py             # Accuracy & SLA evaluation runner
│   └── ...
├── tests/                       # Automated unit & integration tests (87 passing tests)
│   ├── test_engine.py
│   ├── test_preprocessor.py
│   ├── test_pruner.py
│   └── ...
├── notebooks/                   # Interactive Jupyter notebooks
│   ├── c3_oracle_demonstration.ipynb   # Visual demonstration with Matplotlib overlays
│   ├── evaluate_c3_model.ipynb         # Held-out test split benchmarking
│   └── opening_screen.png              # Reference defect evaluation screen
├── docs/                        # Oral defense & replication documentation
│   ├── MANUAL_REPLICATION_GUIDE.md
│   ├── session_09_manual_replication_and_defense_guide.md
│   └── HEART_CONTEXT_MAP_AND_INTEGRATION_SPEC.md
├── pyproject.toml               # Package build specification
├── requirements.txt             # Dependency manifest
├── .gitignore                   # Excludes weights, checkpoints & caches
└── README.md                    # Component documentation
```

---

## 4. Setup & Installation

### Prerequisites
- Python 3.10+
- NVIDIA GPU with CUDA support (e.g. RTX 3050 4GB+) or CPU
- Local model weights (base `Qwen2-VL-2B-Instruct` + `c3_lora_final`)

### Environment Setup
```bash
python -m venv .venv

# Windows:
.venv\Scripts\activate

# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

---

## 5. Verification & Testing

### 1. Automated Test Suite (87 Automated Cases)
Run the full test suite covering all modules:
```bash
pytest tests/ -v
```
**Expected Result:** `87 passed in ~50s` (100% pass rate).

### 2. Single-Screen Visual Inference (CLI)
Evaluate any screenshot directly from the terminal:
```bash
python -m local_vision_oracle.cli inspect --image notebooks/opening_screen.png
```

### 3. Interactive Notebook Demonstration
Launch the interactive Jupyter notebook for visual bounding box inspection:
```bash
jupyter notebook notebooks/c3_oracle_demonstration.ipynb
```

---

## 6. Interface Specification (`IF-C3-to-C4`)

The oracle emits structured JSON consumed by Component 4 (Self-Healing Telemetry):

```json
{
  "screen_id": "scr_746ee9b5be863e97",
  "verdict": {
    "has_defect": true,
    "defect_type": "component_overlap",
    "sub_category": null,
    "confidence": 1.0,
    "bounding_box": [750, 0, 984, 1000],
    "affected_element_id": null,
    "explanation": "Visual UI rendering defect: abnormal component collision detected on screen."
  },
  "latency_breakdown": {
    "capture_ms": 0.0,
    "preprocess_ms": 54.76,
    "prune_ms": 0.0,
    "inference_ms": 116382.14,
    "total_pipeline_ms": 116436.9,
    "meets_sla": false
  },
  "timestamp": "2026-10-15T09:41:51.407252+00:00",
  "engine_used": "qwen2-vl-awq-4bit",
  "metadata": {
    "screen_id": "scr_746ee9b5be863e97",
    "detected_by": "sahi_dynamic_tiling",
    "sahi_slice": 2
  }
}
```

---

## 7. Oral Defense & Manual Replication Guide

For step-by-step viva instructions ("what to look at", "what commands to run", and "what conclusion to come to"), refer to:
👉 [docs/MANUAL_REPLICATION_GUIDE.md](docs/MANUAL_REPLICATION_GUIDE.md)
