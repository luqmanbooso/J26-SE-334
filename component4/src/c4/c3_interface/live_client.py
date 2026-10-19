"""
Production live Component 3 client for Component 4 self-healing pipeline (IF-C3-to-C4, FR7).
Supports dual execution:
1. In-process direct evaluation via OracleService/OracleEngine.
2. Local loopback HTTP REST client via http://127.0.0.1:8003.
Fulfills zero cloud egress (100% local execution).
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Literal, Mapping, Optional

from c4.schemas import FailureJourney, NormalizedEvent
from c4.c3_interface.contract import C3Verdict, DefectRegion, ScreenshotEvidence

logger = logging.getLogger("c4.c3_interface.live_client")


class C3LiveClient:
    """
    Live Component 3 client implementing C3Client protocol.
    Communicates with local Vision Oracle either via direct in-process call or
    local loopback REST API (http://127.0.0.1:8003).
    """

    def __init__(
        self,
        mode: Literal["auto", "in_process", "http"] = "auto",
        base_url: str = "http://127.0.0.1:8003",
        timeout_s: float = 3.0,
        fallback_on_error: bool = True,
        engine: Any = None,
    ) -> None:
        self.mode = mode
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.fallback_on_error = fallback_on_error
        self._engine = engine

    def get_verdict(
        self,
        session_id: str,
        failure: NormalizedEvent,
        journey: FailureJourney | None = None,
    ) -> C3Verdict:
        """
        Obtains visual verdict for a failure event.
        Extracts screenshot references from event attributes or queries the local C3 ledger.
        """
        # 1. Check if a screenshot or hierarchy is directly attached
        screenshot_path = self._extract_screenshot_path(failure, journey)
        hierarchy_xml = self._extract_hierarchy_xml(failure, journey)

        # 2. Dispatch evaluation based on configured mode
        try:
            if self.mode in ("auto", "in_process") and self._can_use_in_process():
                return self._evaluate_in_process(
                    session_id=session_id,
                    screenshot_path=screenshot_path,
                    hierarchy_xml=hierarchy_xml,
                    failure=failure,
                )
            elif self.mode in ("auto", "http"):
                return self._evaluate_http(
                    session_id=session_id,
                    screenshot_path=screenshot_path,
                    hierarchy_xml=hierarchy_xml,
                    failure=failure,
                )
        except Exception as exc:
            logger.warning("C3LiveClient evaluation failed: %s", exc)
            if not self.fallback_on_error:
                raise

        # 3. Graceful fallback when no visual screenshot or service unreachable
        return self._build_default_verdict(session_id, failure)

    def _can_use_in_process(self) -> bool:
        if self._engine is not None:
            return True
        try:
            import vision_oracle.services.oracle_service  # noqa: F401
            return True
        except ImportError:
            return False

    def _evaluate_in_process(
        self,
        session_id: str,
        screenshot_path: Optional[str],
        hierarchy_xml: Optional[str],
        failure: NormalizedEvent,
    ) -> C3Verdict:
        from vision_oracle.services.oracle_service import get_oracle_service

        service = get_oracle_service()
        if self._engine is not None:
            service.set_engine(self._engine)

        if screenshot_path and Path(screenshot_path).exists():
            payload = service.evaluate(
                image_input=screenshot_path,
                raw_hierarchy=hierarchy_xml,
                screen_id=failure.screen or failure.name,
                action_context=f"Failure: {failure.name} ({failure.kind.value})",
                session_id=session_id,
            )
            return C3Verdict.model_validate(payload["c4_verdict"])

        # Check existing cached verdict for this session in service ledger
        existing = service.get_verdict(session_id)
        if existing and "c4_verdict" in existing:
            return C3Verdict.model_validate(existing["c4_verdict"])

        return self._build_default_verdict(session_id, failure)

    def _evaluate_http(
        self,
        session_id: str,
        screenshot_path: Optional[str],
        hierarchy_xml: Optional[str],
        failure: NormalizedEvent,
    ) -> C3Verdict:
        # If screenshot path exists, send evaluate request
        if screenshot_path and Path(screenshot_path).exists():
            req_data = {
                "image_path": str(Path(screenshot_path).resolve()),
                "hierarchy_xml": hierarchy_xml,
                "screen_id": failure.screen or failure.name,
                "session_id": session_id,
                "action_context": f"Failure: {failure.name} ({failure.kind.value})",
            }
            url = f"{self.base_url}/api/oracle/evaluate"
            req = urllib.request.Request(
                url,
                data=json.dumps(req_data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return C3Verdict.model_validate(data["c4_verdict"])

        # Query existing session verdict from local server
        url = f"{self.base_url}/api/oracle/verdicts/{session_id}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "c4_verdict" in data:
                return C3Verdict.model_validate(data["c4_verdict"])

        return self._build_default_verdict(session_id, failure)

    def _extract_screenshot_path(
        self, failure: NormalizedEvent, journey: FailureJourney | None
    ) -> Optional[str]:
        for src in (failure.attributes, failure.raw, (journey.metadata if journey else {})):
            for key in ("screenshot_path", "screenshot", "image_path"):
                val = src.get(key)
                if val and isinstance(val, str):
                    return val
        return None

    def _extract_hierarchy_xml(
        self, failure: NormalizedEvent, journey: FailureJourney | None
    ) -> Optional[str]:
        for src in (failure.attributes, failure.raw, (journey.metadata if journey else {})):
            for key in ("hierarchy_xml", "view_hierarchy", "hierarchy"):
                val = src.get(key)
                if val and isinstance(val, str):
                    return val
        return None

    def _build_default_verdict(self, session_id: str, failure: NormalizedEvent) -> C3Verdict:
        return C3Verdict(
            schema_version="1.0.0",
            verdict_id=f"c3-live-{session_id}",
            session_id=session_id,
            has_gui_defect=False,
            defect_type=None,
            confidence=0.0,
            evidence={"note": "no_screenshot_attached_or_oracle_offline"},
            metadata={"screen": failure.screen, "failure_name": failure.name},
        )
