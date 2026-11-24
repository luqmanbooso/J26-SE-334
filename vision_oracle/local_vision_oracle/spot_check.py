"""Spot-check a trained C3 adapter on a few screens and scan for data leakage. No GPU needed.

Reads the saved evaluation records (score run and optional end-to-end run), then:
  1. prints the headline numbers recomputed from the records, so they can be compared with reports;
  2. shows score spread per label (a leak or a bug shows up as scores piled at 0 or 1);
  3. checks the splits for shared images, shared Rico source screens and OwlEye near-duplicates;
  4. re-scores the test set without the near-duplicate screens;
  5. writes contact sheets of random screens (model box red, true box green) to look at by eye.

Run from the repository root:
    python -m vision_oracle.local_vision_oracle.spot_check --scores <test_scores.json> --manifests <LLaMA-Factory/data> --out <folder>
        [--e2e <end_to_end.json>] [--threshold 0.30075] [--n 8] [--seed 1]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageDraw

SPLITS = ("train", "val", "test")


def _bool(v) -> bool:
    return v if isinstance(v, bool) else str(v).lower() == "true"


def auc(labels: List[bool], scores: List[float]) -> float:
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def metrics_at(records: List[Dict], threshold: float) -> Dict:
    tp = sum(r["p"] >= threshold and r["gold"] for r in records)
    fp = sum(r["p"] >= threshold and not r["gold"] for r in records)
    fn = sum(r["p"] < threshold and r["gold"] for r in records)
    tn = sum(r["p"] < threshold and not r["gold"] for r in records)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(prec, 3), "recall": round(rec, 3),
            "f1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0,
            "false_alarm_rate": round(fp / (fp + tn), 3) if fp + tn else 0.0}


def load_scores(path: Path) -> List[Dict]:
    d = json.loads(path.read_text(encoding="utf-8"))
    return [{"image": r["image"], "gold": _bool(r["gold_has"]), "type": r.get("gold_type"),
             "p": float(r["p_defect"])} for r in d["records"] if r.get("p_defect") is not None]


def dhash(path: str) -> Optional[int]:
    try:
        px = list(Image.open(path).convert("L").resize((9, 8)).getdata())
    except OSError:
        return None
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    return bits


def split_images(manifests: Path) -> Dict[str, List[str]]:
    out = {}
    for s in SPLITS:
        rows = json.loads((manifests / f"c3v3_vision_{s}.json").read_text(encoding="utf-8"))
        out[s] = [r["images"][0].replace("\\", "/") for r in rows]
    return out


def rico_source(path: str) -> Optional[str]:
    m = re.search(r"(\d+)(?:_v3_\w+)?\.jpg$", path)
    return m.group(1) if m and "OwlEye" not in path else None


def leak_report(manifests: Path, test_records: List[Dict], threshold: float) -> Dict:
    imgs = split_images(manifests)
    report: Dict = {"shared_images": {}, "rico_source_overlap": {}, "owleye_near_duplicates": {}}
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        report["shared_images"][f"{a}&{b}"] = len(set(imgs[a]) & set(imgs[b]))
        sa = {rico_source(p) for p in imgs[a]} - {None}
        sb = {rico_source(p) for p in imgs[b]} - {None}
        report["rico_source_overlap"][f"{a}&{b}"] = len(sa & sb)
    owl = {s: [(p, dhash(p)) for p in imgs[s] if "OwlEye" in p] for s in SPLITS}
    flagged = set()
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        pairs = [(pa, pb) for pa, ha in owl[a] for pb, hb in owl[b]
                 if ha is not None and hb is not None and bin(ha ^ hb).count("1") <= 6]
        kinds: Dict[str, int] = {}
        for pa, pb in pairs:
            k = ("bug" if "bug." in pa else "normal") + "-" + ("bug" if "bug." in pb else "normal")
            kinds[k] = kinds.get(k, 0) + 1
        report["owleye_near_duplicates"][f"{a}&{b}"] = {"pairs": len(pairs), "by_kind": kinds}
        if a == "train" and b == "test":
            flagged = {os.path.basename(pb) for _, pb in pairs}
    keep = [r for r in test_records if os.path.basename(r["image"]) not in flagged]
    report["test_auc_all"] = round(auc([r["gold"] for r in test_records], [r["p"] for r in test_records]), 4)
    report["test_auc_without_near_duplicates"] = round(auc([r["gold"] for r in keep], [r["p"] for r in keep]), 4)
    report["test_screens_dropped"] = len(test_records) - len(keep)
    return report


def spread(records: List[Dict]) -> Dict:
    out = {}
    for name, rs in (("defect", [r for r in records if r["gold"]]), ("clean", [r for r in records if not r["gold"]])):
        ps = sorted(r["p"] for r in rs)
        if ps:
            q = lambda f: round(ps[min(len(ps) - 1, int(f * len(ps)))], 3)
            out[name] = {"n": len(ps), "p10": q(0.1), "median": q(0.5), "p90": q(0.9),
                         "share_above_0.95": round(sum(p > 0.95 for p in ps) / len(ps), 3),
                         "share_below_0.05": round(sum(p < 0.05 for p in ps) / len(ps), 3)}
    return out


def _box(img: Image.Image, box, color):
    if not box:
        return
    w, h = img.size
    y1, x1, y2, x2 = box
    ImageDraw.Draw(img).rectangle([x1 * w / 1000, y1 * h / 1000, x2 * w / 1000, y2 * h / 1000], outline=color, width=4)


def contact_sheet(items: List[Dict], path: Path, cols: int = 4, width: int = 300) -> None:
    tiles = []
    for it in items:
        img = Image.open(it["image"]).convert("RGB")
        _box(img, it.get("gold_box"), (0, 200, 0))
        _box(img, it.get("pred_box"), (230, 0, 0))
        tile = img.resize((width, int(width * img.height / img.width)))
        d = ImageDraw.Draw(tile)
        d.rectangle([0, 0, width, 30], fill=(0, 0, 0))
        d.text((4, 2), it["caption"][:46], fill=(255, 255, 255))
        d.text((4, 15), it["caption2"][:46], fill=(255, 220, 0))
        tiles.append(tile)
    rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
    sheet = Image.new("RGB", (cols * width, sum(max(t.height for t in r) for r in rows)), "white")
    y = 0
    for r in rows:
        for i, t in enumerate(r):
            sheet.paste(t, (i * width, y))
        y += max(t.height for t in r)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scores", required=True)
    ap.add_argument("--manifests", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--e2e", default=None)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    rng, out = random.Random(a.seed), Path(a.out)
    recs = load_scores(Path(a.scores))

    result = {"headline": {"n": len(recs), "auc": round(auc([r["gold"] for r in recs], [r["p"] for r in recs]), 4),
                           f"at_{a.threshold}": metrics_at(recs, a.threshold)},
              "score_spread": spread(recs),
              "leakage": leak_report(Path(a.manifests), recs, a.threshold)}

    sample = rng.sample([r for r in recs if r["gold"]], min(a.n, sum(r["gold"] for r in recs))) + \
             rng.sample([r for r in recs if not r["gold"]], min(a.n, sum(not r["gold"] for r in recs)))
    e2e = {}
    if a.e2e:
        for r in json.loads(Path(a.e2e).read_text(encoding="utf-8"))["records"]:
            e2e[r["image"]] = r
    items = []
    for r in sample:
        e = e2e.get(r["image"], {})
        box = lambda v: json.loads(v) if isinstance(v, str) else v
        flagged = r["p"] >= a.threshold
        ok = flagged == r["gold"]
        items.append({"image": r["image"], "gold_box": box(e.get("gold_box")) if e else None,
                      "pred_box": box(e.get("pred_box")) if e else None,
                      "caption": f"{'DEFECT' if r['gold'] else 'CLEAN'} p={r['p']:.2f} {'OK' if ok else 'WRONG'}",
                      "caption2": os.path.basename(r["image"])})
    contact_sheet(items[:a.n], out / "spot_defect_screens.png")
    contact_sheet(items[a.n:], out / "spot_clean_screens.png")
    (out / "spot_check.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))
    print("contact sheets:", out / "spot_defect_screens.png", out / "spot_clean_screens.png")


if __name__ == "__main__":
    main()
