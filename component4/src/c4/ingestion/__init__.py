"""Telemetry ingestion adapters and normalization."""

from c4.ingestion.crashlytics import CrashlyticsAdapter
from c4.ingestion.loader import TelemetryIngestionError, TelemetryIngestionService
from c4.ingestion.sentry import SentryAdapter

__all__ = [
    "CrashlyticsAdapter",
    "SentryAdapter",
    "TelemetryIngestionError",
    "TelemetryIngestionService",
]
