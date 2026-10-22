"""Copies the demo screens into one folder and verifies each through the app's service call.

Run from the repo root:  python -m vision_oracle.local_vision_oracle.pp1_demo_inputs
Every screen is from the held-out test split. Results go to demo_inputs/RESULTS.md.
"""

import json
import shutil
from pathlib import Path

import vision_oracle.services.oracle_service as svc_mod

C3 = Path(__file__).resolve().parents[1]
OUT = C3 / "demo_inputs"
BUG, OK = "C:/Games/OwlEye/Dataset/bug-aug/bug-aug/", "C:/Games/OwlEye/Dataset/normal-aug/normal-aug/"
MUT, CLEAN = "D:/university/Resesarch/dataset/mutated_bugs/", "D:/university/Resesarch/dataset/clean/"

# (file name in demo folder, source image, layout file or None, expected verdict, expected type, what to point at)
DEMO = [
    ("01_overlap_team_names.jpg", BUG + "bug.4031.jpg", None, "defect", "component_overlap", "team names and labels drawn over each other"),
    ("02_overlap_title.jpg", BUG + "bug.4007.jpg", None, "defect", "component_overlap", "'Classes' title drawn over the description"),
    ("03_null_text.jpg", BUG + "bug.4418.jpg", None, "defect", "data_binding_null", "result shows the word 'null'"),
    ("04_missing_icons.jpg", BUG + "bug.4037.jpg", None, "defect", "missing_component", "category icons not rendered"),
    ("05_missing_widget_inserted.jpg", MUT + "11083_mut_missing.jpg", CLEAN + "11083.json", "defect", "missing_component", "grey placeholder replaces a widget"),
    ("06_overlap_inserted.jpg", MUT + "13067_mut_overlap.jpg", CLEAN + "13067.json", "defect", "component_overlap", "widget pasted over another"),
    ("07_clean_owleye.jpg", OK + "normal.4234.jpg", None, "clean", "none", "normal screen, not flagged"),
    ("08_clean_rico.jpg", CLEAN + "14229.jpg", None, "clean", "none", "normal screen, not flagged"),
    ("09_known_miss_truncation.jpg", BUG + "bug.4296.jpg", None, "defect", "text_truncation", "thin clipped text: the model misses it (honest limitation)"),
]


def main():
    OUT.mkdir(exist_ok=True)
    svc = svc_mod.get_oracle_service()
    rows = []
    for name, src, layout, exp_verdict, exp_type, point in DEMO:
        shutil.copy2(src, OUT / name)
        lay_name = None
        if layout:
            lay_name = name.rsplit(".", 1)[0] + "_layout.json"
            shutil.copy2(layout, OUT / lay_name)
        res = svc.evaluate(image_input=str(OUT / name), session_id="pp1_demo",
                           raw_hierarchy=Path(layout).read_text(encoding="utf-8") if layout else None, enable_sahi=False)
        v = res["verdict_v2"]
        dec = v["decision"].value if hasattr(v["decision"], "value") else v["decision"]
        f = v["findings"][0] if v["findings"] else {}
        got = "defect" if dec == "defect_detected" else ("clean" if dec == "no_defect_detected" else "inconclusive")
        got_type = f.get("type", "none")
        rows.append({"file": name, "layout": lay_name, "expected": f"{exp_verdict} / {exp_type}",
                     "app_result": f"{got} / {got_type}", "score": v["metadata"].get("defect_probability"),
                     "element": f.get("element_ref"), "correct": got == exp_verdict and got_type == exp_type,
                     "point_at": point, "seconds": round(v["timings_ms"]["total_pipeline_ms"] / 1000, 1)})
        print(json.dumps(rows[-1]), flush=True)
    md = ["# C3 demo screens (verified through the app's service)", "",
          "Load each image in HEART > Screen inspection > Choose screenshot > Inspect screenshot. "
          "For 05 and 06, also attach the matching `_layout.json` under Advanced options > Add layout file. "
          "Keep 'Extra tile views' off.", "",
          "| File | Layout | Expected | App result | Score | Element | Correct | Point at |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        s = f"{r['score']:.2f}" if isinstance(r["score"], (int, float)) else "-"
        md.append(f"| {r['file']} | {r['layout'] or '-'} | {r['expected']} | {r['app_result']} | {s} | {r['element'] or '-'} | "
                  f"{'yes' if r['correct'] else 'NO'} | {r['point_at']} |")
    md += ["", "These are selected screens that show behaviour. They are not the accuracy. Quote accuracy only from the "
           "held-out test (AUC 0.75, F1 0.69, precision 61%, recall 79%, 316 screens). Boxes are approximate."]
    (OUT / "RESULTS.md").write_text("\n".join(md), encoding="utf-8")
    (OUT / "results.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(sum(r["correct"] for r in rows), "of", len(rows), "as expected")


if __name__ == "__main__":
    main()
