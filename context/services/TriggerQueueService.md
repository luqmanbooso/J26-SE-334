---
type: service
path: vision_oracle/services/trigger_queue.py
depends_on: [[OracleService]], [[AdbBridge]]
used_by: [[POST-api-oracle-trigger]]
updated: 2026-10-17
---
# TriggerQueueService

Background worker executing asynchronous screen captures and oracle evaluations triggered by Component 2. Prevents blocking C2 touch gesture loops while asynchronously validating screen defect state.
