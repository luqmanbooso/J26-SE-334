# Prototype Feedback & Iterative Refinement Ledger (PP1 Evaluation)

**Component:** HEART Component 3 (Local Vision-Semantic Oracle)  
**Requirement Source:** `01-PP1-Assessment-Criteria.pdf`, `02-PP1-Template.pdf` (Prototype User Feedback)  
**Evaluators:** Software Engineering Project Peers, QA Practitioners, and Mobile Testers

---

## 1. Stakeholder Feedback Sessions

| Reviewer Role | Focus Area | Observed Limitation / User Feedback | Architectural Change Implemented |
|---|---|---|---|
| **C1 Lead Developer (Desktop GUI)** | Operator usability & live evidence inspection | *"The backend returns raw JSON with [ymin, xmin, ymax, xmax]. During testing, developers cannot mentally map numbers to the screen to see what is clipped."* | Implemented **live visual bounding box rendering** in the C1 Desktop Application and Matplotlib overlays (`demo1_defective_screen_overlay.png`) drawing colored rectangles and defect tags directly over mobile screenshots. |
| **C2 Lead Developer (Biometry Crawler)** | Crawler throughput & concurrency | *"When the crawler triggers C3 synchronously over ADB, the ~1.5s VLM forward pass blocks UI exploration, causing the test runner to think the app froze."* | Built **non-blocking asynchronous capture queue** (`/v2/captures`, `capture_service.py`) returning instant acknowledgement (`<150ms ACK`) with a SHA-256 hash, while processing inference in a background worker pool. |
| **C4 Lead Developer (Test Synthesis)** | Test case generation contract | *"If C3 returns a boolean `has_defect: false` when an image is blurred or corrupt, C4 marks the test as passing and fails to generate regression assertions."* | Hardened **Contract V2 (`VerdictEnvelopeV2`)**: `has_gui_defect` is typed as `bool | None`. Corrupted inputs or partial scans evaluate strictly as `inconclusive` (`None`), signaling C4 to skip test synthesis rather than generating invalid assertions. |
| **Mobile QA Engineer (External Tester)** | Edge hardware stability | *"Running inference on low-memory laptops (4GB VRAM) risks crashing the machine with Out Of Memory (OOM) if screenshots are high resolution."* | Integrated **bitsandbytes 4-bit NF4 quantization** and **dynamic SAHI slicing with OOM auto-recovery**, locking maximum VRAM consumption to **3.24 GB** and passing the 50-cycle stress benchmark. |

---

## 2. Resulting Product Refinements

1. **Explainable Overlays:** Every verdict now pairs structured JSON with an annotated visual artifact so testers immediately see the offending element.
2. **Backpressure Protections:** Added bounded queue size (20 items max) returning HTTP 503 instead of unbounded memory growth.
3. **Audit Ledger:** Added SQLite WAL database (`evidence.db`) recording all captures, monotonic timestamps, and verdict hashes for full test reproducibility.
