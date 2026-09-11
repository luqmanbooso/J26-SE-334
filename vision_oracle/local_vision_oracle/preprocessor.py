"""
Dynamic Aspect-Ratio Preserving Image Preprocessor & Input Sanitizer.
Grounded in METHOD-Image-Preprocessing, Wang et al. (Qwen2-VL), and EXP-04.
"""

import io
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Union, Tuple, Optional, List
from PIL import Image


@dataclass
class SahiSlice:
    """
    Uniform high-resolution image tile for Slicing Aided Hyper Inference (SAHI).
    Enables small boundary defect detection on tall mobile viewports.
    """
    image: Image.Image
    slice_index: int
    y_start_ratio: float  # [0.0, 1.0]
    y_end_ratio: float    # [0.0, 1.0]
    crop_box: Tuple[int, int, int, int]  # (x1, y1, x2, y2)

    def map_bbox_to_global(self, local_bbox: Optional[List[int]]) -> Optional[List[int]]:
        """
        Maps normalized [ymin, xmin, ymax, xmax] in [0, 1000] from slice space
        back to full-screen normalized [0, 1000] space.
        """
        if not local_bbox or len(local_bbox) != 4:
            return None
        ymin, xmin, ymax, xmax = local_bbox
        y_span = self.y_end_ratio - self.y_start_ratio
        global_ymin = round((self.y_start_ratio + (ymin / 1000.0) * y_span) * 1000)
        global_ymax = round((self.y_start_ratio + (ymax / 1000.0) * y_span) * 1000)
        return [
            max(0, min(1000, global_ymin)),
            max(0, min(1000, xmin)),
            max(0, min(1000, global_ymax)),
            max(0, min(1000, xmax)),
        ]


@dataclass
class PreprocessedImage:
    """
    Standardized, sanitized image container for Vision-Language Model ingestion.
    """
    image: Image.Image
    original_size: Tuple[int, int]   # (width, height)
    processed_size: Tuple[int, int]  # (new_width, new_height)
    scale_factor: float
    aspect_ratio: float              # width / height
    preprocess_latency_ms: float

    @property
    def width(self) -> int:
        return self.processed_size[0]

    @property
    def height(self) -> int:
        return self.processed_size[1]


