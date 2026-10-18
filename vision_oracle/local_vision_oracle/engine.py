"""
Oracle Pipeline Engine for Component C3 (HEART Framework).
Orchestrates hierarchy pruning, image preprocessing, prompt compilation,
inference execution, and verdict parsing with sub-millisecond telemetry.
Grounded in Proposal FR3, FR4, FR7 and CLAIM-01, CLAIM-02.
"""

import os
import sys
if "PYTORCH_CUDA_ALLOC_CONF" not in os.environ:
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import time
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any, Union, Callable
from PIL import Image

logger = logging.getLogger("vision_oracle.engine")

from local_vision_oracle.schemas import (
    Verdict,
    LatencyBreakdown,
    C3OracleResult,
    DefectType,
)
from local_vision_oracle.pruner import HierarchyPruner, PrunedNode
from local_vision_oracle.preprocessor import ImagePreprocessor, PreprocessedImage
from local_vision_oracle.prompt import PromptBuilder, VerdictParser, ORACLE_SYSTEM_PROMPT
from local_vision_oracle.freeze_detector import TemporalFreezeDetector, FreezeDetectionResult


class InferenceBackend(ABC):
    """
    Abstract interface for model inference backends.
    Allows zero-dependency deterministic unit testing and pluggable local edge inference.
    """

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, Any]],
        image: Image.Image,
        **kwargs: Any,
    ) -> str:
        """
        Executes inference pass and returns raw generated text string.
        """
        pass


class MockInferenceBackend(InferenceBackend):
    """
    Deterministic mock backend for testing, ablation simulation, and offline CI.
    """

    def __init__(
        self,
        default_response: Optional[str] = None,
        response_fn: Optional[Callable[[List[Dict[str, Any]], Image.Image], str]] = None,
        simulated_latency_ms: float = 15.0,
    ):
        self.default_response = default_response or (
            '{\n'
            '  "has_defect": false,\n'
            '  "defect_type": "none",\n'
            '  "confidence": 0.98,\n'
            '  "bounding_box": null,\n'
            '  "affected_element_id": null,\n'
            '  "explanation": "Clean screen rendering without visual or functional defects."\n'
            '}'
        )
        self.response_fn = response_fn
        self.simulated_latency_ms = simulated_latency_ms
        self.call_count = 0
        self.last_messages: Optional[List[Dict[str, Any]]] = None

    def generate(
        self,
        messages: List[Dict[str, Any]],
        image: Image.Image,
        **kwargs: Any,
    ) -> str:
        self.call_count += 1
        self.last_messages = messages
        if self.simulated_latency_ms > 0:
            time.sleep(self.simulated_latency_ms / 1000.0)

        if self.response_fn is not None:
            return self.response_fn(messages, image)
        return self.default_response


