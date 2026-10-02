---
type: schema
path: vision_oracle/local_vision_oracle/schemas.py
depends_on: []
used_by: [[LocalVisionOracleEngine]], [[OracleService]], [[POST-api-oracle-evaluate]], [[VerdictLedgerStore]]
updated: 2026-10-17
---
# OracleSchemas

Pydantic schemas for Component 3. Defines `BoundingBox`, `DefectCategory` (`OVERFLOW_Y_COLLISION`, `OVERLAP_TEXT_IMAGE`, `OCCLUDED_INTERACTIVE`, `NULL_STATE_FROZEN`), `DefectSeverity`, `C3OracleResult`, and normalized `C3Verdict` envelope for Component 4.
