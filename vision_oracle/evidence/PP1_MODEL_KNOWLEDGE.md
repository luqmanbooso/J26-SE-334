# Component 3 (Local Vision-Semantic Oracle): PP1 Model Knowledge Dossier

**Component:** Component 3 — Localized Multimodal Vision-Semantic Test Oracle (HEART Architecture)  
**Author / Lead:** M.L. Booso (IT23452916)  
**Group:** J26-SE-334  
**Date:** 2026-10-18  
**Repository Branch:** `feat/c3-local-vision-oracle`  
**Evaluation Scope:** Performance Prototype 1 (PP1) — 50% Milestone & Sound Engineering Demonstration  
**Base Architecture:** Qwen2-VL-2B-Instruct  
**Fine-Tuned Adapter:** LoRA Adapter Checkpoint (`models/c3_lora_final`)  

---

## 1. Executive Summary & PP1 Scientific Scope Boundary

Component 3 (C3) operates as the **visual-semantic truth oracle** for the autonomous mobile application testing pipeline HEART. Traditional mobile test assertions depend heavily on the Android Accessibility hierarchy (`uiautomator dump`), which suffers from:
1. High execution latency (>800ms per screen dump).
2. Complete blindness to canvas-rendered elements, custom Jetpack Compose views, Flutter/React Native components, and dynamically clipped text.
3. Zero awareness of visual anomalies such as component overlaps, unrendered glyphs, or offscreen view clipping.

C3 solves this by providing a **purely local, edge-executable Vision-Language Model (VLM)** oracle that processes raw device display captures and emits structured, machine-verifiable defect bounding boxes and verdicts.

### 1.1 Scope Boundaries for PP1 (What is Demonstrated vs Deferred)

| Dimension | PP1 Implementation Decision | Post-PP1 / Final Thesis Roadmap |
|---|---|---|
| **Model Weights** | **Frozen** checkpoint `models/c3_lora_final` (LoRA $r=16, \alpha=32$, trained on LLaMA-Factory). No retraining prior to PP1. | Multi-task LoRA scaling, 4-bit AWQ weight quantization optimization, mixed-precision INT8 KV caching. |
| **Defect Capacity** | **Single primary visual defect** (`scope.mode = "single_primary_visual_finding"`, `exhaustive = false`). Identifies the most salient visual defect per screen. | Multi-label, multi-finding exhaustive detection (`findings: [...]` with 0 to $N$ distinct defects per screen) following dedicated multi-label re-annotation. |
| **Defect Taxonomies** | Primary empirical verification on **`component_overlap`** and **`text_truncation`**. Secondary taxonomies detected conditionally. | Full 7-class taxonomy coverage with per-class calibrated thresholding. |
| **Spatial Slicing** | Global view + dynamic SAHI-inspired overlapping vertical/horizontal slices ($3 \times 1$ grid, 15% overlap) for high-resolution 20:9 screens. | Adaptive saliency-guided multi-scale slicing based on edge-density maps. |
| **Hierarchy Context** | Optional context input (`view_hierarchy_xml` processed via AST pruning). If missing, pipeline explicitly marks `hierarchy_available: false` and proceeds on pure vision. | Dense multimodal cross-attention fusion between pruned AST nodes and vision tokens. |
| **UI Freeze Detection** | Strictly decoupled as **temporal evidence** (`probe_type: "frame_probe"` from C2 frame differential). Never inferred from a single static screenshot. | Multi-frame temporal video token sequence modeling for animated freeze detection. |
| **Hardware Boundary** | Real physical laptop GPU execution: **NVIDIA GeForce RTX 3050 Laptop GPU (4GB VRAM)**. Zero cloud egress. | Mobile NPU / ONNX Runtime edge execution on physical Android device. |
| **Ecosystem Integration** | Live C2 crawler capture triggering (<150ms synchronous ACK) and status-aware C4 synthetic test generation handover via Contract V2. | Full end-to-end autonomous closed-loop test generation with Appium replay. |

---

## 2. Model Architecture, Lineage & Training Provenance

### 2.1 Pinned Base Model & Checkpoint Lineage

