---
type: endpoint
method: POST
route: /api/perturbation/reset
status: done
path: env testing/server.py
depends_on: [[PerturbationOrchestrator]]
used_by: [[C1DesktopStudio]]
updated: 2026-10-17
---
# POST /api/perturbation/reset

Reverts all environmental chaos stressors (CPU, RAM, network latency, traffic shaping, thermal states) back to nominal baseline condition.
