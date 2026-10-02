---
type: adr
status: accepted
updated: 2026-10-17
---
# ADR-0003: Centralized ADB device management via common.adb

Decision: Consolidate all Android Debug Bridge operations across components into `common/adb.py` (`AdbDevice`, `AdbBridge`). Eliminates duplicate subprocess shell calls, prevents ADB server port collisions between C1, C2, and C3, and supports automatic fallback to simulated mock devices during offline testing.
Affects [[AdbBridge]], [[PerturbationOrchestrator]], [[BiometricSimulator]], [[OracleService]].
