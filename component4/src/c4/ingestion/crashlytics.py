"""Firebase Crashlytics event and breadcrumb ingestion."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from c4.ingestion.base import first_string, string_value
from c4.ingestion.normalizer import attributes_without_keys, parse_timestamp
from c4.schemas import EventKind, EventSource, NormalizedEvent


class CrashlyticsAdapter:
    """Parse exported Crashlytics reports and custom keys/logs."""

    def parse(self, payload: Mapping[str, Any]) -> list[NormalizedEvent]:
        event_id = first_string(
            [payload.get("event_id"), payload.get("id"), payload.get("crash_id")]
        ) or "crashlytics-event"
        session_id = first_string(
            [payload.get("session_id"), payload.get("user_session_id")]
        )
        events = self._events(payload, event_id, session_id)
        failure = NormalizedEvent(
            event_id=f"{event_id}:error",
            session_id=session_id,
            source=EventSource.CRASHLYTICS,
            kind=EventKind.ERROR,
            timestamp=parse_timestamp(
                payload.get("timestamp")
                or payload.get("event_timestamp")
                or datetime.now(tz=timezone.utc)
            ),
            name=first_string(
                [payload.get("exception_type"), payload.get("issue_title"), "crash"]
            ) or "crash",
            error=dict(payload.get("exception", {}))
            if isinstance(payload.get("exception"), Mapping)
            else {"message": payload.get("issue_title")},
            raw=dict(payload),
        )
        return sorted([*events, failure], key=lambda event: event.timestamp)

    def _events(
        self,
        payload: Mapping[str, Any],
        event_id: str,
        session_id: str | None,
    ) -> list[NormalizedEvent]:
        breadcrumbs = payload.get("breadcrumbs") or payload.get("logs") or []
        if not isinstance(breadcrumbs, list):
            return []
        events: list[NormalizedEvent] = []
        for index, item in enumerate(breadcrumbs):
            if not isinstance(item, Mapping):
                continue
            attributes = dict(item)
            timestamp = parse_timestamp(
                item.get("timestamp")
                or item.get("time")
                or payload.get("timestamp")
                or datetime.now(tz=timezone.utc)
            )
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
                    locator=self._locator(item),
                    attributes=attributes_without_keys(
                        attributes, {"name", "message", "action", "type", "screen"}
                    ),
                    raw=attributes,
                )
            )
        return events

    @staticmethod
    def _locator(item: Mapping[str, Any]) -> dict[str, str]:
        keys = ("text", "resource_id", "content_desc", "xpath", "accessibility_id")
        return {
            key: value
            for key in keys
            if (value := string_value(item.get(key))) is not None
        }
