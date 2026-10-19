---
type: endpoint
method: GET
route: /api/oracle/verdicts
status: done
path: vision_oracle/api/routes_verdicts.py
depends_on: [[OracleService]], [[VerdictLedgerStore]]
used_by: [[SynthesisService]]
updated: 2026-10-17
---
# GET /api/oracle/verdicts

Queries historical evaluation verdicts from [[VerdictLedgerStore]]. Supports listing reverse-chronological verdicts (`limit=20`) and fetching individual records by `verdict_id`.
