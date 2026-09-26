"""
Oracle Service for Component 3.
Manages engine lifecycle, real model weights, verdict persistence, and inference dispatch.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from PIL import Image

from vision_oracle.core.config import (
    VERDICTS_DIR,
    BASE_MODEL_PATH,
    LORA_WEIGHTS_PATH,
    resolve_path,
)
from local_vision_oracle.engine import (
    OracleEngine,
    MockInferenceBackend,
    TransformersInferenceBackend,
)
from local_vision_oracle.schemas import C3OracleResult
from common.adb import AdbDevice, NoDeviceError

logger = logging.getLogger("vision_oracle.service")


def create_default_engine() -> OracleEngine:
    """
    Initializes production OracleEngine strictly with real 4-bit NF4 quantized Qwen2-VL-2B model + LoRA adapter.
    Raises RuntimeError immediately if weights not found or loading fails. Zero mock fallbacks.
    """
    if not (BASE_MODEL_PATH and BASE_MODEL_PATH.exists()):
        raise RuntimeError(
            f"C3 base model path not found: {BASE_MODEL_PATH}. "
            "Ensure RD/models/Qwen2-VL-2B-Instruct exists on disk."
        )
    if not (LORA_WEIGHTS_PATH and LORA_WEIGHTS_PATH.exists()):
        raise RuntimeError(
            f"C3 LoRA adapter path not found: {LORA_WEIGHTS_PATH}. "
            "Ensure results/c3_lora_final exists on disk."
        )

    logger.info(
        "Loading real 4-bit Qwen2-VL model from %s with LoRA from %s",
        BASE_MODEL_PATH,
        LORA_WEIGHTS_PATH,
    )
    backend = TransformersInferenceBackend(
        model_name_or_path=str(BASE_MODEL_PATH),
        adapter_dir=str(LORA_WEIGHTS_PATH),
        quantization_bit=4,
        lazy_load=False,
    )
    return OracleEngine(
        backend=backend,
        engine_descriptor="qwen2-vl-2b-instruct+c3-lora-4bit",
    )


class OracleService:
    """Service layer managing engine instance and verdict ledgers."""

    def __init__(self, engine: Optional[OracleEngine] = None):
        self._engine: OracleEngine = engine or create_default_engine()
        self._recent_verdicts: List[Dict[str, Any]] = []

    @property
    def engine(self) -> OracleEngine:
        return self._engine

    def set_engine(self, engine: OracleEngine) -> None:
        self._engine = engine

    def save_verdict_to_ledger(
        self, result: C3OracleResult, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Converts result to C4 envelope, caches in memory, and persists to disk."""
        c4_envelope = OracleEngine.to_c4_verdict(result, session_id=session_id).model_dump(mode="json")
        record = {
            "verdict_id": c4_envelope["verdict_id"],
            "session_id": session_id or "default_session",
            "timestamp": result.timestamp,
            "oracle_result": result.to_dict(),
            "c4_verdict": c4_envelope,
        }
        self._recent_verdicts.insert(0, record)

        try:
            out_file = VERDICTS_DIR / f"{record['verdict_id']}.json"
            out_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
        except Exception:
            pass

        return record

    def list_verdicts(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if limit is not None:
            return self._recent_verdicts[:limit]
        return list(self._recent_verdicts)

    def get_verdict(self, verdict_id: str) -> Optional[Dict[str, Any]]:
        for record in self._recent_verdicts:
            if record["verdict_id"] == verdict_id:
                return record

        target_file = VERDICTS_DIR / f"{verdict_id}.json"
        if target_file.exists():
            try:
                return json.loads(target_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def evaluate(
        self,
        image_input: Union[Image.Image, str],
        raw_hierarchy: Optional[str] = None,
        screen_id: Optional[str] = None,
        action_context: Optional[str] = None,
        enable_sahi: bool = True,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if isinstance(image_input, str):
            resolved = resolve_path(image_input)
            if resolved:
                image_input = str(resolved)

        result = self._engine.evaluate(
            image_input=image_input,
            raw_hierarchy=raw_hierarchy,
            screen_id=screen_id,
            action_context=action_context,
            enable_sahi=enable_sahi,
        )
        record = self.save_verdict_to_ledger(result, session_id=session_id)
        return {
            "oracle_result": result.to_dict(),
            "c4_verdict": record["c4_verdict"],
        }

    def evaluate_device(
        self,
        serial: Optional[str] = None,
        action_context: Optional[str] = None,
        session_id: Optional[str] = "live_device_session",
    ) -> Dict[str, Any]:
        devices = AdbDevice.list_devices()
        if not devices:
            raise NoDeviceError("No Android device or emulator is attached. Connect phone via USB or start emulator.")

        target_serial = serial or devices[0]
        device = AdbDevice(serial=target_serial, verify=True)
        result = self._engine.evaluate_device(
            device=device,
            enable_sahi=True,
            action_context=action_context or f"Direct device evaluation on {device.serial}",
        )
        record = self.save_verdict_to_ledger(result, session_id=session_id)
        return {
            "oracle_result": result.to_dict(),
            "c4_verdict": record["c4_verdict"],
        }

    def evaluate_sequence(
        self,
        screens: List[Union[Image.Image, str]],
        hierarchies: Optional[List[str]] = None,
        time_delta_s: float = 2.5,
        action_dispatched: bool = True,
        action_context: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_screens = []
        for s in screens:
            if isinstance(s, str):
                resolved = resolve_path(s)
                resolved_screens.append(str(resolved) if resolved else s)
            else:
                resolved_screens.append(s)

        result = self._engine.evaluate_sequence(
            screens=resolved_screens,
            hierarchies=hierarchies,
            time_delta_s=time_delta_s,
            action_dispatched=action_dispatched,
            action_context=action_context,
        )
        record = self.save_verdict_to_ledger(result, session_id=session_id)
        return {
            "oracle_result": result.to_dict(),
            "c4_verdict": record["c4_verdict"],
        }


# Singleton service instance
_ORACLE_SERVICE: Optional[OracleService] = None


def get_oracle_service() -> OracleService:
    global _ORACLE_SERVICE
    if _ORACLE_SERVICE is None:
        _ORACLE_SERVICE = OracleService()
    return _ORACLE_SERVICE


def set_oracle_service(service: OracleService) -> None:
    global _ORACLE_SERVICE
    _ORACLE_SERVICE = service
