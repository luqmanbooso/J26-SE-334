"""
Unit Tests for DatasetCompiler.
Tests pixel diff bbox extraction, zero-leakage splits, and ShareGPT export.
"""

import json
import numpy as np
import cv2
import pytest
from pathlib import Path
from PIL import Image

from local_vision_oracle.dataset_compiler import DatasetCompiler, CompiledSample


def test_pixel_diff_bbox_identical_images(tmp_path):
    img_a = tmp_path / "img_a.jpg"
    img_b = tmp_path / "img_b.jpg"

    # 100x100 white image
    canvas = np.full((100, 100, 3), 255, dtype=np.uint8)
    cv2.imwrite(str(img_a), canvas)
    cv2.imwrite(str(img_b), canvas)

    bbox = DatasetCompiler.extract_pixel_diff_bbox(img_a, img_b)
    # Identical images have no diff -> default safe box
    assert bbox == [100, 100, 900, 900]


def test_pixel_diff_bbox_with_injected_diff(tmp_path):
    norm_path = tmp_path / "normal.jpg"
    bug_path = tmp_path / "bug.jpg"

    # 1000x1000 canvas
    norm_img = np.full((1000, 1000, 3), 255, dtype=np.uint8)
    bug_img = norm_img.copy()

    # Inject red rectangle at y: 200..400, x: 100..500
    bug_img[200:400, 100:500] = [0, 0, 255]

    cv2.imwrite(str(norm_path), norm_img)
    cv2.imwrite(str(bug_path), bug_img)

    bbox = DatasetCompiler.extract_pixel_diff_bbox(bug_path, norm_path)
    ymin, xmin, ymax, xmax = bbox

    # Allow slight rounding tolerance (within 2 permille)
    assert abs(ymin - 200) <= 2
    assert abs(xmin - 100) <= 2
    assert abs(ymax - 400) <= 2
    assert abs(xmax - 500) <= 2


def test_compiled_sample_to_sharegpt_abs_path(tmp_path):
    sample = CompiledSample(
        screen_id="test_screen",
        image_rel_path="dataset/clean/test_screen.jpg",
        hierarchy_rel_path=None,
        has_defect=False,
        defect_type="none",
        bounding_box=None,
        affected_element_id=None,
        explanation="Clean screen.",
        source_dataset="rico_clean",
    )
    sg_rel = sample.to_sharegpt(use_absolute_path=False)
    assert sg_rel["images"] == ["dataset/clean/test_screen.jpg"]

    sg_abs = sample.to_sharegpt(use_absolute_path=True, base_parent=tmp_path)
    expected_abs = str((tmp_path / "dataset/clean/test_screen.jpg").resolve()).replace("\\", "/")
    assert sg_abs["images"] == [expected_abs]
