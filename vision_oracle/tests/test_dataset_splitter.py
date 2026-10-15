"""
Unit tests for DatasetSplitter and CLI split-data command.
"""

import json
import pytest
from pathlib import Path
from PIL import Image

from local_vision_oracle.dataset_splitter import (
    DatasetSplitter,
    SplitStats,
    ManifestExportSummary,
)
from local_vision_oracle.evaluation import EvaluationItem
from local_vision_oracle.cli import build_parser


@pytest.fixture
def mock_split_env(tmp_path):
    """
    Creates a mock OwlEye (100 images) and Rico (50 images) dataset environment.
    """
    owleye_base = tmp_path / "OwlEye" / "Dataset"
    bug_dir = owleye_base / "bug-aug" / "bug-aug"
    normal_dir = owleye_base / "normal-aug" / "normal-aug"
    bug_dir.mkdir(parents=True)
    normal_dir.mkdir(parents=True)

    # 50 bug + 50 normal images
    for i in range(50):
        img_b = Image.new("RGB", (1080, 1920), color=(255, 0, 0))
        img_b.save(bug_dir / f"bug.{4001 + i}.jpg")

        img_n = Image.new("RGB", (1080, 1920), color=(0, 255, 0))
        img_n.save(normal_dir / f"normal.{4001 + i}.jpg")

    # 20 Rico paired images + hierarchies
    rico_dir = tmp_path / "rico" / "semantic_annotations"
    rico_dir.mkdir(parents=True)
    for i in range(20):
        img_r = Image.new("RGBA", (1440, 2560), color=(0, 0, 255, 255))
        img_r.save(rico_dir / f"{i}.png")
        with open(rico_dir / f"{i}.json", "w", encoding="utf-8") as f:
            json.dump({"class": "android.view.View", "bounds": [0, 0, 1440, 2560]}, f)

    return {
        "owleye_dir": owleye_base,
        "rico_dir": rico_dir,
        "out_dir": tmp_path / "manifests",
    }


def test_owleye_stratified_split(mock_split_env):
    splitter = DatasetSplitter(
        owleye_dir=mock_split_env["owleye_dir"],
        rico_dir=mock_split_env["rico_dir"],
        seed=42,
    )
    splits = splitter.split_owleye(train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)

    # 50 bugs + 50 normal = 100 images
    # Train: 35 bugs + 35 normal = 70 items
    # Val: 7 bugs + 7 normal = 14 items (int(50 * 0.15) = 7)
    # Test: remaining = 8 bugs + 8 normal = 16 items
    train = splits["train"]
    val = splits["val"]
    test = splits["test"]

    assert len(train) == 70
    assert len(val) == 14
    assert len(test) == 16

    # Verify 50/50 balance in each partition
    assert sum(1 for x in train if x.expected_has_defect) == 35
    assert sum(1 for x in val if x.expected_has_defect) == 7
    assert sum(1 for x in test if x.expected_has_defect) == 8

    # Verify ZERO DATA LEAKAGE (disjoint sets)
    train_ids = set(x.screen_id for x in train)
    val_ids = set(x.screen_id for x in val)
    test_ids = set(x.screen_id for x in test)

    assert len(train_ids & val_ids) == 0
    assert len(train_ids & test_ids) == 0
    assert len(val_ids & test_ids) == 0


def test_seed_determinism(mock_split_env):
    s1 = DatasetSplitter(owleye_dir=mock_split_env["owleye_dir"], seed=42)
    s2 = DatasetSplitter(owleye_dir=mock_split_env["owleye_dir"], seed=42)

    res1 = s1.split_owleye()
    res2 = s2.split_owleye()

    assert [x.screen_id for x in res1["train"]] == [x.screen_id for x in res2["train"]]
    assert [x.screen_id for x in res1["test"]] == [x.screen_id for x in res2["test"]]


def test_rico_subset_extraction(mock_split_env):
    splitter = DatasetSplitter(
        rico_dir=mock_split_env["rico_dir"],
        seed=42,
    )
    calib, clean_eval = splitter.extract_rico_subsets(calibration_count=8, clean_eval_count=10)

    assert len(calib) == 8
    assert len(clean_eval) == 10

    # Ensure zero overlap
    calib_ids = set(x.screen_id for x in calib)
    eval_ids = set(x.screen_id for x in clean_eval)
    assert len(calib_ids & eval_ids) == 0

    # Verify hierarchy path is set
    assert calib[0].hierarchy_path is not None
    assert Path(calib[0].hierarchy_path).exists()


def test_export_all_manifests(mock_split_env):
    splitter = DatasetSplitter(
        owleye_dir=mock_split_env["owleye_dir"],
        rico_dir=mock_split_env["rico_dir"],
        seed=42,
    )
    summary = splitter.export_all_manifests(
        output_dir=mock_split_env["out_dir"],
        rico_calib_count=5,
        rico_clean_eval_count=5,
    )

    assert summary.leakage_detected is False
    assert (mock_split_env["out_dir"] / "owleye_train.json").exists()
    assert (mock_split_env["out_dir"] / "owleye_val.json").exists()
    assert (mock_split_env["out_dir"] / "owleye_test.json").exists()
    assert (mock_split_env["out_dir"] / "rico_calibration_5.json").exists()
    assert (mock_split_env["out_dir"] / "rico_clean_eval_5.json").exists()
    assert (mock_split_env["out_dir"] / "manifest_summary.json").exists()

    # Load exported test manifest and validate pydantic compatibility
    with open(mock_split_env["out_dir"] / "owleye_test.json", "r", encoding="utf-8") as f:
        raw = json.load(f)
    items = [EvaluationItem(**d) for d in raw]
    assert len(items) == summary.test_stats.total_count


def test_cli_split_data_subparser():
    parser = build_parser()
    args = parser.parse_args(["split-data", "--output-dir", "custom/manifests", "--seed", "123"])
    assert args.subcommand == "split-data"
    assert args.output_dir == "custom/manifests"
    assert args.seed == 123
