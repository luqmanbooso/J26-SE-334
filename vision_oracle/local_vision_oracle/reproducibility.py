"""Compare two runs of the same C3 adapter on the same screens (reproducibility check).

A hosted model can change between runs without notice. C3's weights are frozen and local,
so the same screen should get the same verdict. This module measures that by pairing two
result files from ``contract_benchmark`` screen by screen.

Usage:
    python -m local_vision_oracle.reproducibility --score A.json B.json --threshold 0.30075 \
        [--e2e A_e2e.json B_e2e.json] --output report.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# Image folders that moved between runs; keys are matched after path normalisation.
PATH_ALIASES: Tuple[Tuple[str, str], ...] = (("c:/games/owleye/", "d:/dataset/owleye/"),)


def screen_key(path: str) -> str:
    """Normalise an image path so the same file matches across runs and moved folders."""
    key = path.replace("\\", "/").lower()
    for old, new in PATH_ALIASES:
        if key.startswith(old):
            key = new + key[len(old):]
    return key


def pair_records(a: Iterable[Dict], b: Iterable[Dict]) -> Tuple[List[Tuple[Dict, Dict]], int, int]:
    """Pair records by image. Returns (pairs, only_in_a, only_in_b)."""
    index_a = {screen_key(r["image"]): r for r in a}
    index_b = {screen_key(r["image"]): r for r in b}
    shared = sorted(set(index_a) & set(index_b))
    return [(index_a[k], index_b[k]) for k in shared], len(set(index_a) - set(index_b)), len(set(index_b) - set(index_a))


def compare_scores(a: Iterable[Dict], b: Iterable[Dict], threshold: float) -> Dict:
    """Agreement of P(defect) and of the thresholded verdict between two scoring runs."""
    pairs, only_a, only_b = pair_records(a, b)
    if not pairs:
        raise ValueError("no screens in common between the two runs")
    diffs = [abs(float(x["p_defect"]) - float(y["p_defect"])) for x, y in pairs]
    flips = [x["image"] for x, y in pairs if (float(x["p_defect"]) >= threshold) != (float(y["p_defect"]) >= threshold)]
    return {
        "screens": len(pairs),
        "only_in_first": only_a,
        "only_in_second": only_b,
        "threshold": threshold,
        "max_abs_diff": max(diffs),
        "mean_abs_diff": sum(diffs) / len(diffs),
        "identical_scores": sum(d == 0 for d in diffs),
        "verdict_agreement": 1 - len(flips) / len(pairs),
        "verdict_flips": flips,
    }


def compare_e2e(a: Iterable[Dict], b: Iterable[Dict]) -> Dict:
    """Agreement of generated outputs (raw text, verdict, type, box) between two generation runs."""
    pairs, only_a, only_b = pair_records(a, b)
    if not pairs:
        raise ValueError("no screens in common between the two runs")
    n = len(pairs)
    same = lambda field: sum(x.get(field) == y.get(field) for x, y in pairs) / n  # noqa: E731
    return {
        "screens": n,
        "only_in_first": only_a,
        "only_in_second": only_b,
        "raw_text_identical": same("raw"),
        "verdict_agreement": same("pred_has"),
        "type_agreement": same("pred_type"),
        "box_identical": same("pred_box"),
        "differing_screens": [x["image"] for x, y in pairs if x.get("raw") != y.get("raw")],
    }


def _records(path: str) -> List[Dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["records"]


def main(argv: Optional[List[str]] = None) -> Dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--score", nargs=2, metavar=("FIRST", "SECOND"), required=True)
    ap.add_argument("--threshold", type=float, required=True, help="decision threshold chosen on validation")
    ap.add_argument("--e2e", nargs=2, metavar=("FIRST", "SECOND"))
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)
    report = {"score_files": args.score, "score": compare_scores(_records(args.score[0]), _records(args.score[1]), args.threshold)}
    if args.e2e:
        report["e2e_files"] = args.e2e
        report["e2e"] = compare_e2e(_records(args.e2e[0]), _records(args.e2e[1]))
    Path(args.output).write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


if __name__ == "__main__":
    out = main()
    s = out["score"]
    print(f"screens {s['screens']}  max|dP| {s['max_abs_diff']:.6f}  verdict agreement {s['verdict_agreement']:.1%}")
    if "e2e" in out:
        e = out["e2e"]
        print(f"e2e screens {e['screens']}  raw identical {e['raw_text_identical']:.1%}  type {e['type_agreement']:.1%}  box {e['box_identical']:.1%}")
