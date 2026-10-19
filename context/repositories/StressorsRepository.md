---
type: repository
path: env testing/stressors/
depends_on: []
used_by: [[PerturbationOrchestrator]], [[POST-api-perturbation-apply]]
updated: 2026-10-17
---
# StressorsRepository

Subsystem drivers for environmental perturbation: CPU stress (`stress-ng` / python busy loops), RAM allocation pressure, Linux traffic control (`tc netem`) for network latency and packet loss, DNS fault injection, and Android thermal state mocks.
