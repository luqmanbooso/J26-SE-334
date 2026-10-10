"""File loading and provider dispatch for telemetry payloads."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from c4.ingestion.crashlytics import CrashlyticsAdapter
from c4.ingestion.sentry import SentryAdapter
from c4.schemas import EventSource, IngestionReport, NormalizedEvent


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

    def parse_report(
        self,
        payload: Mapping[str, Any],
        source: EventSource | str,
    ) -> IngestionReport:
        event_source = EventSource(source)
        return self._adapters[event_source].parse_report(payload)

    def parse_file(
        self,
        path: str | Path,
        source: EventSource | str,
    ) -> list[NormalizedEvent]:
        file_path = Path(path)
        if file_path.suffix.lower() == ".jsonl":
            return self.parse_jsonl_report(file_path, source).events
        try:
            with file_path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
        except OSError as error:
            raise TelemetryIngestionError(f"Unable to read telemetry file: {file_path}") from error
        except json.JSONDecodeError as error:
            raise TelemetryIngestionError(f"Invalid telemetry JSON in: {file_path}") from error

        if isinstance(payload, Mapping):
            return self.parse(payload, source)
        if isinstance(payload, list):
            events: list[NormalizedEvent] = []
            for record in payload:
                if not isinstance(record, Mapping):
                    continue
                events.extend(self.parse(record, source))
            return events
        raise TelemetryIngestionError(f"Telemetry payload must be an object or array: {file_path}")

    def parse_file_report(
        self,
        path: str | Path,
        source: EventSource | str,
    ) -> IngestionReport:
        """Parse an object, array, or JSONL file while preserving diagnostics."""
        file_path = Path(path)
        if file_path.suffix.lower() == ".jsonl":
            return self.parse_jsonl_report(file_path, source)
        try:
            with file_path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
        except OSError as error:
            raise TelemetryIngestionError(f"Unable to read telemetry file: {file_path}") from error
        except json.JSONDecodeError as error:
            raise TelemetryIngestionError(f"Invalid telemetry JSON in: {file_path}") from error

        if isinstance(payload, Mapping):
            return self.parse_report(payload, source)
        if isinstance(payload, list):
            from c4.ingestion.base import make_report
            from c4.schemas import QuarantinedRecord

            events: list[NormalizedEvent] = []
            quarantined = []
            for index, record in enumerate(payload):
                if not isinstance(record, Mapping):
                    quarantined.append(
                        QuarantinedRecord(record_index=index, reason="record must be a JSON object")
                    )
                    continue
                report = self.parse_report(record, source)
                events.extend(report.events)
                quarantined.extend(report.quarantined)
            return make_report(events, quarantined)
        raise TelemetryIngestionError(f"Telemetry payload must be an object or array: {file_path}")

    def parse_jsonl_report(
        self,
        path: str | Path,
        source: EventSource | str,
    ) -> IngestionReport:
        file_path = Path(path)
        events: list[NormalizedEvent] = []
        quarantined = []
        with file_path.open("r", encoding="utf-8") as stream:
            for index, line in enumerate(stream):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    from c4.schemas import QuarantinedRecord

                    quarantined.append(
                        QuarantinedRecord(record_index=index, reason=str(error))
                    )
                    continue
                if not isinstance(payload, Mapping):
                    from c4.schemas import QuarantinedRecord

                    quarantined.append(
                        QuarantinedRecord(record_index=index, reason="record must be a JSON object")
                    )
                    continue
                report = self.parse_report(payload, source)
                events.extend(report.events)
                quarantined.extend(report.quarantined)
        from c4.ingestion.base import make_report

        return make_report(events, quarantined)
