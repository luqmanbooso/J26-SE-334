"""
Oracle Service for Component 3.
Manages engine lifecycle, real model weights, verdict persistence, and inference dispatch.
Compliant with Phase F, H, and I of HEART C3 Full Implementation Plan.
"""

import os
import io
import json
import uuid
import logging
import queue
import threading
import time
from collections import deque
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Union
from PIL import Image

# An older copy of this package is pip-installed (editable) from
# D:/university/Resesarch/local-vision-oracle. Without the next lines, any launch that
# does not put vision_oracle/ first on sys.path silently loads that stale engine,
# which lacks the inference contract fix.
import sys as _sys

_C3_DIR = str(Path(__file__).resolve().parents[1])


def _norm(p: str) -> str:
    return str(Path(p).resolve()).lower() if p else ""


# Place vision_oracle/ just ahead of installed packages (where the stale copy lives), not at the
# very front: other components put their own folders first (C1's "env testing" has a package
# named `core`, as does vision_oracle/), and moving C3 to the front broke their imports.
_paths = [_norm(p) for p in _sys.path]
_first_installed = next((i for i, p in enumerate(_paths)
                         if "site-packages" in p or "local-vision-oracle" in p), len(_sys.path))
_mine = _paths.index(_norm(_C3_DIR)) if _norm(_C3_DIR) in _paths else None
if _mine is None or _mine > _first_installed:
    if _mine is not None:
        del _sys.path[_mine]
    _sys.path.insert(_first_installed, _C3_DIR)
_stale = _sys.modules.get("local_vision_oracle")
if _stale is not None and not str(getattr(_stale, "__file__", "")).startswith(_C3_DIR):
    raise ImportError(
        f"Stale local_vision_oracle already imported from {_stale.__file__}; expected {_C3_DIR}. "
        "Run 'pip uninstall local-vision-oracle' or import vision_oracle.services first."
    )

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
from local_vision_oracle.schemas import (
    C3OracleResult,
    Verdict,
    LatencyBreakdown,
    DefectType,
)
from common.adb import AdbDevice, NoDeviceError

from vision_oracle.contracts.v2 import (
    JobState,
    AnalysisStatus,
    AnalysisDecision,
    CoveragePolicy,
    CaptureBundle,
    VerdictEnvelopeV2,
)
from vision_oracle.persistence.repository import OracleRepository, get_repository
from vision_oracle.local_vision_oracle.pipeline import AnalysisPipeline, CoordinateMapper
from vision_oracle.core.manifest import log_model_configuration

logger = logging.getLogger("vision_oracle.service")


def create_default_engine(adapter_dir: Optional[Path] = None) -> OracleEngine:
    """
    Initializes production OracleEngine strictly with real 4-bit NF4 quantized Qwen2-VL-2B model + LoRA adapter.
    ``adapter_dir`` overrides the configured default adapter (used by the desktop app's model selector).
    Raises RuntimeError immediately if weights not found or loading fails. Zero mock fallbacks.
    """
    adapter = Path(adapter_dir) if adapter_dir else LORA_WEIGHTS_PATH
    if not (BASE_MODEL_PATH and BASE_MODEL_PATH.exists()):
        raise RuntimeError(
            f"C3 base model path not found: {BASE_MODEL_PATH}. "
            "Ensure RD/models/Qwen2-VL-2B-Instruct exists on disk."
        )
    if not (adapter and adapter.exists()):
        raise RuntimeError(
            f"C3 LoRA adapter path not found: {adapter}. "
            "Ensure vision_oracle/models/c3_v3_vision_1ep exists on disk, or set C3_ADAPTER to an adapter folder."
        )

    logger.info(
        "Loading real 4-bit Qwen2-VL model from %s with LoRA from %s",
        BASE_MODEL_PATH,
        adapter,
    )
    backend = TransformersInferenceBackend(
        model_name_or_path=str(BASE_MODEL_PATH),
        adapter_dir=str(adapter),
        quantization_bit=4,
        lazy_load=False,
    )
    if backend.inference_contract is None:
        logger.warning(
            "C3 adapter %s has no inference_contract.json. It will receive a prompt and "
            "resolution it was not trained on and will under-detect defects. See "
            "vision_oracle/evidence/MODEL_V2_DECISIONS.md.", adapter,
        )
    else:
        logger.info("C3 inference contract active: %s px, decision threshold %s",
                    backend.inference_contract["image_max_pixels"],
                    backend.inference_contract.get("decision_threshold"))
    return OracleEngine(
        backend=backend,
        engine_descriptor="qwen2-vl-2b-instruct+c3-lora-4bit",
    )


