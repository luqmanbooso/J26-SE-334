---
type: endpoint
method: POST
route: /api/perturbation/attribution
status: done
path: env testing/server.py
depends_on: [[AttributionEngine]], [[PerturbationOrchestrator]], [[AttributionSchema]]
used_by: [[C1DesktopStudio]]
updated: 2026-10-17
---
# POST /api/perturbation/attribution

Correlates observed test run failure traces against the active perturbation event log, producing a statistical attribution verdict attributing faults to environmental perturbations versus genuine application logic bugs.
