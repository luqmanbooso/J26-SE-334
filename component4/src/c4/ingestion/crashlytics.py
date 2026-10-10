"""Firebase Crashlytics event and breadcrumb ingestion."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from c4.ingestion.base import first_present, first_string, locator_from_mapping, make_report, string_value
from c4.ingestion.normalizer import attributes_without_keys, parse_timestamp, payload_id
from c4.schemas import EventKind, EventSource, IngestionReport, NormalizedEvent, QuarantinedRecord


class CrashlyticsAdapter:
    """Parse exported Crashlytics reports and custom keys/logs."""

    def parse(self, payload: Mapping[str, Any]) -> list[NormalizedEvent]:
        return self.parse_report(payload).events

    def parse_report(self, payload: Mapping[str, Any]) -> IngestionReport:
        event_id = first_string(
            [payload.get("event_id"), payload.get("id"), payload.get("crash_id")]
        ) or payload_id(payload, "crashlytics")
        session_id = first_string(
            [payload.get("session_id"), payload.get("user_session_id")]
        )
        events, quarantined = self._events(payload, event_id, session_id)
        timestamp_value = first_present(payload, "timestamp", "event_timestamp")
        if timestamp_value is None:
            return make_report(events, [
                *quarantined,
                QuarantinedRecord(record_index=-1, reason="missing crash timestamp", raw=dict(payload)),
            ])
        try:
            failure_timestamp = parse_timestamp(timestamp_value)
        except (TypeError, ValueError) as error:
            return make_report(
                events,
                [
                    *quarantined,
                    QuarantinedRecord(record_index=-1, reason=str(error), raw=dict(payload)),
                ],
            )
        failure = NormalizedEvent(
            event_id=f"{event_id}:error",
            session_id=session_id,
            source=EventSource.CRASHLYTICS,
            kind=EventKind.ERROR,
            timestamp=failure_timestamp,
            name=first_string([payload.get("exception_type"), payload.get("issue_title"), "crash"]) or "crash",
            error=self._error(payload),
            raw=dict(payload),
        )
        return make_report([*events, failure], quarantined)

    def _events(
        self,
        payload: Mapping[str, Any],
        event_id: str,
        session_id: str | None,
    ) -> tuple[list[NormalizedEvent], list[QuarantinedRecord]]:
        breadcrumbs = payload.get("breadcrumbs") or payload.get("logs") or []
        if not isinstance(breadcrumbs, list):
            return [], []
        events: list[NormalizedEvent] = []
        quarantined: list[QuarantinedRecord] = []
        for index, item in enumerate(breadcrumbs):
            if not isinstance(item, Mapping):
                quarantined.append(
                    QuarantinedRecord(
                        record_index=index,
                        reason="breadcrumb must be an object",
                    )
                )
                continue
            attributes = dict(item)
            try:
                timestamp = parse_timestamp(first_present(item, "timestamp", "time"))
            except (TypeError, ValueError) as error:
                quarantined.append(QuarantinedRecord(record_index=index, reason=str(error), raw=dict(item)))
                continue
            action = string_value(item.get("action") or item.get("type"))
            events.append(
                NormalizedEvent(
                    event_id=f"{event_id}:breadcrumb:{index}",
                    session_id=session_id,
                    source=EventSource.CRASHLYTICS,
                    kind=EventKind.ACTION if action else EventKind.UNKNOWN,
                    timestamp=timestamp,
                    name=first_string(
                        [item.get("name"), item.get("message"), action]
                    ) or "crashlytics.breadcrumb",
                    action=action,
                    screen=string_value(item.get("screen")),
                    locator=locator_from_mapping(item),
                    attributes=attributes_without_keys(
                        attributes, {"name", "message", "action", "type", "screen"}
                    ),
                    raw=attributes,
                )
            )
        return events, quarantined

    @staticmethod
    def _error(payload: Mapping[str, Any]) -> dict[str, Any]:
        exception = payload.get("exception")
        if isinstance(exception, Mapping):
            return dict(exception)
        return {
            key: value for key in ("issue_title", "exception_type", "stack_trace", "message")
            if (value := payload.get(key)) is not None
        }
