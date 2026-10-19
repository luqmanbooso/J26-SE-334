"""Versioned, provider-neutral journey seed documents."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from c4.schemas.session import FailureJourney


class JourneyStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    action: str
    name: str
    screen: str | None
    locator: dict[str, str]
    value: str | None
    event_id: str
    timestamp: datetime


class JourneyFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str
    message: str
    timestamp: datetime


class JourneyTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    action: str
    label: str
    locator: dict[str, str]
    screen: str | None


class PerturbationHint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stressor: str
    step_index: int
    reason: str
    basis: str = "heuristic"


class JourneySeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[JourneyTarget]
    failing_step_index: int | None
    failing_screen: str | None
    exception_type: str | None
    perturbation_hints: list[PerturbationHint]


class JourneyDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "c4.journey/1"
    journey_id: str
    session_id: str
    source: str
    app_version: str | None
    failing_screen: str | None
    exception_type: str | None
    reproducible: bool
    not_reproducible_reason: str | None
    truncated: bool
    action_count: int
    steps: list[JourneyStep]
    failure: JourneyFailure
    seed: JourneySeed


def journey_to_document(
    journey: FailureJourney,
    hint_rules: list[dict[str, Any]] | None = None,
) -> JourneyDocument:
    """Convert a failure journey to the versioned export contract."""
    exception_type = journey.metadata.get("exception_type") or _exception_type(journey)
    failing_screen = journey.metadata.get("failing_screen") or journey.failure.screen
    steps = [
        JourneyStep(
            index=index,
            action=str(event.action or "unknown"),
            name=event.name,
            screen=event.screen,
            locator=dict(event.locator),
            value=_value(event),
            event_id=event.event_id,
            timestamp=event.timestamp,
        )
        for index, event in enumerate(journey.events)
    ]
    targets = [
        JourneyTarget(
            index=step.index,
            action=step.action,
            label=(
                step.locator.get("text")
                or step.locator.get("content_desc")
                or step.name
            ),
            locator=step.locator,
            screen=step.screen,
        )
        for step in steps
        if step.action in {"tap", "input", "navigate"}
    ]
    action_steps = [step for step in steps if step.action != "unknown"]
    failing_step_index = action_steps[-1].index if action_steps else None
    hints = _hints(
        exception_type,
        _failure_message(journey),
        failing_step_index,
        hint_rules or [],
    )
    app_version = next(
        (event.app_version for event in [*journey.events, journey.failure] if event.app_version),
        None,
    )
    return JourneyDocument(
        journey_id=journey.journey_id,
        session_id=journey.session_id,
        source=journey.failure.source.value,
        app_version=app_version,
        failing_screen=failing_screen,
        exception_type=exception_type,
        reproducible=bool(journey.metadata.get("reproducible", False)),
        not_reproducible_reason=journey.metadata.get("not_reproducible_reason"),
        truncated=bool(journey.metadata.get("truncated", False)),
        action_count=int(journey.metadata.get("action_count", len(steps))),
        steps=steps,
        failure=JourneyFailure(
            name=journey.failure.name,
            type=exception_type,
            message=_failure_message(journey),
            timestamp=journey.failure.timestamp,
        ),
        seed=JourneySeed(
            targets=targets,
            failing_step_index=failing_step_index,
            failing_screen=failing_screen,
            exception_type=exception_type,
            perturbation_hints=hints,
        ),
    )


def document_to_journey(doc: JourneyDocument) -> FailureJourney:
    """Reconstruct the journey fields consumed by synthesis and execution."""
    from c4.schemas.telemetry import EventKind, EventSource, NormalizedEvent

    events = [
        NormalizedEvent(
            event_id=step.event_id,
            session_id=doc.session_id,
            app_version=doc.app_version,
            source=EventSource(doc.source),
            kind=EventKind.ACTION,
            timestamp=step.timestamp,
            name=step.name,
            action=step.action,
            screen=step.screen,
            locator=dict(step.locator),
            attributes={"value": step.value} if step.value is not None else {},
        )
        for step in doc.steps
    ]
    failure = NormalizedEvent(
        event_id=f"{doc.journey_id}:failure",
        session_id=doc.session_id,
        app_version=doc.app_version,
        source=EventSource(doc.source),
        kind=EventKind.ERROR,
        timestamp=doc.failure.timestamp,
        name=doc.failure.name,
        screen=doc.failing_screen,
        error={"type": doc.failure.type, "message": doc.failure.message},
    )
    return FailureJourney(
        journey_id=doc.journey_id,
        session_id=doc.session_id,
        events=events,
        failure=failure,
        metadata={
            "failing_screen": doc.failing_screen,
            "exception_type": doc.exception_type,
            "reproducible": doc.reproducible,
            "not_reproducible_reason": doc.not_reproducible_reason,
            "truncated": doc.truncated,
            "action_count": doc.action_count,
        },
    )


def _value(event: Any) -> str | None:
    value = event.attributes.get("value")
    return None if value is None else str(value)


def _exception_type(journey: FailureJourney) -> str:
    return str((journey.failure.error or {}).get("type") or journey.failure.name)


def _failure_message(journey: FailureJourney) -> str:
    error = journey.failure.error or {}
    return str(error.get("value") or error.get("message") or journey.failure.name)


def _hints(
    exception_type: str | None,
    message: str,
    step_index: int | None,
    rules: list[dict[str, Any]],
) -> list[PerturbationHint]:
    if step_index is None:
        return []
    hints = []
    for rule in rules:
        match = rule["match"]
        if any(
            token.lower() in value.lower()
            for key, values in match.items()
            for token in values
            for value in ([exception_type] if key == "exception_type_contains" else [message])
            if value
        ):
            hints.append(
                PerturbationHint(
                    stressor=rule["stressor"],
                    step_index=step_index,
                    reason=rule["note"],
                )
            )
            break
    return hints
