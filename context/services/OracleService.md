---
type: service
path: vision_oracle/services/oracle_service.py
depends_on: [[LocalVisionOracleEngine]], [[FreezeDetector]], [[AdbBridge]], [[VerdictLedgerStore]], [[OracleSchemas]]
used_by: [[POST-api-oracle-evaluate]], [[POST-api-oracle-evaluate-device]], [[POST-api-oracle-sequence]], [[GET-api-oracle-verdicts]], [[GET-api-status]], [[TriggerQueueService]]
updated: 2026-10-17
---
# OracleService

Singleton managing the offline VLM inference pipeline. Coordinates Tier 1 AST bounding-box collision detection (<5ms CPU), Tier 2 SAHI 720x720 dynamic tiling VLM inference, multi-frame freeze checks, evaluation caching, and disk persistence to [[VerdictLedgerStore]].