class TransformersInferenceBackend(InferenceBackend):
    """
    Local edge inference using HuggingFace Transformers / AutoModelForVision2Seq.
    Loads Qwen2-VL (2B or 7B) or 4-bit AWQ quantized weights for GPU/CPU inference.
    """

    def __init__(
        self,
        model_name_or_path: str = "Qwen/Qwen2-VL-2B-Instruct",
        adapter_dir: Optional[str] = None,
        quantization_bit: Optional[int] = None,
        device: Optional[str] = None,
        torch_dtype: Optional[str] = "auto",
        lazy_load: bool = True,
    ):
        self.model_name_or_path = model_name_or_path
        self.adapter_dir = adapter_dir
        self.quantization_bit = quantization_bit
        self.device = device
        self.torch_dtype = torch_dtype
        self.model = None
        self.processor = None

        if not lazy_load:
            self._load_model()

    def _load_model(self) -> None:
        if self.model is not None and self.processor is not None:
            return

        import torch
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor

        resolved_device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.processor = AutoProcessor.from_pretrained(self.model_name_or_path)

        if self.quantization_bit == 4 and resolved_device == "cuda":
            from transformers import BitsAndBytesConfig
            import gc
            gc.collect()
            torch.cuda.empty_cache()
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                llm_int8_enable_fp32_cpu_offload=True,
            )
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                self.model_name_or_path,
                quantization_config=bnb_config,
                device_map="auto",
            )
        else:
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                self.model_name_or_path,
                torch_dtype=self.torch_dtype,
                device_map="auto" if resolved_device == "cuda" else None,
            )
            if resolved_device == "cpu":
                self.model.to("cpu")

        if self.adapter_dir:
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, self.adapter_dir)
            self.model.eval()

    def generate(
        self,
        messages: List[Dict[str, Any]],
        image: Image.Image,
        max_new_tokens: int = 160,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> str:
        self._load_model()
        import gc
        import torch

        # Ensure image is constrained to prevent VRAM thrashing
        img_eval = image.copy()
        img_eval.thumbnail((720, 1280), Image.Resampling.LANCZOS)

        inputs = None
        generated_ids = None
        trimmed_ids = None

        try:
            if self.adapter_dir:
                clean_prompt = (
                    "<|im_start|>user\n"
                    "<|vision_start|><|image_pad|><|vision_end|>"
                    "Analyze this mobile screen for non-crash visual and semantic defects.\n\n"
                    "Return the verdict in the specified JSON format.<|im_end|>\n"
                    "<|im_start|>assistant\n"
                )
                inputs = self.processor(
                    text=[clean_prompt],
                    images=[img_eval],
                    return_tensors="pt",
                )
            else:
                text_prompt = self.processor.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
                inputs = self.processor(
                    text=[text_prompt],
                    images=[img_eval],
                    padding=True,
                    return_tensors="pt",
                )

            if hasattr(self.model, "device"):
                inputs = inputs.to(self.model.device)

            with torch.inference_mode():
                generated_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=(temperature > 0.0),
                    temperature=temperature if temperature > 0.0 else None,
                )

            trimmed_ids = [
                out_ids[len(in_ids):]
                for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]
            response_text = self.processor.batch_decode(
                trimmed_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )[0]
            return response_text

        finally:
            if inputs is not None:
                try:
                    if hasattr(inputs, "keys"):
                        for k in list(inputs.keys()):
                            del inputs[k]
                except Exception:
                    pass
                del inputs
            if generated_ids is not None:
                del generated_ids
            if trimmed_ids is not None:
                del trimmed_ids
            if "img_eval" in locals():
                del img_eval
            gc.collect()
            if hasattr(torch, "cuda") and torch.cuda.is_available():
                torch.cuda.empty_cache()


