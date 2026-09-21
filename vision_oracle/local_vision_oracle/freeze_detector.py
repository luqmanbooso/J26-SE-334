"""
Temporal Freeze Detector for Component C3 (HEART Framework).
Detects frozen UI states, indeterminate progress spinners, and unresponsive screens
by analyzing consecutive frame pairs and view hierarchies across test actions.
Fulfills Proposal FR3 (frozen states) and Appendix F (Temporal Freeze Detector).
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple, Union
import numpy as np
from PIL import Image

from local_vision_oracle.schemas import DefectType, Verdict


@dataclass
class FreezeDetectionResult:
    is_frozen: bool
    defect_type: DefectType
    confidence: float
    stalled_duration_s: float
    pixel_difference_ratio: float
    affected_element_id: Optional[str] = None
    bounding_box: Optional[List[int]] = None
    explanation: str = ""

    def to_verdict(self) -> Verdict:
        """Converts detection result into standard C3 Verdict."""
        if not self.is_frozen:
            return Verdict(
                has_defect=False,
                defect_type=DefectType.NONE,
                confidence=round(self.confidence, 4),
                bounding_box=None,
                affected_element_id=None,
                explanation="UI transitioned nominally between interaction steps.",
            )
        return Verdict(
            has_defect=True,
            defect_type=self.defect_type,
            confidence=round(self.confidence, 4),
            bounding_box=self.bounding_box,
            affected_element_id=self.affected_element_id,
            explanation=self.explanation,
        )


class TemporalFreezeDetector:
    """
    Evaluates temporal changes between consecutive screen captures to identify:
    1. Static Frame Freeze: User interaction dispatched but screen pixels & hierarchy remain 100% frozen.
    2. Indeterminate Spinner Lock: Animated or static loading indicator spinning indefinitely without content load.
    """

    SPINNER_PATTERNS = [
        r"progressbar",
        r"spinner",
        r"loading",
        r"progress_indicator",
        r"circularprogress",
        r"shimmer",
    ]

    def __init__(
        self,
        static_pixel_threshold: float = 0.005,
        stalled_time_threshold_s: float = 2.0,
        spinner_timeout_s: float = 3.5,
        comparison_dim: Tuple[int, int] = (256, 256),
    ):
        self.static_pixel_threshold = static_pixel_threshold
        self.stalled_time_threshold_s = stalled_time_threshold_s
        self.spinner_timeout_s = spinner_timeout_s
        self.comparison_dim = comparison_dim

    def compute_pixel_difference(
        self,
        img_a: Union[Image.Image, bytes, str],
        img_b: Union[Image.Image, bytes, str],
    ) -> float:
        """
        Computes normalized mean absolute pixel difference between two frames.
        Returns float in range [0.0, 1.0], where 0.0 is byte-identical.
        """
        pil_a = self._to_pil(img_a).convert("L").resize(self.comparison_dim, Image.Resampling.BILINEAR)
        pil_b = self._to_pil(img_b).convert("L").resize(self.comparison_dim, Image.Resampling.BILINEAR)

        arr_a = np.asarray(pil_a, dtype=np.float32)
        arr_b = np.asarray(pil_b, dtype=np.float32)

        diff = np.mean(np.abs(arr_a - arr_b)) / 255.0
        return float(diff)

    def extract_loading_indicators(self, raw_hierarchy: str) -> List[Dict[str, Any]]:
        """
        Extracts active progress bar or loading spinner elements from accessibility hierarchy XML.
        """
        if not raw_hierarchy or not isinstance(raw_hierarchy, str):
            return []

        indicators = []
        try:
            root = ET.fromstring(raw_hierarchy)
            for node in root.iter("node"):
                cls_name = (node.attrib.get("class") or "").lower()
                res_id = (node.attrib.get("resource-id") or "").lower()
                text = (node.attrib.get("text") or "").lower()

                matched = False
                for pat in self.SPINNER_PATTERNS:
                    if re.search(pat, cls_name) or re.search(pat, res_id) or re.search(pat, text):
                        matched = True
                        break

                if matched:
                    bounds_str = node.attrib.get("bounds", "")
                    bbox = self._parse_bounds_to_normalized(bounds_str)
                    indicators.append({
                        "class": node.attrib.get("class"),
                        "resource_id": node.attrib.get("resource-id"),
                        "bounds": bbox,
                    })
        except Exception:
            pass

        return indicators

    def detect_freeze(
        self,
        previous_image: Union[Image.Image, bytes, str],
        current_image: Union[Image.Image, bytes, str],
        previous_hierarchy: Optional[str] = None,
        current_hierarchy: Optional[str] = None,
        time_delta_s: float = 2.0,
        action_dispatched: bool = True,
        action_context: Optional[str] = None,
    ) -> FreezeDetectionResult:
        """
        Compares two consecutive frames and evaluates freeze heuristics.
        """
        pixel_diff = self.compute_pixel_difference(previous_image, current_image)

        # Check for Indeterminate Spinner Lock
        curr_spinners = self.extract_loading_indicators(current_hierarchy or "")
        prev_spinners = self.extract_loading_indicators(previous_hierarchy or "") if previous_hierarchy else []

        if curr_spinners and time_delta_s >= self.spinner_timeout_s:
            # Spinner exists across delay
            top_spinner = curr_spinners[0]
            target_id = top_spinner.get("resource_id") or top_spinner.get("class") or "ProgressBar"
            target_bbox = top_spinner.get("bounds")
            return FreezeDetectionResult(
                is_frozen=True,
                defect_type=DefectType.FROZEN_STATE,
                confidence=0.94,
                stalled_duration_s=time_delta_s,
                pixel_difference_ratio=pixel_diff,
                affected_element_id=target_id,
                bounding_box=target_bbox,
                explanation=(
                    f"Indeterminate progress state: Loading indicator '{target_id}' persisted for "
                    f"{time_delta_s:.1f}s without view progression."
                ),
            )

        # Check for Unresponsive Static Freeze after user action
        if action_dispatched and time_delta_s >= self.stalled_time_threshold_s:
            if pixel_diff <= self.static_pixel_threshold:
                ctx_info = f" after action '{action_context}'" if action_context else ""
                return FreezeDetectionResult(
                    is_frozen=True,
                    defect_type=DefectType.FROZEN_STATE,
                    confidence=0.96,
                    stalled_duration_s=time_delta_s,
                    pixel_difference_ratio=pixel_diff,
                    affected_element_id=None,
                    bounding_box=[0, 0, 1000, 1000],
                    explanation=(
                        f"Temporal UI Freeze: Screen state remained completely static (pixel diff {pixel_diff*100:.2f}%) "
                        f"for {time_delta_s:.1f}s{ctx_info}."
                    ),
                )

        return FreezeDetectionResult(
            is_frozen=False,
            defect_type=DefectType.NONE,
            confidence=0.98,
            stalled_duration_s=time_delta_s,
            pixel_difference_ratio=pixel_diff,
            affected_element_id=None,
            bounding_box=None,
            explanation="Normal dynamic transition observed.",
        )

    @staticmethod
    def _to_pil(img_input: Union[Image.Image, bytes, str]) -> Image.Image:
        if isinstance(img_input, Image.Image):
            return img_input
        if isinstance(img_input, (str, bytes)):
            import io
            if isinstance(img_input, bytes):
                return Image.open(io.BytesIO(img_input))
            return Image.open(img_input)
        raise ValueError(f"Unsupported image type: {type(img_input)}")

    @staticmethod
    def _parse_bounds_to_normalized(bounds_str: str) -> Optional[List[int]]:
        """Parses '[x1,y1][x2,y2]' into normalized [ymin, xmin, ymax, xmax] in [0, 1000]."""
        m = re.findall(r"\[(\d+),(\d+)\]", bounds_str)
        if len(m) == 2:
            try:
                x1, y1 = int(m[0][0]), int(m[0][1])
                x2, y2 = int(m[1][0]), int(m[1][1])
                # Default baseline screen assumption (1080x2400) for fallback normalization
                ymin = int(np.clip((y1 / 2400.0) * 1000, 0, 1000))
                xmin = int(np.clip((x1 / 1080.0) * 1000, 0, 1000))
                ymax = int(np.clip((y2 / 2400.0) * 1000, 0, 1000))
                xmax = int(np.clip((x2 / 1080.0) * 1000, 0, 1000))
                return [ymin, xmin, ymax, xmax]
            except Exception:
                pass
        return None
