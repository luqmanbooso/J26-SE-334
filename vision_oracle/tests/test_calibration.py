"""
Unit tests for AWQ Calibration and Memory Profiler.
"""

import json
import pytest
from pathlib import Path
from PIL import Image

from local_vision_oracle.calibration import (
    AWQConfig,
    MemoryProfile,
    AWQCalibrator,
    AWQCalibrationSummary,
)
from local_vision_oracle.cli import build_parser


@pytest.fixture
def mock_calib_env(tmp_path):
    """
    Creates a temporary manifest and dummy Rico screens for calibration testing.
    """
    data_dir = tmp_path / "rico"
    data_dir.mkdir(parents=True)

    manifest_items = []
    for i in range(5):
        img_p = data_dir / f"{i}.png"
        json_p = data_dir / f"{i}.json"

        img = Image.new("RGBA", (1440, 2560), color=(10, 20, 30, 255))
        img.save(img_p)

        hierarchy = {
            "class": "com.android.internal.policy.PhoneWindow$DecorView",
            "bounds": [0, 0, 1440, 2560],
            "children": [
                {
                    "class": "android.widget.Button",
                    "text": f"Action Button {i}",
                    "bounds": [100, 200, 800, 350],
                    "clickable": True,
                }
            ],
        }
        with open(json_p, "w", encoding="utf-8") as f:
            json.dump(hierarchy, f)

        manifest_items.append({
            "screen_id": str(i),
            "image_path": img_p.as_posix(),
            "hierarchy_path": json_p.as_posix(),
            "expected_has_defect": False,
            "expected_defect_type": "none",
        })

    manifest_path = tmp_path / "test_calib_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_items, f)

    return {
        "manifest_path": manifest_path,
        "out_summary": tmp_path / "awq_summary.json",
    }


def test_memory_profile_calculation():
    # 2B parameter Qwen2-VL model
    calibrator_2b = AWQCalibrator(base_params_billion=2.0)
    profile_2b = calibrator_2b.compute_memory_profile()

    assert profile_2b.fp16_weight_gb == 4.0
    assert profile_2b.int4_awq_weight_gb == 1.15
    assert profile_2b.total_peak_vram_gb < 3.0
    assert profile_2b.compression_ratio > 3.0
    assert profile_2b.fits_4gb_vram is True

    # 7B parameter model (requires >6GB)
    calibrator_7b = AWQCalibrator(base_params_billion=7.0)
    profile_7b = calibrator_7b.compute_memory_profile()
    assert profile_7b.fp16_weight_gb == 14.0
    assert profile_7b.fits_4gb_vram is False


def test_prepare_calibration_batch(mock_calib_env):
    calibrator = AWQCalibrator()
    batch = calibrator.prepare_calibration_batch(
        manifest_path=mock_calib_env["manifest_path"],
        max_samples=5,
    )

    assert len(batch) == 5
    assert batch[0]["screen_id"] == "0"
    assert "Action Button 0" in batch[0]["hierarchy_tokens"]
    assert batch[0]["token_count"] > 0


def test_calibrate_and_export_summary(mock_calib_env):
    calibrator = AWQCalibrator(base_params_billion=2.0)
    summary = calibrator.calibrate_and_export_summary(
        manifest_path=mock_calib_env["manifest_path"],
        output_path=mock_calib_env["out_summary"],
        max_samples=5,
    )

    assert summary.calibration_status == "CALIBRATED"
    assert summary.num_samples_calibrated == 5
    assert summary.memory_profile.fits_4gb_vram is True
    assert mock_calib_env["out_summary"].exists()

    with open(mock_calib_env["out_summary"], "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["calibration_status"] == "CALIBRATED"
    assert data["memory_profile"]["compression_ratio"] > 3.0


def test_cli_calibrate_subparser():
    parser = build_parser()
    args = parser.parse_args([
        "calibrate",
        "--manifest", "custom_manifest.json",
        "--output", "custom_out.json",
        "--params-b", "2.0",
        "--bits", "4",
        "--samples", "100",
    ])
    assert args.subcommand == "calibrate"
    assert args.manifest == "custom_manifest.json"
    assert args.params_b == 2.0
    assert args.bits == 4
