"""Calls every C3 REST endpoint on a running server (real model) and records status, timing and checks.

Start the server first (repo root):  python vision_oracle/server.py
Then:                                 python -m vision_oracle.local_vision_oracle.backend_smoke
"""

import base64
import io
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8003"
OUT = Path(__file__).resolve().parents[1] / "evidence" / "14_pipeline_audit" / "backend_smoke.json"
DEFECT = "C:/Games/OwlEye/Dataset/bug-aug/bug-aug/bug.4418.jpg"
PHONE = Path(__file__).resolve().parents[1] / "notebooks" / "live_phone_screen.png"
PHONE_XML = Path(__file__).resolve().parents[1] / "notebooks" / "live_phone_hierarchy.xml"
results = []


def call(method, path, body=None, expect=(200,), check=None, timeout=300):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code, payload = r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        code, payload = e.code, json.loads(e.read() or b"null")
    ms = round((time.perf_counter() - t) * 1000, 1)
    ok = code in expect
    note = ""
    if ok and check:
        try:
            note = check(payload) or ""
        except Exception as exc:  # a failed check is a failed endpoint
            ok, note = False, f"check failed: {exc}"
    results.append({"method": method, "path": path, "status": code, "expected": list(expect), "ok": ok,
                    "ms": ms, "note": note if ok else (note or str(payload)[:300])})
    print(("PASS " if ok else "FAIL ") + f"{method} {path} -> {code} {ms} ms {note}", flush=True)
    return payload


def b64(path):
    return base64.b64encode(Path(path).read_bytes()).decode()


def main():
    for _ in range(120):  # wait for model load
        try:
            with urllib.request.urlopen(BASE + "/health/live", timeout=5):
                break
        except Exception:
            time.sleep(2)
    call("GET", "/health/live")
    call("GET", "/health/ready", check=lambda p: f"ready={p.get('ready')}")
    call("GET", "/", check=lambda p: "ok")
    call("GET", "/api/status", check=lambda p: "ok")

    def defect_check(p):
        v = p["verdict_v2"]
        assert v["decision"] == "defect_detected", v["decision"]
        assert v["findings"][0]["type"] == "data_binding_null"
        return f"decision={v['decision']} type={v['findings'][0]['type']} score={v['metadata'].get('defect_probability')}"
    call("POST", "/api/oracle/evaluate", {"image_path": DEFECT, "session_id": "smoke"}, check=defect_check)
    r = call("POST", "/api/oracle/evaluate", {"image_base64": b64(PHONE), "hierarchy_xml": PHONE_XML.read_text(encoding="utf-8"),
                                    "session_id": "smoke"},
             check=lambda p: f"decision={p['verdict_v2']['decision']} hierarchy={p['verdict_v2']['metadata'].get('hierarchy_status')}")
    call("POST", "/api/oracle/evaluate", {"image_base64": "not-base64!!", "session_id": "smoke"}, expect=(400, 422))
    call("POST", "/api/oracle/evaluate", {"session_id": "smoke"}, expect=(400, 422))
    call("POST", "/api/oracle/sequence", {"image_paths": [DEFECT, DEFECT], "session_id": "smoke", "time_delta_s": 3.0},
         check=lambda p: f"keys={sorted(p)[:4]}")

    cap = call("POST", "/v2/captures", {"session_id": "smoke_v2", "action_id": "act_smoke_1", "image_base64": b64(DEFECT)},
               expect=(201,), check=lambda p: p["capture_id"])
    job = call("POST", "/v2/jobs", {"capture_id": cap["capture_id"], "session_id": "smoke_v2", "policy": "global_only"},
               expect=(202,), check=lambda p: p["job_id"])
    state = None
    for _ in range(60):
        st = json.loads(urllib.request.urlopen(BASE + f"/v2/jobs/{job['job_id']}").read())
        state = st["state"]
        if state in ("completed", "failed", "cancelled"):
            break
        time.sleep(1)
    results.append({"method": "GET", "path": "/v2/jobs/{id} (final)", "status": 200, "expected": [200],
                    "ok": state == "completed", "ms": None, "note": f"state={state} error={st.get('error_message')}"})
    print(("PASS" if state == "completed" else "FAIL") + f" job final state {state}")
    if state == "completed":
        call("GET", f"/v2/results/{st['verdict_id']}", check=lambda p: f"decision={p.get('decision', p.get('verdict', {}).get('decision'))}")
        call("GET", "/v2/sessions/smoke_v2/results", check=lambda p: f"n={len(p) if isinstance(p, list) else p.get('count', '?')}")
        call("POST", "/v2/reviews", {"verdict_id": st["verdict_id"], "review_status": "accepted",
                                     "reviewer_notes": "backend smoke"}, expect=(201,),
             check=lambda p: "ok")
    call("POST", "/v2/jobs", {"capture_id": "cap_does_not_exist", "policy": "global_only"}, expect=(404,))
    call("GET", "/api/oracle/verdicts", check=lambda p: f"n={len(p) if isinstance(p, list) else '?'}")
    call("POST", "/api/oracle/trigger", {"action_id": "act_smoke_dev", "session_id": "smoke"}, expect=(503, 409, 404),
         check=lambda p: "no device -> clear error")
    call("POST", "/api/oracle/evaluate_device", {"session_id": "smoke"}, expect=(503, 409),
         check=lambda p: "no device -> clear error")
    OUT.write_text(json.dumps({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "base": BASE,
                               "passed": sum(r["ok"] for r in results), "total": len(results), "results": results},
                              indent=1), encoding="utf-8")
    print(f"{sum(r['ok'] for r in results)}/{len(results)} passed -> {OUT}")


if __name__ == "__main__":
    main()
