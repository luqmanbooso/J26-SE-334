# HEART Component 3: Empirical Evaluation & Evidence Repository (PP1 Panel Audit)

**Student:** M.L. Booso (IT23452916)  
**Group:** J26-SE-334  
**Component:** C3 Local Vision-Semantic Oracle  
**Branch:** `feat/c3-local-vision-oracle`  
**Repository Location:** `vision_oracle/results/`

---

## 1. Executive Summary & PP1 Core Proofs

This directory contains empirical evidence, audit manifests, confusion matrices, and ablation data supporting the implementation of Component 3 (Local Vision Oracle) in the HEART framework.

| Requirement | Panel Question | Empirical Proof & File Artifact | Status / Metric |
|---|---|---|---|
| **Useful Detection Task** | Does fine-tuned LoRA detect mobile UI bugs? | `evaluation_300_test/evaluation_summary.json` | **71.0% Acc**, **80.58% Precision**, **55.33% Recall**, **65.61% F1** |
| **Localization Proof** | Can the model localize bugs with bounding boxes? | `benchmarks/groq_test_bug4001_overlay.png` | `[ymin, xmin, ymax, xmax]` normalized visual bounding box |
| **Fine-Tuning Impact** | Did LoRA adaptation improve over base model? | `benchmarks/c3_run3_baseline_eval/` vs `evaluation_300_test/` | Base model: **0% Recall** (cannot predict boxes) $\rightarrow$ Adapter: **55.33% Recall** |
| **Slicing Benefit (SAHI)** | Does dynamic slicing help small UI elements? | `experiments/exp-02/ablation_analysis.json` | **+19.55% F1 boost** on small text truncations ($<5\%$ viewport) |
| **Hardware Feasibility** | Does it run locally under 4GB VRAM? | `experiments/exp-05/vram_profile.csv` | **3.24 GB VRAM** peak (RTX 3050 Laptop GPU verified) |
| **Inference Latency** | Is processing fast enough for automated testing? | `experiments/exp-04/latency_profile.csv` | **1.42s** (full frame), **2.89s** (3-slice SAHI), **<15ms** (AST collision check) |
| **Zero Cloud Egress** | Does inference leak screenshots to cloud APIs? | `contracts/v2.py`, `core/config.py` | Air-gapped edge execution (`ZERO_CLOUD_EGRESS=True`) |

---

## 2. Evidence Directory Structure

```
vision_oracle/results/
├── README.md                           # This panel audit guide
├── evaluation_300_test/                # Primary held-out evaluation (300 screens: 150 clean, 150 defective)
│   ├── evaluation_summary.json         # Precision, Recall, F1, Accuracy, Latency
│   ├── evaluation_confusion_matrix.png # Visual confusion matrix (TP: 83, FP: 20, TN: 130, FN: 67)
│   ├── evaluation_metrics.csv          # Per-class metrics breakdown
│   └── eval_checkpoint.json            # Item-by-item inference ledger (300 predictions)
├── experiments/                        # Rigorous academic ablation experiments (EXP-01 to EXP-05)
│   ├── exp-01/                         # OwlEye vs Rico baseline comparison
│   │   ├── confusion_matrices.json
│   │   └── metrics_summary.csv
│   ├── exp-02/                         # Multi-modal AST Pruning & Slicing ablation
│   │   ├── ablation_analysis.json
│   │   └── ablation_results.csv
│   ├── exp-03/                         # Statistical significance test (McNemar χ²)
│   │   └── mcnemar_contingency.csv
│   ├── exp-04/                         # Latency profiling & decomposition across pipeline stages
│   │   └── latency_profile.csv
│   └── exp-05/                         # VRAM consumption footprint profiling (<4GB constraint)
│       └── vram_profile.csv
├── manifests/                          # Verifiable dataset manifests (2,000 balanced corpus)
│   ├── dataset_manifest_summary.json   # 1,000 clean Rico + 500 mutated Rico + 500 OwlEye
│   ├── manifest_summary.json           # Train/Val/Test split splits (70/15/15)
│   ├── owleye_train.json               # Physical paths and annotations for OwlEye training split
│   ├── owleye_val.json                 # Validation split
│   ├── owleye_test.json                # Test split
│   ├── rico_calibration_256.json       # AWQ/Quantization calibration subset
│   └── rico_clean_eval_600.json        # Clean screen baseline evaluation subset
├── benchmarks/                         # Checkpoint progress history
│   ├── c3_run3_baseline_eval/          # Evaluation of intermediate Run 3 checkpoint
│   ├── c3_run4_eval/                   # Preliminary Run 4 evaluation
│   ├── c3_final_model_eval/            # Mini test set evaluation
│   ├── old_run1_eval/                  # Run 1 collapsed baseline audit (historical negative control)
│   ├── awq_calibration_summary.json    # NF4/AWQ quantization calibration report
│   ├── data_inspection_report.json     # Dataset distribution and integrity audit
│   ├── deduplication_owleye_test.json  # Exact perceptual duplicate removal hash table
│   ├── test_confusion_matrix.png       # Test split graphical confusion matrix
│   └── groq_test_bug4001_overlay.png   # Production overlay test visual sample
└── weights/                            # Local weights storage (gitignored; tracked in models/c3_lora_final)
    └── c3_lora_final/                  # Checkpoints 175, 350 & LoRA adapter weights
```

---

## 3. Defense Talking Points (Panel Alignment)

1. **Why Qwen2-VL-2B?**  
   Target deployment requires running on edge testing nodes (e.g. developer laptop with 4GB VRAM). Larger 7B+ models exceed the 4GB ceiling even under 4-bit quantization. Qwen2-VL-2B fits comfortably in 3.24GB VRAM.

2. **Why LoRA (Rank 16, Alpha 32)?**  
   Zero-shot base model has 0% recall on mobile UI bounding box prediction because web-scale pretraining lacks structured mobile coordinates. LoRA adapts query/value/key projections without catastrophic forgetting of general visual comprehension.

3. **Why Dynamic Slicing (SAHI)?**  
   Mobile screens have 20:9 aspect ratios. Downscaling high-resolution mobile screenshots (1080x2400) directly to 448x448 causes fine text (12-16px) to blur, hiding clipping defects. Slicing preserves pixel fidelity for small components ($<5\%$ of screen area).

4. **Why Multi-Modal AST Pruning?**  
   Pure visual reasoning can flag intentional overlapping UI elements (such as floating action buttons over lists). Querying the Android Accessibility Node Hierarchy (`boundsInScreen`) eliminates false positives in $<15\text{ ms}$.
