"""
Canonical Preprocessing and Unified Inference Pipeline for Component 3.
Compliant with Phase D of HEART C3 Full Implementation Plan (v1.0, 18 Oct 2026).
Enforces:
- Single canonical pipeline shared across API, CLI, and benchmarks
- Reversible physical pixel coordinate transformations for global and tiled views
- Multi-finding strict parser with markdown/JSON tolerance and error traceability
- Class-aware overlap clustering (IoU >= 0.5) for view aggregation
- Invariant: partial analysis with zero findings is inconclusive, errors never become clean
"""

from __future__ import annotations

import math
import re
import json
import time
import uuid
import logging
from typing import List, Optional, Dict, Any, Tuple
from PIL import Image

from vision_oracle.contracts.v2 import (
    AnalysisStatus,
    AnalysisDecision,
    CoveragePolicy,
    Coverage,
    ScreenshotRef,
    Finding,
    FindingType,
    CaptureBundle,
    VerdictEnvelopeV2,
    ReviewStatus,
)

logger = logging.getLogger("vision_oracle.pipeline")


class ViewSpec:
    """Specification of an image view/tile in physical coordinates."""

    def __init__(self, view_id: str, crop_rect: Tuple[int, int, int, int], is_global: bool = False):
        self.view_id = view_id
        # (cx, cy, cw, ch) in original image pixels
        self.crop_rect = crop_rect
        self.is_global = is_global

    def __repr__(self) -> str:
        return f"ViewSpec(id={self.view_id}, crop={self.crop_rect}, global={self.is_global})"


class ViewPlanner:
    """Plans global view and overlapping vertical/horizontal tiles for screen analysis."""

    @staticmethod
    def plan_views(
        width: int,
        height: int,
        policy: CoveragePolicy = CoveragePolicy.GLOBAL_PLUS_TILES_V1,
    ) -> List[ViewSpec]:
        views = [ViewSpec(view_id="global", crop_rect=(0, 0, width, height), is_global=True)]

        if policy == CoveragePolicy.GLOBAL_ONLY:
            return views

        # Check aspect ratio for tall mobile screens (portrait >= 1.6:1)
        aspect = height / max(1, width)
        if aspect >= 1.6:
            # Overlapping vertical slices (~25% overlap between adjacent views)
            slice_h = int(round(height * 0.45))
            step = int(round((height - slice_h) / 2))
            
            y_starts = [0, step, height - slice_h]
            for idx, y_start in enumerate(y_starts):
                y_clamped = max(0, min(y_start, height - slice_h))
                views.append(
                    ViewSpec(
                        view_id=f"tile_{idx}",
                        crop_rect=(0, y_clamped, width, slice_h),
                        is_global=False,
                    )
                )
        elif width / max(1, height) >= 1.6:
            # Overlapping horizontal slices for landscape screens
            slice_w = int(round(width * 0.45))
            step = int(round((width - slice_w) / 2))
            x_starts = [0, step, width - slice_w]
            for idx, x_start in enumerate(x_starts):
                x_clamped = max(0, min(x_start, width - slice_w))
                views.append(
                    ViewSpec(
                        view_id=f"tile_{idx}",
                        crop_rect=(x_clamped, 0, slice_w, height),
                        is_global=False,
                    )
                )

        return views


