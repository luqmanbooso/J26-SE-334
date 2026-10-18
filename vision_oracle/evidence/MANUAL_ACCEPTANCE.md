# Manual Acceptance Procedures: Component 3 (PP1)

**Component:** Component 3 Local Vision Oracle &bull; **Owner:** M.L. Booso (IT23452916)  
**Standard:** 8 Acceptance Verification Procedures (M01 to M08)  

---

### M01: Saved-Image End-to-End Analysis
1. Launch C3 API (`python -m vision_oracle.server`).
2. Submit `vision_oracle/evidence/05_live_demonstration/demo1_defective_screen_original.png` via `POST /v2/captures`.
3. Verify verdict returns `defect_detected` with primary finding `component_overlap` and valid bounding box.
4. Verify round-trip SQLite persistence retains identical `action_id`.

### M02: Live Capture via Shared ADB
1. Attach real Android device or emulator (`adb devices`).
2. Open target app (`com.solvance.android`).
3. Send capture trigger (`POST /v2/captures`). Verify capture ACK arrives in $<150$ ms.
4. Verify foreground package policy accepts app and tags launcher screens as warnings.

### M03: Operational Recovery & Queue Backpressure
1. Submit 21 concurrent jobs to bounded queue (`maxsize=20`).
2. Verify job 21 receives explicit rejection (`RuntimeError` / HTTP 503).
3. Kill server mid-job and restart; verify interrupted job reconciles to `interrupted` status.

### M04: Desktop GUI Panel Verification
1. Launch `python c1_desktop_app.py`.
2. Select Vision Oracle panel; load image.
3. Verify bounding box overlay renders accurately on preview card.
4. Export JSON evidence; confirm fields match active SQLite database.

### M05: C2 &bull; C3 Capture Coordination
1. Execute C2 stress crawler against device.
2. Verify C3 returns synchronous capture acknowledgement without blocking crawler exploration.

### M06: C1 &bull; C2 &bull; C3 Context Association
1. Inject network delay perturbation via C1.
2. Trigger C2 crawl and C3 analysis.
3. Verify perturbation event IDs attach to capture session context.

### M07: C4 Test Synthesis Receipt
1. Deliver positive defect verdict to C4 adapter.
2. Verify C4 emits `handover_outcome: ready_for_test_generation`.
3. Deliver inconclusive scan; verify C4 preserves `has_gui_defect: null` and abstains from false regression test generation.

### M08: Offline Feasibility & VRAM Benchmark
1. Disconnect external network.
2. Run 50 inference cycles on NVIDIA RTX 3050 Laptop GPU (4GB).
3. Verify peak VRAM $\le 3,242\text{ MB}$ and memory delta $= 0\text{ MB}$.
