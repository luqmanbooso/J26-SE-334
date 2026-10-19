---
type: adr
status: accepted
updated: 2026-10-17
---
# ADR-0002: Zero cloud egress and on-device VLM execution

Decision: Enforce 100% offline, zero-cloud-egress execution for Component 3 Vision Oracle (`ZERO_CLOUD_EGRESS=True`). Quantize Qwen2-VL using 4-bit AWQ to run within local 6GB VRAM constraint. Eliminates API costs, network transmission overhead, and privacy leaks of proprietary application screens.
Affects [[LocalVisionOracleEngine]] and [[OracleService]].
