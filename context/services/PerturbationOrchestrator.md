---
type: service
path: env testing/orchestrator.py
depends_on: [[AdbBridge]], [[StressorsRepository]], [[AttributionSchema]]
used_by: [[POST-api-perturbation-apply]], [[POST-api-perturbation-reset]], [[POST-api-perturbation-attribution]]
updated: 2026-10-17
---
# PerturbationOrchestrator

Manages the lifecycle of environmental stress scenarios. Translates high-level chaos profiles into low-level driver calls across hardware (CPU/RAM/Disk), network (latency/loss/DNS), and thermal sub-modules. Maintains active event ledger in `perturbation_event_log.json`.
