"""Sentry event and breadcrumb ingestion."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from c4.ingestion.base import first_string, string_value
from c4.ingestion.normalizer import attributes_without_keys, parse_timestamp
from c4.schemas import EventKind, EventSource, NormalizedEvent


class SentryAdapter:
    """Parse Sentry event payloads and their breadcrumb trail."""

    def parse(self, payload: Mapping[str, Any]) -> list[NormalizedEvent]:
        event_id = string_value(payload.get("event_id")) or "sentry-event"
        session_id = self._session_id(payload)
        events = [
            self._breadcrumb(
                breadcrumb,
                index=index,
                event_id=event_id,
                session_id=session_id,
            )
            for index, breadcrumb in enumerate(self._breadcrumbs(payload))
        ]

        error = payload.get("exception") or payload.get("error")
        if error is not None:
            timestamp = self._event_timestamp(payload, events)
            events.append(
                NormalizedEvent(
                    event_id=f"{event_id}:error",
                    session_id=session_id,
                    source=EventSource.SENTRY,
                    kind=EventKind.ERROR,
                    timestamp=timestamp,
                    name="sentry.exception",
                    error=error if isinstance(error, dict) else {"value": error},
                    raw=dict(payload),
                )
            )
        return sorted(events, key=lambda event: event.timestamp)

    def _breadcrumbs(self, payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        breadcrumbs = payload.get("breadcrumbs", [])
        if isinstance(breadcrumbs, Mapping):
            breadcrumbs = breadcrumbs.get("values", [])
        return [
            item for item in breadcrumbs
            if isinstance(item, Mapping)
        ]

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
    ) -> NormalizedEvent:
        category = string_value(breadcrumb.get("category")) or "unknown"
        message = string_value(breadcrumb.get("message"))
        kind = EventKind.ACTION if category in {"ui.click", "navigation", "user"} else EventKind.UNKNOWN
        timestamp = parse_timestamp(
            breadcrumb.get("timestamp")
            or datetime.now(tz=timezone.utc)
        )
        data = breadcrumb.get("data")
        attributes = dict(data) if isinstance(data, Mapping) else {}
        return NormalizedEvent(
            event_id=f"{event_id}:breadcrumb:{index}",
            session_id=session_id,
            source=EventSource.SENTRY,
            kind=kind,
            timestamp=timestamp,
            name=message or category,
            action=category,
            screen=string_value(attributes.get("screen")),
            locator=self._locator(attributes),
            attributes=attributes_without_keys(attributes, {"screen"}),
            raw=dict(breadcrumb),
        )

    def _event_timestamp(
        self,
        payload: Mapping[str, Any],
        events: list[NormalizedEvent],
    ) -> datetime:
        if payload.get("timestamp") is not None:
            return parse_timestamp(payload["timestamp"])
        if events:
            return events[-1].timestamp
        return datetime.now(tz=timezone.utc)

    @staticmethod
    def _locator(attributes: Mapping[str, Any]) -> dict[str, str]:
        keys = ("text", "resource_id", "content_desc", "xpath", "accessibility_id")
        return {
            key: value
            for key in keys
            if (value := string_value(attributes.get(key))) is not None
        }