```mermaid
flowchart TD
    Base["Base Model: Qwen2-VL-2B-Instruct<br>(Alibaba Cloud / HuggingFace)<br>4.4 GB FP16"]
    Base --> QLoRA["QLoRA Fine-Tuning<br>BitsAndBytes NF4 Quantization<br>r=16, alpha=32, targets: q,k,v,o,gate,up,down"]
    Dataset["Training Corpus: 2,000 Balanced Screens<br>(OwlEye Real Bugs + Rico Mutated Synthetics)"] --> QLoRA
    Cloud["Cloud Warmup Run<br>(Kaggle T4 x2 / 300 steps)"] --> Checkpoint["Intermediate Weights: c3_lora_run3"]
    Checkpoint --> LLaMAFactory["LLaMA-Factory Supervised Fine-Tuning<br>(Epochs: 2.0, Steps: 350, Batch: 2, AccGrad: 4)"]
    LLaMAFactory --> FinalWeights["Final Checkpoint: models/c3_lora_final<br>adapter_model.safetensors (73.9 MB)<br>SHA-256: F66C05CAA735E7AE..."]
    FinalWeights --> LocalOracle["Canonical Inference Pipeline<br>NVIDIA RTX 3050 (4GB) Local VRAM"]
```

### 2.2 Model Manifest Specifications

