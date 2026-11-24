"""Copies Rico test screens with their UI hierarchy into demo_inputs/with_layout for the layout demo.

Selection rule (fixed in advance, not by model outcome): the first test screen of each synthetic
defect type in sorted file order, plus the first two clean Rico test screens. All are in the v3 test
split, so neither adapter trained on them. Run from the repo root:
    python -m vision_oracle.local_vision_oracle.layout_demo_inputs
"""

import json
import shutil
from pathlib import Path

C3 = Path(__file__).resolve().parents[1]
MUT = C3 / "evidence" / "12_dataset_v3" / "mutated_v3" / "test"
TEST_MANIFEST = Path("D:/university/Resesarch/RD/LLaMA-Factory/data/c3v3_vision_test.json")
OUT = C3 / "demo_inputs" / "with_layout"
TYPES = ("overlap", "truncation", "missing", "null")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    screens = []
    for kind in TYPES:
        meta_path = sorted(MUT.glob(f"*_v3_{kind}.meta.json"))[0]
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        name = meta_path.name.replace(".meta.json", "")
        shutil.copy2(MUT / f"{name}.jpg", OUT / f"{name}.jpg")
        shutil.copy2(meta["source_hierarchy"], OUT / f"{name}_layout.json")
        screens.append({"image": f"{name}.jpg", "layout": f"{name}_layout.json", "expected": meta["defect_type"],
                        "gold_box": meta["bounding_box"], "note": "synthetic defect; layout is the original screen's"})
    rows = json.loads(TEST_MANIFEST.read_text(encoding="utf-8"))
    clean = sorted(r["images"][0] for r in rows
                   if "/dataset/clean/" in r["images"][0].replace("\\", "/") and '"has_defect": false' in r["messages"][-1]["content"])
    for image in clean[:2]:
        src = Path(image)
        shutil.copy2(src, OUT / src.name)
        shutil.copy2(src.with_suffix(".json"), OUT / f"{src.stem}_layout.json")
        screens.append({"image": src.name, "layout": f"{src.stem}_layout.json", "expected": "none",
                        "gold_box": None, "note": "clean screen"})
    (OUT / "screens.json").write_text(json.dumps(screens, indent=1), encoding="utf-8")
    for s in screens:
        print(s["image"], s["expected"], s["gold_box"])


if __name__ == "__main__":
    main()
