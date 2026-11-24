"""Global-only vs global+tiles through the production pipeline, on validation screens only.

Usage:
    python -c "import vision_oracle.services.oracle_service; import runpy,sys; sys.argv=['x','--n','60','--out','evidence/14_pipeline_audit/tile_ablation_val60.json']; runpy.run_module('vision_oracle.local_vision_oracle.tile_ablation', run_name='__main__')"
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from PIL import Image

VAL = "D:/university/Resesarch/RD/LLaMA-Factory/data/c3v2_val.json"


def run(n: int, out: Path, seed: int = 11) -> dict:
    from vision_oracle.services.oracle_service import create_default_engine
    from vision_oracle.local_vision_oracle.pipeline import AnalysisPipeline
    from vision_oracle.local_vision_oracle.contract_benchmark import summarize

    rows = json.loads(Path(VAL).read_text(encoding="utf-8"))
    random.Random(seed).shuffle(rows)
    rows = rows[:n]
    pipe = AnalysisPipeline(backend=create_default_engine().backend, model_run_id="tile-ablation")
    result = {"n": n, "seed": seed, "split": "c3v2_val (validation only)", "policies": {}}
    for policy in ("global_only", "global_plus_tiles_v1"):
        recs = []
        for row in rows:
            gold = json.loads(row["messages"][-1]["content"])
            img = Image.open(row["images"][0]).convert("RGB")
            t = time.perf_counter()
            v = pipe.analyze(image=img, coverage_policy=policy).model_dump(mode="json")
            ms = (time.perf_counter() - t) * 1000
            f = v["primary_finding"] or {}
            flagged = v["decision"] == "defect_detected"
            recs.append({"image": row["images"][0], "gold_has": bool(gold["has_defect"]), "gold_type": gold["defect_type"],
                         "pred_has": True if flagged else (False if v["decision"] == "no_defect_detected" else None),
                         "pred_type": f.get("type") if flagged else "none", "iou": None, "latency_ms": round(ms, 1),
                         "decision": v["decision"], "views": v["coverage"]["planned_views"],
                         "flagging_views": sorted({vid for fd in v["findings"] for vid in fd.get("view_ids", [])})})
            print(policy, len(recs), gold["defect_type"], v["decision"], round(ms), flush=True)
        result["policies"][policy] = {"summary": summarize(recs), "records": recs}
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--out", default="vision_oracle/evidence/14_pipeline_audit/tile_ablation_val60.json")
    a = ap.parse_args()
    r = run(a.n, Path(a.out))
    for k, v in r["policies"].items():
        s = v["summary"]
        print(k, {x: s[x] for x in ("precision", "recall", "f1", "accuracy", "fp", "fn", "median_latency_ms")})
