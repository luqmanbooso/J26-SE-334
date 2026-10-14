# HEART Component 3: Local Vision Oracle Replication Guide
## Oral Defense & Empirical Audit Manual

**Component:** Component 3 (Local Vision Oracle / `vision_oracle`)  
**Student:** M.L. Booso (IT23452916)  
**Research Group:** J26-SE-334  
**Project:** HEART (Holistic Evaluation and Autonomous Repair Toolkit for Android Mobile GUIs)  
**Security Boundary:** 100% Air-Gapped Local Loopback (`127.0.0.1:8003`), Zero Cloud Egress  
**Target Hardware:** NVIDIA GeForce RTX 3050 Laptop GPU (4.0 GB VRAM), CUDA 12+, Python 3.13  

---

## 1. Executive Summary

This replication manual provides step-by-step instructions for academic examiners, peer researchers, and evaluators to independently verify, audit, and replicate the empirical claims of **Component 3 (Local Vision Oracle)**.

Component 3 delivers:
1. **Air-Gapped Multimodal Oracle:** Quantized 4-bit NF4 Qwen2-VL-2B base model fine-tuned via QLoRA, executing entirely on edge consumer hardware without cloud API dependencies.
2. **Canonical Single Primary Defect Policy:** Strict detection and physical pixel localization for visual defect classes (`component_overlap` and `text_truncation`), rejecting non-boolean or empty VLM outputs.
3. **Action-Linked Evidence Capture (C2 Link):** Immediate synchronous snapshot acknowledgement (<150ms) bound directly to C2 action identifiers (`action_id`), decoupled from asynchronous VLM inference.
4. **Status-Aware Handover (C4 Link):** Preserves partial view degradation and inconclusive states (`has_gui_defect: null`, `handover_outcome: "evidence_only"`), preventing C4 from generating erroneous regression tests.
5. **Tamper-Evident Persistence:** SQLite WAL-mode evidence repository storing SHA-256 image hashes, inter-modality skew metrics, job states, and human review feedback.

---

## 2. What to Look At (Inspection Points)

### Inspection Point A: Local Model Manifest & Weight Pinning
- **File:** `models/c3_model_manifest.json` and `vision_oracle/core/manifest.py`
- **What to verify:**
  - `adapter_path`: Points to `models/c3_lora_final` (`adapter_model.safetensors`, ~73.9 MB).
  - `adapter_sha256`: Verified SHA-256 checksum matching active disk file.
  - `quantization_config`: `load_in_4bit: true`, `bnb_4bit_quant_type: "nf4"`, `bnb_4bit_compute_dtype: "float16"`.
  - `zero_cloud_egress: true`: No external network endpoints, API keys, or cloud fallbacks.

### Inspection Point B: Canonical Pipeline & Coordinate Mapper
- **File:** `vision_oracle/local_vision_oracle/pipeline.py`
- **What to verify:**
  - `CoordinateMapper.model_to_pixels` and `pixels_to_model`: Ensures bidirectional conversion between `[0, 1000]` normalized coordinates and `[height, width]` physical screen pixels.
  - `FindingParser.parse_findings`: Explicitly rejects empty dictionaries `{}`, non-boolean `has_defect` strings (`"true"`/`"false"`), out-of-order bounding boxes, and uncataloged defect types.
  - `AnalysisPipeline.analyze`: Canonical entry point enforcing scientific decision logic:
    - All views valid + $\ge 1$ findings $\rightarrow$ `Status: COMPLETE`, `Decision: DEFECT_DETECTED`
    - All views valid + $0$ findings $\rightarrow$ `Status: COMPLETE`, `Decision: NO_DEFECT_DETECTED`
    - Partial views valid + $0$ findings $\rightarrow$ `Status: PARTIAL`, `Decision: INCONCLUSIVE`
    - 0 views valid $\rightarrow$ `Status: ERROR`, `Decision: INCONCLUSIVE`

### Inspection Point C: C1 Desktop Inspection Panel & Visual Overlay
- **File:** `c1_desktop_app.py`
- **What to verify:**
  - Inspect the **"Vision Oracle (Component 3)"** tab in the desktop application.
  - Live status indicator: Displays real model readiness (`Qwen2-VL-2B (Local 4-bit)`), device serial, and target package.
  - Primary Defect Summary Card: Visual pill indicating `DEFECT DETECTED` (red) or `CLEAN` (green).
  - Graphical Overlay: PIL-rendered red bounding box on top of the mobile screenshot preview with defect class label and confidence score.
  - "Export Evidence JSON" button: Exports structured C3 verdict envelope.

### Inspection Point D: Component 4 Handover Contract
- **File:** `vision_oracle/contracts/v2.py` and `component4/src/c4/c3_interface/contract.py`
- **What to verify:**
  - `has_gui_defect` is typed as `bool | None`. When `decision == INCONCLUSIVE`, `has_gui_defect` evaluates to `None` (JSON `null`), preventing false-negative clean assertions.
  - `handover_outcome`: Values include `"ready_for_test_generation"`, `"evidence_only"`, and `"unsupported_inconclusive"`.

### Inspection Point E: SQLite Evidence Ledger & WAL Mode
- **File:** `results/oracle_evidence.db` (and `vision_oracle/persistence/db.py`)
- **What to verify:**
  - `PRAGMA journal_mode` is `wal` (Write-Ahead Logging enabled for high-concurrency read/write).
  - `captures` table schema includes `action_id`, `inter_modality_skew_ms`, `image_sha256`, and `hierarchy_status`.
  - `jobs` table schema includes `c4_delivery_status` (`pending`, `delivered`, `failed`).

