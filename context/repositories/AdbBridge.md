---
type: repository
path: common/adb.py
depends_on: []
used_by: [[OracleService]], [[PerturbationOrchestrator]], [[BiometricSimulator]], [[GET-api-status]], [[POST-api-oracle-evaluate-device]]
updated: 2026-10-17
---
# AdbBridge

Central hardware bridge providing `AdbDevice` abstraction. Encapsulates subprocess calls to ADB: `screencap`, `uiautomator dump`, `input tap`, package info, device status checks, and automatic fallback to simulated mock device.
