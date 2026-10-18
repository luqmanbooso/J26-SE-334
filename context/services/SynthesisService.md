---
type: service
path: component4/src/c4/synthesis/service.py
depends_on: [[AppiumGenerator]], [[SessionizationService]], [[VerdictLedgerStore]], [[TelemetrySchema]]
used_by: []
updated: 2026-10-17
---
# SynthesisService

Orchestrates self-healing test automation synthesis. Ingests broken test step failures, matches current UI nodes via Sentence-BERT semantic similarity, and invokes [[AppiumGenerator]] to regenerate executable Appium Python scripts.
