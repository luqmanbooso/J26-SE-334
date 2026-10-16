"""
Unit tests for DatasetScanner and CLI scan-data command.
"""

import json
import pytest
from pathlib import Path
from PIL import Image

from local_vision_oracle.dataset_scanner import (
    DatasetScanner,
    OwlEyeAuditResult,
    RicoAuditResult,
    CompleteAuditReport,
)
from local_vision_oracle.cli import build_parser


@pytest.fixture
def mock_dataset_env(tmp_path):
    """
    Creates a miniature mock dataset folder matching OwlEye and Rico directory layout.
    """
    # 1. Mock OwlEye
    owleye_base = tmp_path / "OwlEye" / "Dataset"
    bug_dir = owleye_base / "bug-aug" / "bug-aug"
    normal_dir = owleye_base / "normal-aug" / "normal-aug"
    bug_dir.mkdir(parents=True)
    normal_dir.mkdir(parents=True)

    for i in range(3):
        img = Image.new("RGB", (1080, 1920), color=(255, 0, 0))
        img.save(bug_dir / f"bug.{4001 + i}.jpg")

        img_norm = Image.new("RGB", (1080, 1920), color=(0, 255, 0))
        img_norm.save(normal_dir / f"normal.{4001 + i}.jpg")

    # 2. Mock Rico
    rico_dir = tmp_path / "rico" / "semantic_annotations"
    rico_dir.mkdir(parents=True)

    for i in [0, 1]:
        img_rico = Image.new("RGBA", (1440, 2560), color=(0, 0, 255, 255))
        img_rico.save(rico_dir / f"{i}.png")

        hierarchy = {
            "class": "com.android.internal.policy.PhoneWindow$DecorView",
            "bounds": [0, 0, 1440, 2560],
            "children": [
                {
                    "class": "android.widget.TextView",
                    "text": f"Title {i}",
                    "bounds": [100, 100, 500, 200],
                    "clickable": True,
                }
            ],
        }
        with open(rico_dir / f"{i}.json", "w", encoding="utf-8") as f:
            json.dump(hierarchy, f)

    # Add an orphaned PNG
    orphan_img = Image.new("RGBA", (1440, 2560), color=(100, 100, 100, 255))
    orphan_img.save(rico_dir / "999.png")

    return {
        "owleye_dir": owleye_base,
        "rico_dir": rico_dir,
        "out_dir": tmp_path / "results",
    }


def test_owleye_audit(mock_dataset_env):
    scanner = DatasetScanner(owleye_dir=mock_dataset_env["owleye_dir"])
    res = scanner.audit_owleye()

    assert res.bug_image_count == 3
    assert res.normal_image_count == 3
    assert res.total_images == 6
    assert res.is_balanced is True
    assert (1080, 1920) in res.sample_resolutions
    assert "RGB" in res.sample_modes
    assert res.corrupt_files_detected == 0
    assert res.verified is True


def test_rico_audit_with_orphan(mock_dataset_env):
    scanner = DatasetScanner(rico_dir=mock_dataset_env["rico_dir"])
    res = scanner.audit_rico()

    assert res.total_png_count == 3
    assert res.total_json_count == 2
    assert res.paired_count == 2
    assert res.orphaned_png_count == 1
    assert res.orphaned_json_count == 0
    assert (1440, 2560) in res.sample_resolutions
    assert "RGBA" in res.sample_modes
    assert res.sample_pruning_ratio > 0.0
    # Because of orphan, verified is False
    assert res.verified is False


def test_generate_full_report(mock_dataset_env):
    scanner = DatasetScanner(
        owleye_dir=mock_dataset_env["owleye_dir"],
        rico_dir=mock_dataset_env["rico_dir"],
    )
    report_path = mock_dataset_env["out_dir"] / "report.json"
    report = scanner.generate_full_report(output_path=report_path)

    assert report.owleye.verified is True
    assert report.rico.verified is False
    assert report.summary_verdict == "FAILED"
    assert report_path.exists()

    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["owleye"]["total_images"] == 6
    assert data["rico"]["paired_count"] == 2


def test_missing_directory_handling(tmp_path):
    scanner = DatasetScanner(
        owleye_dir=tmp_path / "non_existent_owleye",
        rico_dir=tmp_path / "non_existent_rico",
    )
    res_owleye = scanner.audit_owleye()
    assert res_owleye.total_images == 0
    assert res_owleye.verified is False

    res_rico = scanner.audit_rico()
    assert res_rico.paired_count == 0
    assert res_rico.verified is False


def test_cli_scan_data_subparser():
    parser = build_parser()
    args = parser.parse_args(["scan-data", "--output", "test_report.json"])
    assert args.subcommand == "scan-data"
    assert args.output == "test_report.json"
