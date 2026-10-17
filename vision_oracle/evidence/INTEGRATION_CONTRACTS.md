# Integration Contracts Specification (Contract V2)

**Component:** Component 3 (Local Vision Oracle)  
**Consumers:** Component 2 (Stress Engine), Component 4 (Synthetic Test Generator), Component 1 (Desktop GUI)  
**Schema Version:** `2.0.0` (Dual backwards compatibility with `1.0.0`)  

---

## 1. C2 &bull; C3 Capture Coordination Contract

```json
{
  "schema_version": "2.0",
  "session_id": "sess_c2_stress_01",
  "action_id": "act_tap_button_14",
  "device_serial": "emulator-5554",
  "app_package": "com.solvance.android",
  "action_started_epoch_ms": 1792348000100,
  "action_completed_epoch_ms": 1792348000210,
  "observation": {
    "probe_type": "frame_probe",
    "ui_delay_ms": 112.5,
    "responded": true,
    "provocation": "tap"
  },
  "perturbation_event_ids": []
}
```

### C3 Synchronous Acknowledgement Response (HTTP 201)
```json
{
  "status": "captured",
  "capture_id": "cap_8f21e0ba",
  "job_id": "job_3a910fbc",
  "action_id": "act_tap_button_14",
  "session_id": "sess_c2_stress_01",
  "foreground_package": "com.solvance.android",
  "capture_duration_ms": 112.0,
  "capture_started_epoch_ms": 1792348000220,
  "capture_completed_epoch_ms": 1792348000332,
  "inter_modality_skew_ms": 0.0,
  "warnings": []
}
```

---

## 2. C3 &bull; C4 Synthesis Handover Contract

Emitted via `verdict_v2.to_c4_verdict()`:
```json
{
  "schema_version": "2.0.0",
  "verdict_id": "vrd_9a8b7c6d",
  "session_id": "sess_c2_stress_01",
  "action_id": "act_tap_button_14",
  "capture_id": "cap_8f21e0ba",
  "has_gui_defect": true,
  "status": "complete",
  "decision": "defect_detected",
  "primary_finding": {
    "finding_id": "fnd_01",
    "type": "component_overlap",
    "confidence": 0.88,
    "bbox_xyxy": [765, 36, 878, 955],
    "explanation": "TextView collides with underlying CardView boundary."
  },
  "evidence": {
    "handover_outcome": "ready_for_test_generation",
    "storage_path": "captures/cap_8f21e0ba.png",
    "image_sha256": "4a8e..."
  }
}
```

### Handover Outcomes
- `ready_for_test_generation`: Defect localized with bounding box and valid action context.
- `evidence_only`: Clean screen or missing reproduction steps.
- `unsupported_inconclusive`: Corrupted or partial scan; `has_gui_defect` set to `null` to avoid false regression tests.
