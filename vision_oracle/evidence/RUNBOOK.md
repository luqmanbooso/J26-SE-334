# Operational Runbook: Component 3 Local Vision Oracle

**Component:** Component 3 (Local Vision Oracle) &bull; **Lead:** M.L. Booso (IT23452916)  
**Port:** `8003` &bull; **Host:** `127.0.0.1` &bull; **Environment:** Python 3.13.3 / PyTorch 2.6.0+cu126  

---

## 1. Environment & Weights Setup

```powershell
# 1. Pull Git LFS LoRA weights (74MB)
git lfs pull --include="models/c3_lora_final/*"

# 2. Download 4.4GB Qwen2-VL-2B-Instruct base model (one-time setup into gitignored directory)
python scripts/download_base_model.py

# 3. Verify model manifest and adapter SHA-256
python -c "from vision_oracle.core.manifest import get_model_manifest; print(get_model_manifest())"
```

---

## 2. Launching the Canonical Backend

Start the sole model-owning backend process:
```powershell
# In repository root:
$env:HF_HUB_OFFLINE="1"
$env:TRANSFORMERS_OFFLINE="1"
python -m vision_oracle.server
```

In a second terminal, verify liveness and readiness:
```powershell
Invoke-RestMethod "http://127.0.0.1:8003/health/live"
Invoke-RestMethod "http://127.0.0.1:8003/health/ready"
```

---

## 3. Submitting an Evaluation Job via REST API v2

```powershell
# 1. Register capture
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("evidence/sample.png"))
$cap = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8003/v2/captures" `
    -ContentType "application/json" `
    -Body (@{session_id="eval_run"; image_base64=$b64; hierarchy_status="missing"} | ConvertTo-Json)

# 2. Submit async analysis job
$job = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8003/v2/jobs" `
    -ContentType "application/json" `
    -Body (@{capture_id=$cap.capture_id; policy="global_plus_tiles_v1"} | ConvertTo-Json)

# 3. Poll result
Invoke-RestMethod "http://127.0.0.1:8003/v2/jobs/$($job.job_id)"
```

---

## 4. Launching Desktop Interface

```powershell
# Ensure background API is stopped if GPU VRAM is constrained (leaves 4GB exclusively for GUI service)
python c1_desktop_app.py
```
Open **Vision Oracle** panel, select Local Image Mode or live ADB device, and click **Analyze Screen**.