class ImagePreprocessor:
    """
    Sanitizes raw mobile screenshots, strips transparency onto white matte,
    and dynamically resizes dimensions to multiples of 28 (ViT patch grid)
    while strictly preserving the screen's native aspect ratio.
    """

    def __init__(
        self,
        max_dimension: int = 1008,
        min_dimension: int = 28,
        patch_size: int = 28,
    ):
        self.max_dimension = max_dimension
        self.min_dimension = min_dimension
        self.patch_size = patch_size

    def _snap_to_patch_grid(self, dimension: int) -> int:
        """
        Snaps a dimension to the nearest positive multiple of patch_size.
        """
        snapped = max(self.patch_size, round(dimension / self.patch_size) * self.patch_size)
        return snapped

    def _sanitize_color_mode(self, img: Image.Image) -> Image.Image:
        """
        Converts RGBA, Grayscale, or Palette images to 3-channel RGB.
        Blends transparent alpha channels onto an opaque white matte.
        """
        if img.mode == "RGB":
            return img

        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            # Convert to RGBA for consistent matte compositing
            rgba_img = img.convert("RGBA")
            white_background = Image.new("RGBA", rgba_img.size, (255, 255, 255, 255))
            blended = Image.alpha_composite(white_background, rgba_img)
            return blended.convert("RGB")

        return img.convert("RGB")

    def preprocess(
        self,
        image_input: Union[str, Path, bytes, Image.Image]
    ) -> PreprocessedImage:
        """
        Loads, sanitizes, and scales an image input.
        Returns a PreprocessedImage container with latency telemetry.
        """
        start_time = time.perf_counter()

        # 1. Load image stream
        if isinstance(image_input, (str, Path)):
            path_obj = Path(image_input)
            if not path_obj.exists():
                raise FileNotFoundError(f"Screenshot file does not exist: {path_obj}")
            try:
                raw_img = Image.open(str(path_obj))
                raw_img.load()  # Force read from disk
            except Exception as e:
                raise ValueError(f"Failed to decode image file {path_obj}: {str(e)}") from e
        elif isinstance(image_input, bytes):
            if len(image_input) == 0:
                raise ValueError("Cannot preprocess empty zero-byte image buffer.")
            try:
                raw_img = Image.open(io.BytesIO(image_input))
                raw_img.load()
            except Exception as e:
                raise ValueError(f"Failed to decode image byte buffer: {str(e)}") from e
        elif isinstance(image_input, Image.Image):
            raw_img = image_input.copy()
        else:
            raise TypeError(f"Unsupported image input type: {type(image_input)}")

        orig_w, orig_h = raw_img.size
        if orig_w <= 0 or orig_h <= 0:
            raise ValueError(f"Invalid image dimensions: ({orig_w}, {orig_h})")

        aspect_ratio = round(orig_w / orig_h, 4)

        # 2. Sanitize color channels (strip alpha)
        rgb_img = self._sanitize_color_mode(raw_img)

        # 3. Dynamic scaling preserving aspect ratio
        max_side = max(orig_w, orig_h)
        if max_side > self.max_dimension:
            scale_factor = self.max_dimension / max_side
            target_w = orig_w * scale_factor
            target_h = orig_h * scale_factor
        else:
            scale_factor = 1.0
            target_w = float(orig_w)
            target_h = float(orig_h)

        # 4. Snap to ViT patch grid multiple
        new_w = self._snap_to_patch_grid(round(target_w))
        new_h = self._snap_to_patch_grid(round(target_h))

        # 5. Resample if dimensions changed
        if (new_w, new_h) != (orig_w, orig_h):
            processed_img = rgb_img.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)
        else:
            processed_img = rgb_img

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        return PreprocessedImage(
            image=processed_img,
            original_size=(orig_w, orig_h),
            processed_size=(new_w, new_h),
            scale_factor=round(scale_factor, 4),
            aspect_ratio=aspect_ratio,
            preprocess_latency_ms=elapsed_ms,
        )

    def get_sahi_slices(
        self,
        image_input: Union[str, Path, bytes, Image.Image],
    ) -> List[SahiSlice]:
        """
        Partitions mobile screen into uniform overlapping high-resolution tiles.
        Preserves native pixel density for boundary defect detection (SAHI).
        Produces:
          - Full screen (global context)
          - Top slice: 0% - 40% (header / action bar)
          - Mid slice: 30% - 75% (scrollable body)
          - Bottom slice: 65% - 100% (fixed navigation / bottom sheets)
        """
        if isinstance(image_input, (str, Path)):
            raw_img = Image.open(str(image_input))
        elif isinstance(image_input, bytes):
            raw_img = Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, Image.Image):
            raw_img = image_input.copy()
        else:
            raise TypeError(f"Unsupported image type: {type(image_input)}")

        raw_img = self._sanitize_color_mode(raw_img)
        w, h = raw_img.size

        # Only slice tall screens (height >= 1.25 * width)
        if h < 1.25 * w:
            return [SahiSlice(image=raw_img, slice_index=0, y_start_ratio=0.0, y_end_ratio=1.0, crop_box=(0, 0, w, h))]

        slice_windows = [
            (0.00, 0.45),
            (0.30, 0.75),
            (0.75, 1.00),
        ]

        slices: List[SahiSlice] = []
        for idx, (y_start, y_end) in enumerate(slice_windows):
            y1 = int(round(y_start * h))
            y2 = int(round(y_end * h))
            crop = raw_img.crop((0, y1, w, y2))
            slices.append(
                SahiSlice(
                    image=crop,
                    slice_index=idx,
                    y_start_ratio=y_start,
                    y_end_ratio=y_end,
                    crop_box=(0, y1, w, y2),
                )
            )
        return slices

