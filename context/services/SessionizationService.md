---
type: service
path: component4/src/c4/sessionization/service.py
depends_on: [[TelemetrySchema]], [[IngestionService]]
used_by: [[SynthesisService]]
updated: 2026-10-17
---
# SessionizationService

Processes unstructured raw interaction and telemetry logs, clustering events into distinct user activity sessions and extracting reproducible user test flows for synthesis into automated regression suites.
