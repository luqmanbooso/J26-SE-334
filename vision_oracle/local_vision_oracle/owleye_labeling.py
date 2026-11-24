"""OwlEye relabelling: contact sheets for labelling, review sheets for human verification.

Label file ``owleye_labels_v3.json`` maps an OwlEye file name to::

    {"status": "labelled" | "unclear" | "no_visible_defect",
     "defect_type": "component_overlap" | "text_truncation" | "missing_component" | "data_binding_null" | null,
     "bounding_box": [ymin, xmin, ymax, xmax] in 0-1000 | null,
     "note": "what is wrong, in a few words",
     "labeller": "model-assisted:<model id>" | "human:<name>",
     "human_verified": false | true,
     "split": "train" | "val" | "test"}

Only ``labelled`` screens enter training/evaluation. ``unclear`` and
``no_visible_defect`` are excluded rather than guessed. Model-assisted labels must
be checked by a person before a test set built from them is reported as ground truth.

Usage:
    python -m local_vision_oracle.owleye_labeling sheets --split test --out <dir>
    python -m local_vision_oracle.owleye_labeling review --labels <json> --split test --out <dir>
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

DEFECT_TYPES = ("component_overlap", "text_truncation", "missing_component", "data_binding_null")
STATUSES = ("labelled", "unclear", "no_visible_defect")
TILE_H = 900


def _font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def validate_label(name: str, lab: Dict) -> List[str]:
    """Return problems with one label entry (empty list when valid)."""
    errs = []
    if lab.get("status") not in STATUSES:
        errs.append(f"{name}: status must be one of {STATUSES}")
    if lab.get("status") == "labelled":
        if lab.get("defect_type") not in DEFECT_TYPES:
            errs.append(f"{name}: defect_type must be one of {DEFECT_TYPES}")
        box = lab.get("bounding_box")
        if not (isinstance(box, list) and len(box) == 4 and all(isinstance(v, int) and 0 <= v <= 1000 for v in box)
                and box[0] < box[2] and box[1] < box[3]):
            errs.append(f"{name}: bounding_box must be [ymin,xmin,ymax,xmax] integers in 0-1000 with min < max")
    if "human_verified" in lab and not isinstance(lab["human_verified"], bool):
        errs.append(f"{name}: human_verified must be true/false")
    return errs


def owleye_bug_files(data_dir: Path, split: str) -> List[str]:
    """OwlEye bug-screen paths that the v1 manifests assigned to ``split``."""
    fname = {"train": "train.json", "val": "val.json", "test": "test.json"}[split]
    rows = json.loads((data_dir / fname).read_text(encoding="utf-8"))
    out = []
    for r in rows:
        img = r["images"][0].replace("\\", "/")
        if "bug-aug" in img and img not in out:
            out.append(img)
    return sorted(out)


def grid_tile(path: str, index: int, label: Optional[Dict] = None) -> Image.Image:
    """Screenshot with a 0-1000 grid (every 100, labelled) and optional label box."""
    im = Image.open(path).convert("RGB")
    w = int(im.width * TILE_H / im.height)
    im = im.resize((w, TILE_H))
    d = ImageDraw.Draw(im, "RGBA")
    f = _font(16)
    for v in range(100, 1000, 100):
        x, y = v * w / 1000, v * TILE_H / 1000
        d.line([(x, 0), (x, TILE_H)], fill=(0, 160, 255, 110), width=1)
        d.line([(0, y), (w, y)], fill=(0, 160, 255, 110), width=1)
        d.text((x + 2, 2), str(v), fill=(0, 90, 200, 255), font=f)
        d.text((2, y + 2), str(v), fill=(0, 90, 200, 255), font=f)
    if label and label.get("bounding_box"):
        y1, x1, y2, x2 = label["bounding_box"]
        d.rectangle([x1 * w / 1000, y1 * TILE_H / 1000, x2 * w / 1000, y2 * TILE_H / 1000], outline=(255, 0, 0, 255), width=4)
    head = f"#{index} {Path(path).name}"
    if label:
        head += f"  {label.get('status')}: {label.get('defect_type') or '-'}"
    d.rectangle([0, TILE_H - 26, w, TILE_H], fill=(0, 0, 0, 220))
    d.text((4, TILE_H - 23), head, fill=(255, 230, 0, 255), font=_font(17))
    return im


def make_sheets(files: List[str], out_dir: Path, per_sheet: int = 4,
                labels: Optional[Dict[str, Dict]] = None, prefix: str = "sheet") -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for start in range(0, len(files), per_sheet):
        tiles = [grid_tile(f, start + i, (labels or {}).get(Path(f).name)) for i, f in enumerate(files[start:start + per_sheet])]
        sheet = Image.new("RGB", (sum(t.width for t in tiles) + 12 * (len(tiles) - 1), TILE_H), "white")
        x = 0
        for t in tiles:
            sheet.paste(t, (x, 0))
            x += t.width + 12
        p = out_dir / f"{prefix}_{start // per_sheet:03d}.png"
        sheet.save(p)
        paths.append(p)
    (out_dir / f"{prefix}_index.json").write_text(json.dumps(
        {str(i): f for i, f in enumerate(files)}, indent=1), encoding="utf-8")
    return paths


def write_review_csv(labels: Dict[str, Dict], files: List[str], out: Path) -> None:
    """Checklist for the human reviewer: one row per screen, with blank verdict columns."""
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["index", "file", "status", "defect_type", "bounding_box", "note",
                    "reviewer_agrees (y/n)", "reviewer_correction"])
        for i, f in enumerate(files):
            lab = labels.get(Path(f).name, {})
            w.writerow([i, Path(f).name, lab.get("status"), lab.get("defect_type"),
                        lab.get("bounding_box"), lab.get("note"), "", ""])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["sheets", "review", "validate"])
    ap.add_argument("--data-dir", default="D:/university/Resesarch/RD/LLaMA-Factory/data")
    ap.add_argument("--split", choices=["train", "val", "test"], default="test")
    ap.add_argument("--labels", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--per-sheet", type=int, default=4)
    a = ap.parse_args(argv)
    files = owleye_bug_files(Path(a.data_dir), a.split)
    labels = json.loads(Path(a.labels).read_text(encoding="utf-8")) if a.labels else {}
    if a.mode == "validate":
        problems = [e for n, lab in labels.items() for e in validate_label(n, lab)]
        print("\n".join(problems) or f"{len(labels)} labels valid")
        return
    out = Path(a.out)
    if a.mode == "sheets":
        paths = make_sheets(files, out, a.per_sheet, prefix=f"label_{a.split}")
    else:
        paths = make_sheets(files, out, a.per_sheet, labels, prefix=f"review_{a.split}")
        write_review_csv(labels, files, out / f"review_{a.split}.csv")
    print(f"{len(files)} screens -> {len(paths)} sheets in {out}")


if __name__ == "__main__":
    main()
