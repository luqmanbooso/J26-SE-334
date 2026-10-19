---
type: schema
path: results/verdicts/
depends_on: [[OracleSchemas]]
used_by: [[OracleService]], [[GET-api-oracle-verdicts]], [[SynthesisService]]
updated: 2026-10-17
---
# VerdictLedgerStore

File-based immutable audit ledger. Each evaluation persists a JSON record formatted as `verdict_<screen_id>_<timestamp>.json` containing raw findings, defect bounding boxes, detection latencies, and C4 verdict payload.
