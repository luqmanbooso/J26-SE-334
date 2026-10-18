# Research Progress, Limitations, & Post-PP1 Roadmap

**Component:** HEART Component 3 (Local Vision Oracle)  
**Student:** M.L. Booso (IT23452916)  
**Group:** J26-SE-334  

---

## 1. PP1 Completion Milestone (~50% Implementation Scope)

| Proposal Milestone | PP1 Target | Status Achieved | Empirical Evidence |
|---|---|---|---|
| **FR1: VLM Model Selection** | Identify compact edge model capable of mobile UI comprehension | **100% Done** | Selected Qwen2-VL-2B; verified 3.24GB VRAM ceiling on RTX 3050 Laptop GPU. |
| **FR2: Parameter-Efficient Fine-Tuning** | Adapt model to mobile UI coordinates | **100% Done** | LoRA (Rank 16, Alpha 32) trained over 2,000 balanced corpus; achieved 71.0% accuracy, 80.58% precision, 55.33% recall. |
| **FR3: Spatial Dynamic Slicing (SAHI)** | Overcome downsampling blur on 20:9 screens | **100% Done** | Implemented 3-view vertical slicing; demonstrated +19.55% F1 gain on small UI elements ($<5\%$ viewport). |
| **FR4: Multi-Modal AST Pruning** | Prune false positives using accessibility hierarchy | **100% Done** | Pruned intentional layout overlaps in $<15\text{ ms}$; verified in unit tests. |
| **FR5: Air-Gapped Local REST API** | Zero cloud egress edge deployment | **100% Done** | FastAPI server running 100% on localhost:8003 with zero external network requests. |
| **FR6: C2 Crawler Integration** | Asynchronous capture trigger queue | **100% Done** | Synchronous $<150\text{ ms}$ capture ACK with background worker queue. |
| **FR7: C4 Test Synthesis Handover** | Status-aware contract preservation | **100% Done** | Typed contract v2 with nullable boolean `has_gui_defect` preserving inconclusive states. |

---

## 2. Acknowledged Limitations & Research Boundaries (PP1 Defense Honesty)

1. **Single-Primary Visual Defect Scope:**  
   The current fine-tuned adapter is explicitly bounded to detecting at most one primary salient defect (`component_overlap` or `text_truncation`) per screen. Dense multi-defect detection requires multi-label retraining.
2. **Synthetic to Real Domain Shift:**  
   Synthetic DOM-mutated Rico defects provide controlled training ground truth, but real-world mobile app bugs can feature idiosyncratic CSS/XML quirks.
3. **Inference Latency Tradeoff:**  
   Full-frame inference takes ~1.42s; 3-slice SAHI takes ~2.89s. While feasible for offline test suites, extreme high-speed test automation requires further caching or speculative decoding.

---

## 3. Post-PP1 Research Roadmap (Toward Final Thesis Delivery)

- **Phase 1 (Post-PP1 Retraining):** Expand training corpus to include multi-defect bounding boxes and fine-grained classification (e.g. font occlusion vs element clipping).
- **Phase 2 (AWQ INT4 Compilation):** Compile model weights using TensorRT-LLM / vLLM-OpenVINO to push inference latency under 800ms.
- **Phase 3 (Full End-to-End Test Regeneration):** Complete closed-loop validation with C1-C2-C4 under live continuous integration testing.
