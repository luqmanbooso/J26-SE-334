"""Sentry event and breadcrumb ingestion."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from c4.ingestion.base import (
    first_string,
    first_present,
    locator_from_mapping,
    make_report,
    string_value,
)
from c4.ingestion.normalizer import attributes_without_keys, parse_timestamp, payload_id
from c4.schemas import EventKind, EventSource, IngestionReport, NormalizedEvent, QuarantinedRecord


class SentryAdapter:
    """Parse Sentry event payloads and their breadcrumb trail."""

    def parse(self, payload: Mapping[str, Any]) -> list[NormalizedEvent]:
        return self.parse_report(payload).events

    def parse_report(self, payload: Mapping[str, Any]) -> IngestionReport:
        event_id = string_value(payload.get("event_id")) or payload_id(payload, "sentry")
        session_id = self._session_id(payload)
        events: list[NormalizedEvent] = []
        quarantined: list[QuarantinedRecord] = []
        for index, breadcrumb in enumerate(self._breadcrumbs(payload)):
            if not isinstance(breadcrumb, Mapping):
                quarantined.append(
                    QuarantinedRecord(
                        record_index=index,
                        reason="breadcrumb must be an object",
                    )
                )
                continue
            try:
                event = self._breadcrumb(
                    breadcrumb, index=index, event_id=event_id, session_id=session_id,
                    payload=payload,
                )
            except (TypeError, ValueError) as error:
                quarantined.append(
                    QuarantinedRecord(record_index=index, reason=str(error), raw=dict(breadcrumb))
                )
            else:
                events.append(event)

        error = payload.get("exception") or payload.get("error")
        if error is not None:
            timestamp = self._event_timestamp(payload, events)
            if timestamp is not None:
                events.append(
                NormalizedEvent(
                    event_id=f"{event_id}:error",
                    session_id=session_id,
                    source=EventSource.SENTRY,
                    kind=EventKind.ERROR,
                    timestamp=timestamp,
                    name=self._exception_name(error),
                    error=self._exception_data(error),
                    raw=dict(payload),
                    app_version=self._app_version(payload),
                    device=self._device(payload),
                    os_version=self._os_version(payload),
                )
                )
            else:
                quarantined.append(
                    QuarantinedRecord(record_index=-1, reason="missing event timestamp", raw=dict(payload))
                )
        return make_report(events, quarantined)

    def _breadcrumbs(self, payload: Mapping[str, Any]) -> list[Any]:
        breadcrumbs = payload.get("breadcrumbs", [])
        if isinstance(breadcrumbs, Mapping):
            breadcrumbs = breadcrumbs.get("values", [])
        return list(breadcrumbs) if isinstance(breadcrumbs, list) else []

    def _session_id(self, payload: Mapping[str, Any]) -> str | None:
        contexts = payload.get("contexts")
        context_session = contexts.get("session") if isinstance(contexts, Mapping) else {}
        return first_string(
            [
                payload.get("session_id"),
                payload.get("session", {}).get("id")
                if isinstance(payload.get("session"), Mapping)
                else None,
                context_session.get("id")
                if isinstance(context_session, Mapping)
                else None,
            ]
        )

    def _breadcrumb(
        self,
        breadcrumb: Mapping[str, Any],
        *,
        index: int,
        event_id: str,
        session_id: str | None,
        payload: Mapping[str, Any],
    ) -> NormalizedEvent:
        category = string_value(breadcrumb.get("category")) or "unknown"
        message = string_value(breadcrumb.get("message"))
        if breadcrumb.get("timestamp") is None:
            raise ValueError("missing breadcrumb timestamp")
        timestamp = parse_timestamp(breadcrumb["timestamp"])
        data = breadcrumb.get("data")
        attributes = dict(data) if isinstance(data, Mapping) else {}
        kind = (
            EventKind.ACTION
            if category in {"ui.click", "navigation", "user"}
            else EventKind.SCREEN
            if category in {"navigation"} or category.startswith("navigation.")
            else EventKind.LIFECYCLE
            if category.startswith("app.")
            else EventKind.UNKNOWN
        )
        screen = first_string([
            attributes.get("screen"),
            attributes.get("to") if category.startswith("navigation") else None,
        ])
        return NormalizedEvent(
            event_id=f"{event_id}:breadcrumb:{index}",
            session_id=session_id,
            source=EventSource.SENTRY,
            kind=kind,
            timestamp=timestamp,
            name=message or category,
            action=category,
            screen=screen,
            locator=locator_from_mapping(attributes),
            attributes=attributes_without_keys(attributes, {"screen"}),
            raw=dict(breadcrumb),
            app_version=self._app_version(payload),
            device=self._device(payload),
            os_version=self._os_version(payload),
        )

    def _event_timestamp(
        self,
        payload: Mapping[str, Any],
        events: list[NormalizedEvent],
    ) -> datetime | None:
        timestamp_value = first_present(payload, "timestamp")
        if timestamp_value is not None:
            return parse_timestamp(timestamp_value)
        if events:
            return events[-1].timestamp
        return None

    @staticmethod
    def _exception_name(error: Any) -> str:
        values = error.get("values") if isinstance(error, Mapping) else None
        last = values[-1] if isinstance(values, list) and values and isinstance(values[-1], Mapping) else {}
        return first_string([last.get("type"), last.get("value"), "sentry.exception"]) or "sentry.exception"

    @staticmethod
    def _exception_data(error: Any) -> dict[str, Any]:
        if not isinstance(error, Mapping):
            return {"value": error}
        values = error.get("values")
        last = values[-1] if isinstance(values, list) and values and isinstance(values[-1], Mapping) else {}
        return dict(last) if last else dict(error)

    @staticmethod
    def _app_version(payload: Mapping[str, Any]) -> str | None:
        release = payload.get("release")
        return first_string([payload.get("app_version"), release])

    @staticmethod
    def _device(payload: Mapping[str, Any]) -> str | None:
        device = payload.get("device")
        return first_string([device.get("name"), device.get("model")] if isinstance(device, Mapping) else [device])

    @staticmethod
    def _os_version(payload: Mapping[str, Any]) -> str | None:
        operating_system = payload.get("os")
        return first_string([operating_system.get("version")] if isinstance(operating_system, Mapping) else [operating_system])
