---
type: endpoint
method: POST
route: /api/oracle/evaluate_device
status: done
path: vision_oracle/api/routes_evaluate.py
depends_on: [[OracleService]], [[AdbBridge]], [[OracleSchemas]]
used_by: [[InspectLiveDeviceCLI]]
updated: 2026-10-17
---
# POST /api/oracle/evaluate_device

Triggers live on-device screenshot and UIAutomator dump via [[AdbBridge]] on attached Android device. Executes multimodal oracle evaluation directly without manual payload formatting.
