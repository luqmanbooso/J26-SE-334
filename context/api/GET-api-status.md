---
type: endpoint
method: GET
route: /api/status
status: done
path: vision_oracle/api/routes_status.py
depends_on: [[OracleService]], [[AdbBridge]]
used_by: []
updated: 2026-10-17
---
# GET /api/status

Returns system health, GPU compute availability (CUDA/CPU), engine configuration (`ZERO_CLOUD_EGRESS`), and list of active ADB attached devices via [[AdbBridge]].
