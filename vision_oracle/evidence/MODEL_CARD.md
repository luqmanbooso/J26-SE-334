# Model Card: C3 LoRA Final (Mobile UI Vision-Semantic Oracle)

## Model Details
- **Model Name:** C3 Local Vision-Semantic Test Oracle (`c3_lora_final`)
- **Base Model:** `Qwen/Qwen2-VL-2B-Instruct`
- **Architecture:** Multimodal Vision-Language Model with LoRA Parameter-Efficient Fine-Tuning
- **Developers:** M.L. Booso (IT23452916), HEART Research Group (J26-SE-334)
- **Model Type:** Vision-Language Mobile UI Defect Classifier and Localizer
- **Release Date:** October 2026
- **Status:** Production Freeze for Performance Prototype 1 (PP1)

## Checkpoint Provenance & Checksums
- **Adapter Location:** `models/c3_lora_final`
- **Adapter File:** `adapter_model.safetensors`
- **File Size:** 77,532,848 bytes (~73.94 MB)
- **SHA-256 Checksum:** `F66C05CAA735E7AE0226312553560942AC8621541b2ECC819CD4CC1BE5E125F4`
- **Adapter Config:** `adapter_config.json`
- **Target Modules:** `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`
- **LoRA Parameters:** $r=16, \alpha=32$, dropout=0.05 (19,988,480 trainable parameters, 0.90% of base model)
- **Base Quantization:** BitsAndBytes NF4 (4-bit NormalFloat), compute dtype `bfloat16`

## Intended Use
- **Primary Use Case:** Automated detection and spatial localization of primary visual GUI anomalies on mobile Android application screens (specifically `component_overlap` and `text_truncation`).
- **Primary Consumers:** Component 2 (Stress Engine) and Component 4 (Synthetic Test Generator) within the HEART automated testing framework.
- **Out-of-Scope Uses:** Non-visual logic bugs (e.g. incorrect calculation), backend API failures, temporal UI freezing without multi-frame probes, and dense multi-label defect counting across the entire screen prior to multi-label retraining.

## Training Data & Methodology
- **Training Corpus:** 2,000 balanced mobile UI screen annotations.
- **Data Sources:** 
  - Real defective mobile screens from the OwlEye repository (271 real bug screens with teacher pseudo-labels).
  - Mutated synthetic screens based on the Rico mobile dataset (systematically injected bounding box overlaps and text clipping).
  - Clean real-world production mobile screens.
- **Data Splits:** 70% Train (1,400 screens), 15% Validation (300 screens), 15% Held-Out Test (300 screens).
- **Leakage Protection:** Strict application-level deduplication to guarantee zero synthetic parent leakage into the test set.
- **Training Framework:** LLaMA-Factory SFT (Supervised Fine-Tuning)
- **Hyperparameters:**
  - Effective Batch Size: 8 (Batch Size 2, Gradient Accumulation 4)
  - Learning Rate: $2.0 \times 10^{-4}$ with cosine annealing
  - Training Epochs: 2.0 (350 total optimizer steps)
  - Final Loss: `0.1582` (converged from `1.8420`)

## Performance & Evaluation
- **Held-Out Test Set (N=300):**
  - Accuracy: **71.00%** (213 / 300)
  - Precision: **80.58%** (83 / 103)
  - Recall: **55.33%** (83 / 150)
  - F1-Score: **65.61%**
  - Specificity: **86.67%** (130 / 150)
  - True Positives: 83 | False Positives: 20 | False Negatives: 67 | True Negatives: 130
- **Ablation vs Base Model:**
  - Base Model Zero-Shot Recall: 0.00%
  - LoRA Adapter Recall: 55.33% (McNemar $\chi^2 = 81.01, p < 10^{-18}$)
- **Small Defect Slicing Gain (SAHI):**
  - Small defect F1 (<5% screen area): 42.10% (Global only) $\rightarrow$ 61.65% (Dynamic SAHI Slicing) (+19.55% absolute gain).

## Hardware & Deployment Requirements
- **Target Hardware:** Consumer Laptop GPU (NVIDIA GeForce RTX 3050 Laptop GPU, 4GB VRAM)
- **VRAM Footprint:** Idle 412 MB, Model Loaded 2,840 MB, Peak Forward Pass 3,242 MB
- **VRAM Stability:** 0 byte leakage across 50 consecutive inference cycles
- **Inference Latency:** Median ($p50$) = 1,420 ms, $p90$ = 1,610 ms, $p99$ = 1,890 ms
- **Offline Air-Gap:** 100% local loopback execution (`ZERO_CLOUD_EGRESS = True`)

## Limitations & Ethical Considerations
- Current weights detect the **single primary visual defect** on a screen; secondary visual bugs are ignored until multi-label retraining.
- Optical character recognition (OCR) and text reasoning depend on resolution; low-DPI screenshots may cause minor text truncation misidentifications.
- The model outputs bounding boxes in normalized coordinates `[0, 1000]`, which require physical resolution mapping via `CoordinateMapper`.
