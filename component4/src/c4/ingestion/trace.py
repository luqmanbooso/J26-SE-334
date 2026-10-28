"""Neutral step-trace ingestion for datasets that are not Sentry or Crashlytics exports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from c4.ingestion.base import first_string, locator_from_mapping, make_report, string_value
from c4.ingestion.normalizer import attributes_without_keys, parse_timestamp, payload_id
from c4.schemas import EventKind, EventSource, IngestionReport, NormalizedEvent, QuarantinedRecord

_STEP_FIELDS = {
    "timestamp", "action", "name", "screen", "text", "resource_id", "resource-id",
    "content_desc", "content-desc", "accessibility_id", "xpath", "view",
}


class TraceAdapter:
    """Parse one ``{trace_id, steps, failure}`` record into normalized events.

    Every step is an action with its own timestamp. A trace without a ``failure``
    produces events but no journey, and no timestamp is ever invented.
    """

    def parse(self, payload: Mapping[str, Any]) -> list[NormalizedEvent]:
        return self.parse_report(payload).events

    def parse_report(self, payload: Mapping[str, Any]) -> IngestionReport:
        trace_id = string_value(payload.get("trace_id")) or payload_id(payload, "trace")
        steps = payload.get("steps")
        if not isinstance(steps, list):
            return make_report([], [
                QuarantinedRecord(record_index=-1, reason="trace must contain a steps list", raw=dict(payload)),
            ])
        context = {
            "session_id": trace_id,
            "app_version": string_value(payload.get("app_version")),
            "device": string_value(payload.get("device")),
            "os_version": string_value(payload.get("os_version")),
        }
        events: list[NormalizedEvent] = []
        quarantined: list[QuarantinedRecord] = []
        for index, step in enumerate(steps):
            try:
                events.append(self._step(step, index, trace_id, context))
            except (TypeError, ValueError, OverflowError, OSError) as error:
                quarantined.append(QuarantinedRecord(
                    record_index=index, reason=str(error), raw=dict(step) if isinstance(step, Mapping) else {},
                ))
        failure = payload.get("failure")
        if isinstance(failure, Mapping):
            try:
                events.append(self._failure(failure, trace_id, context, events))
            except (TypeError, ValueError, OverflowError, OSError) as error:
                quarantined.append(QuarantinedRecord(record_index=-1, reason=str(error), raw=dict(failure)))
        return make_report(events, quarantined)

    @staticmethod
    def _step(step: Any, index: int, trace_id: str, context: dict[str, Any]) -> NormalizedEvent:
        if not isinstance(step, Mapping):
            raise ValueError("step must be an object")
        action = string_value(step.get("action"))
        if action is None:
            raise ValueError("missing step action")
        if step.get("timestamp") is None:
            raise ValueError("missing step timestamp")
        return NormalizedEvent(
            event_id=f"{trace_id}:step:{index}",
            source=EventSource.TRACE,
            kind=EventKind.ACTION,
            timestamp=parse_timestamp(step["timestamp"]),
            name=string_value(step.get("name")) or action,
            action=action,
            screen=string_value(step.get("screen")),
            locator=locator_from_mapping(step),
            attributes=attributes_without_keys(dict(step), _STEP_FIELDS),
            raw=dict(step),
            **context,
        )

    @staticmethod
    def _failure(
        failure: Mapping[str, Any],
        trace_id: str,
        context: dict[str, Any],
        events: list[NormalizedEvent],
    ) -> NormalizedEvent:
        name = first_string([failure.get("type"), failure.get("name")])
        if name is None:
            raise ValueError("failure needs a type")
        if failure.get("timestamp") is not None:
            timestamp = parse_timestamp(failure["timestamp"])
        elif events:
            timestamp = events[-1].timestamp
        else:
            raise ValueError("failure has no timestamp and the trace has no steps")
        return NormalizedEvent(
            event_id=f"{trace_id}:error",
            source=EventSource.TRACE,
            kind=EventKind.ERROR,
            timestamp=timestamp,
            name=name,
            error={"type": name, "value": string_value(failure.get("message")) or name},
            raw=dict(failure),
            **context,
        )
