---
type: endpoint
method: POST
route: /api/oracle/trigger
status: done
path: vision_oracle/api/routes_trigger.py
depends_on: [[TriggerQueueService]], [[OracleService]]
used_by: [[BiometricSimulator]]
updated: 2026-10-17
---
# POST /api/oracle/trigger

Asynchronous non-blocking capture trigger invoked by Component 2 (`IF-C2-to-C3`). Returns HTTP 202 in <10ms and enqueues screen capture and evaluation in background task queue.