class OracleService:
    """Service layer managing engine instance, concurrency locks, job queues, and persistence."""

    def __init__(
        self,
        engine: Optional[OracleEngine] = None,
        repository: Optional[OracleRepository] = None,
    ):
        self._engine: OracleEngine = engine or create_default_engine(_ADAPTER_OVERRIDE)
        self._repo: OracleRepository = repository or get_repository()
        self._inference_lock = threading.Lock()
        self._verdict_lock = threading.Lock()
        self._recent_verdicts: deque = deque(maxlen=100)
        self._cancelled_jobs: set[str] = set()
        self._job_queue: queue.Queue = queue.Queue(maxsize=20)

        backend = getattr(self._engine, "backend", self._engine)
        descriptor = getattr(self._engine, "engine_descriptor", "qwen2-vl-local")
        self._pipeline = AnalysisPipeline(backend=backend, model_run_id=descriptor)

        # Log startup model configuration and manifest
        try:
            log_model_configuration(logger)
        except Exception as exc:
            logger.debug("Model manifest logging skipped: %s", exc)

        # Reconcile interrupted jobs from previous server runs
        try:
            interrupted_count = self._repo.reconcile_interrupted_jobs()
            if interrupted_count > 0:
                logger.info("Reconciled %d interrupted jobs on startup.", interrupted_count)
        except Exception as exc:
            logger.warning("Job reconciliation warning: %s", exc)

        # Start background job worker
        self._worker_thread = threading.Thread(target=self._job_worker_loop, daemon=True, name="OracleJobWorker")
        self._worker_thread.start()

    def close(self) -> None:
        """Stop the job worker (which otherwise keeps this service, and its model, alive) and unload the model."""
        try:
            self._job_queue.put_nowait(None)
        except queue.Full:
            pass
        unload = getattr(getattr(self._engine, "backend", None), "unload", None)
        if callable(unload):
            with self._inference_lock:  # let a running forward pass finish first
                unload()

    @property
    def engine(self) -> OracleEngine:
        return self._engine

    @property
    def pipeline(self) -> AnalysisPipeline:
        return self._pipeline

    @property
    def repository(self) -> OracleRepository:
        return self._repo

    @property
    def inference_lock(self) -> threading.Lock:
        """Mutex guarding GPU forward passes across all endpoints and background queues."""
        return self._inference_lock

    @property
    def verdict_lock(self) -> threading.Lock:
        """Mutex guarding memory access to recent verdicts."""
        return self._verdict_lock

    def set_engine(self, engine: OracleEngine) -> None:
        """Updates active engine and reconfigures pipeline."""
        self._engine = engine
        backend = getattr(engine, "backend", engine)
        descriptor = getattr(engine, "engine_descriptor", "qwen2-vl-local")
        self._pipeline = AnalysisPipeline(backend=backend, model_run_id=descriptor)

    def clear_verdicts(self) -> None:
        """Clears in-memory recent verdicts (useful for test isolation)."""
        with self._verdict_lock:
            self._recent_verdicts.clear()

    def check_readiness(self) -> Dict[str, Any]:
        """Probes model backend, SQLite repository, and ADB connectivity truthfully."""
        ready = True
        details = {}

        # 1. Model readiness
        try:
            has_backend = self._engine is not None and getattr(self._engine, "backend", None) is not None
            details["model_ready"] = bool(has_backend)
            if not has_backend:
                ready = False
        except Exception as exc:
            details["model_ready"] = False
            details["model_error"] = str(exc)
            ready = False

        # 2. Database readiness
        try:
            conn = self._repo.db.get_connection()
            cur = conn.execute("SELECT 1;")
            details["db_ready"] = cur.fetchone()[0] == 1
        except Exception as exc:
            details["db_ready"] = False
            details["db_error"] = str(exc)
            ready = False

        # 3. ADB devices
        try:
            devices = AdbDevice.list_devices()
            details["adb_devices"] = devices
            details["adb_ready"] = True
        except Exception as exc:
            details["adb_ready"] = False
            details["adb_devices"] = []
            details["adb_error"] = str(exc)

        return {"ready": ready, **details}

    # --- Asynchronous Job Queue Processing ---

    def submit_job(
        self,
        capture_id: str,
        session_id: Optional[str] = None,
        policy: str = CoveragePolicy.GLOBAL_ONLY.value,
    ) -> Dict[str, Any]:
        """Submits capture for asynchronous analysis, returning job metadata immediately."""
        capture = self._repo.get_capture(capture_id)
        if not capture:
            raise ValueError(f"Capture ID '{capture_id}' not found in evidence repository.")

        # Idempotency check: Return existing active job for this capture and policy
        existing_jobs = self._repo.list_capture_jobs(capture_id)
        for ej in existing_jobs:
            if ej["policy"] == policy and ej["state"] in (JobState.QUEUED.value, JobState.RUNNING.value):
                logger.info("Returning active job '%s' for capture '%s' (idempotency)", ej["job_id"], capture_id)
                return ej

        planned_views = 4 if policy == CoveragePolicy.GLOBAL_PLUS_TILES_V1.value else 1
        job_record = self._repo.create_job(
            capture_id=capture_id,
            session_id=session_id or capture.session_id,
            policy=policy,
            planned_views=planned_views,
        )

        try:
            self._job_queue.put_nowait(job_record["job_id"])
        except queue.Full:
            self._repo.update_job(
                job_record["job_id"],
                JobState.FAILED,
                error_message="Job queue capacity exceeded (backpressure maxsize=20)",
            )
            raise RuntimeError("Analysis job queue is full (capacity=20). Request rejected under backpressure.")

        return job_record

    def cancel_job(self, job_id: str) -> bool:
        """Requests cancellation of a queued or running job."""
        job = self._repo.get_job(job_id)
        if not job:
            return False
        self._cancelled_jobs.add(job_id)
        if job["state"] in (JobState.QUEUED.value, JobState.RUNNING.value):
            self._repo.update_job(job_id, JobState.CANCELLED, error_message="User requested cancellation")
        return True

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves job status and metadata."""
        return self._repo.get_job(job_id)

    def _job_worker_loop(self) -> None:
        """Dedicated background worker consuming submitted analysis jobs."""
        while True:
            try:
                job_id = self._job_queue.get()
                if job_id is None:
                    break

                if job_id in self._cancelled_jobs:
                    self._cancelled_jobs.discard(job_id)
                    continue

                job = self._repo.get_job(job_id)
                if not job or job["state"] == JobState.CANCELLED.value:
                    continue

                self._repo.update_job(job_id, JobState.RUNNING)
                capture = self._repo.get_capture(job["capture_id"])
                if not capture or not capture.artifact_path or not Path(capture.artifact_path).exists():
                    self._repo.update_job(job_id, JobState.FAILED, error_message="Capture image artifact missing")
                    continue

                try:
                    img = Image.open(capture.artifact_path).convert("RGB")
                    pol = CoveragePolicy(job["policy"]) if job.get("policy") in [p.value for p in CoveragePolicy] else CoveragePolicy.GLOBAL_ONLY

                    with self._inference_lock:
                        if job_id in self._cancelled_jobs:
                            self._cancelled_jobs.discard(job_id)
                            self._repo.update_job(job_id, JobState.CANCELLED, error_message="Cancelled prior to inference")
                            continue

                        verdict_v2 = self._pipeline.analyze(
                            bundle=capture,
                            image=img,
                            policy=pol,
                            job_id=job_id,
                        )

                    # Post-generation cancellation check: never publish completed verdict if job was cancelled
                    if job_id in self._cancelled_jobs:
                        self._cancelled_jobs.discard(job_id)
                        self._repo.update_job(job_id, JobState.CANCELLED, error_message="Cancelled during inference")
                        continue

                    latest_job = self._repo.get_job(job_id)
                    if latest_job and latest_job["state"] == JobState.CANCELLED.value:
                        continue

                    # Persist verdict to SQLite
                    self._repo.save_verdict(verdict_v2)
                    self._repo.update_job(
                        job_id=job_id,
                        state=JobState.COMPLETED,
                        completed_views=verdict_v2.coverage.completed_views,
                    )

                    # Cache in memory ledger for legacy observers (isolated so C4 failure never fails inference)
                    try:
                        c4_dict = verdict_v2.to_c4_verdict().model_dump()
                    except Exception as c4_err:
                        logger.warning("C4 verdict conversion failed for job %s: %s", job_id, c4_err)
                        c4_dict = {"status": "conversion_error", "error": str(c4_err)}

                    record = {
                        "verdict_id": verdict_v2.verdict_id,
                        "session_id": verdict_v2.session_id or "default_session",
                        "timestamp": capture.timestamp_utc,  # was `bundle`, undefined here: every job flipped to FAILED
                        "verdict_v2": verdict_v2.model_dump(),
                        "c4_verdict": c4_dict,
                    }
                    with self._verdict_lock:
                        self._recent_verdicts.appendleft(record)

                except Exception as exc:
                    err_msg = f"Job {job_id} inference failure: {exc}"
                    logger.error(err_msg, exc_info=True)
                    current = self._repo.get_job(job_id)
                    if current and current["state"] == JobState.COMPLETED.value:
                        # The verdict is already saved; a later bookkeeping error must not hide it.
                        logger.warning("Post-completion error for job %s ignored: %s", job_id, exc)
                        continue
                    self._repo.update_job(job_id, JobState.FAILED, error_message=str(exc))
                    if "OutOfMemoryError" in type(exc).__name__ or "out of memory" in str(exc).lower():
                        import gc
                        import torch
                        gc.collect()
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()

                finally:
                    self._job_queue.task_done()

            except Exception as outer_exc:
                logger.error("Job worker loop uncaught exception: %s", outer_exc)
                time.sleep(0.5)

    # --- Synchronous Legacy Ledgers & Endpoints ---

    def save_verdict_to_ledger(
        self, result: C3OracleResult, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Converts result to C4 envelope, caches in memory, and persists to disk and SQLite."""
        c4_envelope = OracleEngine.to_c4_verdict(result, session_id=session_id).model_dump(mode="json")
        record = {
            "verdict_id": c4_envelope["verdict_id"],
            "session_id": session_id or "default_session",
            "timestamp": result.timestamp,
            "oracle_result": result.to_dict(),
            "c4_verdict": c4_envelope,
        }
        with self._verdict_lock:
            self._recent_verdicts.appendleft(record)

        try:
            out_file = VERDICTS_DIR / f"{record['verdict_id']}.json"
            out_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
        except Exception:
            pass

        return record

    def list_verdicts(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Returns recent verdicts in reverse chronological order under verdict_lock."""
        with self._verdict_lock:
            if limit is not None:
                return list(self._recent_verdicts)[:limit]
            return list(self._recent_verdicts)

    def get_verdict(self, verdict_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a verdict by ID under verdict_lock with disk and SQLite fallback."""
        with self._verdict_lock:
            for record in self._recent_verdicts:
                if record["verdict_id"] == verdict_id:
                    return record

        # Check SQLite repository
        v_v2 = self._repo.get_verdict(verdict_id)
        if v_v2:
            return {
                "verdict_id": v_v2.verdict_id,
                "session_id": v_v2.session_id,
                "timestamp": v_v2.timings_ms.get("timestamp", ""),
                "verdict_v2": v_v2.model_dump(),
                "c4_verdict": v_v2.to_c4_verdict().model_dump(),
            }

        target_file = VERDICTS_DIR / f"{verdict_id}.json"
        if target_file.exists():
            try:
                return json.loads(target_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return self.get_latest_session_verdict(verdict_id)

    def get_latest_session_verdict(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Most recent verdict of a session. C4's live client asks get_verdict(session_id),
        which before 2026-10-21 never matched a verdict id, so C4 silently fell back to a
        default verdict and lost C3's evidence."""
        if not session_id:
            return None
        with self._verdict_lock:
            for record in self._recent_verdicts:  # newest first
                if record.get("session_id") == session_id:
                    return record
        verdicts = self._repo.list_session_verdicts(session_id)
        if not verdicts:
            return None
        v_v2 = verdicts[0]  # list_session_verdicts is newest first
        return {
            "verdict_id": v_v2.verdict_id,
            "session_id": v_v2.session_id,
            "timestamp": "",
            "verdict_v2": v_v2.model_dump(),
            "c4_verdict": v_v2.to_c4_verdict().model_dump(),
        }

    def evaluate(
        self,
        image_input: Union[Image.Image, str],
        raw_hierarchy: Optional[str] = None,
        screen_id: Optional[str] = None,
        action_context: Optional[str] = None,
        enable_sahi: bool = False,  # tile views not validated with the current adapter (see MODEL_V2_DECISIONS.md)
        session_id: Optional[str] = None,
        action_id: Optional[str] = None,
        capture_ms: float = 0.0,
        device_serial: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synchronously evaluates screen image and hierarchy via canonical AnalysisPipeline."""
        if isinstance(image_input, str):
            resolved = resolve_path(image_input)
            img_path = resolved if resolved else Path(image_input)
            pil_img = Image.open(img_path).convert("RGB")
        elif isinstance(image_input, Image.Image):
            pil_img = image_input.convert("RGB")
        else:
            raise ValueError(f"Unsupported image_input type: {type(image_input)}")

        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        image_bytes = buf.getvalue()
        width, height = pil_img.size

        capture_id = f"cap_{uuid.uuid4().hex[:12]}"
        artifact_path, sha256_hex = self._repo.save_image_artifact(capture_id, image_bytes)

        bundle = CaptureBundle(
            capture_id=capture_id,
            session_id=session_id or "default_session",
            action_id=action_id or (action_context if (action_context and action_context.startswith("act_")) else None),
            device_serial=device_serial,
            width=width,
            height=height,
            image_sha256=sha256_hex,
            artifact_path=str(artifact_path),
            raw_hierarchy=raw_hierarchy,
            hierarchy_status="available" if raw_hierarchy else "missing",
        )
        self._repo.save_capture(bundle)

        policy = CoveragePolicy.GLOBAL_PLUS_TILES_V1 if enable_sahi else CoveragePolicy.GLOBAL_ONLY

        with self._inference_lock:
            verdict_v2 = self._pipeline.analyze(
                bundle=bundle,
                image=pil_img,
                policy=policy,
            )

        verdict_v2.timings_ms["capture_ms"] = capture_ms
        verdict_v2.timings_ms["total_pipeline_ms"] = round(verdict_v2.timings_ms.get("total_pipeline_ms", 0.0) + capture_ms, 2)
        self._repo.save_verdict(verdict_v2)

        c4_envelope = verdict_v2.to_c4_verdict(schema_version="1.0.0").model_dump(mode="json")

        primary = verdict_v2.primary_finding
        defect_type = (
            DefectType(primary.type)
            if primary and primary.type in [d.value for d in DefectType]
            else (DefectType.OTHER if primary else DefectType.NONE)
        )
        # Legacy envelope needs a number. Use the model's own probability: P(defect) for a
        # finding, 1 - P(defect) for a clean verdict, 0.0 when the model reported none.
        p_defect = verdict_v2.metadata.get("defect_probability")
        if primary and primary.confidence is not None:
            confidence = float(primary.confidence)
        elif verdict_v2.decision == AnalysisDecision.NO_DEFECT_DETECTED and isinstance(p_defect, (int, float)):
            confidence = round(1.0 - float(p_defect), 4)
        else:
            confidence = 0.0

        norm_box = None
        if primary and primary.bbox_xyxy:
            x1, y1, x2, y2 = primary.bbox_xyxy
            norm_box = CoordinateMapper.pixels_to_model(x1, y1, x2, y2, width, height)

        verdict = Verdict(
            has_defect=(verdict_v2.decision == AnalysisDecision.DEFECT_DETECTED),
            defect_type=defect_type,
            confidence=confidence,
            bounding_box=norm_box,
            affected_element_id=primary.element_ref if primary else None,
            explanation=primary.explanation
            if primary
            else (
                "Clean screen rendering without visual or functional defects."
                if verdict_v2.decision == AnalysisDecision.NO_DEFECT_DETECTED
                else "Inconclusive scan"
            ),
        )
        res_meta = {**verdict_v2.metadata, "action_context": action_context or ""}
        if verdict_v2.findings:
            res_meta["detected_by"] = "sahi_dynamic_tiling" if any(v != "global" for f in verdict_v2.findings for v in f.view_ids) else "global_vlm"

        oracle_result = C3OracleResult(
            screen_id=screen_id or bundle.capture_id,
            verdict=verdict,
            latency_breakdown=LatencyBreakdown(
                capture_ms=capture_ms,
                preprocess_ms=verdict_v2.timings_ms.get("preprocess_ms", 0.0),
                inference_ms=verdict_v2.timings_ms.get("inference_ms", 0.0),
                total_pipeline_ms=verdict_v2.timings_ms.get("total_pipeline_ms", 0.0),
                meets_sla=(verdict_v2.timings_ms.get("total_pipeline_ms", 0.0) <= 1500.0),
            ),
            timestamp=bundle.timestamp_utc,
            engine_used=verdict_v2.model_run_id,
            metadata=res_meta,
        )

        record = {
            "verdict_id": verdict_v2.verdict_id,
            "session_id": verdict_v2.session_id or "default_session",
            "timestamp": bundle.timestamp_utc,
            "oracle_result": oracle_result.to_dict(),
            "c4_verdict": c4_envelope,
            "verdict_v2": verdict_v2.model_dump(),
        }
        with self._verdict_lock:
            self._recent_verdicts.appendleft(record)

        try:
            out_file = VERDICTS_DIR / f"{record['verdict_id']}.json"
            out_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
        except Exception:
            pass

        return {
            "oracle_result": oracle_result.to_dict(),
            "c4_verdict": c4_envelope,
            "verdict_v2": verdict_v2.model_dump(),
        }

    def evaluate_device(
        self,
        serial: Optional[str] = None,
        action_context: Optional[str] = None,
        session_id: Optional[str] = "live_device_session",
        device: Optional[Any] = None,
        enable_sahi: bool = False,  # tile views not validated with the current adapter (see MODEL_V2_DECISIONS.md)
        action_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Captures and evaluates screen from Android device via canonical AnalysisPipeline."""
        if device is None:
            target_serial = AdbDevice.resolve_serial(serial)
            device = AdbDevice(serial=target_serial, verify=True)

        t_cap_start = time.perf_counter()
        screenshot = device.screencap(as_pil=True)
        xml_text = device.dump_hierarchy(max_age_s=0.5)
        t_cap_end = time.perf_counter()
        capture_ms = round((t_cap_end - t_cap_start) * 1000.0, 2)

        try:
            metrics = device.get_display_metrics()
        except Exception:
            metrics = {"width": screenshot.width, "height": screenshot.height, "density": 0}

        eval_res = self.evaluate(
            image_input=screenshot,
            raw_hierarchy=xml_text,
            screen_id=f"live_{getattr(device, 'serial', 'unknown')}",
            action_context=action_context or f"Direct device evaluation on {getattr(device, 'serial', 'unknown')}",
            enable_sahi=enable_sahi,
            session_id=session_id,
            action_id=action_id,
            capture_ms=capture_ms,
            device_serial=getattr(device, "serial", None),
        )
        eval_res["oracle_result"]["metadata"]["device_serial"] = getattr(device, "serial", "unknown")
        eval_res["oracle_result"]["metadata"]["viewport_resolution"] = [
            metrics.get("width", screenshot.width),
            metrics.get("height", screenshot.height),
        ]
        eval_res["oracle_result"]["metadata"]["viewport_density"] = metrics.get("density", 0)

        return eval_res

    def evaluate_sequence(
        self,
        screens: List[Union[Image.Image, str]],
        hierarchies: Optional[List[str]] = None,
        time_delta_s: float = 2.5,
        action_dispatched: bool = True,
        action_context: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluates consecutive frames for temporal freeze detection under inference mutex."""
        resolved_screens = []
        for s in screens:
            if isinstance(s, str):
                resolved = resolve_path(s)
                resolved_screens.append(str(resolved) if resolved else s)
            else:
                resolved_screens.append(s)

        if len(resolved_screens) < 2:
            raise ValueError("Temporal freeze analysis requires at least 2 screen frames.")
        curr_hier = hierarchies[-1] if (hierarchies and len(hierarchies) >= len(resolved_screens)) else None
        prev_hier = hierarchies[-2] if (hierarchies and len(hierarchies) >= len(resolved_screens)) else None

        # 1. Temporal freeze rule (deterministic, CPU only).
        with self._inference_lock:
            freeze = self._engine.freeze_detector.detect_freeze(
                current_image=resolved_screens[-1], previous_image=resolved_screens[-2],
                current_hierarchy=curr_hier, previous_hierarchy=prev_hier,
                time_delta_s=time_delta_s, action_dispatched=action_dispatched,
            )
        if freeze.is_frozen:
            with self._inference_lock:
                result = self._engine.evaluate_sequence(
                    screens=resolved_screens, hierarchies=hierarchies, time_delta_s=time_delta_s,
                    action_dispatched=action_dispatched, action_context=action_context,
                )
            record = self.save_verdict_to_ledger(result, session_id=session_id)
            return {"oracle_result": result.to_dict(), "c4_verdict": record["c4_verdict"]}

        # 2. Not frozen: inspect the latest frame through the production pipeline (same as
        # /evaluate). Before 2026-10-21 this used the legacy engine with tile views on, which
        # disagreed with /evaluate on the same screen.
        latest = resolved_screens[-1]
        return self.evaluate(
            image_input=latest if isinstance(latest, (str, Image.Image)) else Image.open(io.BytesIO(latest)),
            raw_hierarchy=curr_hier, action_context=action_context, session_id=session_id, enable_sahi=False,
        )


# Singleton service instance
_ORACLE_SERVICE: Optional[OracleService] = None
_ADAPTER_OVERRIDE: Optional[Path] = None
_SERVICE_INIT_LOCK = threading.Lock()


def get_oracle_service() -> OracleService:
    global _ORACLE_SERVICE
    with _SERVICE_INIT_LOCK:
        if _ORACLE_SERVICE is None:
            _ORACLE_SERVICE = OracleService()
    return _ORACLE_SERVICE


def set_oracle_service(service: OracleService) -> None:
    global _ORACLE_SERVICE
    _ORACLE_SERVICE = service


_ADAPTER_LABELS = {
    "c3_v3_vision_1ep": "Vision (default): screenshot only",
    "c3_v3_fusion_1ep": "Fusion (experimental): screenshot + layout",
    "c3_qwen2vl_2b_lora_step246": "Earlier version (v1)",
}


def available_adapters() -> List[Tuple[str, Path]]:
    """Adapter folders next to the default one that carry weights and an inference contract: (label, folder)."""
    root = (LORA_WEIGHTS_PATH.parent if LORA_WEIGHTS_PATH else None)
    if root is None or not root.exists():
        return []
    found = [(_ADAPTER_LABELS.get(d.name, d.name), d) for d in sorted(root.iterdir())
             if (d / "adapter_model.safetensors").exists() and (d / "inference_contract.json").exists()]
    return sorted(found, key=lambda item: (item[1].name not in _ADAPTER_LABELS, list(_ADAPTER_LABELS).index(item[1].name)
                                           if item[1].name in _ADAPTER_LABELS else 0, item[0]))


def active_adapter() -> Optional[Path]:
    """The adapter folder the next (or current) service uses."""
    return _ADAPTER_OVERRIDE or LORA_WEIGHTS_PATH


def switch_adapter(adapter_dir: Path) -> None:
    """Use a different adapter from the next inspection on. Drops the loaded model so the 4 GB GPU holds only one."""
    global _ORACLE_SERVICE, _ADAPTER_OVERRIDE
    adapter_dir = Path(adapter_dir)
    if not (adapter_dir / "adapter_model.safetensors").exists():
        raise FileNotFoundError(f"No adapter weights in {adapter_dir}")
    with _SERVICE_INIT_LOCK:
        _ADAPTER_OVERRIDE = adapter_dir
        old, _ORACLE_SERVICE = _ORACLE_SERVICE, None
    close = getattr(old, "close", None)
    if callable(close):
        close()
    del old, close
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
