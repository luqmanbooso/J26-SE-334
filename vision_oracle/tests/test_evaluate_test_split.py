"""
Unit Tests for Test Dataset Loader and Evaluation Helpers.
"""

import io
import json
import zipfile
import pytest
from pathlib import Path
from PIL import Image

from local_vision_oracle.evaluate_test_split import (
    TestDatasetLoader,
    find_default_weights_dir,
    find_default_dataset_path,
    find_default_base_model,
)


def test_test_dataset_loader_zip(tmp_path):
    # Create mock zip archive with test.json and image
    zip_path = tmp_path / "mock_dataset.zip"
    img = Image.new("RGB", (200, 200), color=(255, 0, 0))
    img_bytes_io = io.BytesIO()
    img.save(img_bytes_io, format="JPEG")

    mock_manifest = [
        {
            "messages": [
                {"role": "user", "content": "<image>Analyze this mobile screen."},
                {"role": "assistant", "content": json.dumps({"has_defect": False, "defect_type": "none"})}
            ],
            "images": ["images/test_01.jpg"]
        }
    ]

    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("test.json", json.dumps(mock_manifest))
        z.writestr("images/test_01.jpg", img_bytes_io.getvalue())

    loader = TestDatasetLoader(str(zip_path))
    assert len(loader) == 1

    sample, loaded_img = loader.get_sample(0)
    assert sample["images"][0] == "images/test_01.jpg"
    assert loaded_img.size == (200, 200)
    loader.close()


def test_test_dataset_loader_json(tmp_path):
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img_path = img_dir / "test_02.jpg"
    Image.new("RGB", (100, 100), color=(0, 255, 0)).save(img_path)

    json_path = tmp_path / "test.json"
    mock_manifest = [
        {
            "messages": [
                {"role": "user", "content": "<image>Check for errors."},
                {"role": "assistant", "content": json.dumps({"has_defect": True, "defect_type": "text_truncation"})}
            ],
            "images": [str(img_path)]
        }
    ]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(mock_manifest, f)

    loader = TestDatasetLoader(str(json_path))
    assert len(loader) == 1
    sample, loaded_img = loader.get_sample(0)
    assert loaded_img.size == (100, 100)
    loader.close()


def test_find_defaults():
    # Should resolve known research paths without throwing
    dataset = find_default_dataset_path()
    assert dataset.exists()

    base_model = find_default_base_model()
    assert base_model is not None
