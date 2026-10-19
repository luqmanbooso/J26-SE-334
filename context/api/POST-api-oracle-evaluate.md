---
type: endpoint
method: POST
route: /api/oracle/evaluate
status: done
path: vision_oracle/api/routes_evaluate.py
depends_on: [[OracleService]], [[OracleSchemas]], [[LocalVisionOracleEngine]]
used_by: [[LiveDemonstrationNotebook]]
updated: 2026-10-17
---
# POST /api/oracle/evaluate

Executes synchronous multimodal evaluation of base64/file screenshot and XML hierarchy. Runs Tier 1 AST fast-path or Tier 2 SAHI VLM inference. Returns `C3OracleResult` with defect bounding boxes and persists `C3Verdict` to [[VerdictLedgerStore]].