class OracleEngine:
    """
    Main C3 Local Multimodal Vision-Semantic Oracle Engine.
    Coordinates the full end-to-end evaluation pipeline with SLA compliance tracking.
    """

    def __init__(
        self,
        backend: Optional[InferenceBackend] = None,
        pruner: Optional[HierarchyPruner] = None,
        preprocessor: Optional[ImagePreprocessor] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        freeze_detector: Optional[TemporalFreezeDetector] = None,
        engine_descriptor: str = "qwen2-vl-awq-4bit",
    ):
        self.backend = backend or MockInferenceBackend()
        self.pruner = pruner or HierarchyPruner()
        self.preprocessor = preprocessor or ImagePreprocessor()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.freeze_detector = freeze_detector or TemporalFreezeDetector()
        self.engine_descriptor = engine_descriptor

    @staticmethod
    def _compute_screen_hash(image_input: Union[str, Path, bytes, Image.Image]) -> str:
        hasher = hashlib.sha256()
        if isinstance(image_input, (str, Path)):
            hasher.update(str(image_input).encode("utf-8"))
        elif isinstance(image_input, bytes):
            hasher.update(image_input)
        elif isinstance(image_input, Image.Image):
            hasher.update(image_input.tobytes())
        else:
            hasher.update(str(time.time()).encode("utf-8"))
        return hasher.hexdigest()[:16]

    def evaluate(
        self,
        image_input: Union[str, Path, bytes, Image.Image],
        raw_hierarchy: Optional[Union[str, Path, Dict[str, Any], List[Any]]] = None,
        screen_id: Optional[str] = None,
        action_context: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        enable_sahi: bool = True,
        previous_image: Optional[Union[str, Path, bytes, Image.Image]] = None,
        previous_hierarchy: Optional[Union[str, Path, Dict[str, Any], List[Any]]] = None,
        time_delta_s: float = 0.0,
        action_dispatched: bool = False,
    ) -> C3OracleResult:
        """
        Executes single-turn fused evaluation over a captured screen state.
        
        Stages:
        0. Temporal Freeze Detection (FR3, Appendix F)
        1. Hierarchy AST Pruning & Deterministic Collision Check (CLAIM-01)
        2. Visual Sanitization & Patch-Grid Alignment (Aspect ratio preservation)
        3. Fused Prompt Compilation (Single-turn multimodal payload)
        4. Edge Model Inference Pass
        5. SAHI High-Res Slicing Fallback (For tall mobile viewports)
        6. Verdict Parsing, Spatial Normalization & SLA Instrumentation
        """
        resolved_screen_id = screen_id or f"scr_{self._compute_screen_hash(image_input)}"
        current_time = datetime.now(timezone.utc).isoformat()
        run_metadata = dict(metadata or {})
        run_metadata["screen_id"] = resolved_screen_id
        if action_context:
            run_metadata["action_context"] = action_context

        # Stage 0: Temporal Freeze Check (FR3, Appendix F)
        if previous_image is not None and (action_dispatched or time_delta_s > 0):
            t_freeze_start = time.perf_counter()
            prev_xml = previous_hierarchy if isinstance(previous_hierarchy, str) else ""
            curr_xml = raw_hierarchy if isinstance(raw_hierarchy, str) else ""
            freeze_res = self.freeze_detector.detect_freeze(
                previous_image=previous_image,
                current_image=image_input,
                previous_hierarchy=prev_xml,
                current_hierarchy=curr_xml,
                time_delta_s=time_delta_s,
                action_dispatched=action_dispatched,
                action_context=action_context,
            )
            t_freeze_end = time.perf_counter()
            freeze_ms = round((t_freeze_end - t_freeze_start) * 1000.0, 2)
            if freeze_res.is_frozen:
                run_metadata["detected_by"] = "temporal_freeze_detector"
                run_metadata["freeze_details"] = {
                    "stalled_duration_s": freeze_res.stalled_duration_s,
                    "pixel_difference_ratio": freeze_res.pixel_difference_ratio,
                }
                latency = LatencyBreakdown(
                    capture_ms=0.0,
                    preprocess_ms=0.0,
                    prune_ms=freeze_ms,
                    inference_ms=0.0,
                )
                latency.compute_total()
                return C3OracleResult(
                    screen_id=resolved_screen_id,
                    verdict=freeze_res.to_verdict(),
                    latency_breakdown=latency,
                    timestamp=current_time,
                    engine_used=self.engine_descriptor,
                    metadata=run_metadata,
                )

        # Stage 1: AST Pruning & Collision Check (CLAIM-01)
        t_prune_start = time.perf_counter()
        pruned_nodes: List[PrunedNode] = []
        collisions: List[Dict[str, Any]] = []
        if raw_hierarchy:
            if isinstance(raw_hierarchy, list):
                pruned_nodes = [n for n in raw_hierarchy if isinstance(n, PrunedNode)]
            else:
                pruned_nodes = self.pruner.prune(raw_hierarchy)
            run_metadata["pruning_stats"] = self.pruner.get_reduction_stats()
            # Fast deterministic layout collision check (<5ms on CPU)
            collisions = self.pruner.detect_layout_collisions(pruned_nodes)
        t_prune_end = time.perf_counter()
        prune_ms = round((t_prune_end - t_prune_start) * 1000.0, 2)

        # If deterministic collision found in DOM, emit immediate verdict (<15ms)
        if collisions:
            top_col = collisions[0]
            verdict = Verdict(
                has_defect=True,
                defect_type=DefectType.COMPONENT_OVERLAP,
                confidence=0.99,
                bounding_box=top_col["collision_bbox"],
                affected_element_id=top_col["element_b_id"],
                explanation=f"Layout collision defect: Element '{top_col['element_a_id']}' occludes '{top_col['element_b_id']}'.",
            )
            run_metadata["detected_by"] = "ast_collision_detector"
            run_metadata["collisions"] = collisions
            latency = LatencyBreakdown(
                capture_ms=0.0,
                preprocess_ms=0.0,
                prune_ms=prune_ms,
                inference_ms=0.0,
            )
            latency.compute_total()
            return C3OracleResult(
                screen_id=resolved_screen_id,
                verdict=verdict,
                latency_breakdown=latency,
                timestamp=current_time,
                engine_used=self.engine_descriptor,
                metadata=run_metadata,
            )

        # Stage 2: Visual Preprocessing
        t_prep_start = time.perf_counter()
        preprocessed = self.preprocessor.preprocess(image_input)
        t_prep_end = time.perf_counter()
        preprocess_ms = round((t_prep_end - t_prep_start) * 1000.0, 2)

        # Stage 3: Prompt Construction
        messages = self.prompt_builder.build_qwen_chat_input(
            image_content=preprocessed.image,
            pruned_nodes=pruned_nodes,
            metadata=run_metadata,
        )

        # Stage 4: Global Inference Execution
        t_inf_start = time.perf_counter()
        try:
            raw_output = self.backend.generate(
                messages=messages,
                image=preprocessed.image,
            )
        except Exception as inf_err:
            if inf_err.__class__.__name__ == "OutOfMemoryError" or "out of memory" in str(inf_err).lower():
                logger.error("CUDA OutOfMemoryError during global inference pass: %s", inf_err)
                import gc
                gc.collect()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
            raise
        t_inf_end = time.perf_counter()
        inference_ms = round((t_inf_end - t_inf_start) * 1000.0, 2)

        # Stage 5: Verdict Parsing
        verdict: Verdict = VerdictParser.parse(raw_output)

        # Stage 6: Universal SAHI High-Res Verification (if clean on global downsample)
        if not verdict.has_defect and enable_sahi and isinstance(self.backend, TransformersInferenceBackend):
            slices = self.preprocessor.get_sahi_slices(image_input)
            if len(slices) > 1:
                detected_slice_verdicts = []
                for current_slice in slices:
                    slice_prep = None
                    slice_msgs = None
                    slice_raw = None
                    try:
                        slice_prep = self.preprocessor.preprocess(current_slice.image)
                        slice_msgs = self.prompt_builder.build_qwen_chat_input(
                            image_content=slice_prep.image,
                            pruned_nodes=None,
                            metadata={"viewport_slice_index": current_slice.slice_index},
                        )
                        t_slice_start = time.perf_counter()
                        slice_raw = self.backend.generate(messages=slice_msgs, image=slice_prep.image)
                        t_slice_end = time.perf_counter()
                        inference_ms += round((t_slice_end - t_slice_start) * 1000.0, 2)
                        sv = VerdictParser.parse(slice_raw)
                        if sv.has_defect:
                            global_bbox = current_slice.map_bbox_to_global(sv.bounding_box)
                            detected_slice_verdicts.append((current_slice, sv, global_bbox))
                    except Exception as slice_err:
                        if slice_err.__class__.__name__ == "OutOfMemoryError" or "out of memory" in str(slice_err).lower():
                            logger.warning(
                                "CUDA OutOfMemoryError encountered during SAHI slice %d. "
                                "Reclaiming VRAM cache and aborting SAHI passes (falling back to global verdict).",
                                current_slice.slice_index,
                            )
                            run_metadata["sahi_oom_recovered"] = True
                            import gc
                            gc.collect()
                            try:
                                import torch
                                if torch.cuda.is_available():
                                    torch.cuda.empty_cache()
                            except Exception:
                                pass
                            break
                        raise
                    finally:
                        if slice_prep is not None:
                            del slice_prep
                        if slice_msgs is not None:
                            del slice_msgs
                        if slice_raw is not None:
                            del slice_raw
                        try:
                            import torch
                            if torch.cuda.is_available():
                                import gc
                                gc.collect()
                                torch.cuda.empty_cache()
                        except Exception:
                            pass

                if detected_slice_verdicts:
                    primary_slice, primary_sv, primary_bbox = detected_slice_verdicts[0]
                    all_regions = []
                    all_explanations = []
                    for s_tile, s_res, g_box in detected_slice_verdicts:
                        all_regions.append({
                            "slice_index": s_tile.slice_index,
                            "defect_type": s_res.defect_type.value if hasattr(s_res.defect_type, "value") else str(s_res.defect_type),
                            "bounding_box": g_box,
                            "confidence": s_res.confidence,
                            "affected_element_id": s_res.affected_element_id,
                            "explanation": s_res.explanation,
                        })
                        all_explanations.append(f"[Slice {s_tile.slice_index}] {s_res.explanation}")

                    verdict = Verdict(
                        has_defect=True,
                        defect_type=primary_sv.defect_type,
                        confidence=primary_sv.confidence,
                        bounding_box=primary_bbox,
                        affected_element_id=primary_sv.affected_element_id,
                        explanation=" | ".join(all_explanations),
                    )
                    run_metadata["detected_by"] = "sahi_dynamic_tiling"
                    run_metadata["sahi_slices_with_defects"] = [s[0].slice_index for s in detected_slice_verdicts]
                    run_metadata["all_detected_regions"] = all_regions

        del preprocessed
        del messages
        if 'slices' in locals():
            del slices
        try:
            import torch
            if torch.cuda.is_available():
                import gc
                gc.collect()
                torch.cuda.empty_cache()
        except Exception:
            pass

        latency = LatencyBreakdown(
            capture_ms=0.0,
            preprocess_ms=preprocess_ms,
            prune_ms=prune_ms,
            inference_ms=inference_ms,
        )
        latency.compute_total()

        return C3OracleResult(
            screen_id=resolved_screen_id,
            verdict=verdict,
            latency_breakdown=latency,
            timestamp=current_time,
            engine_used=self.engine_descriptor,
            metadata=run_metadata,
        )

    def evaluate_device(
        self,
        device: Optional[Any] = None,
        serial: Optional[str] = None,
        enable_sahi: bool = True,
        action_context: Optional[str] = None,
    ) -> C3OracleResult:
        """
        Captures live screen and UI hierarchy from connected Android device/emulator via shared common.adb,
        and streams through the AST Pruner and Universal SAHI Dynamic Slicing engine.
        Zero mocks, zero simulated seeds — raises NoDeviceError if no device attached.
        """
        if device is None:
            from common.adb import AdbDevice
            device = AdbDevice(serial=serial)

        t_cap_start = time.perf_counter()
        screenshot = device.screencap(as_pil=True)
        xml_text = device.dump_hierarchy(max_age_s=0.5)
        t_cap_end = time.perf_counter()
        capture_ms = round((t_cap_end - t_cap_start) * 1000.0, 2)

        metrics = device.get_display_metrics()
        result = self.evaluate(
            image_input=screenshot,
            raw_hierarchy=xml_text,
            screen_id=f"live_{device.serial}",
            action_context=action_context,
            enable_sahi=enable_sahi,
        )
        result.latency_breakdown.capture_ms = capture_ms
        result.latency_breakdown.compute_total()
        result.metadata["device_serial"] = device.serial
        result.metadata["viewport_resolution"] = [metrics["width"], metrics["height"]]
        result.metadata["viewport_density"] = metrics["density"]
        return result

    def evaluate_sequence(
        self,
        screens: List[Union[str, Path, bytes, Image.Image]],
        hierarchies: Optional[List[Optional[Union[str, Path, Dict[str, Any], List[Any]]]]] = None,
        screen_ids: Optional[List[str]] = None,
        time_delta_s: float = 2.5,
        action_dispatched: bool = True,
        action_context: Optional[str] = None,
        enable_sahi: bool = True,
    ) -> C3OracleResult:
        """
        Evaluates a sequence of 2 or more consecutive screen frames to detect temporal
        freezes (FR3) or evaluate the final post-action state.
        """
        if not screens or len(screens) < 2:
            raise ValueError("evaluate_sequence requires at least 2 screen frames for temporal analysis.")

        prev_img = screens[-2]
        curr_img = screens[-1]
        prev_hier = hierarchies[-2] if (hierarchies and len(hierarchies) >= 2) else None
        curr_hier = hierarchies[-1] if (hierarchies and len(hierarchies) >= 1) else None
        curr_id = screen_ids[-1] if (screen_ids and len(screen_ids) >= 1) else None

        return self.evaluate(
            image_input=curr_img,
            raw_hierarchy=curr_hier,
            screen_id=curr_id,
            action_context=action_context,
            enable_sahi=enable_sahi,
            previous_image=prev_img,
            previous_hierarchy=prev_hier,
            time_delta_s=time_delta_s,
            action_dispatched=action_dispatched,
        )

    @staticmethod

    def to_c4_verdict(result: C3OracleResult, screenshot_path: Optional[str] = None, session_id: Optional[str] = None) -> Any:
        """
        Directly maps C3 Oracle evaluation result to Component 4's C3Verdict contract.
        Fulfills component4/src/c4/c3_interface/contract.py schema.
        """
        try:
            from c4.c3_interface.contract import C3Verdict, ScreenshotEvidence, DefectRegion

        except ImportError:
            import sys
            from pathlib import Path
            repo_root = Path(__file__).resolve().parent.parent.parent
            search_paths = [
                repo_root / "component4" / "src",
                Path.cwd() / "component4" / "src",
            ]
            for p in search_paths:
                if p.exists() and str(p) not in sys.path:
                    sys.path.insert(0, str(p))
            from c4.c3_interface.contract import C3Verdict, ScreenshotEvidence, DefectRegion

        verdict = result.verdict

        resolution = result.metadata.get("viewport_resolution", [720, 1600])
        width = int(resolution[0]) if len(resolution) > 0 else 720
        height = int(resolution[1]) if len(resolution) > 1 else 1600

        screenshot_evidence = ScreenshotEvidence(
            path=screenshot_path,
            width=width,
            height=height,
        )

        regions = []
        all_detected = result.metadata.get("all_detected_regions")
        if all_detected:
            for item in all_detected:
                bbox = item.get("bounding_box")
                if bbox and len(bbox) == 4:
                    ymin, xmin, ymax, xmax = bbox
                    px_x = int((xmin / 1000.0) * width)
                    px_y = int((ymin / 1000.0) * height)
                    px_w = max(1, int(((xmax - xmin) / 1000.0) * width))
                    px_h = max(1, int(((ymax - ymin) / 1000.0) * height))
                    if px_x + px_w > width:
                        px_w = width - px_x
                    if px_y + px_h > height:
                        px_h = height - px_y
                    regions.append(DefectRegion(
                        x=px_x,
                        y=px_y,
                        width=px_w,
                        height=px_h,
                        label=item.get("defect_type", "component_overlap"),
                    ))
        elif verdict.has_defect and verdict.bounding_box:
            ymin, xmin, ymax, xmax = verdict.bounding_box
            px_x = int((xmin / 1000.0) * width)
            px_y = int((ymin / 1000.0) * height)
            px_w = max(1, int(((xmax - xmin) / 1000.0) * width))
            px_h = max(1, int(((ymax - ymin) / 1000.0) * height))

            # Clamp within screenshot dimensions
            if px_x + px_w > width:
                px_w = width - px_x
            if px_y + px_h > height:
                px_h = height - px_y

            regions.append(DefectRegion(
                x=px_x,
                y=px_y,
                width=px_w,
                height=px_h,
                label=verdict.defect_type.value if hasattr(verdict.defect_type, "value") else str(verdict.defect_type),
            ))

        return C3Verdict(
            schema_version="1.0.0",
            verdict_id=f"verdict_{result.screen_id}_{int(time.time())}",
            session_id=session_id,
            has_gui_defect=verdict.has_defect,
            defect_type=verdict.defect_type.value if verdict.has_defect and hasattr(verdict.defect_type, "value") else (str(verdict.defect_type) if verdict.has_defect else None),
            confidence=float(verdict.confidence),
            screenshot=screenshot_evidence,
            regions=regions,
            evidence={
                "explanation": verdict.explanation,
                "latency_breakdown": result.latency_breakdown.model_dump(),
                "detected_by": result.metadata.get("detected_by", "vlm_inference"),
                "engine_used": result.engine_used,
            },
            metadata=result.metadata,
        )


