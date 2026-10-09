"""File loading and provider dispatch for telemetry payloads."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from c4.ingestion.crashlytics import CrashlyticsAdapter
from c4.ingestion.sentry import SentryAdapter
from c4.schemas import EventSource, NormalizedEvent


class TelemetryIngestionError(ValueError):
    """Raised when a telemetry payload cannot be loaded or dispatched."""


class TelemetryIngestionService:
    """Load provider payloads and route them to the correct adapter."""

    def __init__(self) -> None:
        self._adapters = {
            EventSource.SENTRY: SentryAdapter(),
            EventSource.CRASHLYTICS: CrashlyticsAdapter(),
        }

    def parse(
        self,
        payload: Mapping[str, Any],
        source: EventSource | str,
    ) -> list[NormalizedEvent]:
        try:
            event_source = EventSource(source)
        except ValueError as error:
            raise TelemetryIngestionError(
                f"Unsupported telemetry source: {source!r}"
            ) from error
        return self._adapters[event_source].parse(payload)

    def parse_file(
        self,
        path: str | Path,
        source: EventSource | str,
    ) -> list[NormalizedEvent]:
        file_path = Path(path)
        try:
            with file_path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
        except OSError as error:
            raise TelemetryIngestionError(
                f"Unable to read telemetry file: {file_path}"
            ) from error
        except json.JSONDecodeError as error:
            raise TelemetryIngestionError(
                f"Invalid telemetry JSON in: {file_path}"
            ) from error

        if not isinstance(payload, Mapping):
            raise TelemetryIngestionError(
                f"Telemetry payload must be a JSON object: {file_path}"
            )
        return self.parse(payload, source)
