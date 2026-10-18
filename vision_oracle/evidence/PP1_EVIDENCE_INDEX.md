# HEART Component 3: Master PP1 Evidence Index & Audit Dossier

**Student:** M.L. Booso (IT23452916)  
**Research Component:** C3 Local Vision-Semantic Test Oracle  
**Group:** J26-SE-334  
**Branch:** `feat/c3-local-vision-oracle`  
**Evaluation Rubric:** `01-PP1-Assessment-Criteria.pdf`, `02-PP1-Template.pdf`  

---

## 1. Master Evidence Traceability Matrix

Every single requirement from the PP1 Rubric is mapped below directly to an inspectable artifact file on disk:

| # | Evidence Domain | What Panel Inspects | File Artifact on Disk | Provenance / Metric Verified |
|---|---|---|---|---|
| **1** | **Working Prototype** | Real defective screenshot evaluated with bounding box overlay & latency | [`05_live_demonstration/demo1_defective_screen_overlay.png`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/05_live_demonstration/demo1_defective_screen_overlay.png)<br>[`05_live_demonstration/demo1_defective_verdict.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/05_live_demonstration/demo1_defective_verdict.json) | Local pipeline detects `component_overlap` at `[765, 36, 878, 955]` in **1.42s**. |
| **2** | **Model Identity & Weights** | Base model, adapter checksum, runtime config, and training run | [`01_model_identity/c3_model_manifest.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/01_model_identity/c3_model_manifest.json)<br>[`01_model_identity/training_loss.png`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/01_model_identity/training_loss.png)<br>[`01_model_identity/01_kaggle_training_yaml.png`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/01_model_identity/01_kaggle_training_yaml.png) | Qwen2-VL-2B-Instruct + LoRA ($r=16, \alpha=32$). Adapter SHA-256: `f66c05caa7...`. Converged train loss: `0.2324`. |
| **3** | **Detection Evaluation** | Held-out 300 test screens evaluation with confusion matrix | [`03_detection_evaluation/evaluation_summary.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/03_detection_evaluation/evaluation_summary.json)<br>[`03_detection_evaluation/evaluation_confusion_matrix.png`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/03_detection_evaluation/evaluation_confusion_matrix.png)<br>[`03_detection_evaluation/04_held_out_eval_mcnemar.png`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/03_detection_evaluation/04_held_out_eval_mcnemar.png) | **71.0% Accuracy**, **80.58% Precision**, **55.33% Recall**, **65.61% F1** across 150 clean and 150 defective screens. |
| **4** | **Fine-Tuning Comparison** | Base Qwen2-VL-2B vs fine-tuned LoRA adapter | [`04_comparison_and_ablations/baseline_vs_lora_comparison.csv`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/04_comparison_and_ablations/baseline_vs_lora_comparison.csv) | Zero-shot base model: **0% Recall** (cannot predict mobile UI boxes) $\rightarrow$ LoRA adapter: **55.33% Recall**. |
| **5** | **Slicing (SAHI) Ablation** | Adapter without tiling vs adapter with dynamic tiling | [`04_comparison_and_ablations/sahi_tiling_ablation.csv`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/04_comparison_and_ablations/sahi_tiling_ablation.csv) | Tiling recovers small clipping defects on 20:9 screens: **+19.55% F1 boost** on elements $<5\%$ screen area. |
| **6** | **Integration Trace** | Matching session/action/capture IDs across C2 crawler and C3 oracle | [`05_live_demonstration/demo3_c2_c3_integration_trace.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/05_live_demonstration/demo3_c2_c3_integration_trace.json)<br>[`05_live_demonstration/demo3_c2_c3_integration_overlay.png`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/05_live_demonstration/demo3_c2_c3_integration_overlay.png) | Synchronous C2 `<150ms` capture ACK; C3 verdict published to C4 synthesis via Contract V2 (`to_c4_verdict`). |
| **7** | **Hardware Measurements** | Host laptop specs, measured peak VRAM, and latency | [`06_hardware_measurements/device_specifications.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/06_hardware_measurements/device_specifications.json)<br>[`06_hardware_measurements/vram_profile.csv`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/06_hardware_measurements/vram_profile.csv) | NVIDIA RTX 3050 Laptop GPU (4GB VRAM). Peak footprint: **3.24 GB VRAM**. Zero leak over 50 cycles. |
| **8** | **Reliability & Error Handling** | Malformed inputs, queue backpressure, and inconclusive handling | [`07_backend_reliability/reliability_test_report.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/07_backend_reliability/reliability_test_report.json)<br>[`05_live_demonstration/demo4_inconclusive_malformed_verdict.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/05_live_demonstration/demo4_inconclusive_malformed_verdict.json) | 23/23 tests pass. Malformed inputs return `inconclusive`, never clean. Queue returns HTTP 503 on saturation. |
| **9** | **Offline Execution Proof** | Verification of zero external cloud egress | [`08_offline_execution/zero_cloud_egress_proof.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/08_offline_execution/zero_cloud_egress_proof.json) | Air-gapped edge execution verified with networking disabled. `ZERO_CLOUD_EGRESS = True`. |
| **10** | **Prototype User Feedback** | Feedback from team members and testers with resulting changes | [`09_prototype_feedback/user_feedback_log.md`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/09_prototype_feedback/user_feedback_log.md) | Led to visual bounding box overlays in C1 app, non-blocking capture queue, and C4 nullable defect contract. |
| **11** | **Research Progress & Defense** | Proposal progress (~50%), acknowledged limits, and viva script | [`10_research_progress_and_viva/research_progress_summary.md`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/10_research_progress_and_viva/research_progress_summary.md)<br>[`10_research_progress_and_viva/viva_defense_script.md`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/10_research_progress_and_viva/viva_defense_script.md) | Addresses all 10 panel defense questions with defensible empirical evidence. |

---

## 2. Prepared 2-Minute Live Demonstration Sequence

1. **Step 1: One Defective Screen (`demo1_defective_screen_overlay.png`):**  
   - Show original mobile screenshot and run local analysis.
   - Predicted defect: `component_overlap` with red bounding box over clipped container.
   - Measured time: **1.42s**. Verdict saved to SQLite ledger.
2. **Step 2: One Clean Screen (`demo2_clean_screen_overlay.png`):**  
   - Show that C3 returns `no_defect_detected` with green badge.
   - Explain visual scope boundary (does not claim to detect all non-visual bugs).
3. **Step 3: One Real Integration Example (`demo3_c2_c3_integration_overlay.png`):**  
   - Show C2 crawler action trigger $\rightarrow$ C3 capture ACK ($<150\text{ ms}$) $\rightarrow$ C3 verdict $\rightarrow$ C4 contract handover.
   - Shared `session_id`, `action_id`, `capture_id` matching across the ledger.
4. **Step 4: One Failure / Inconclusive Example (`demo4_inconclusive_malformed_verdict.json`):**  
   - Show malformed/corrupted screen input evaluating strictly as `inconclusive` rather than clean.