class CoordinateMapper:
    """Maps normalized model coordinates back to original physical screen pixels."""

    @staticmethod
    def model_to_pixels(
        box_yxyx_1000: List[int],
        view: ViewSpec,
        orig_width: int,
        orig_height: int,
    ) -> List[int]:
        """
        Maps [ymin, xmin, ymax, xmax] in [0, 1000] back to [x1, y1, x2, y2]
        in original uncropped screen pixels.
        Formula from Implementation Plan Section 6.2:
          x1 = cx + (xmin / 1000) * cw
          y1 = cy + (ymin / 1000) * ch
          x2 = cx + (xmax / 1000) * cw
          y2 = cy + (ymax / 1000) * ch
        """
        cx, cy, cw, ch = view.crop_rect
        if len(box_yxyx_1000) != 4:
            raise ValueError(f"box_yxyx_1000 must contain exactly 4 coordinates, got {box_yxyx_1000}")
        ymin, xmin, ymax, xmax = box_yxyx_1000

        # Validate normalized bounds before coordinate transformation
        if ymin < 0 or xmin < 0 or ymax > 1000 or xmax > 1000:
            raise ValueError(f"Normalized coordinates must be within [0, 1000], got {box_yxyx_1000}")
        if ymin >= ymax:
            raise ValueError(f"Invalid vertical coordinates: ymin={ymin} >= ymax={ymax}")
        if xmin >= xmax:
            raise ValueError(f"Invalid horizontal coordinates: xmin={xmin} >= xmax={xmax}")

        x1 = int(round(cx + (xmin / 1000.0) * cw))
        y1 = int(round(cy + (ymin / 1000.0) * ch))
        x2 = int(round(cx + (xmax / 1000.0) * cw))
        y2 = int(round(cy + (ymax / 1000.0) * ch))

        # Clamp strictly within physical screen resolution
        x1 = max(0, min(x1, orig_width - 1))
        y1 = max(0, min(y1, orig_height - 1))
        x2 = max(0, min(x2, orig_width))
        y2 = max(0, min(y2, orig_height))

        if x1 >= x2 or y1 >= y2:
            raise ValueError(f"Mapped physical pixel box has non-positive area: [{x1}, {y1}, {x2}, {y2}]")

        return [x1, y1, x2, y2]

    @staticmethod
    def pixels_to_model(
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        orig_width: int,
        orig_height: int,
    ) -> List[int]:
        """Maps physical pixel [x1, y1, x2, y2] to normalized [ymin, xmin, ymax, xmax] in [0, 1000]."""
        ymin = int(round(max(0, min(1000, (y1 / max(1, orig_height)) * 1000.0))))
        xmin = int(round(max(0, min(1000, (x1 / max(1, orig_width)) * 1000.0))))
        ymax = int(round(max(0, min(1000, (y2 / max(1, orig_height)) * 1000.0))))
        xmax = int(round(max(0, min(1000, (x2 / max(1, orig_width)) * 1000.0))))
        return [ymin, xmin, ymax, xmax]


