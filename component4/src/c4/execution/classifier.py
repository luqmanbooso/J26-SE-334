"""Failure classification for generated test execution."""

from __future__ import annotations

from c4.execution.models import FailureKind


_ELEMENT_STATE_MARKERS = (
    "StaleElementReference",
    "ElementNotInteractable",
    "ElementClickIntercepted",
)
_INFRASTRUCTURE_MARKERS = (
    "ConnectionRefused",
    "Max retries exceeded",
    "SessionNotCreated",
    "Could not start a new session",
    "Failed to establish a new connection",
)
_SCRIPT_ERROR_MARKERS = (
    "SyntaxError",
    "NameError",
    "ImportError",
    "ModuleNotFoundError",
)


def classify_failure(
    failure_json: dict[str, object] | None,
    stderr: str,
    timed_out: bool = False,
) -> FailureKind:
    """Classify a subprocess failure using stable exception markers."""
    exception_type = str((failure_json or {}).get("exception_type", ""))
    haystack = f"{exception_type}\n{stderr}"
    if "NoSuchElementException" in haystack or "no such element" in haystack.lower():
        return FailureKind.LOCATOR_NOT_FOUND
    if any(marker in haystack for marker in _ELEMENT_STATE_MARKERS):
        return FailureKind.ELEMENT_STATE
    if timed_out or any(marker in haystack for marker in _INFRASTRUCTURE_MARKERS):
        return FailureKind.INFRASTRUCTURE
    if any(marker in haystack for marker in _SCRIPT_ERROR_MARKERS):
        return FailureKind.SCRIPT_ERROR
    return FailureKind.UNKNOWN
