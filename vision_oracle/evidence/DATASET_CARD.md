# Dataset Card: Mobile UI Visual Defect Corpus (HEART-C3-2K)

## Summary
The **HEART-C3-2K** dataset is a balanced mobile application visual defect benchmark consisting of 2,000 Android UI screenshots and ground-truth bounding box annotations. It was compiled specifically for fine-tuning and evaluating edge Vision-Language Models as automated GUI testing oracles.

## Dataset Structure
- **Total Corpus Size:** 2,000 annotated mobile screenshots
- **Split Proportions:**
  - **Train Split (`train.json`):** 1,400 screenshots (70%) — 700 clean, 700 defective
  - **Validation Split (`val.json`):** 300 screenshots (15%) — 150 clean, 150 defective
  - **Held-Out Test Split (`test.json`):** 300 screenshots (15%) — 150 clean, 150 defective
- **Annotation Format:**
  Normalized bounding box format in $[0, 1000]$ integer coordinate space:
  ```json
  {
    "image": "dataset/images/screen_0142.jpg",
    "conversations": [
      {
        "from": "user",
        "value": "<image>\nAnalyze this Android mobile UI screenshot for visual GUI defects. Output JSON."
      },
      {
        "from": "assistant",
        "value": "{\"has_defect\": true, \"defect_type\": \"component_overlap\", \"bounding_box\": [765, 36, 878, 955], \"explanation\": \"TextView collides with underlying CardView boundary.\"}"
      }
    ]
  }
  ```

## Data Sources & Lineage
1. **OwlEye Real Mobile Bug Dataset:**
   - 271 real-world visual defect screenshots collected from open-source Android applications (GitHub, Google Play).
   - Distilled via high-capacity vision teacher model (Qwen2-VL-72B / Groq Vision) into high-fidelity normalized bounding boxes with human verification.
2. **Rico Repository Mutated Synthetics:**
   - 729 synthetically perturbed layouts derived from the Rico interaction corpus.
   - Perturbations systematically injected programmatically (font scale escalation causing text truncation; layout margin collapse causing component overlaps).
3. **Clean Production Baselines:**
   - 1,000 clean Android screens from top Google Play production apps across diverse categories (e-commerce, social, finance, tools).

## Data Quality & Leakage Protection
- **Application-Level Isolation:** To prevent data leakage where synthetic mutations share the same layout template as test screens, splitting was enforced at the **application package level** rather than random screen-level sampling.
- **Deduplication:** Perceptual hashing (pHash) and feature vector cosine similarity were executed across all images. Duplicate or near-duplicate screens ($pHash \le 3$) were quarantined and eliminated.
- **Coordinate Integrity:** Every bounding box was programmatically validated:
  - $0 \le y_{min} < y_{max} \le 1000$
  - $0 \le x_{min} < x_{max} \le 1000$
  - Bounding box area $> 0.001$ of total screen area.
  - Zero reversed or out-of-bounds coordinates allowed.

## Dataset Manifest Reference
The active dataset manifest and audit ledger are physically located at:
- [`vision_oracle/evidence/02_dataset_record/dataset_manifest_summary.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/02_dataset_record/dataset_manifest_summary.json)
- [`vision_oracle/evidence/02_dataset_record/data_inspection_report.json`](file:///d:/university/Resesarch/J26-SE-334/vision_oracle/evidence/02_dataset_record/data_inspection_report.json)
