"""Proves inference runs with networking disabled: every socket connect raises, then the app service runs.

Usage (repo root):
    python -c "import vision_oracle.services.oracle_service; import runpy; runpy.run_module('vision_oracle.local_vision_oracle.offline_check', run_name='__main__')"
"""

import json
import socket
import time
from datetime import datetime, timezone
from pathlib import Path

ATTEMPTS = []


def _blocked(self, address, *args, **kwargs):
    ATTEMPTS.append(str(address))
    raise OSError(f"network blocked by offline_check: {address}")


def main(image="C:/Games/OwlEye/Dataset/bug-aug/bug-aug/bug.4418.jpg",
         out=Path(__file__).resolve().parents[1] / "evidence" / "14_pipeline_audit" / "offline_inference_check.json"):
    socket.socket.connect = _blocked
    socket.socket.connect_ex = _blocked
    socket.create_connection = lambda *a, **k: _blocked(None, a[0] if a else None)
    from vision_oracle.services.oracle_service import OracleService

    t = time.perf_counter()
    svc = OracleService()
    load_s = time.perf_counter() - t
    t = time.perf_counter()
    res = svc.evaluate(image_input=image, enable_sahi=False)
    v2 = res["verdict_v2"]
    report = {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "method": "socket.connect / connect_ex / create_connection replaced with a function that raises, before the model is loaded and the service is created",
              "image": image, "model_load_seconds": round(load_s, 1), "inference_seconds": round(time.perf_counter() - t, 1),
              "decision": v2["decision"], "findings": [(f["type"], f.get("bbox_xyxy")) for f in v2["findings"]],
              "defect_probability": v2["metadata"].get("defect_probability"),
              "network_connection_attempts": ATTEMPTS, "completed_offline": True}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
