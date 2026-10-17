"""
Unit tests for Synthetic Mutator and Dataset Compiler.
Validates:
  1. Extracting leaf UI nodes from Rico JSON hierarchies.
  2. Component overlap mutation logic and bounding box normalization.
  3. Text truncation and missing component mutations.
  4. Bounding boxes strictly within [0, 1000] and properly ordered [ymin, xmin, ymax, xmax].
  5. ShareGPT training format emission.
"""

import json
from pathlib import Path
from PIL import Image
import pytest

from local_vision_oracle.synthetic_mutator import SyntheticMutator, UINode
from local_vision_oracle.dataset_compiler import CompiledSample
from local_vision_oracle.schemas import DefectType


@pytest.fixture
def mock_rico_hierarchy(tmp_path: Path):
    h_data = {
        "activity": {
            "root": {
                "class": "android.widget.FrameLayout",
                "bounds": [0, 0, 1440, 2560],
                "children": [
                    {
                        "class": "android.widget.Button",
                        "resource-id": "com.test:id/btn_submit",
                        "bounds": [100, 200, 500, 400],
                        "text": "Submit",
                        "clickable": True,
                        "children": [],
                    },
                    {
                        "class": "android.widget.TextView",
                        "resource-id": "com.test:id/txt_desc",
                        "bounds": [100, 450, 800, 600],
                        "text": "This is a detailed description label.",
                        "clickable": False,
                        "children": [],
                    },
                    {
                        "class": "android.widget.ImageView",
                        "resource-id": "com.test:id/img_avatar",
                        "bounds": [100, 650, 400, 950],
                        "clickable": False,
                        "children": [],
                    },
                ],
            }
        }
    }
    h_file = tmp_path / "test_screen.json"
    with open(h_file, "w", encoding="utf-8") as f:
        json.dump(h_data, f)
    return h_file


@pytest.fixture
def mock_screen_image(tmp_path: Path):
    img = Image.new("RGB", (1440, 2560), color=(240, 240, 240))
    img_file = tmp_path / "test_screen.jpg"
    img.save(img_file)
    return img_file


def test_leaf_node_extraction(mock_rico_hierarchy: Path):
    with open(mock_rico_hierarchy, "r", encoding="utf-8") as f:
        data = json.load(f)
    nodes = SyntheticMutator._extract_leaf_nodes(data)
    assert len(nodes) == 3
    assert any(n.class_name == "Button" for n in nodes)
    assert any(n.class_name == "TextView" for n in nodes)
    assert any(n.class_name == "ImageView" for n in nodes)


def test_bounding_box_normalization():
    box = (144, 256, 720, 1280)
    norm = SyntheticMutator._normalize_box(box, 1440, 2560)
    assert len(norm) == 4
    ymin, xmin, ymax, xmax = norm
    assert 0 <= ymin <= 1000
    assert 0 <= xmin <= 1000
    assert ymin < ymax
    assert xmin < xmax
    assert ymin == 100
    assert xmin == 100
    assert ymax == 500
    assert xmax == 500


def test_mutate_component_overlap(mock_screen_image: Path, mock_rico_hierarchy: Path):
    mutator = SyntheticMutator(seed=42)
    res = mutator.mutate(mock_screen_image, mock_rico_hierarchy, mutation_type="overlap")
    assert res is not None
    assert res.defect_type == DefectType.COMPONENT_OVERLAP
    assert len(res.bounding_box) == 4
    assert res.bounding_box[0] < res.bounding_box[2]
    assert res.bounding_box[1] < res.bounding_box[3]
    assert res.affected_element_id is not None


def test_mutate_text_truncation(mock_screen_image: Path, mock_rico_hierarchy: Path):
    mutator = SyntheticMutator(seed=42)
    res = mutator.mutate(mock_screen_image, mock_rico_hierarchy, mutation_type="truncation")
    assert res is not None
    assert res.defect_type == DefectType.TEXT_TRUNCATION
    assert len(res.bounding_box) == 4
    assert "truncation" in res.explanation.lower()


def test_mutate_missing_component(mock_screen_image: Path, mock_rico_hierarchy: Path):
    mutator = SyntheticMutator(seed=42)
    res = mutator.mutate(mock_screen_image, mock_rico_hierarchy, mutation_type="missing")
    assert res is not None
    assert res.defect_type == DefectType.MISSING_COMPONENT
    assert len(res.bounding_box) == 4
    assert "missing" in res.explanation.lower()


def test_compiled_sample_to_sharegpt():
    sample = CompiledSample(
        screen_id="test_001",
        image_rel_path="dataset/clean/test_001.jpg",
        hierarchy_rel_path="dataset/clean/test_001.json",
        has_defect=True,
        defect_type="component_overlap",
        bounding_box=[100, 100, 500, 500],
        affected_element_id="com.test:id/btn",
        explanation="Overlap detected.",
        source_dataset="rico_mutated",
    )
    sg = sample.to_sharegpt()
    assert "messages" in sg
    assert len(sg["messages"]) == 2
    assert sg["messages"][0]["role"] == "user"
    assert sg["messages"][1]["role"] == "assistant"
    ans = json.loads(sg["messages"][1]["content"])
    assert ans["has_defect"] is True
    assert ans["bounding_box"] == [100, 100, 500, 500]
    assert sg["images"] == ["dataset/clean/test_001.jpg"]
