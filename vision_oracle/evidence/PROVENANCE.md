# Provenance, Training Lineage & Experimental Quarantine Log

**Component:** Component 3 (Local Vision-Semantic Oracle)  
**Lead Researcher:** M.L. Booso (IT23452916)  
**Auditor:** HEART Academic Evaluation Committee  

---

## 1. Checkpoint Training & Lineage Timeline

The training and development timeline follows an unbroken, verified chain of physical evidence:

```mermaid
timeline
    title Component 3 Model & Pipeline Timeline
    2026-10-01 to 2026-10-06 : Dataset curation & distillation : OwlEye extraction and teacher pseudo-labeling
    2026-10-08 to 2026-10-12 : Cloud training warm-up : Kaggle Dual T4 GPU QLoRA warm-up (c3_lora_run3)
    2026-10-14 23:54 : Final local fine-tuning : LLaMA-Factory SFT run completes (c3_lora_final, loss=0.1582)
    2026-10-15 07:39 : Held-out empirical evaluation : 300 test screen run (71% acc, 80.58% prec, 55.33% rec)
    2026-10-16 14:22 : Repository integration : C3 pipeline integrated into J26-SE-334 (commit 3d1c292)
    2026-10-18 20:00 : PP1 freeze & hardening : Bounded queue, action-linked capture, contract v2, GUI panel
```

### 1.1 Physical Training Artifacts on Disk
- **Training Config:** `RD/LLaMA-Factory/examples/train_lora/qwen2vl_lora_c3_final.yaml`
- **Initial Weights:** `c3_lora_run3_weights.zip` (Kaggle SFT run 3)
- **Final Weights Safetensors:** `models/c3_lora_final/adapter_model.safetensors`
- **Checksum:** `F66C05CAA735E7AE0226312553560942AC8621541b2ECC819CD4CC1BE5E125F4`
- **Manifest:** [`models/c3_model_manifest.json`](file:///d:/university/Resesarch/J26-SE-334/models/c3_model_manifest.json)

---

## 2. Experimental Quarantine Log

In accordance with **Protocol 2 (Ground Truth Invariance & Evidence Traceability)**, the following code artifact is formally quarantined:

### 2.1 Quarantined Artifact: `compare_c3_vs_owleye()`
- **Location:** `vision_oracle/local_vision_oracle/confusion_matrix.py::compare_c3_vs_owleye()`
- **Description:** A legacy mock function returning fixed synthetic values ($\text{TP}=288, \text{FP}=3$).
- **Reason for Quarantine:** These numbers represent a synthetic unit test fixture created during initial stubbing, NOT an actual empirical evaluation.
- **Audit Action Taken:**
  1. The function is quarantined and tagged as test-mock-only.
  2. All references to this function have been completely excised from all thesis claims, documentation, and evaluation summaries.
  3. The **sole authoritative empirical evaluation** recognized for Component 3 is the held-out 300 test screen benchmark:
     - **True Positives (TP):** 83
     - **False Positives (FP):** 20
     - **False Negatives (FN):** 67
     - **True Negatives (TN):** 130
     - **Total:** 300 screens (150 clean, 150 defective)
     - **Evidence Path:** [`vision_oracle/evidence/03_detection_evaluation/evaluation_summary.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/03_detection_evaluation/evaluation_summary.json)
