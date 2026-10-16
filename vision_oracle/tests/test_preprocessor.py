"""
Unit tests for ImagePreprocessor.
Verifies aspect-ratio preservation, patch-grid alignment (multiple of 28), alpha stripping, and latency telemetry.
"""

import pytest
from PIL import Image
from local_vision_oracle.preprocessor import ImagePreprocessor, PreprocessedImage


def test_dynamic_scaling_preserves_aspect_ratio_and_snaps_to_28():
    preprocessor = ImagePreprocessor(max_dimension=1008, patch_size=28)
    # Simulate high-res 1080x2400 Android screenshot (tall 20:9 ratio)
    raw_img = Image.new("RGB", (1080, 2400), color=(100, 150, 200))

    result = preprocessor.preprocess(raw_img)

    assert isinstance(result, PreprocessedImage)
    assert result.original_size == (1080, 2400)
    w_new, h_new = result.processed_size

    # ViT constraint: Dimensions must be exact multiples of 28
    assert w_new % 28 == 0
    assert h_new % 28 == 0
    assert max(w_new, h_new) <= 1008

    # Aspect ratio check: 1080 / 2400 = 0.45
    # Processed ratio must be within 3% of original ratio
    orig_ratio = 1080 / 2400
    proc_ratio = w_new / h_new
    assert abs(proc_ratio - orig_ratio) < 0.03


def test_rgba_compositing_onto_white_matte():
    preprocessor = ImagePreprocessor()
    # Create RGBA image with semi-transparent red block
    rgba_img = Image.new("RGBA", (400, 800), color=(255, 0, 0, 128))

    result = preprocessor.preprocess(rgba_img)

    # Must be sanitized to 3-channel RGB
    assert result.image.mode == "RGB"
    # Transparent red on white should composite to pinkish/light-red (not black void)
    pixel = result.image.getpixel((10, 10))
    assert pixel[0] > 200  # High red
    assert pixel[1] > 100  # White blended green
    assert pixel[2] > 100  # White blended blue


def test_grayscale_and_palette_conversion():
    preprocessor = ImagePreprocessor()
    # 1-channel grayscale
    gray_img = Image.new("L", (300, 600), color=128)
    res_gray = preprocessor.preprocess(gray_img)
    assert res_gray.image.mode == "RGB"

    # Palette image
    pal_img = Image.new("P", (300, 600))
    res_pal = preprocessor.preprocess(pal_img)
    assert res_pal.image.mode == "RGB"


def test_preprocess_latency_telemetry():
    preprocessor = ImagePreprocessor()
    img = Image.new("RGB", (1080, 1920), color=(50, 50, 50))
    result = preprocessor.preprocess(img)

    assert result.preprocess_latency_ms > 0.0
    # Must comfortably meet Proposal NFR SLA (<200 ms)
    assert result.preprocess_latency_ms < 200.0


def test_error_handling_invalid_inputs():
    preprocessor = ImagePreprocessor()

    # Non-existent file
    with pytest.raises(FileNotFoundError):
        preprocessor.preprocess("non_existent_screen_12345.png")

    # Empty bytes
    with pytest.raises(ValueError):
        preprocessor.preprocess(b"")

    # Corrupted bytes
    with pytest.raises(ValueError):
        preprocessor.preprocess(b"corrupted_header_data_not_an_image")


def test_sahi_slices_tall_screen():
    preprocessor = ImagePreprocessor()
    tall_img = Image.new("RGB", (720, 1600), color=(255, 255, 255))
    slices = preprocessor.get_sahi_slices(tall_img)

    assert len(slices) == 3
    assert slices[0].y_start_ratio == 0.0
    assert slices[2].y_end_ratio == 1.0

    # Test coordinate mapping from bottom slice back to global screen
    bot_slice = slices[2]  # y in [0.75, 1.00]
    local_bbox = [0, 50, 500, 950]  # top half of bottom slice
    global_bbox = bot_slice.map_bbox_to_global(local_bbox)

    assert global_bbox is not None
    assert global_bbox[0] == 750  # 750 + 0 * 250
    assert global_bbox[1] == 50
    assert global_bbox[2] == 875  # 750 + 0.5 * 250
    assert global_bbox[3] == 950


