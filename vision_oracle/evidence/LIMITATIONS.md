# Measured Limitations & Post-PP1 Research Roadmap

**Component:** Component 3 (Local Vision Oracle)  
**Lead Researcher:** M.L. Booso (IT23452916)  
**Phase:** PP1 Freeze & Evaluation  

---

## 1. Known PP1 Technical Boundaries

1. **Single Primary Defect Policy:**
   - Current weights (`c3_lora_final`) were trained on single-defect annotations.
   - When a screen exhibits multiple simultaneous bugs (e.g. text truncation and an unrendered icon), C3 focuses on the single most salient defect (`scope.mode = "single_primary_visual_finding"`).
   - Multi-defect exhaustive counting is explicitly deferred to post-PP1 multi-label retraining.

2. **Temporal Defect Decoupling:**
   - UI freezes and infinite spinning loaders cannot be detected from a single static screenshot.
   - Decoupled into C2's `FrameProbe` temporal frame delta analysis; C3 treats freeze as temporal metadata, not vision weight inference.

3. **Multimodal Hierarchy Grounding:**
   - View hierarchy XML is captured and stored as contextual evidence.
   - Current default inference relies on raw visual tokens; dense cross-attention AST multimodal fusion remains under ablation and is not claimed as verified production capability for PP1.

4. **Edge Hardware Constraints:**
   - Target laptop GPU (RTX 3050 4GB VRAM) leaves 854 MB VRAM headroom under 4-bit NF4 quantization.
   - Co-locating C3 VLM and C4 local LLM in VRAM simultaneously will cause CUDA OOM. Sequential phase execution is enforced.

---

## 2. Post-PP1 Thesis Completion Roadmap

- **Milestone PP2 / Final Dissertation:**
  - Dedicated multi-label visual defect dataset re-annotation (0 to $N$ bugs per screen).
  - W4A16 AWQ quantization optimization targeting $<1.8\text{ GB}$ static model weights.
  - Saliency-guided adaptive multi-scale tiling.
  - Closed-loop autonomous Appium replay integration with Component 4.
