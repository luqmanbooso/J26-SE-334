import json

import pytest

from local_vision_oracle.reproducibility import compare_e2e, compare_scores, main, screen_key


def test_screen_key_maps_moved_owleye_folder_and_case():
    assert screen_key("C:/Games/OwlEye/Dataset/bug.1.jpg") == screen_key("D:\\Dataset\\OwlEye\\Dataset\\bug.1.jpg")


def test_identical_runs_agree_fully():
    recs = [{"image": "a.jpg", "p_defect": 0.2}, {"image": "b.jpg", "p_defect": 0.9}]
    r = compare_scores(recs, recs, threshold=0.5)
    assert r["max_abs_diff"] == 0 and r["verdict_agreement"] == 1 and r["identical_scores"] == 2


def test_flip_across_threshold_is_counted():
    a = [{"image": "a.jpg", "p_defect": 0.49}, {"image": "b.jpg", "p_defect": 0.9}]
    b = [{"image": "a.jpg", "p_defect": 0.51}, {"image": "b.jpg", "p_defect": 0.9}]
    r = compare_scores(a, b, threshold=0.5)
    assert r["verdict_flips"] == ["a.jpg"] and r["verdict_agreement"] == 0.5
    assert r["max_abs_diff"] == pytest.approx(0.02)


def test_unmatched_screens_are_reported_not_compared():
    r = compare_scores([{"image": "a.jpg", "p_defect": 0.1}, {"image": "x.jpg", "p_defect": 0.1}],
                       [{"image": "a.jpg", "p_defect": 0.1}], threshold=0.5)
    assert r["screens"] == 1 and r["only_in_first"] == 1


def test_no_overlap_raises():
    with pytest.raises(ValueError):
        compare_scores([{"image": "a.jpg", "p_defect": 0.1}], [{"image": "b.jpg", "p_defect": 0.1}], 0.5)


def test_e2e_agreement_fields():
    a = [{"image": "a.jpg", "raw": "x", "pred_has": True, "pred_type": "t", "pred_box": [1, 2, 3, 4]}]
    b = [{"image": "a.jpg", "raw": "y", "pred_has": True, "pred_type": "t", "pred_box": [1, 2, 3, 5]}]
    r = compare_e2e(a, b)
    assert r["verdict_agreement"] == 1 and r["type_agreement"] == 1
    assert r["box_identical"] == 0 and r["raw_text_identical"] == 0 and r["differing_screens"] == ["a.jpg"]


def test_main_writes_report(tmp_path):
    f = tmp_path / "s.json"
    f.write_text(json.dumps({"records": [{"image": "a.jpg", "p_defect": 0.3}]}))
    out = tmp_path / "r.json"
    main(["--score", str(f), str(f), "--threshold", "0.5", "--output", str(out)])
    assert json.loads(out.read_text())["score"]["verdict_agreement"] == 1
