---
type: service
path: env testing/attribution_engine.py
depends_on: [[PerturbationOrchestrator]], [[AttributionSchema]]
used_by: [[POST-api-perturbation-attribution]]
updated: 2026-10-17
---
# AttributionEngine

Root-cause analysis engine for test failures. Compares failure timestamps, stack traces, and network timeouts against the active perturbation timeline to calculate statistical attribution scores and produce failure attribution reports.
