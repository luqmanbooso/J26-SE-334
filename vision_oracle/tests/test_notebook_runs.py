from local_vision_oracle.notebook_runs import box_to_pixels, iou, parse_answer


def test_parse_answer_reads_json_with_surrounding_text():
    out = parse_answer('ok {"has_defect": true, "defect_type": "component_overlap", "bounding_box": [10, 20, 30, 40]} done')
    assert out == {"type": "component_overlap", "has_defect": True, "box": [10, 20, 30, 40]}


def test_parse_answer_unreadable_is_not_an_error():
    assert parse_answer("I cannot tell")["type"] == "unreadable"
    assert parse_answer("{broken")["type"] == "unreadable"


def test_parse_answer_drops_malformed_box():
    assert parse_answer('{"has_defect": false, "defect_type": "none", "bounding_box": null}')["box"] is None
    assert parse_answer('{"defect_type": "x", "bounding_box": [1, 2]}')["box"] is None


def test_box_to_pixels_scales_from_thousandths():
    assert box_to_pixels([100, 200, 300, 600], 1000, 2000) == (200.0, 200.0, 400.0, 400.0)
    assert box_to_pixels(None, 10, 10) is None


def test_iou():
    assert iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0
    assert iou(None, [0, 0, 1, 1]) == 0.0
    assert abs(iou([0, 0, 10, 10], [0, 5, 10, 15]) - 1 / 3) < 1e-9
