---
type: repository
path: vision_oracle/local_vision_oracle/engine.py
depends_on: [[OracleSchemas]], [[HierarchyPruner]]
used_by: [[OracleService]], [[POST-api-oracle-evaluate]]
updated: 2026-10-17
---
# LocalVisionOracleEngine

Core VLM engine. Implements two-tier triage: Tier 1 AST deterministic hierarchy collision checks (<5ms, 0 VRAM) and Tier 2 Qwen2-VL 4-bit AWQ inference with SAHI 720x720 slice tiling. Emits normalized defect detections and bounding boxes.