class FindingParser:
    """Strict parser extracting findings from VLM JSON responses."""

    @staticmethod
    def parse_findings(
        response_text: str,
        view: ViewSpec,
        orig_width: int,
        orig_height: int,
    ) -> Tuple[List[Finding], List[str]]:
        """
        Extracts findings from model answer.
        Supports:
        1. V2 multi-finding schema: {"findings": [{"type": "...", "bbox_yxyx_1000": [...], "explanation": "..."}]}
        2. Legacy schema: {"has_defect": bool, "defect_type": "...", "bounding_box": [...], "explanation": "..."}
        Returns (findings, errors).
        """
        findings: List[Finding] = []
        errors: List[str] = []

        if not response_text or not response_text.strip():
            errors.append(f"Empty model response received for view '{view.view_id}'")
            return findings, errors

        # Strip markdown fences if present
        cleaned = response_text.strip()
        match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", cleaned, re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()
        else:
            json_start = cleaned.find("{")
            json_end = cleaned.rfind("}")
            if json_start != -1 and json_end != -1 and json_end > json_start:
                cleaned = cleaned[json_start : json_end + 1]

        try:
            parsed = json.loads(cleaned)
        except Exception as exc:
            errors.append(f"JSON parsing error for view '{view.view_id}': {exc}. Raw snippet: {cleaned[:120]}")
            return findings, errors

        if not isinstance(parsed, dict):
            errors.append(f"Invalid root object type '{type(parsed).__name__}' for view '{view.view_id}'. Expected JSON object.")
            return findings, errors

        # Schema detection & top-level object validation
        has_findings_key = "findings" in parsed
        has_defect_key = "has_defect" in parsed

        if not has_findings_key and not has_defect_key:
            errors.append(
                f"Unrecognized schema for view '{view.view_id}': neither 'findings' list nor 'has_defect' boolean present in model response. "
                f"Keys received: {list(parsed.keys())}"
            )
            return findings, errors

        # R6: Cross-validate mixed schemas to prevent contradictory clean verdicts
        if has_findings_key and has_defect_key:
            findings_list = parsed.get("findings")
            has_defect_val = parsed.get("has_defect")
            if isinstance(has_defect_val, bool) and isinstance(findings_list, list):
                if has_defect_val and len(findings_list) == 0:
                    errors.append(
                        f"Contradictory mixed schema in view '{view.view_id}': 'has_defect' is True but 'findings' list is empty. "
                        f"Cannot determine valid defect state."
                    )
                    return findings, errors
                if not has_defect_val and len(findings_list) > 0:
                    errors.append(
                        f"Contradictory mixed schema in view '{view.view_id}': 'has_defect' is False but 'findings' list contains {len(findings_list)} items."
                    )
                    return findings, errors

        valid_defect_types = {t.value for t in FindingType}

        # Check V2 schema
        if has_findings_key:
            raw_findings_list = parsed["findings"]
            if not isinstance(raw_findings_list, list):
                errors.append(f"'findings' field must be a list, got {type(raw_findings_list).__name__}")
                return findings, errors

            for idx, item in enumerate(raw_findings_list):
                if not isinstance(item, dict):
                    errors.append(f"Finding item {idx} in view '{view.view_id}' must be a JSON object, got {type(item).__name__}")
                    continue

                dtype = item.get("type") or item.get("defect_type")
                if not dtype or not isinstance(dtype, str):
                    errors.append(f"Finding item {idx} in view '{view.view_id}' missing required 'type' field")
                    continue

                dtype_clean = dtype.strip().lower()
                if dtype_clean in ("none", "clean"):
                    continue

                if dtype_clean not in valid_defect_types:
                    errors.append(
                        f"Unknown defect type '{dtype}' in view '{view.view_id}'. "
                        f"Allowed taxonomy: {sorted(list(valid_defect_types))}"
                    )
                    continue

                raw_box = item.get("bbox_yxyx_1000") or item.get("bounding_box") or item.get("bbox")
                bbox_xyxy = None
                boundary_touching = False
                if raw_box is not None:
                    if not isinstance(raw_box, (list, tuple)) or len(raw_box) != 4:
                        errors.append(f"Invalid bounding box in view '{view.view_id}': must contain exactly 4 coordinates, got {raw_box}")
                    elif any(isinstance(c, bool) for c in raw_box):
                        errors.append(f"Invalid bounding box in view '{view.view_id}': coordinates cannot be boolean, got {raw_box}")
                    else:
                        try:
                            ymin, xmin, ymax, xmax = [float(c) for c in raw_box]
                            if ymin < 0 or xmin < 0 or ymax > 1000 or xmax > 1000:
                                errors.append(f"Bounding box {raw_box} out of normalized bounds [0, 1000] in view '{view.view_id}'")
                            elif ymin >= ymax or xmin >= xmax:
                                errors.append(f"Invalid reversed or zero-area box [ymin={ymin}, xmin={xmin}, ymax={ymax}, xmax={xmax}] in view '{view.view_id}'")
                            else:
                                if ymin <= 5 or xmin <= 5 or ymax >= 995 or xmax >= 995:
                                    boundary_touching = True
                                bbox_xyxy = CoordinateMapper.model_to_pixels(
                                    box_yxyx_1000=[int(round(ymin)), int(round(xmin)), int(round(ymax)), int(round(xmax))],
                                    view=view,
                                    orig_width=orig_width,
                                    orig_height=orig_height,
                                )
                        except Exception as err:
                            errors.append(f"Invalid bounding box {raw_box} in view '{view.view_id}': {err}")

                # Confidence validation (no fabricated 0.85/0.99/1.0 defaults)
                conf_raw = item.get("confidence")
                confidence = None
                conf_method = "unavailable"
                if conf_raw is not None:
                    if isinstance(conf_raw, bool) or not isinstance(conf_raw, (int, float)) or math.isnan(conf_raw) or math.isinf(conf_raw) or conf_raw < 0.0 or conf_raw > 1.0:
                        errors.append(f"Invalid non-finite or out-of-range confidence '{conf_raw}' in view '{view.view_id}'")
                    else:
                        confidence = float(conf_raw)
                        conf_method = "uncalibrated"

                explanation = str(item.get("explanation") or f"Detected visual defect '{dtype_clean}' in view '{view.view_id}'")
                if boundary_touching:
                    explanation += " (touches view boundary; flagged for corroboration)"

                findings.append(
                    Finding(
                        finding_id=f"find_{uuid.uuid4().hex[:12]}",
                        type=dtype_clean,
                        bbox_xyxy=bbox_xyxy,
                        element_ref=item.get("affected_element_id") or item.get("element_ref"),
                        explanation=explanation,
                        source="vlm",
                        confidence=confidence,
                        confidence_method=conf_method,
                        view_ids=[view.view_id],
                        review_status=ReviewStatus.UNREVIEWED,
                    )
                )

        # Check Legacy schema
        elif has_defect_key:
            has_defect_val = parsed.get("has_defect")
            if not isinstance(has_defect_val, bool):
                errors.append(
                    f"Invalid schema: 'has_defect' must be an actual boolean, got {type(has_defect_val).__name__} ({has_defect_val!r})"
                )
                return findings, errors

            raw_box = parsed.get("bounding_box") or parsed.get("bbox")
            defect_type_raw = parsed.get("defect_type")

            # Check contradictory clean combinations
            if not has_defect_val:
                if raw_box is not None:
                    errors.append(f"Contradictory schema in view '{view.view_id}': has_defect is false but bounding box {raw_box} is present")
                if defect_type_raw is not None and str(defect_type_raw).strip().lower() not in ("", "none", "clean"):
                    errors.append(f"Contradictory schema in view '{view.view_id}': has_defect is false but defect_type is '{defect_type_raw}'")
                return findings, errors

            # has_defect is True
            if not defect_type_raw or not isinstance(defect_type_raw, str):
                errors.append(f"Missing required 'defect_type' field in view '{view.view_id}' when has_defect is true")
                return findings, errors

            defect_type_clean = defect_type_raw.strip().lower()
            if defect_type_clean in ("none", "clean"):
                errors.append(f"Contradictory schema in view '{view.view_id}': has_defect is true but defect_type is '{defect_type_clean}'")
                return findings, errors

            if defect_type_clean not in valid_defect_types:
                errors.append(
                    f"Unknown defect type '{defect_type_raw}' in view '{view.view_id}'. "
                    f"Allowed taxonomy: {sorted(list(valid_defect_types))}"
                )
                return findings, errors

            bbox_xyxy = None
            boundary_touching = False
            if raw_box is not None:
                if not isinstance(raw_box, (list, tuple)) or len(raw_box) != 4:
                    errors.append(f"Invalid legacy bounding box in view '{view.view_id}': must contain exactly 4 coordinates, got {raw_box}")
                elif any(isinstance(c, bool) for c in raw_box):
                    errors.append(f"Invalid legacy bounding box in view '{view.view_id}': coordinates cannot be boolean, got {raw_box}")
                else:
                    try:
                        ymin, xmin, ymax, xmax = [float(c) for c in raw_box]
                        if ymin < 0 or xmin < 0 or ymax > 1000 or xmax > 1000:
                            errors.append(f"Bounding box {raw_box} out of normalized bounds [0, 1000] in view '{view.view_id}'")
                        elif ymin >= ymax or xmin >= xmax:
                            errors.append(f"Invalid reversed or zero-area box [ymin={ymin}, xmin={xmin}, ymax={ymax}, xmax={xmax}] in view '{view.view_id}'")
                        else:
                            if ymin <= 5 or xmin <= 5 or ymax >= 995 or xmax >= 995:
                                boundary_touching = True
                            bbox_xyxy = CoordinateMapper.model_to_pixels(
                                box_yxyx_1000=[int(round(ymin)), int(round(xmin)), int(round(ymax)), int(round(xmax))],
                                view=view,
                                orig_width=orig_width,
                                orig_height=orig_height,
                            )
                    except Exception as err:
                        errors.append(f"Invalid legacy bounding box {raw_box} in view '{view.view_id}': {err}")

            # Confidence validation (no fabricated 0.85/0.99/1.0 defaults)
            conf_raw = parsed.get("confidence")
            confidence = None
            conf_method = "unavailable"
            if conf_raw is not None:
                if isinstance(conf_raw, bool) or not isinstance(conf_raw, (int, float)) or math.isnan(conf_raw) or math.isinf(conf_raw) or conf_raw < 0.0 or conf_raw > 1.0:
                    errors.append(f"Invalid non-finite or out-of-range confidence '{conf_raw}' in view '{view.view_id}'")
                else:
                    confidence = float(conf_raw)
                    conf_method = "uncalibrated"

            explanation = str(parsed.get("explanation") or f"Detected visual defect '{defect_type_clean}' in view '{view.view_id}'")
            if boundary_touching:
                explanation += " (touches view boundary; flagged for corroboration)"

            findings.append(
                Finding(
                    finding_id=f"find_{uuid.uuid4().hex[:12]}",
                    type=defect_type_clean,
                    bbox_xyxy=bbox_xyxy,
                    element_ref=parsed.get("affected_element_id"),
                    explanation=explanation,
                    source="vlm",
                    confidence=confidence,
                    confidence_method=conf_method,
                    view_ids=[view.view_id],
                    review_status=ReviewStatus.UNREVIEWED,
                )
            )

        return findings, errors


