"""C3 client that reads verdicts persisted by the desktop inspection handover."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from c4.c3_interface.contract import C3Verdict
from c4.c3_interface.normalize import normalize_verdict
from c4.schemas import FailureJourney, NormalizedEvent


def inbox_path(inbox: Path, verdict_id: str) -> Path:
    """Return the file a verdict is stored under (shared with the receiver)."""
    return Path(inbox) / (hashlib.sha256(verdict_id.encode()).hexdigest() + ".json")


def list_inbox(inbox: Path | None) -> list[C3Verdict]:
    """Return every valid verdict stored in the inbox, oldest file first."""
    if inbox is None or not Path(inbox).is_dir():
        return []
    verdicts = []
    for path in sorted(Path(inbox).glob("*.json"), key=lambda item: item.stat().st_mtime):
        try:
            verdicts.append(C3Verdict.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError, ValidationError):
            continue
    return verdicts


class InboxC3Client:
    """Resolve the verdict for a journey from the persisted C3 inbox.

    A verdict explicitly chosen by ``verdict_id`` wins; otherwise the newest
    verdict whose ``session_id`` equals the journey's session is used. No other
    verdict is ever attached implicitly.
    """

    def __init__(self, inbox: Path | None, verdict_id: str | None = None) -> None:
        self.inbox = Path(inbox) if inbox else None
        self.verdict_id = verdict_id
        self.last_status = "no_evidence"
        self.last_error: str | None = None

    def get_verdict(
        self,
        session_id: str,
        failure: NormalizedEvent,
        journey: FailureJourney | None = None,
        **_: object,
    ) -> C3Verdict:
        self.last_error = None
        verdicts = list_inbox(self.inbox)
        if self.verdict_id:
            match = next((v for v in verdicts if v.verdict_id == self.verdict_id), None)
            if match is None:
                self.last_status = "unavailable"
                self.last_error = f"C3 verdict {self.verdict_id} not found in inbox"
        else:
            match = next((v for v in reversed(verdicts) if v.session_id == session_id), None)
        if match is None:
            if not self.verdict_id:
                self.last_status = "no_evidence"
            return C3Verdict(
                schema_version="1.0", verdict_id=f"inbox-none-{session_id}",
                session_id=session_id, has_gui_defect=False, confidence=0.0,
            )
        self.last_status = "used"
        return normalize_verdict(match)
