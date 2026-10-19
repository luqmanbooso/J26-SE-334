# Prototype User Feedback & Engineering Refinements

**Component:** Component 3 (Local Vision Oracle) &bull; **Auditor:** HEART Testing Project Team  

---

## 1. Prototype Feedback Summary

During internal demonstration and integration testing of Component 3, team members and peer evaluators provided the following constructive feedback:

| Observer / Role | Observed Limitation / Feedback | Concrete Engineering Refinement Applied |
|---|---|---|
| **C1 Lead (Dashboard)** | "Raw terminal JSON output is hard for non-ML developers to evaluate during live exploratory runs." | Built integrated Vision Oracle panel in `c1_desktop_app.py` with real PIL bounding box overlays, defect summary cards, and JSON evidence export. |
| **C2 Lead (Stress Engine)** | "C2 exploratory crawler was lagging because waiting for 1.5s VLM inference stalled user interaction dispatch." | Built decoupled `CaptureService` returning synchronous capture acknowledgement in $<150$ ms while queuing VLM inference asynchronously. |
| **C4 Lead (Test Synthesizer)** | "When C3 encountered an image decode error or partial view, emitting false clean passes caused C4 to generate broken regression tests." | Refactored Contract V2 with nullable `has_gui_defect: Optional[bool]`; errors and partial scans strictly evaluate as `inconclusive`, preserving safety. |
| **Supervisor / Advisor** | "Claiming exhaustive multi-defect detection before multi-label dataset retraining risks severe examiner criticism during viva." | Hardened Contract V2 with explicit `scope: {"mode": "single_primary_visual_finding", "exhaustive": false}` policy and clear scientific scope boundary. |
