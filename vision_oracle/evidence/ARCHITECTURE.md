# Component 3 Architecture & Operational Blueprint

**Component:** Component 3 (Local Vision-Semantic Test Oracle)  
**System:** HEART (Hybrid Exploration & Automated Regression Testing)  
**Lead:** M.L. Booso (IT23452916)  
**Version:** 2.0.0 (PP1 Baseline)  

---

## 1. System Architecture Diagram

```mermaid
flowchart TD
    subgraph Host["Host Machine (NVIDIA RTX 3050 Laptop GPU / Windows 11)"]
        subgraph C1["Component 1 (Desktop Dashboard)"]
            GUI["c1_desktop_app.py<br>(Tkinter / Main Thread)"]
            UIThread["Non-blocking Worker Thread<br>Requests & Live Polls"]
        end

        subgraph C2["Component 2 (Stress Engine)"]
            Crawler["biometry / crawler<br>(FrameProbe / Impatient Tester)"]
        end

        subgraph C3["Component 3 (Local Vision Oracle) :8003"]
            CapSvc["CaptureService<br>(Action-linked capture, <150ms ACK)"]
            JobQ["Bounded JobQueue<br>(Capacity: 20, Backpressure 503)"]
            Worker["Inference Worker Loop<br>(Single GPU Model Owner)"]
            
            subgraph Engine["Local VLM Engine"]
                Model["Qwen2-VL-2B (NF4 4-bit) +<br>LoRA Adapter (c3_lora_final)"]
                Pipe["Canonical AnalysisPipeline<br>(SAHI Tiler + FindingParser)"]
            end
            
            Ledger[("SQLite WAL Ledger<br>sessions, captures, jobs, verdicts")]
        end

        subgraph C4["Component 4 (Test Synthesizer)"]
            Synth["C4 Test Generation Engine<br>(Appium Replay / Script Gen)"]
        end

        Device["Physical Android Device / Emulator<br>(Target App: ShopEase)"]
    end

    C2 -- "1. POST /v2/captures (action_id)" --> CapSvc
    CapSvc -- "Takes screencap under shared lock" --> Device
    CapSvc -- "2. HTTP 201 ACK (<150ms)" --> C2
    CapSvc -- "3. Enqueue job" --> JobQ
    JobQ --> Worker
    Worker --> Pipe
    Pipe --> Model
    Pipe --> Ledger
    GUI -- "GET /health/ready & POST /v2/captures" --> CapSvc
    GUI -- "Polls job status" --> JobQ
    CapSvc -- "4. Handover to_c4_verdict()" --> Synth
```

---

## 2. Core Architectural Principles

### 2.1 Single Model Ownership
- **Strict Rule:** Component 3 is the **sole owner** of the Vision-Language Model in the operating system.
- Component 1 (Desktop GUI), Component 2 (Stress Engine), and Component 4 (Test Synthesizer) **never load another model instance**.
- All components interact with C3 through REST API v2 loopback endpoints (`http://127.0.0.1:8003`).

### 2.2 Canonical Analysis Pipeline
- Every visual analysis request (manual image upload, live ADB screencap, C2 trigger, or test suite evaluation) executes through a single unified class: `vision_oracle.local_vision_oracle.pipeline.AnalysisPipeline`.
- Legacy endpoints (`/api/oracle/evaluate`, `/api/oracle/evaluate-device`) are thin compatibility wrappers that delegate directly to `AnalysisPipeline`.

### 2.3 Decoupled Action-Linked Capture
- C2 actions trigger a synchronous capture request:
  `POST /v2/captures` with `{session_id, action_id, app_package}`.
- CaptureService acquires the shared ADB lock, takes the screencap, validates foreground package, generates SHA-256 hash, and returns an immediate HTTP 201 ACK ($p50 < 112\text{ ms}$) containing `capture_id` and `job_id`.
- The expensive VLM inference pass (~1.5s) executes asynchronously in the bounded queue, ensuring C2's interaction cadence is never degraded.

### 2.4 Durable Persistence & ACID Guarantees
- Persistence is managed by SQLite in Write-Ahead Logging (WAL) mode (`vision_oracle/persistence/db.py`).
- Image files are stored using atomic filesystem writes with hex-digest naming (`captures/<hash>.png`).
- Interrupted jobs from sudden process terminations are reconciled to `interrupted` status on startup.

### 2.5 Contract V2 & C4 Inter-Component Handover
- Contract schema: `vision_oracle.contracts.v2.VerdictEnvelopeV2`.
- Inconclusive results preserve `has_gui_defect = None` (nullable).
- Adapter `to_c4_verdict()` formats predictions for C4 consumption, emitting typed handover tags:
  - `ready_for_test_generation`: Defect confirmed with bounding box.
  - `evidence_only`: Clean screen or uncontextualized capture.
  - `unsupported_inconclusive`: Corrupted or partial scan requiring triage.
