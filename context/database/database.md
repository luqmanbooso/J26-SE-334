---
type: moc
domain: database
updated: 2026-10-17
---
# Database & Schema Stores

## Schemas & Data Contracts
- [[OracleSchemas|Oracle Verdict & Defect Schemas]] — C3 Pydantic models for bounding boxes, defects, and C4 verdict envelope
- [[AttributionSchema|Attribution & Stress Event Schemas]] — C1 failure correlation records and perturbation profiles
- [[BiometrySchemas|Biometric Spatial & Timing Models]] — C2 Rotational Gaussian and stress state data structures
- [[TelemetrySchema|Telemetry & Self-Healing Schemas]] — C4 Sessionization, action flows, and repair records

## Persistence & Storage
- [[VerdictLedgerStore|Verdict Ledger JSON Storage]] — Atomic JSON disk store in `results/verdicts/`
