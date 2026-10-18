---
type: endpoint
method: POST
route: /api/perturbation/apply
status: done
path: env testing/server.py
depends_on: [[PerturbationOrchestrator]], [[StressorsRepository]]
used_by: [[C1DesktopStudio]]
updated: 2026-10-17
---
# POST /api/perturbation/apply

Injects configured hardware and network chaos parameters (CPU stress, RAM pressure, disk I/O, added network latency, packet loss, DNS failure, thermal state) into the target environment via [[PerturbationOrchestrator]].