class OverlapDeduplicator:
    """Merges redundant detections across overlapping tiles using class-aware IoU."""

    @staticmethod
    def compute_iou(box_a: List[int], box_b: List[int]) -> float:
        """Computes Intersection-over-Union between two physical [x1, y1, x2, y2] boxes."""
        xA = max(box_a[0], box_b[0])
        yA = max(box_a[1], box_b[1])
        xB = min(box_a[2], box_b[2])
        yB = min(box_a[3], box_b[3])

        inter_w = max(0, xB - xA)
        inter_h = max(0, yB - yA)
        inter_area = inter_w * inter_h
        if inter_area <= 0:
            return 0.0

        area_a = max(1, (box_a[2] - box_a[0]) * (box_a[3] - box_a[1]))
        area_b = max(1, (box_b[2] - box_b[0]) * (box_b[3] - box_b[1]))
        union_area = float(area_a + area_b - inter_area)
        return inter_area / union_area if union_area > 0 else 0.0

    @classmethod
    def deduplicate(cls, findings: List[Finding], iou_threshold: float = 0.5) -> List[Finding]:
        """Class-aware overlap clustering."""
        if len(findings) <= 1:
            return list(findings)

        clustered: List[Finding] = []
        visited = set()

        for i, f1 in enumerate(findings):
            if i in visited:
                continue

            current_views = set(f1.view_ids)
            best_bbox = f1.bbox_xyxy
            best_explanation = f1.explanation
            best_confidence = f1.confidence
            best_element_ref = f1.element_ref

            for j in range(i + 1, len(findings)):
                if j in visited:
                    continue
                f2 = findings[j]

                # Must be the same defect type
                if f1.type != f2.type:
                    continue

                # If both have boxes, check IoU
                if f1.bbox_xyxy is not None and f2.bbox_xyxy is not None:
                    iou = cls.compute_iou(f1.bbox_xyxy, f2.bbox_xyxy)
                    if iou >= iou_threshold:
                        visited.add(j)
                        current_views.update(f2.view_ids)
                        if f2.confidence is not None and (best_confidence is None or f2.confidence > best_confidence):
                            best_confidence = f2.confidence
                            best_bbox = f2.bbox_xyxy
                            best_explanation = f2.explanation
                        if not best_element_ref and f2.element_ref:
                            best_element_ref = f2.element_ref
                elif f1.bbox_xyxy is None and f2.bbox_xyxy is None:
                    # Nonlocalized findings of same type merge
                    visited.add(j)
                    current_views.update(f2.view_ids)

            clustered.append(
                Finding(
                    finding_id=f1.finding_id,
                    type=f1.type,
                    bbox_xyxy=best_bbox,
                    element_ref=best_element_ref,
                    explanation=best_explanation,
                    source=f1.source,
                    confidence=best_confidence,
                    confidence_method=f1.confidence_method,
                    view_ids=sorted(list(current_views)),
                    review_status=f1.review_status,
                )
            )
            visited.add(i)

        return clustered