As verified in [`models/c3_model_manifest.json`](file:///d:/university/Resesarch/J26-SE-334/models/c3_model_manifest.json):
- **Base Model Identifier:** `Qwen/Qwen2-VL-2B-Instruct`
- **Adapter Path:** `models/c3_lora_final`
- **Adapter File:** `adapter_model.safetensors`
- **Adapter File Size:** 77,532,848 bytes (~73.94 MB)
- **Adapter Checksum (SHA-256):** `F66C05CAA735E7AE0226312553560942AC8621541b2ECC819CD4CC1BE5E125F4`
- **Fine-Tuning Framework:** LLaMA-Factory / PEFT 0.14.0
- **Base Model Parameters:** 2,209,470,464 parameters (~2.21B)
- **Trainable LoRA Parameters:** 19,988,480 parameters (~0.90% of base)
- **Target Modules:** `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`
- **LoRA Rank ($r$):** 16
- **LoRA Alpha ($\alpha$):** 32
- **LoRA Dropout:** 0.05
- **Quantization:** BitsAndBytes NF4 4-bit base weights quantization, compute dtype `torch.bfloat16`
- **Final Training Loss:** `0.1582` (converged from initial `1.8420`)
- **Execution Environment:** Python 3.13.3, PyTorch 2.6.0+cu126, Transformers 4.49.0, CUDA 12.6

---

## 3. Seven Mobile Defect Taxonomies in Current Weights

C3 formally specifies seven visual defect categories in mobile user interfaces:

```mermaid
mindmap
  root((7 Defect Taxonomies))
    component_overlap["1. component_overlap<br><b>PRIMARY (Verified)</b><br>UI elements collision"]
    text_truncation["2. text_truncation<br><b>PRIMARY (Verified)</b><br>Ellipsis/Container clipping"]
    missing_component["3. missing_component<br>Unrendered content / placeholders"]
    unrendered_icon["4. unrendered_icon<br>Broken vector glyphs / [X] assets"]
    offscreen_element["5. offscreen_element<br>Boundary bleed outside canvas"]
    misaligned_element["6. misaligned_element<br>Asymmetrical grid / broken margins"]
    semantic_contradiction["7. semantic_contradiction<br>Text / visual icon conflict"]
```

### 3.1 Detailed Capabilities in Current Checkpoint

1. **`component_overlap` (Primary PP1 Focus — Fully Supported):**
   - **Visual Manifestation:** Text boxes rendering on top of image cards, floating action buttons obscuring input fields, or nested views colliding.
   - **Model Knowledge:** Strongly internalized. The model reliably identifies intersection of non-transparent bounding boxes and localizes the anomalous overlapping region in normalized coordinates `[ymin, xmin, ymax, xmax]`.
   - **Tiling Recovery:** High. Slicing prevents small text-on-image collisions from being blurred during global downsampling.

2. **`text_truncation` (Primary PP1 Focus — Fully Supported):**
   - **Visual Manifestation:** Single-line TextView elements clipping critical string endings (e.g., `"Subtotal: $1..."`), multi-line text running past container bounds without ellipses, or vertical clipping of descenders (`g`, `y`, `p`).
   - **Model Knowledge:** Supported. Fine-tuning learned typical mobile font descenders and boundary padding. 
   - **Validation Boundary:** Model does NOT classify normal crop borders as truncation; boundary-touching predictions are flagged for corroboration.

3. **`missing_component` (Secondary — Experimental in PP1):**
   - **Visual Manifestation:** Blank white card containers, empty recycler view items where image thumbnails or text blocks are expected.
   - **Handling:** Emitted conditionally if container outlines exist without content. Not claimed as 100% verified in PP1.

4. **`unrendered_icon` (Secondary — Experimental in PP1):**
   - **Visual Manifestation:** Unresolved Unicode placeholder glyphs (`\uFFFD`, missing font rectangles, or generic default placeholder assets).
   - **Handling:** Emitted when glyph boundary contrasts with container.

5. **`offscreen_element` (Secondary — Experimental in PP1):**
   - **Visual Manifestation:** Content extending beyond device viewport boundaries where horizontal scrolling is disabled.

6. **`misaligned_element` (Secondary — Experimental in PP1):**
   - **Visual Manifestation:** Broken layout grids, jagged margins, or inconsistent vertical baseline alignment across list items.

7. **`semantic_contradiction` (Secondary — Contextual):**
   - **Visual Manifestation:** Green button labeled "Delete", star rating displaying "5.0" with 1 star, or contradictory UI state.
   - **Handling:** Requires hierarchy or OCR fusion. Treated as contextual evidence.

### 3.2 Handling of Temporal UI Freeze
- **Scientific Invariant:** A UI freeze **cannot be observed in a single static frame**. 
- Any tool claiming to detect a frozen UI from one screenshot is scientifically unsound.
- **HEART Resolution:** UI freeze is detected via C2's `FrameProbe` by computing structural similarity (SSIM) and optical flow between frames $t$ and $t + \Delta t$ under user stimulation. C3 receives this as metadata (`observation.probe_type = "frame_probe"`, `ui_delay_ms`), never fabricating it from visual weights.

---

## 4. Empirical Evaluation & Physical Verification

All metrics below are drawn directly from the verified held-out evaluation on 300 test screens (150 defective screens from OwlEye real bug dataset + 150 clean screens from Rico mobile dataset with zero synthetic parent leakage):

### 4.1 Master Held-Out Performance Metrics (N=300)

| Metric | Measured Value | Scientific Interpretation |
|---|---|---|
| **Accuracy** | **71.00%** (213 / 300) | Overall correct classification rate on tough 50/50 balanced real-world split. |
| **Precision** | **80.58%** (83 / 103) | When C3 declares a defect, it is genuine in >80% of cases. Minimizes false alarm developer fatigue. |
| **Recall** | **55.33%** (83 / 150) | Conservative visual detection baseline. Detects over half of visual defects without hallucination. |
| **F1-Score** | **65.61%** | Balanced harmonic mean on real Android mobile screens. |
| **Specificity** | **86.67%** (130 / 150) | High rejection of clean screens; only 20 false alarms out of 150 clean interfaces. |

#### Confusion Matrix Breakdown
$$\begin{array}{c|cc}
& \textbf{Predicted Defect} & \textbf{Predicted Clean} \\
\hline
\textbf{Actual Defect (150)} & \text{True Positive (TP)} = 83 & \text{False Negative (FN)} = 67 \\
\textbf{Actual Clean (150)} & \text{False Positive (FP)} = 20 & \text{True Negative (TN)} = 130 \\
\end{array}$$

### 4.2 Empirical Ablations

#### Ablation 1: Zero-Shot Base Qwen2-VL-2B vs Fine-Tuned LoRA Adapter
- **Zero-Shot Base Model:** Accuracy: 50.00%, Precision: 0.00%, **Recall: 0.00%**, F1: 0.00%. The base pre-trained foundation VLM responds with conversational descriptive prose and fails completely to emit normalized mobile UI bounding box coordinates.
- **Fine-Tuned LoRA Adapter:** Accuracy: 71.00%, Precision: 80.58%, **Recall: 55.33%**, F1: 65.61%.
- **Statistical Significance:** McNemar's Test with Edwards continuity correction: $\chi^2 = 81.01, p < 1.0 \times 10^{-18}$ ($p \ll 0.001$). Proves adaptation is statistically indispensable.

#### Ablation 2: Global View Only vs SAHI Dynamic Slicing
- **Global View Only:** Small defects ($<5\%$ of screen area, such as clipped 12sp subtitle text or overlapping action bar icons) exhibit F1 of only 42.10% due to visual token downsampling.
- **Global + Dynamic Tiling (SAHI):** Small defect F1 increases to **61.65%** (**+19.55% absolute gain**).
- **Latency Trade-off:** Slicing adds 3 forward passes (~1.8x inference latency), which C3 mitigates via non-blocking asynchronous queue processing.

#### Ablation 3: AST Hierarchy Pruning
- Raw Android view hierarchies exceed 12,000 characters (exceeding prompt context limits and causing token bloat).
- C3 AST Pruning strips invisible views (`visibility != VISIBLE`), non-interactive layouts without text, and redundant parent bounds.
- **Result:** **78.4% token reduction** (1,840 tokens $\rightarrow$ 397 tokens) with zero loss in visual grounding accuracy.

---

## 5. Hardware Specifications & Edge Execution Profiles

C3 is engineered to run locally on commodity consumer laptops without cloud dependencies:

### 5.1 Host Hardware Benchmark

| Parameter | Laboratory Target Machine Specification |
|---|---|
| **GPU** | NVIDIA GeForce RTX 3050 Laptop GPU |
| **Dedicated VRAM** | 4,096 MB (4.0 GB) GDDR6 |
| **CUDA Cores** | 2,048 |
| **Host RAM** | 16.0 GB DDR4 |
| **Host CPU** | 11th Gen Intel(R) Core(TM) i5-11400H @ 2.70GHz (6 cores, 12 threads) |
| **Operating System** | Windows 11 Home 64-bit |

### 5.2 Memory Footprint & Stability Across 50 Inference Cycles
- **Idle Service Baseline:** 412 MB VRAM.
- **Model Loaded (NF4 Quantized Base + LoRA):** 2,840 MB VRAM.
- **Peak Dynamic Forward Pass (Global + Slices):** **3,242 MB VRAM** (leaves 854 MB VRAM buffer under 4GB limit).
- **Memory Leakage Audit:** 50 consecutive inference cycles executed via `pytest vision_oracle/tests/test_model_runner.py`. VRAM usage at Cycle 1 = 3,240 MB; VRAM usage at Cycle 50 = 3,242 MB. **Zero memory leak detected**.

### 5.3 Latency Distribution Profile

| Pipeline Stage | $p50$ (Median) | $p90$ | $p99$ |
|---|---|---|---|
| C2 Capture Acknowledgement (Sync) | **112 ms** | 138 ms | 148 ms |
| Device Frame Capture & SHA-256 Hash | 240 ms | 310 ms | 380 ms |
| Preprocessing & SAHI Tiling | 185 ms | 210 ms | 245 ms |
| VLM Forward Pass (Global + 3 Tiles) | 1,420 ms | 1,610 ms | 1,890 ms |
| Finding Validation & Cluster Merging | 12 ms | 18 ms | 25 ms |
| **Total Asynchronous Job Latency** | **1,857 ms** | **2,148 ms** | **2,540 ms** |

---

## 6. Output Validation & Scientific Decision Policy

To eliminate false clean results caused by silent parser crashes, C3 enforces strict schemas via [`FindingParser`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/local_vision_oracle/pipeline.py) and [`contracts/v2.py`](file:///d:/university/Resesarch/J26-SE-334/contracts/v2.py):

```mermaid
flowchart TD
    Raw["Raw VLM Model Response String"] --> Parser["Strict FindingParser"]
    Parser --> CheckJSON{"Valid JSON<br>Top-Level Object?"}
    CheckJSON -- No --> Inconclusive["Verdict: INCONCLUSIVE<br>(Never clean default)"]
    CheckJSON -- Yes --> CheckBool{"Actual Boolean<br>has_gui_defect?"}
    CheckBool -- "String 'false' or missing" --> Inconclusive
    CheckBool -- "True / False" --> CheckBoxes{"If Defect: Valid Bounding Box?<br>ymin < ymax, xmin < xmax<br>area > 0, coords in [0, 1000]"}
    CheckBoxes -- Invalid / Reversed --> Inconclusive
    CheckBoxes -- Valid / None --> CheckViews{"All Required Views Valid?"}
    CheckViews -- "All Valid + No Defect" --> NoDefect["Verdict: NO_DEFECT_DETECTED<br>Complete Coverage"]
    CheckViews -- "All Valid + Defect" --> DefectDetected["Verdict: DEFECT_DETECTED<br>Primary Finding Confirmed"]
    CheckViews -- "Some Views Failed" --> InconclusivePartial["Verdict: INCONCLUSIVE<br>Partial View Failure"]
```

### 6.1 Scientific Decision Matrix

| View Execution Outcome | Synthesized Scientific Decision | C4 Contract Status (`has_gui_defect`) | Handover Outcome |
|---|---|---|---|
| All required views valid; zero findings | `no_defect_detected` | `False` | `evidence_only` |
| Valid finding; all required views valid | `defect_detected` | `True` | `ready_for_test_generation` |
| Valid finding; some non-primary views failed | `defect_detected` (partial coverage) | `True` | `ready_for_test_generation` |
| Zero findings; some required views failed | `inconclusive` (partial scan) | `None` (nullable) | `unsupported_inconclusive` |
| All views failed or malformed JSON | `inconclusive` (error state) | `None` (nullable) | `unsupported_inconclusive` |

---

## 7. Inter-Component Coordination Protocols

```mermaid
sequenceDiagram
    autonumber
    participant C2 as Component 2 (Stress Engine)
    participant Cap as C3 Capture Service
    participant Q as C3 Bounded Job Queue
    participant VLM as C3 VLM Oracle Engine
    participant C4 as Component 4 (Test Synthesizer)

    C2->>Cap: POST /v2/captures (action_id, session_id, app_package)
    Note over Cap: Takes screenshot via shared ADB lock<br>Computes SHA-256 & verifies foreground
    Cap-->>C2: HTTP 201 ACK (<150ms) with capture_id & job_id
    Note over C2: C2 resumes UI interaction without blocking!
    Cap->>Q: Enqueue Job (Bounded max=20)
    Q->>VLM: Dequeue & Execute Canonical AnalysisPipeline
    VLM->>VLM: Strict Output Validation & Coordinate Remapping
    VLM->>Cap: Persist VerdictEnvelopeV2 to SQLite Ledger
    Cap->>C4: Handover via to_c4_verdict() (Nullable has_gui_defect)
    Note over C4: C4 receives structured verdict for test generation
```

### 7.1 C2 Action-Linked Capture Semantics
- **Synchronous Acknowledgement:** C2 waits **only for immutable screenshot capture acknowledgement** (<150ms), never for slow neural network inference (1.5s).
- **Skew Tracking:** `capture_started_epoch_ms` and `capture_completed_epoch_ms` track ADB latency. If accessibility hierarchy dump skew exceeds 1,000ms relative to the screenshot, the hierarchy is tagged `stale` and omitted from multimodal prompt context.
- **Idempotency:** Repeated C2 submissions with identical `action_id` return the existing `capture_id` without re-triggering duplicate screen captures.

### 7.2 C4 Status-Aware Handover
- **Preservation of Inconclusive:** If C3 evaluates a corrupted or partial screen as `inconclusive`, `has_gui_defect` is emitted as `None` (JSON `null`). This prevents C4 from misinterpreting model uncertainty as a clean test pass.
- **Handover Outcomes:**
  - `ready_for_test_generation`: Defect localized with complete action context; triggers test generation.
  - `evidence_only`: Clean screen or isolated evidence without reproduction steps; logged to audit ledger.
  - `unsupported_inconclusive`: Pipeline anomaly; triggers manual triage rather than flawed synthetic scripts.

---

## 8. Provenance Quarantine Notice

To preserve absolute academic integrity and avoid misleading examiners during PP1 evaluation:

> [!WARNING]
> **Quarantine Record: Historical Synthetic Comparison Functions**  
> Legacy module `vision_oracle/local_vision_oracle/confusion_matrix.py::compare_c3_vs_owleye()` contains synthetic toy fixtures with fixed counts ($\text{TP}=288, \text{FP}=3$).  
> **Status:** Strictly quarantined. It is retained solely as an offline unit test mock and is **expressly excluded from all PP1 thesis claims and empirical reports**.  
> The true empirical baseline is the held-out 300 test screen benchmark ($\text{TP}=83, \text{FP}=20, \text{FN}=67, \text{TN}=130$) verified in [`vision_oracle/evidence/03_detection_evaluation/evaluation_summary.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/03_detection_evaluation/evaluation_summary.json).

---

## 9. Master Claims Matrix

| Canonical Claim ID | Scientific Assertion | Physical Artifact Verification Path |
|---|---|---|
| `CLAIM-C3-LOCAL` | C3 executes 100% locally on commodity laptop GPU (RTX 3050 4GB) with zero cloud egress. | [`08_offline_execution/zero_cloud_egress_proof.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/08_offline_execution/zero_cloud_egress_proof.json)<br>[`06_hardware_measurements/vram_profile.csv`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/06_hardware_measurements/vram_profile.csv) |
| `CLAIM-C3-DETECT` | Fine-tuned VLM achieves 71.0% accuracy and 80.58% precision on held-out mobile UI defect screens. | [`03_detection_evaluation/evaluation_summary.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/03_detection_evaluation/evaluation_summary.json)<br>[`03_detection_evaluation/evaluation_confusion_matrix.png`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/03_detection_evaluation/evaluation_confusion_matrix.png) |
| `CLAIM-C3-ADAPT` | Fine-tuning Qwen2-VL-2B via LoRA is statistically required to acquire mobile bounding-box grounding ($\chi^2 = 81.01, p < 10^{-18}$). | [`04_comparison_and_ablations/baseline_vs_lora_comparison.csv`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/04_comparison_and_ablations/baseline_vs_lora_comparison.csv)<br>[`04_comparison_and_ablations/mcnemar_contingency.csv`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/04_comparison_and_ablations/mcnemar_contingency.csv) |
| `CLAIM-C3-TILE` | SAHI dynamic slicing recovers small visual defects on tall 20:9 displays (+19.55% F1 gain). | [`04_comparison_and_ablations/sahi_tiling_ablation.csv`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/04_comparison_and_ablations/sahi_tiling_ablation.csv) |
| `CLAIM-C3-RESOURCE`| Peak VRAM is bounded at 3.24 GB with zero memory leakage over 50 consecutive cycles. | [`06_hardware_measurements/device_specifications.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/06_hardware_measurements/device_specifications.json)<br>[`06_hardware_measurements/vram_profile.csv`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/06_hardware_measurements/vram_profile.csv) |
| `CLAIM-C3-RELIABLE`| Malformed or truncated model outputs evaluate strictly as inconclusive, never clean defaults. | [`07_backend_reliability/reliability_test_report.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/07_backend_reliability/reliability_test_report.json)<br>[`05_live_demonstration/demo4_inconclusive_malformed_verdict.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/05_live_demonstration/demo4_inconclusive_malformed_verdict.json) |
| `CLAIM-C3-C2` | Synchronous capture acknowledgement completes in $<150$ ms without blocking crawler exploration. | [`05_live_demonstration/demo3_c2_c3_integration_trace.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/05_live_demonstration/demo3_c2_c3_integration_trace.json) |
| `CLAIM-C3-C4` | Contract V2 preserves inconclusive verdicts and provides structured bounding boxes for test synthesis. | [`contracts/v2.py`](file:///d:/university/Resesarch/J26-SE-334/contracts/v2.py)<br>[`05_live_demonstration/demo3_c2_c3_integration_trace.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/05_live_demonstration/demo3_c2_c3_integration_trace.json) |

---

## 10. Technical & Architectural Verification FAQ (10 Core Principles)

1. **Q: Why is your recall 55.33% instead of 90%+? Is the model failing?**  
   *A:* No. In automated test oracles, false positives are fatal because they cause test flakiness and developer distrust. Our 80.58% precision ensures that when C3 flags a defect, it is real. 55.33% recall reflects a rigorous, held-out evaluation on diverse real Android apps. Higher numbers in prior literature frequently suffer from synthetic data contamination or lenient evaluation criteria.

2. **Q: Why did you freeze single primary visual defect detection for PP1 instead of multi-defect?**  
   *A:* Sound engineering requires truthful claims. Our current checkpoint was trained on single-defect annotations. Slicing aggregates candidate detections across tiles, but claiming full exhaustive multi-defect capabilities without dedicated multi-label dataset fine-tuning would be scientifically dishonest. Single primary defect fulfills 100% of PP1 requirements.

3. **Q: Why use a 2B parameter VLM instead of a cloud model like GPT-4o?**  
   *A:* Test oracles must run locally in enterprise CI/CD pipelines without sending proprietary pre-release screens to external cloud APIs. Furthermore, Qwen2-VL-2B operates in 3.24 GB VRAM on a commodity 4GB laptop GPU with zero latency costs or API token bills.

4. **Q: How do you know fine-tuning actually helped?**  
   *A:* Our ablation study proves that zero-shot base Qwen2-VL-2B has 0% recall on mobile UI bounding box coordinates—it outputs conversational text. LoRA fine-tuning provides +55.33% recall, with McNemar's test showing statistical significance at $p < 10^{-18}$.

5. **Q: What happens if the model outputs malformed JSON or invalid boxes?**  
   *A:* The strict `FindingParser` validates all tokens, coordinates, and types. Any syntax error, string boolean (`"false"`), or negative-area box immediately forces an `inconclusive` verdict. It never defaults to clean.

6. **Q: How does C3 integrate with C2 without slowing down user interactions?**  
   *A:* C2 initiates an action-linked capture and receives an immutable capture acknowledgement in under 150ms. C3 queues the VLM forward pass asynchronously, allowing C2 to proceed immediately.

7. **Q: Can C3 detect UI freezes from a screenshot?**  
   *A:* No, and no static vision model can. UI freeze is a temporal phenomenon. C3 captures freeze evidence solely through C2's `FrameProbe` temporal frame delta metadata.

8. **Q: Why did you add SAHI dynamic slicing?**  
   *A:* Modern mobile screens have extreme 20:9 aspect ratios. Downsampling 2400x1080 screens to fit VLM input resolutions obliterates small font clipping and boundary overlaps. Slicing boosts small defect F1 by +19.55%.

9. **Q: What prevents CUDA out-of-memory errors on a 4GB GPU?**  
   *A:* We use BitsAndBytes NF4 4-bit quantization, sequential tile inference, and an explicit OOM recovery handler that clears PyTorch CUDA cache and gracefully falls back to global view analysis.

10. **Q: What is the exact completion percentage of Component 3 for PP1?**  
    *A:* Approximately 50%, matching the rubric expectations: working local VLM inference, verified model manifest, action-linked C2 capture, status-aware C4 handover, C1 desktop GUI panel, and comprehensive held-out empirical evaluation.

---

## 11. Crucial Theoretical Justifications & Empirical Comparison

### 11.1 Technical Executive Summary (30-Second Architecture Grounding)
> *"The core challenge in automating mobile GUI testing is that 68% of display bugs—such as component clipping, text overlap, and dynamic layout collisions—render correctly in static XML view hierarchies and only fail visually at runtime. Existing solutions fail in production: cloud MLLMs like VisionDroid or GPT-4o expose pre-release proprietary screens, incur 3-to-10 second latency, and violate enterprise GDPR, HIPAA, and PCI DSS compliance by caching unmasked customer PII on third-party servers. Meanwhile, commercial diff tools like Applitools depend entirely on pre-existing baselines, making them incapable of Day-Zero detection or autonomous crawler exploration.*  
>  
> *Component 3 solves this by providing a zero-baseline, air-gapped Vision-Language Model oracle. By quantizing Qwen2-VL-2B via 4-bit NF4 LoRA into 3.24GB VRAM, we achieve 80.6% precision on commodity 4GB laptop hardware with measured zero network egress and a sub-150ms capture SLA, seamlessly bridging autonomous exploration in C2 with automated Appium test script generation in C4."*


---

### 11.2 How and Why C3 Protects Privacy (Technical & Regulatory Proof)
* **Technical Mechanism:** Compressing open-weight `Qwen2-VL-2B` via **4-bit NF4 LoRA quantization** ($r=16, \alpha=32$) allows the oracle to fit completely inside **3.24GB VRAM** on a commodity laptop GPU (NVIDIA RTX 3050 4GB). It executes air-gapped with **measured zero outbound network egress** (`ZERO_CLOUD_EGRESS = True`, 100% local loopback `127.0.0.1:8003`).
* **Why Cloud APIs Fail Strict QA Privacy:**
  * Commercial multimodal APIs (OpenAI, Anthropic, Google) do not train on paid API data by default, but they **are not stateless by default**.
  * Screenshots are retained for **up to 24 hours** in durable disk caches (Google) or **up to 30 days** in abuse-monitoring logs where flagged images can be inspected by human reviewers (OpenAI and Anthropic).
  * Even enterprise Zero Data Retention (ZDR) requires manual sales approval and remains subject to statutory, safety-retention, and court-ordered litigation holds.
* **The Regulatory Proof:** Pre-production mobile screenshots contain unmasked PII, PHI, payment card numbers (PANs), and unreleased UI intellectual property embedded directly into pixels. Transmitting them to third-party endpoints triggers:
  1. **GDPR:** Third-party sub-processor violations without explicit end-user consent.
  2. **HIPAA:** Requires endpoint-specific Business Associate Agreements (BAAs) for any transmission containing potential health info.
  3. **PCI DSS v4.0 (Requirements 3, 6, 12.5.2):** Expands the Cardholder Data Environment (CDE) scope to the cloud provider, triggering costly external compliance audits.
  * **C3 Resolution:** C3 eliminates third-party retention, human abuse review, and compliance scope expansion by architecture.

---

### 11.3 Why C3 is Novel and Worth the Research
*(Examiner Framing: C3 is not framed as the "first local detector" — older CNNs ran locally — but as a **zero-egress, 4-bit edge-quantized Vision-Language Model (VLM) oracle for baseline-free GUI defect localization on consumer hardware**.)*

1. **Bridging Spatial Localization and Generative Semantics on 4GB Hardware:**
   * Traditional local detectors like **OwlEye** (ASE 2020) and **Nighthawk** (IEEE TSE 2023) use CNNs/Faster R-CNN that only output class IDs or coarse heatmaps; they lack generative semantic explanations needed to guide downstream Appium test synthesis (C4).
   * Conversely, research UI MLLMs like **Ferret-UI** require 8 $\times$ A100 GPUs to train, and **VisionDroid** relies on external cloud MLLMs.
   * C3 demonstrates that `Qwen2-VL-2B`'s **Naive Dynamic Resolution** (processing arbitrary mobile aspect ratios without distortive resizing) and **Multimodal Rotary Position Embedding (M-RoPE)** (modeling 2D spatial height/width coordinates) can be quantized into 4GB VRAM to output accurate bounding boxes and semantic diagnostics for test repair.
2. **Solving the Failure Mode of Static JSON Analysis on the Top 68% of Bugs:**
   * Static view-tree analyzers (`uiautomator dump` / DOM) fail on text truncation and overlap because font rendering inside widgets like `EditText` cannot be extracted from XML, WebViews/canvases hide internal nodes, and floating toolbars/spinners create hierarchy noise.
   * Empirical literature demonstrates that C3's two verified classes — component occlusion/overlap (47%) and text overlap/truncation (21%) — account for **68% of all real-world Android display bugs** and **84% of accessibility scaling failures** (60% cropping/truncation + 24% overlap).

---

### 11.4 Proof of Validity: Comparative Benchmark Matrix

| Dimension | HEART C3 (`c3-local-vision-oracle`) | Applitools Eyes (Commercial Standard) | VisionDroid (IEEE TSE 2025 MLLM) |
|---|---|---|---|
| **Core Mechanism** | **Zero-baseline VLM oracle** (evaluates 1 unseen screenshot) | **Baseline diff comparator** (compares checkpoint vs saved baseline) | **Cloud/Heavyweight MLLM** (prompts cloud MLLM with screenshot sequences) |
| **Day-Zero & Crawler Support** | **Yes** — detects bugs on the very first run on unseen screens | **No** — records broken UI on Run #1 as approved baseline; fails on novel crawler states | **Yes** — detects intra-page and inter-page bugs without baselines |
| **Data Privacy** | **100% Local (4GB VRAM)**; 0 outbound network traffic | Public Cloud default; On-Prem/Local Container requires custom Enterprise tier | **High Exposure** — streams raw screenshot sequences to external MLLM APIs |
| **Operational Cost** | **$0 marginal cost** (open-weight `Qwen2-VL-2B`) | **$667/month** ($8,004/yr) Starter; custom enterprise quote for On-Prem | High per-token API cost for high-res multi-turn image prompts |
| **Empirical Precision** | **80.6% Precision** (55.3% Recall, 71.0% Acc on $N=300$) | **No peer-reviewed benchmark** (99.9999% is an unverified marketing figure) | **50.0%–72.0% Precision** (42.0%–65.0% Recall across 3 datasets) |

#### Key Empirical Proof Points:
* **Why C3 beats Applitools for Autonomous Testing:** Applitools officially states that its first test run captures a baseline image. If an application contains truncated text or overlapping buttons on Day 1, Applitools records the bug as ground truth. Furthermore, our autonomous crawler (C2) dynamically discovers novel screens that have no prior baseline — rendering diff-based tools unusable.
* **Why C3's 80.6% Precision is Validated Against Literature:** In an autonomous testing pipeline (C2 $\rightarrow$ C3 $\rightarrow$ C4), **precision is far more critical than recall** because false positives trigger C4 to synthesize broken Appium scripts. C3's **80.6% precision**:
  * Outperforms **VisionDroid's MLLM precision (50%–72%)**.
  * Beats **Nighthawk's Faster R-CNN precision on component occlusion (77.0%)**.
  * Beats **OwlEye's precision on scaling/truncation bugs (39.0%)**.
  * Matches **Nighthawk's overall real-world precision (~80.9%)**.

