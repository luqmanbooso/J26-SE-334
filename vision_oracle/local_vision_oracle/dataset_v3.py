"""C3 dataset v3: visible synthetic defects, app-grouped splits, vision and fusion manifests.

Design (evidence/DATASET_V3_DESIGN.md):
* Rico clean screens carry a view hierarchy; OwlEye screens do not. Each example
  keeps its own input and its own label. Rico examples get the layout text in the
  fusion manifest; OwlEye examples always use the screenshot-only prompt.
* Rico screens are grouped by app package; an app never spans two splits. Screens
  that were in the old val/test splits keep that split so older models stay
  comparable. Each Rico screen has one role: clean negative or mutation source.
* Every synthetic defect is accepted only if, at the training resolution, it
  changes >= 0.2% of pixels and >= 80% of the changed pixels lie inside its box.
* OwlEye defect screens are used only when ``owleye_labels_v3.json`` marks them
  ``labelled``; OwlEye clean screens come from the "normal" folder.
* The vision and fusion manifests contain the same images and labels; only the
  prompt differs. Every example is checked against the training length limit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from local_vision_oracle.dataset_v2 import TRAINING_MAX_PIXELS, TRAINING_PROMPT, compact_target, resize_to_training
from local_vision_oracle.hierarchy_text import FORMAT_VERSION, DEFAULT_MAX_NODES, hierarchy_text

VISION_PROMPT = TRAINING_PROMPT
FUSION_PROMPT = (
    "Layout elements of this screen (type#id \"text\" [ymin,xmin,ymax,xmax] in 0-1000):\n"
    "{hierarchy}\n\n" + TRAINING_PROMPT
)
MIN_VISIBLE_FRACTION = 0.002
MIN_BOX_COVERAGE = 0.8
TOKEN_LIMIT = 1000  # LLaMA-Factory cutoff_len 1024 minus a safety margin
MUTATION_TYPES = ("overlap", "truncation", "missing", "null")
TYPE_LABEL = {"overlap": "component_overlap", "truncation": "text_truncation",
              "missing": "missing_component", "null": "data_binding_null"}


def contract(fusion: bool, threshold: Optional[float] = None) -> Dict:
    """Inference contract for an adapter trained on a v3 manifest."""
    c = {"user_prompt": VISION_PROMPT, "system_prompt": None, "image_max_pixels": TRAINING_MAX_PIXELS,
         "hierarchy_format": FORMAT_VERSION, "hierarchy_max_nodes": DEFAULT_MAX_NODES,
         "source": "local_vision_oracle.dataset_v3"}
    if fusion:
        c["hierarchy_prompt"] = FUSION_PROMPT
    if threshold is not None:
        c["decision_threshold"] = threshold
    return c


# ----------------------------------------------------------------------------- pixels

def change_stats(original, mutated, box: List[int]) -> Tuple[float, float]:
    """(fraction of pixels changed, share of changed pixels inside box) at training scale."""
    import numpy as np

    a = np.asarray(resize_to_training(original.convert("L")), dtype=np.int16)
    b = np.asarray(resize_to_training(mutated.convert("L")), dtype=np.int16)
    changed = np.abs(a - b) > 30
    total = int(changed.sum())
    if total == 0:
        return 0.0, 0.0
    h, w = changed.shape
    y1, x1, y2, x2 = box
    margin = 6  # pixels at training scale, absorbs resampling blur at the box edge
    ys = slice(max(0, int(y1 / 1000 * h) - margin), min(h, int(math.ceil(y2 / 1000 * h)) + margin))
    xs = slice(max(0, int(x1 / 1000 * w) - margin), min(w, int(math.ceil(x2 / 1000 * w)) + margin))
    inside = int(changed[ys, xs].sum())
    return total / changed.size, inside / total


# ----------------------------------------------------------------------------- splits

def _app_of(json_path: Path) -> str:
    try:
        name = json.loads(json_path.read_text(encoding="utf-8")).get("activity_name") or ""
    except (OSError, json.JSONDecodeError):
        return "unknown:" + json_path.stem
    return name.split("/")[0] or "unknown:" + json_path.stem


def _old_split_ids(data_dir: Path) -> Tuple[Dict[str, Tuple[str, str]], Dict[str, str]]:
    """From the v1 manifests: Rico id -> (split, "mutated"|"clean"), OwlEye file -> split."""
    rico: Dict[str, Tuple[str, str]] = {}
    owl: Dict[str, str] = {}
    for split, fname in (("train", "train.json"), ("val", "val.json"), ("test", "test.json")):
        path = data_dir / fname
        if not path.exists():
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            img = row["images"][0].replace("\\", "/")
            base = os.path.basename(img)
            if "OwlEye" in img or "-aug" in img:
                owl[base] = split
                continue
            m = re.match(r"(\d+)(_mut_)?", base)
            if m:
                rico.setdefault(m.group(1), (split, "mutated" if m.group(2) else "clean"))
    return rico, owl


SPLIT_RANK = {"train": 0, "val": 1, "test": 2}


def assign_rico_splits(clean_dir: Path, data_dir: Path, seed: int = 42) -> Dict[str, Tuple[str, str]]:
    """Screen id -> (split, app). An app with any old test screen goes to test, else any
    old val screen to val, else any old train screen to train; unseen apps are hashed 80/10/10."""
    old_rico, _ = _old_split_ids(data_dir)
    screens = sorted(p.stem for p in clean_dir.glob("*.json"))
    app = {sid: _app_of(clean_dir / f"{sid}.json") for sid in screens}
    app_split: Dict[str, str] = {}
    for sid, (split, _) in old_rico.items():
        a = app.get(sid)
        if a is not None and SPLIT_RANK[split] >= SPLIT_RANK.get(app_split.get(a, "train"), 0):
            app_split[a] = split
    for a in sorted(set(app.values())):
        if a not in app_split:
            h = int(hashlib.sha256(f"{seed}:{a}".encode()).hexdigest(), 16) % 100
            app_split[a] = "test" if h < 10 else "val" if h < 20 else "train"
    return {sid: (app_split[app[sid]], app[sid]) for sid in screens}


# ----------------------------------------------------------------------------- mutations

def generate_mutations(clean_dir: Path, out_dir: Path, sources: List[str], seed: int = 42,
                       target: Optional[int] = None) -> Tuple[List[Dict], List[str]]:
    """Mutate source screens until ``target`` verified defects exist, balanced across types.

    Each source screen is used at most once. It first tries the type furthest below its
    quota, then the others. Returns (kept mutations, source ids that were used).
    """
    from PIL import Image
    from local_vision_oracle.synthetic_mutator import SyntheticMutator

    out_dir.mkdir(parents=True, exist_ok=True)
    target = len(sources) if target is None else target
    quota = {t: target // len(MUTATION_TYPES) + (1 if i < target % len(MUTATION_TYPES) else 0)
             for i, t in enumerate(MUTATION_TYPES)}
    have = Counter()
    mutator = SyntheticMutator(seed=seed)
    kept, used, rejected = [], [], Counter()
    for sid in sources:
        if sum(have.values()) >= target:
            break
        image_path, json_path = clean_dir / f"{sid}.jpg", clean_dir / f"{sid}.json"
        if not image_path.exists() or not json_path.exists():
            rejected["missing_source"] += 1
            continue
        original = Image.open(image_path).convert("RGB")
        order = sorted((t for t in MUTATION_TYPES if have[t] < quota[t]), key=lambda t: have[t] - quota[t])
        for kind in order:
            try:
                res = mutator.mutate(image_path, json_path, mutation_type=kind)
            except Exception:
                res = None
            if res is None or res.defect_type.value != TYPE_LABEL[kind]:
                rejected[f"{kind}:no_candidate"] += 1
                continue
            visible, coverage = change_stats(original, res.image, res.bounding_box)
            if visible < MIN_VISIBLE_FRACTION:
                rejected[f"{kind}:invisible"] += 1
                continue
            if coverage < MIN_BOX_COVERAGE:
                rejected[f"{kind}:box_mismatch"] += 1
                continue
            name = f"{sid}_v3_{kind}"
            res.image.save(out_dir / f"{name}.jpg", quality=95)
            meta = {"source_screen": sid, "source_image": str(image_path), "source_hierarchy": str(json_path),
                    "defect_type": res.defect_type.value, "bounding_box": res.bounding_box,
                    "affected_element_id": res.affected_element_id, "visible_fraction": round(visible, 5),
                    "box_coverage": round(coverage, 4), "generator": "dataset_v3 + SyntheticMutator (scaled bounds)"}
            (out_dir / f"{name}.meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
            kept.append({"image": str(out_dir / f"{name}.jpg"), **meta})
            used.append(sid)
            have[kind] += 1
            break
        else:
            rejected["source_without_valid_mutation"] += 1
    (out_dir / "generation_report.json").write_text(json.dumps(
        {"target": target, "kept": len(kept), "quota": quota, "by_type": dict(have),
         "sources_tried": len(used) + rejected["source_without_valid_mutation"] + rejected["missing_source"],
         "rejected": dict(rejected), "min_visible_fraction": MIN_VISIBLE_FRACTION,
         "min_box_coverage": MIN_BOX_COVERAGE}, indent=1), encoding="utf-8")
    return kept, used


# ----------------------------------------------------------------------------- examples

def _image_tokens(image_path: str) -> int:
    from PIL import Image

    with Image.open(image_path) as im:
        w, h = resize_to_training(im).size
    return math.ceil(w / 28) * math.ceil(h / 28)


def make_example(image: str, target: Dict, layout: Optional[str], fusion: bool) -> Dict:
    prompt = FUSION_PROMPT.replace("{hierarchy}", layout) if (fusion and layout) else VISION_PROMPT
    return {"messages": [{"role": "user", "content": "<image>" + prompt},
                         {"role": "assistant", "content": compact_target(target)}],
            "images": [image]}


def build(clean_dir: Path, owleye_bug_dir: Path, owleye_normal_dir: Path, data_dir: Path, out_dir: Path,
          labels_path: Optional[Path], mutations_per_split: Dict[str, int], clean_per_split: Dict[str, int],
          tokenizer_dir: Optional[Path] = None, seed: int = 42) -> Dict:
    rng = random.Random(seed)
    splits = assign_rico_splits(clean_dir, data_dir, seed)
    old_rico, old_owl = _old_split_ids(data_dir)
    by_split: Dict[str, List[str]] = defaultdict(list)
    for sid, (split, _) in splits.items():
        by_split[split].append(sid)

    tok = None
    if tokenizer_dir:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(str(tokenizer_dir), local_files_only=True)

    labels = json.loads(labels_path.read_text(encoding="utf-8")) if labels_path and labels_path.exists() else {}
    report = {"splits": {}, "dropped_over_token_limit": 0, "owleye_bug_unlabelled_excluded": 0,
              "hierarchy_format": FORMAT_VERSION, "app_groups": len({a for _, a in splits.values()})}
    manifests = {("vision", s): [] for s in ("train", "val", "test")}
    manifests.update({("fusion", s): [] for s in ("train", "val", "test")})
    provenance = []

    for split in ("train", "val", "test"):
        pool = sorted(by_split[split])
        rng.shuffle(pool)
        # Old mutated test/val screens stay mutation sources, old clean ones stay clean.
        prev_mut = [s for s in pool if old_rico.get(s) == (split, "mutated")]
        prev_clean = [s for s in pool if old_rico.get(s) == (split, "clean")]
        rest = [s for s in pool if s not in set(prev_mut) | set(prev_clean)]
        n_mut, n_clean = mutations_per_split[split], clean_per_split[split]
        # Reserve clean negatives first (old clean screens keep their role), then mutate
        # from the remaining screens until the per-type quotas are met.
        clean_src = (prev_clean + [s for s in rest if s not in set(prev_mut)])[:n_clean]
        mut_pool = [s for s in prev_mut + rest if s not in set(clean_src)]
        mutations, _ = generate_mutations(clean_dir, out_dir / "mutated_v3" / split, mut_pool,
                                          seed=seed, target=n_mut)

        rows = []
        for sid in clean_src:
            rows.append(("rico_clean", str(clean_dir / f"{sid}.jpg"), {"defect_type": "none"},
                         clean_dir / f"{sid}.json"))
        for m in mutations:
            rows.append(("rico_mutated", m["image"], {"defect_type": m["defect_type"], "bounding_box": m["bounding_box"]},
                         Path(m["source_hierarchy"])))
        owl_rows = []
        for name, s in sorted(old_owl.items()):
            if s != split:
                continue
            if name.startswith("normal"):
                owl_rows.append(("owleye_normal", str(owleye_normal_dir / name), {"defect_type": "none"}, None))
            else:
                lab = labels.get(name)
                if lab and lab.get("status") == "labelled":
                    owl_rows.append(("owleye_bug", str(owleye_bug_dir / name),
                                     {"defect_type": lab["defect_type"], "bounding_box": lab.get("bounding_box")}, None))
                else:
                    report["owleye_bug_unlabelled_excluded"] += 1
        # OwlEye clean screens without OwlEye defect screens would teach "OwlEye look = clean".
        # Use the OwlEye source in a split only when its defect screens are labelled.
        if any(r[0] == "owleye_bug" for r in owl_rows):
            rows.extend(owl_rows)
        else:
            report.setdefault("owleye_withheld_no_labelled_bugs", {})[split] = len(owl_rows)

        counts = Counter()
        for source, image, target, hier in rows:
            ex_v = ex_f = None
            layout = None
            # Shorten the layout text before dropping a screen: dropping only long
            # layouts would remove the most complex screens from the dataset.
            for cap in ((DEFAULT_MAX_NODES, 14, 8) if hier else (DEFAULT_MAX_NODES,)):
                layout = hierarchy_text(hier, cap) if hier else None
                ex_v, ex_f = make_example(image, target, layout, False), make_example(image, target, layout, True)
                if tok is None:
                    break
                n = _image_tokens(image) + len(tok(ex_f["messages"][0]["content"] + ex_f["messages"][1]["content"]).input_ids)
                if n <= TOKEN_LIMIT:
                    if cap != DEFAULT_MAX_NODES:
                        report["layout_shortened"] = report.get("layout_shortened", 0) + 1
                    break
            else:
                report["dropped_over_token_limit"] += 1
                continue
            manifests[("vision", split)].append(ex_v)
            manifests[("fusion", split)].append(ex_f)
            provenance.append({"split": split, "source": source, "image": image, "label": target,
                               "has_layout": bool(layout)})
            counts[(source, target["defect_type"])] += 1
        report["splits"][split] = {f"{a}|{b}": v for (a, b), v in sorted(counts.items())}

    for (variant, split), rows in manifests.items():
        (data_dir / f"c3v3_{variant}_{split}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    _register(data_dir, [f"c3v3_{v}_{s}" for v in ("vision", "fusion") for s in ("train", "val", "test")])
    (out_dir / "dataset_v3_provenance.json").write_text(json.dumps(provenance, indent=1), encoding="utf-8")
    (out_dir / "dataset_v3_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for fusion in (False, True):
        (out_dir / f"inference_contract_{'fusion' if fusion else 'vision'}.json").write_text(
            json.dumps(contract(fusion), indent=2), encoding="utf-8")
    return report


def _register(data_dir: Path, names: List[str]) -> None:
    info_path = data_dir / "dataset_info.json"
    info = json.loads(info_path.read_text(encoding="utf-8"))
    for name in names:
        info[name] = {"file_name": f"{name}.json", "formatting": "sharegpt",
                      "columns": {"messages": "messages", "images": "images"},
                      "tags": {"role_tag": "role", "content_tag": "content",
                               "user_tag": "user", "assistant_tag": "assistant"}}
    info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clean-dir", required=True, help="Rico clean screens: <id>.jpg + <id>.json")
    ap.add_argument("--owleye-bug-dir", required=True)
    ap.add_argument("--owleye-normal-dir", required=True)
    ap.add_argument("--data-dir", required=True, help="LLaMA-Factory data dir (old v1 manifests define frozen splits)")
    ap.add_argument("--out-dir", required=True, help="where mutated images, reports and contracts go")
    ap.add_argument("--labels", default=None, help="owleye_labels_v3.json")
    ap.add_argument("--tokenizer", default=None, help="model dir for the token-length check")
    ap.add_argument("--mutations", default="1000,150,150", help="per split train,val,test")
    ap.add_argument("--clean", default="700,110,110", help="Rico clean negatives per split train,val,test")
    a = ap.parse_args(argv)
    mut = dict(zip(("train", "val", "test"), map(int, a.mutations.split(","))))
    cln = dict(zip(("train", "val", "test"), map(int, a.clean.split(","))))
    report = build(Path(a.clean_dir), Path(a.owleye_bug_dir), Path(a.owleye_normal_dir), Path(a.data_dir),
                   Path(a.out_dir), Path(a.labels) if a.labels else None, mut, cln,
                   Path(a.tokenizer) if a.tokenizer else None)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
