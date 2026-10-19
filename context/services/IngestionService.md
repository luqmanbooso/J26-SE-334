---
type: service
path: component4/src/c4/ingestion/loader.py
depends_on: [[TelemetrySchema]]
used_by: [[SessionizationService]]
updated: 2026-10-17
---
# IngestionService

Normalizes and loads raw telemetry streams from production crash reporters (Crashlytics, Sentry) and internal device execution logs into standard `c4.schemas.ingestion` records.
