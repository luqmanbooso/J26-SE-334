"""Re-run selected held-out test screens through the production pipeline and render evidence.

Every screen comes from the held-out test split (never used for training or for
choosing the model/threshold). Each is run through the same code path as the
HEART desktop app (create_default_engine -> AnalysisPipeline, global view), and
the output image shows the expected box (green) and the model's box (red).

Usage:
    python -m local_vision_oracle.pp1_demo_set --out evidence/13_pp1_demo
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OWL_BUG = "C:/Games/OwlEye/Dataset/bug-aug/bug-aug/"
OWL_OK = "C:/Games/OwlEye/Dataset/normal-aug/normal-aug/"
RICO_MUT = "D:/university/Resesarch/dataset/mutated_bugs/"
RICO_OK = "D:/university/Resesarch/dataset/clean/"

# (image, expected type, expected box [ymin,xmin,ymax,xmax] 0-1000 or None, source, why it is in the set)
DEMO = [
    (OWL_BUG + "bug.4031.jpg", "component_overlap", [200, 0, 340, 1000], "real (OwlEye)", "overlapping team names and labels"),
    (OWL_BUG + "bug.4007.jpg", "component_overlap", [240, 150, 300, 560], "real (OwlEye)", "title drawn over description"),
    (OWL_BUG + "bug.4418.jpg", "data_binding_null", [262, 450, 295, 560], "real (OwlEye)", "result shows 'null'"),
    (OWL_BUG + "bug.4037.jpg", "missing_component", [294, 80, 380, 250], "real (OwlEye)", "category icons not rendered"),
    (RICO_MUT + "11083_mut_missing.jpg", "missing_component", None, "synthetic (Rico)", "grey placeholder replaces a widget"),
    (RICO_MUT + "13067_mut_overlap.jpg", "component_overlap", None, "synthetic (Rico)", "widget pasted over another"),
    (OWL_OK + "normal.4234.jpg", "none", None, "real (OwlEye)", "clean screen, correctly not flagged"),
    (RICO_OK + "14229.jpg", "none", None, "real (Rico)", "clean screen, correctly not flagged"),
    (OWL_BUG + "bug.4296.jpg", "text_truncation", [190, 0, 215, 350], "real (OwlEye)", "known miss: thin clipped text"),
]


def _rico_meta_box(path: str):
    meta = Path(path.replace(".jpg", ".meta.json"))
    return json.loads(meta.read_text(encoding="utf-8")).get("bounding_box") if meta.exists() else None


def _draw(img: Image.Image, box, color, w):
    if not box:
        return
    W, H = img.size
    y1, x1, y2, x2 = box
    ImageDraw.Draw(img).rectangle([x1 * W / 1000, y1 * H / 1000, x2 * W / 1000, y2 * H / 1000], outline=color, width=w)


def run(out: Path) -> list:
    from vision_oracle.services.oracle_service import create_default_engine  # must come first (path guard)
    from vision_oracle.local_vision_oracle.pipeline import AnalysisPipeline

    out.mkdir(parents=True, exist_ok=True)
    engine = create_default_engine()
    pipe = AnalysisPipeline(backend=engine.backend, model_run_id="pp1-demo")
    rows = []
    for i, (path, exp_type, exp_box, source, why) in enumerate(DEMO, 1):
        exp_box = exp_box or _rico_meta_box(path)
        img = Image.open(path).convert("RGB")
        t = time.perf_counter()
        v = pipe.analyze(image=img, screen_id=Path(path).stem, coverage_policy="global_only").model_dump(mode="json")
        secs = time.perf_counter() - t
        f = v["primary_finding"] or {}
        pred_type = f.get("type") or "none"
        pred_box = None
        if f.get("bbox_xyxy"):
            x1, y1, x2, y2 = f["bbox_xyxy"]
            pred_box = [round(y1 / img.height * 1000), round(x1 / img.width * 1000),
                        round(y2 / img.height * 1000), round(x2 / img.width * 1000)]
        decision_ok = (pred_type != "none") == (exp_type != "none")
        row = {"n": i, "image": path, "source": source, "why": why, "expected_type": exp_type,
               "expected_box": exp_box, "decision": v["decision"], "predicted_type": pred_type,
               "predicted_box": pred_box, "defect_score": v["metadata"].get("defect_probability"),
               "threshold": v["metadata"].get("decision_threshold"), "decision_correct": decision_ok,
               "type_correct": pred_type == exp_type, "seconds": round(secs, 1)}
        rows.append(row)
        canvas = img.copy()
        lw = max(4, img.width // 150)
        _draw(canvas, exp_box, (0, 200, 0), lw)
        _draw(canvas, pred_box, (230, 0, 0), lw)
        H = 1100
        canvas = canvas.resize((int(canvas.width * H / canvas.height), H))
        band = Image.new("RGB", (canvas.width, 150), "white")
        d = ImageDraw.Draw(band)
        try:
            font = ImageFont.truetype("arial.ttf", 22)
        except OSError:
            font = ImageFont.load_default()
        ok = "CORRECT" if decision_ok and row["type_correct"] else ("DECISION OK, TYPE WRONG" if decision_ok else "WRONG")
        score = f"{row['defect_score']:.2f}" if isinstance(row["defect_score"], (int, float)) else "-"
        d.text((10, 8), f"#{i} {Path(path).name}  [{source}]  {ok}", fill="black", font=font)
        d.text((10, 42), f"Expected: {exp_type}   Model: {pred_type}   score {score} (flag at {row['threshold']})", fill="black", font=font)
        d.text((10, 76), f"Green = expected region   Red = model region   {row['seconds']} s", fill="black", font=font)
        d.text((10, 110), why, fill=(90, 90, 90), font=font)
        sheet = Image.new("RGB", (canvas.width, H + 150), "white")
        sheet.paste(canvas, (0, 0))
        sheet.paste(band, (0, H))
        sheet.save(out / f"{i:02d}_{Path(path).stem}.png")
        print(json.dumps(row), flush=True)
    (out / "demo_results.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="evidence/13_pp1_demo")
    run(Path(ap.parse_args().out))
