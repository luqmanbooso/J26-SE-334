"""
Unit tests for Dataset Deduplication & Perceptual Sanitization Suite (Pillar 2).
"""

import json
import pytest
from pathlib import Path
from typing import Tuple
from PIL import Image

from local_vision_oracle.deduplicator import (
    compute_sha256,
    compute_dhash,
    hamming_distance,
    DatasetDeduplicator,
    DuplicatePair,
    DeduplicationReport,
)
from local_vision_oracle.cli import build_parser


@pytest.fixture
def sample_images(tmp_path: Path) -> Tuple[Path, Path, Path, Path]:
    """
    Creates:
    - img1: base gradient image
    - img2: identical copy of img1 (exact duplicate)
    - img3: near-duplicate with 1 pixel changed
    - img4: completely inverted/different image
    """
    img1_path = tmp_path / "img1.png"
    img2_path = tmp_path / "img2.png"
    img3_path = tmp_path / "img3.png"
    img4_path = tmp_path / "img4.png"

    # Base 64x64 image: left half white (255), right half black (0)
    im1 = Image.new("L", (64, 64), color=0)
    for x in range(32):
        for y in range(64):
            im1.putpixel((x, y), 255)
    im1.save(img1_path)

    # Identical copy
    im1.save(img2_path)

    # Near-duplicate: same pattern with tiny 1-pixel alteration at (0, 0)
    im3 = im1.copy()
    im3.putpixel((0, 0), 200)
    im3.save(img3_path)

    # Inverted pattern: left half black (0), right half white (255)
    im4 = Image.new("L", (64, 64), color=255)
    for x in range(32):
        for y in range(64):
            im4.putpixel((x, y), 0)
    im4.save(img4_path)

    return img1_path, img2_path, img3_path, img4_path


def test_sha256_exact_match(sample_images):
    img1, img2, img3, img4 = sample_images
    assert compute_sha256(img1) == compute_sha256(img2)
    assert compute_sha256(img1) != compute_sha256(img3)
    assert compute_sha256(img1) != compute_sha256(img4)


def test_dhash_and_hamming_distance(sample_images):
    img1, img2, img3, img4 = sample_images
    h1 = compute_dhash(img1)
    h2 = compute_dhash(img2)
    h3 = compute_dhash(img3)
    h4 = compute_dhash(img4)

    assert len(h1) == 16  # 64 bits = 16 hex chars
    assert h1 == h2
    assert hamming_distance(h1, h2) == 0

    # Near duplicate should have very small Hamming distance (<= 2)
    dist_near = hamming_distance(h1, h3)
    assert dist_near <= 2

    # Different image should have higher distance
    dist_diff = hamming_distance(h1, h4)
    assert dist_diff > 3


def test_deduplicator_scans_and_filters_duplicates(sample_images):
    img1, img2, img3, img4 = sample_images
    dedup = DatasetDeduplicator(hamming_threshold=3)

    report, unique = dedup.scan_file_list([img1, img2, img3, img4], dataset_name="TestDataset")
    assert report.total_files_scanned == 4
    # img2 is exact duplicate of img1
    # img3 is perceptual duplicate of img1
    # img4 is distinct
    # Thus unique retained should be 2 (img1 and img4)
    assert report.unique_files_retained == 2
    assert report.exact_duplicates_found == 1
    assert report.perceptual_duplicates_found == 1
    assert report.total_duplicates == 2
    assert report.duplicate_rate_pct == 50.0
    assert len(unique) == 2


def test_manifest_deduplication(tmp_path: Path, sample_images):
    img1, img2, img3, img4 = sample_images
    manifest_file = tmp_path / "test_manifest.json"
    data = [
        {"screen_id": "s1", "image_path": str(img1)},
        {"screen_id": "s2", "image_path": str(img2)},
        {"screen_id": "s3", "image_path": str(img3)},
        {"screen_id": "s4", "image_path": str(img4)},
    ]
    manifest_file.write_text(json.dumps(data), encoding="utf-8")

    dedup = DatasetDeduplicator(hamming_threshold=3)
    report, sanitized = dedup.scan_manifest_json(manifest_file, image_key="image_path")

    assert report.unique_files_retained == 2
    assert len(sanitized) == 2
    retained_ids = [item["screen_id"] for item in sanitized]
    assert retained_ids == ["s1", "s4"]


def test_report_ascii_and_dict(sample_images):
    img1, img2, _, _ = sample_images
    dedup = DatasetDeduplicator()
    report, _ = dedup.scan_file_list([img1, img2], dataset_name="Demo")

    ascii_str = report.to_ascii_table()
    assert "DATASET SANITIZATION & DEDUPLICATION REPORT" in ascii_str
    assert "Exact SHA-256 Duplicates" in ascii_str

    rep_dict = report.to_dict()
    assert rep_dict["dataset_name"] == "Demo"
    assert rep_dict["exact_duplicates_found"] == 1


def test_cli_deduplicate_subparser():
    parser = build_parser()
    args = parser.parse_args([
        "deduplicate",
        "--input", "results/manifests/owleye_test.json",
        "--threshold", "2",
        "--output", "results/test_dedup.json"
    ])
    assert args.input == "results/manifests/owleye_test.json"
    assert args.threshold == 2
    assert args.output == "results/test_dedup.json"
