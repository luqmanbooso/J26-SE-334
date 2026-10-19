# Master Claims Matrix: Component 3 (Local Vision-Semantic Oracle)

**Component:** Component 3 (HEART Testing Framework)  
**Lead Researcher:** M.L. Booso (IT23452916)  
**Milestone:** PP1 Evidence Verification  
**Evaluation Standard:** Protocol 2 (Traceability & Ground Truth Invariance)  

Every claim asserted for Component 3 is catalogued below with its canonical ID, exact empirical metric, and verifiable physical file artifact on disk.

---

## Master Claims Table

| Claim ID | Core Scientific Assertion | Empirical Metric / Measurement | Primary Physical Evidence File |
|---|---|---|---|
| `CLAIM-C3-LOCAL` | **Edge Deployment Without Cloud Egress:** C3 runs completely offline on consumer laptop GPU (NVIDIA RTX 3050 4GB VRAM) without external network dependencies. | Zero external IP egress connections during 50 inference cycles; 100% loopback (`127.0.0.1`). | [`08_offline_execution/zero_cloud_egress_proof.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/08_offline_execution/zero_cloud_egress_proof.json)<br>[`06_hardware_measurements/vram_profile.csv`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/06_hardware_measurements/vram_profile.csv) |
| `CLAIM-C3-DETECT` | **High-Precision Defect Grounding:** Fine-tuned VLM detects primary mobile UI visual defects with low false alarm rate. | **71.00% Accuracy**, **80.58% Precision**, **55.33% Recall**, **65.61% F1** across 300 balanced held-out screens (150 clean, 150 defective). | [`03_detection_evaluation/evaluation_summary.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/03_detection_evaluation/evaluation_summary.json)<br>[`03_detection_evaluation/evaluation_confusion_matrix.png`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/03_detection_evaluation/evaluation_confusion_matrix.png) |
| `CLAIM-C3-ADAPT` | **Statistical Necessity of Domain Adaptation:** Off-the-shelf foundation VLMs cannot localize mobile defects without QLoRA adaptation. | Base Qwen2-VL-2B: **0% Recall** (fails to output coordinate boxes) $\rightarrow$ LoRA: **55.33% Recall** ($\chi^2 = 81.01, p < 10^{-18}$). | [`04_comparison_and_ablations/baseline_vs_lora_comparison.csv`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/04_comparison_and_ablations/baseline_vs_lora_comparison.csv)<br>[`04_comparison_and_ablations/mcnemar_contingency.csv`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/04_comparison_and_ablations/mcnemar_contingency.csv) |
| `CLAIM-C3-TILE` | **Small Defect Recovery via SAHI Slicing:** Dynamic spatial slicing mitigates token downsampling on tall 20:9 aspect ratio smartphone screens. | **+19.55% F1 boost** (42.10% $\rightarrow$ 61.65%) on small visual defects occupying $<5\%$ screen area. | [`04_comparison_and_ablations/sahi_tiling_ablation.csv`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/04_comparison_and_ablations/sahi_tiling_ablation.csv) |
| `CLAIM-C3-RESOURCE`| **Resource Bound and VRAM Stability:** Peak GPU memory is strictly bounded within 4GB consumer laptop budget with zero runtime memory leakage. | Peak VRAM: **3,242 MB** (854 MB safety headroom under 4,096 MB limit); delta after 50 continuous cycles: **0 MB**. | [`06_hardware_measurements/device_specifications.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/06_hardware_measurements/device_specifications.json)<br>[`06_hardware_measurements/vram_profile.csv`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/06_hardware_measurements/vram_profile.csv) |
| `CLAIM-C3-RELIABLE`| **Scientifically Sound Validation Policy:** Malformed or truncated model outputs evaluate strictly as inconclusive, never clean defaults. | 11 synthetic malformed responses evaluated; 100% categorized as `inconclusive`, 0% false clean passes. | [`07_backend_reliability/reliability_test_report.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/07_backend_reliability/reliability_test_report.json)<br>[`05_live_demonstration/demo4_inconclusive_malformed_verdict.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/05_live_demonstration/demo4_inconclusive_malformed_verdict.json) |
| `CLAIM-C3-C2` | **Action-Linked Asynchronous Decoupling:** C2 crawler action trigger receives synchronous capture acknowledgement without blocking on neural inference. | Synchronous capture ACK latency: **$p50 = 112\text{ ms}, p99 = 148\text{ ms}$**; shared `session_id` and `action_id` immutable correlation. | [`05_live_demonstration/demo3_c2_c3_integration_trace.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/05_live_demonstration/demo3_c2_c3_integration_trace.json) |
| `CLAIM-C3-C4` | **Status-Aware Test Synthesis Handover:** Contract V2 preserves inconclusive verdicts and provides structured bounding boxes for test synthesis. | Nullable `has_gui_defect` prevents false regression test generation on inconclusive screens; typed handover outcomes (`ready_for_test_generation`, `evidence_only`). | [`contracts/v2.py`](file:///d:/university/Resesarch/J26-SE-334/contracts/v2.py)<br>[`05_live_demonstration/demo3_c2_c3_integration_trace.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/05_live_demonstration/demo3_c2_c3_integration_trace.json) |

---

## Traceability Verification Routine

To verify any claim in the terminal:
```powershell
# 1. Verify Model Manifest & Weights Checksum (CLAIM-C3-LOCAL, CLAIM-C3-ADAPT)
python -c "from vision_oracle.core.manifest import get_active_model_manifest; m=get_active_model_manifest(); print(m.to_dict())"

# 2. Run All Empirical Verification Tests (CLAIM-C3-RELIABLE, CLAIM-C3-C2, CLAIM-C3-C4)
pytest tests/ -k "test_contracts_v2 or test_pipeline_transforms or test_api_v2"

# 3. Inspect Held-Out 300 Screen Evaluation Metrics (CLAIM-C3-DETECT)
cat vision_oracle/evidence/03_detection_evaluation/evaluation_summary.json
```