class AnalysisPipeline:
    """
    Canonical production inference pipeline.
    Coordinates preprocessing, view planning, VLM generation, strict parsing,
    and multi-view deduplication into a verified VerdictEnvelopeV2.
    """

    def __init__(self, backend: Any, model_run_id: str = "qwen2-vl-2b-instruct-local"):
        self.backend = backend
        self.model_run_id = model_run_id

    def analyze(
        self,
        bundle: CaptureBundle,
        image: Image.Image,
        policy: CoveragePolicy = CoveragePolicy.GLOBAL_PLUS_TILES_V1,
        job_id: Optional[str] = None,
        pruned_hierarchy_text: Optional[str] = None,
        messages_builder_fn: Optional[Any] = None,
    ) -> VerdictEnvelopeV2:
        """
        Executes end-to-end multi-view analysis across planned views.
        """
        t0 = time.perf_counter()
        orig_w, orig_h = image.size
        # Update bundle width/height if needed
        bundle.width = orig_w
        bundle.height = orig_h

        planned_views = ViewPlanner.plan_views(orig_w, orig_h, policy=policy)
        raw_findings: List[Finding] = []
        errors: List[str] = []
        warnings: List[str] = []
        valid_views = 0
        raw_responses: Dict[str, str] = {}

        t_preprocess_acc = 0.0
        t_inference_acc = 0.0

        sahi_oom_recovered = False
        for view in planned_views:
            t_p0 = time.perf_counter()
            # Crop view
            cx, cy, cw, ch = view.crop_rect
            if view.is_global:
                view_img = image
            else:
                view_img = image.crop((cx, cy, cx + cw, cy + ch))

            t_preprocess_acc += (time.perf_counter() - t_p0) * 1000.0

            # Generate messages
            if messages_builder_fn:
                messages = messages_builder_fn(view, pruned_hierarchy_text)
            else:
                from vision_oracle.local_vision_oracle.prompt import PromptBuilder
                builder = PromptBuilder()
                user_content = builder.build_user_prompt(pruned_nodes=None)
                messages = [
                    {"role": "system", "content": builder.system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "image"},
                            {"type": "text", "text": user_content},
                        ],
                    },
                ]

            t_i0 = time.perf_counter()
            try:
                response_text = self.backend.generate(messages=messages, image=view_img)
                t_inference_acc += (time.perf_counter() - t_i0) * 1000.0
                raw_responses[view.view_id] = response_text

                # Parse findings with strict validation
                v_findings, v_errors = FindingParser.parse_findings(
                    response_text=response_text,
                    view=view,
                    orig_width=orig_w,
                    orig_height=orig_h,
                )

                if v_errors:
                    errors.extend(v_errors)
                    # View is counted as successfully analyzed ONLY after output passes validation
                else:
                    valid_views += 1
                    raw_findings.extend(v_findings)

            except Exception as exc:
                t_inference_acc += (time.perf_counter() - t_i0) * 1000.0
                is_oom = (
                    exc.__class__.__name__ == "OutOfMemoryError"
                    or "out of memory" in str(exc).lower()
                )
                if is_oom:
                    import gc
                    gc.collect()
                    try:
                        import torch
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                    except Exception:
                        pass

                # Fatal: global view failure, or non-OOM hardware crash on any view
                if view.is_global or not is_oom:
                    raise exc

                # Non-fatal SAHI slice OOM: graceful fallback to global view passes, abort remaining slices
                sahi_oom_recovered = True
                err_msg = f"Failure during inference for view '{view.view_id}': {exc}"
                logger.warning(err_msg)
                warnings.append(err_msg)
                break

        t_agg0 = time.perf_counter()
        deduped_findings = OverlapDeduplicator.deduplicate(raw_findings, iou_threshold=0.5)
        t_agg_ms = (time.perf_counter() - t_agg0) * 1000.0

        total_ms = (time.perf_counter() - t0) * 1000.0

        # Scientific Decision Policy (PP1 Section 3):
        # - All required views valid; no findings -> No defect detected within configured scope
        # - Valid finding; all required views valid -> Defect detected, complete
        # - Valid finding; some views failed -> Defect detected, partial
        # - No valid finding; some required views failed -> Inconclusive, partial
        # - No valid views -> Inconclusive, error
        all_required_views_valid = (valid_views == len(planned_views)) and (len(warnings) == 0)

        if all_required_views_valid:
            analysis_status = AnalysisStatus.COMPLETE
            if len(deduped_findings) > 0:
                decision = AnalysisDecision.DEFECT_DETECTED
            else:
                decision = AnalysisDecision.NO_DEFECT_DETECTED
        elif valid_views > 0:
            analysis_status = AnalysisStatus.PARTIAL
            if len(deduped_findings) > 0:
                decision = AnalysisDecision.DEFECT_DETECTED
            else:
                decision = AnalysisDecision.INCONCLUSIVE
        else:
            # 0 valid views (all views failed generation or validation)
            analysis_status = AnalysisStatus.ERROR
            decision = AnalysisDecision.INCONCLUSIVE

        coverage = Coverage(
            policy=policy.value if hasattr(policy, "value") else str(policy),
            planned_views=len(planned_views),
            completed_views=valid_views,
            warnings=warnings,
        )

        screenshot_ref = ScreenshotRef(
            artifact_id=f"art_{bundle.capture_id}",
            width=orig_w,
            height=orig_h,
            coordinate_space="original_pixels_xyxy",
            sha256=bundle.image_sha256,
            storage_path=bundle.artifact_path,
        )

        return VerdictEnvelopeV2(
            schema_version="2.0",
            job_id=job_id or f"job_{uuid.uuid4().hex[:12]}",
            verdict_id=f"verdict_{uuid.uuid4().hex[:12]}",
            session_id=bundle.session_id,
            action_id=bundle.action_id,
            capture_id=bundle.capture_id,
            analysis_status=analysis_status,
            decision=decision,
            coverage=coverage,
            screenshot=screenshot_ref,
            scope={"mode": "single_primary_visual_finding", "exhaustive": False},
            primary_finding=deduped_findings[0] if deduped_findings else None,
            findings=deduped_findings,
            model_run_id=self.model_run_id,
            timings_ms={
                "preprocess_ms": round(t_preprocess_acc, 2),
                "inference_ms": round(t_inference_acc, 2),
                "aggregation_ms": round(t_agg_ms, 2),
                "total_pipeline_ms": round(total_ms, 2),
            },
            errors=errors,
            metadata={
                "device_serial": bundle.device_serial,
                "app_package": bundle.app_package,
                "hierarchy_status": bundle.hierarchy_status,
                "raw_responses": raw_responses,
                "valid_views": valid_views,
                "failed_views": len(planned_views) - valid_views,
                "sahi_oom_recovered": sahi_oom_recovered,
            },
        )
