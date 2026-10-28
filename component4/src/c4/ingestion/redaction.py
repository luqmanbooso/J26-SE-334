"""Mask personal data and credentials in normalized telemetry."""

from __future__ import annotations

import re
from typing import Any

from c4.schemas import NormalizedEvent, QuarantinedRecord

_SENSITIVE_KEYS = {
    "password", "passwd", "secret", "token", "access_token", "refresh_token",
    "api_key", "apikey", "authorization", "cookie", "set-cookie", "email",
    "phone", "ssn",
}
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")
_SECRET_PAIR = re.compile(
    r"(?i)(?<![A-Za-z0-9])(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|authorization)"
    r"([\"']?\s*[:=]\s*[\"']?)([^\s\"',;&]+)"
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_CARD = re.compile(r"(?<![\w-])(?:\d[ -]?){13,19}(?![\w-])")
_PHONE = re.compile(
    r"(?<![\w.-])(?:\+\d[\d ()-]{7,}\d|\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4})(?![\w-])"
)


def redact_text(text: str) -> str:
    """Mask emails, phone numbers, card numbers, and credentials in a string."""
    text = _JWT.sub("[REDACTED:TOKEN]", text)
    text = _BEARER.sub("Bearer [REDACTED:TOKEN]", text)
    text = _SECRET_PAIR.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED:SECRET]", text)
    text = _EMAIL.sub("[REDACTED:EMAIL]", text)
    text = _CARD.sub(lambda m: "[REDACTED:CARD]" if _luhn(m.group(0)) else m.group(0), text)
    return _PHONE.sub("[REDACTED:PHONE]", text)


def redact_value(value: Any) -> Any:
    """Redact every string inside nested mappings and lists."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {
            key: "[REDACTED:SECRET]"
            if isinstance(key, str) and key.lower() in _SENSITIVE_KEYS and isinstance(item, str)
            else redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value


def redact_event(event: NormalizedEvent) -> NormalizedEvent:
    """Return a copy with free-text fields masked; ids and timestamps are kept."""
    return event.model_copy(
        update={
            "name": redact_text(event.name),
            "screen": redact_text(event.screen) if event.screen else event.screen,
            "locator": redact_value(event.locator),
            "attributes": redact_value(event.attributes),
            "error": redact_value(event.error),
            "raw": redact_value(event.raw),
        }
    )


def redact_quarantined(record: QuarantinedRecord) -> QuarantinedRecord:
    return record.model_copy(update={"raw": redact_value(record.raw)})


def _luhn(candidate: str) -> bool:
    digits = [int(char) for char in candidate if char.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2:
            digit = digit * 2 - 9 if digit > 4 else digit * 2
        total += digit
    return total % 10 == 0