---

## 3. What Commands to Run

### Command Set 1: Verify Hardware & Python Environment
Run in terminal (PowerShell):
```powershell
python -c "import torch; print(f'PyTorch {torch.__version__} | CUDA Available: {torch.cuda.is_available()} | Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}')"
```
*Expected Output:*
```text
PyTorch 2.6.0+cu126 | CUDA Available: True | Device: NVIDIA GeForce RTX 3050 Laptop GPU
```

### Command Set 2: Run Full Unit & Fault-Injection Test Suite
Run from repository root (`d:\university\Resesarch\J26-SE-334`):
```powershell
pytest tests/ -v
```
*Expected Output:*
```text
============================= 80 passed in 28.76s =============================
```
This suite rigorously exercises:
- ADB disconnect and reconnect fault injection
- Coordinate transformation invertibility
- Empty/malformed JSON schema rejection (cannot produce false clean verdicts)
- Concurrent multi-endpoint burst stress and mutex deadlock freedom
- Action-linked capture idempotency and queue backpressure (HTTP 503)

### Command Set 3: Run Component 4 Contract Validation Suite
Run from repository root:
```powershell
$env:PYTHONPATH="component4/src"; pytest component4/tests/unit/
```
*Expected Output:*
```text
======================== 93 passed, 2 skipped in 6.46s ========================
```
Confirms Component 4 test generation engine consumes C3 verdicts without contract violations.

### Command Set 4: Start the Local Vision Oracle REST Server
Run in a dedicated terminal:
```powershell
python -m vision_oracle.server
```
*Expected Output:*
```text
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     [Model Manifest] Model configuration initialized: Qwen2-VL-2B-Instruct | LoRA: c3_lora_final | NF4: True | Egress: False
INFO:     Job worker loop started (name=OracleJobWorker).
INFO:     Uvicorn running on http://127.0.0.1:8003 (Press CTRL+C to quit)
```

Verify service liveness and readiness:
```powershell
# Check Liveness (Immediate, <5ms)
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:8003/health/live"

# Check Operational Readiness
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:8003/health/ready"
```

### Command Set 5: Trigger Action-Linked Capture & Evaluation (C2 API)
Send an action-linked trigger payload simulating a C2 crawler action:
```powershell
$body = @{
    device_serial = "emulator-5554"
    action_id = "c2_audit_step_01"
    session_id = "audit_session_oral_defense"
    app_package = "com.ichi2.anki"
    action_context = "Auditor triggered card flip; verifying prompt visibility"
} | ConvertTo-Json

$response = Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8003/api/oracle/trigger" -Body $body -ContentType "application/json"
$response | Format-List
```
*Expected Output:*
- `status`: `enqueued` (HTTP 202 Accepted)
- `capture_id`: `cap_xxxxxxxxxxxx`
- `job_id`: `job_xxxxxxxxxxxx`
- `capture_duration_ms`: `< 150.0 ms` (Synchronous capture acknowledgement SLA satisfied)

### Command Set 6: Launch the C1 Desktop Application UI
Run from repository root:
```powershell
python c1_desktop_app.py
```
1. Click the **Vision Oracle (Component 3)** tab.
2. Confirm the **Model Status Badge** displays `Qwen2-VL-2B (Local 4-bit) | Ready`.
3. Select an attached device or enter an image path.
4. Click **"Run Inspection"**:
   - The UI displays a live spinner without blocking the main event loop.
   - Upon completion, the screen displays the screenshot preview, defect bounding box overlay in bold red/green, defect type badge, confidence score, and explanation.
5. Click **"Export Evidence JSON"** to save the structured audit packet to disk.

### Command Set 7: Run the Interactive Jupyter Notebook
Launch Jupyter:
```powershell
jupyter notebook notebooks/c3_local_vision_oracle_interactive.ipynb
```
Step through Cells 1 to 8:
- Demonstrates hardware check, manifest verification, single primary defect analysis, matplotlib visual overlay, AST layout collision pruning, C4 status-aware handover, and SQLite ledger inspection.

---

## 4. What Conclusion to Come To

When reviewing the empirical evidence from these steps, examiners should reach the following academic and technical conclusions:

1. **Air-Gapped Privacy & Zero Cloud Egress:**
   The entire inference pipeline executes locally via 4-bit NF4 quantization on an NVIDIA RTX 3050 Laptop GPU (4GB VRAM). No telemetry, screenshot frames, or metadata leave the local host (`127.0.0.1`), satisfying enterprise data privacy and medical/banking compliance requirements.

2. **Hard Real-Time Capture SLA (<150ms):**
   The C2 autonomous crawler never blocks on slow VLM forward passes. Captures are acknowledged immediately in $<150$ms, while VLM inference proceeds asynchronously in a bounded worker queue.

3. **Defect Verdict Integrity (No Hallucinated Clean States):**
   Malformed VLM outputs, syntax errors, and zero-area bounding boxes are strictly parsed as errors and classified as `INCONCLUSIVE` rather than defaulting to false-negative "clean" UI states.

4. **Status-Aware Downstream Handover (Component 4 Integration):**
   When visual coverage is incomplete or inconclusive, Component 3 preserves `has_gui_defect: null` and sets `handover_outcome: "evidence_only"`. Component 4 recognizes this state and avoids synthesizing invalid regression tests on dubious evidence.

5. **Defense Evidence Integrity:**
   All evaluation results, image SHA-256 hashes, and execution timings are permanently recorded in SQLite with WAL mode, providing an auditable, reproducible evidence chain suitable for academic defense and peer publication.
