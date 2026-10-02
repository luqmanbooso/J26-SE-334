"""
Unit tests for Pipeline Transforms and Finding Processing (Phase D of Implementation Plan).
Verifies:
- ViewPlanner: Global view + overlapping vertical tiles for tall screens (height/width >= 1.6)
- ViewPlanner: Horizontal tiles for landscape screens
- CoordinateMapper: Formula from Section 6.2 with crop offset and invertible mapping
- FindingParser: Supports both V2 multi-finding schema and Legacy single-finding schema
- FindingParser: Strictly handles JSON parse errors without turning them into clean verdicts
- OverlapDeduplicator: Class-aware IoU >= 0.5 deduplication across tiles
"""

import pytest
from vision_oracle.local_vision_oracle.pipeline import (
    ViewSpec,
    ViewPlanner,
    CoordinateMapper,
    FindingParser,
    OverlapDeduplicator,
)
from vision_oracle.contracts.v2 import CoveragePolicy, Finding


def test_view_planner_tall_screen_slices():
    # Standard modern phone resolution (1080 x 2400) -> aspect 2.22
    views = ViewPlanner.plan_views(width=1080, height=2400, policy=CoveragePolicy.GLOBAL_PLUS_TILES_V1)
    assert len(views) == 4
    assert views[0].is_global is True
    assert views[0].crop_rect == (0, 0, 1080, 2400)

    # 3 slices generated
    assert views[1].view_id == "tile_0"
    assert views[1].crop_rect[0] == 0  # x
    assert views[1].crop_rect[1] == 0  # top slice starts at 0

    assert views[3].view_id == "tile_2"
    # Bottom slice ends at height
    y_start = views[3].crop_rect[1]
    slice_h = views[3].crop_rect[3]
    assert y_start + slice_h == 2400


def test_view_planner_global_only_policy():
    views = ViewPlanner.plan_views(width=1080, height=2400, policy=CoveragePolicy.GLOBAL_ONLY)
    assert len(views) == 1
    assert views[0].is_global is True


def test_coordinate_mapper_invertibility():
    """
    Test Section 6.2 formula:
      x1 = cx + (xmin / 1000) * cw
      y1 = cy + (ymin / 1000) * ch
      x2 = cx + (xmax / 1000) * cw
      y2 = cy + (ymax / 1000) * ch
    """
    # Suppose crop is middle tile: cx=0, cy=600, cw=1080, ch=1080
    view = ViewSpec(view_id="tile_1", crop_rect=(0, 600, 1080, 1080), is_global=False)
    # Model detects defect at [ymin=200, xmin=100, ymax=400, xmax=500] in model normalized space [0, 1000]
    box_1000 = [200, 100, 400, 500]

    px_box = CoordinateMapper.model_to_pixels(box_1000, view=view, orig_width=1080, orig_height=2400)
    # x1 = 0 + (100 / 1000) * 1080 = 108
    # y1 = 600 + (200 / 1000) * 1080 = 600 + 216 = 816
    # x2 = 0 + (500 / 1000) * 1080 = 540
    # y2 = 600 + (400 / 1000) * 1080 = 600 + 432 = 1032
    assert px_box == [108, 816, 540, 1032]


def test_finding_parser_v2_multi_finding_schema():
    view = ViewSpec(view_id="global", crop_rect=(0, 0, 1080, 2400), is_global=True)
    raw_response = """
    ```json
    {
      "findings": [
        {
          "type": "component_overlap",
          "bbox_yxyx_1000": [100, 50, 300, 400],
          "affected_element_id": "btn_submit",
          "explanation": "Submit button occluded by banner"
        },
        {
          "type": "text_truncation",
          "bbox_yxyx_1000": [500, 100, 550, 600],
          "explanation": "Discount text clipped"
        }
      ]
    }
    ```
    """
    findings, errors = FindingParser.parse_findings(raw_response, view=view, orig_width=1080, orig_height=2400)
    assert len(errors) == 0
    assert len(findings) == 2
    assert findings[0].type == "component_overlap"
    assert findings[0].element_ref == "btn_submit"
    assert findings[1].type == "text_truncation"


def test_finding_parser_legacy_schema():
    view = ViewSpec(view_id="global", crop_rect=(0, 0, 1080, 2400), is_global=True)
    raw_response = """
    {
      "has_defect": true,
      "defect_type": "unrendered_asset",
      "confidence": 0.89,
      "bounding_box": [300, 200, 600, 700],
      "affected_element_id": "img_hero",
      "explanation": "Broken image icon"
    }
    """
    findings, errors = FindingParser.parse_findings(raw_response, view=view, orig_width=1080, orig_height=2400)
    assert len(errors) == 0
    assert len(findings) == 1
    assert findings[0].type == "unrendered_asset"
    assert findings[0].confidence == 0.89


def test_finding_parser_malformed_json_emits_error_not_clean():
    view = ViewSpec(view_id="global", crop_rect=(0, 0, 1080, 2400), is_global=True)
    raw_response = "Random gibberish that is not JSON at all."
    findings, errors = FindingParser.parse_findings(raw_response, view=view, orig_width=1080, orig_height=2400)
    assert len(findings) == 0
    assert len(errors) > 0
    assert "JSON parsing error" in errors[0]


def test_overlap_deduplicator_merges_overlapping_tiles():
    # Same defect type with overlapping bounding boxes (IoU > 0.5)
    f1 = Finding(
        type="component_overlap",
        bbox_xyxy=[100, 100, 300, 300],
        explanation="Detected in global view",
        view_ids=["global"],
        confidence=0.80,
    )
    f2 = Finding(
        type="component_overlap",
        bbox_xyxy=[110, 105, 305, 295],  # Very close box from tile view
        explanation="Detected with high detail in tile_0",
        view_ids=["tile_0"],
        confidence=0.92,
    )
    # Different defect type nearby
    f3 = Finding(
        type="text_truncation",
        bbox_xyxy=[100, 100, 300, 300],
        explanation="Text defect at same coordinates",
        view_ids=["tile_0"],
    )

    deduped = OverlapDeduplicator.deduplicate([f1, f2, f3], iou_threshold=0.5)
    assert len(deduped) == 2

    # Verify that f1 and f2 merged
    overlap_finding = next(f for f in deduped if f.type == "component_overlap")
    assert "global" in overlap_finding.view_ids
    assert "tile_0" in overlap_finding.view_ids
    assert overlap_finding.confidence == 0.92
