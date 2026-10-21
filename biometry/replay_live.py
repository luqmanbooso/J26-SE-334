"""Replay a compiled plan on a device — fast, as any persona.

Phase 1 (slow, once): `run_live_adaptive.py ... --out results/<name>` maps the app
and writes `results/<name>_plan.json` (the ordered action stream + a fingerprint
per screen).

Phase 2 (fast, repeatable): this script re-walks that plan with **no uiautomator
dumps**, running the same biometric engine so the timeline/log come out exactly as
in a live run — but quickly, and as whatever persona you pick:

    python replay_live.py --plan results/biznest_plan.json --profile tremor --stress 0.9
    python replay_live.py --plan results/biznest_plan.json --profile calm --no-verify

`--no-verify` is the fastest (blind) mode; the default confirms each screen with a
cheap screenshot fingerprint and resyncs (relaunch + fast-forward) on drift so a
non-deterministic app does not derail the run.
"""
import argparse
import json
import os
import time

from bridge.adb_bridge import ADBBridge
from bridge.device import AdbDispatcher, foreground_activity, foreground_package
from bridge.frame_probe import FrameProbe
from engine.controller import AdaptiveFeedbackController
from engine.fingerprint import DEFAULT_MAX_DISTANCE, ahash
from engine.replay import ReplayEngine
from engine.visualise import plot_timeline
from models.cognitive import StaticStress
from models.profiles import PROFILES, build_engine


def main():
    ap = argparse.ArgumentParser(description="Replay a compiled traversal plan fast, as a persona.")
    ap.add_argument("--plan", required=True, help="the <out>_plan.json produced by a map run")
    ap.add_argument("--device", default=None, help="adb device serial")
    ap.add_argument("--profile", default="default", choices=sorted(PROFILES),
                    help="behaviour persona for the replay")
    ap.add_argument("--static", action="store_true",
                    help="use a fixed stress level (--stress) instead of the adaptive source")
    ap.add_argument("--stress", type=float, default=0.9,
                    help="fixed cognitive stress for --static (0..1); e.g. 0.9 = frustrated")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--px-per-mm", type=float, default=None,
                    help="pixel scale (defaults to the value saved in the plan)")
    ap.add_argument("--no-launch", action="store_true",
                    help="do not cold-start the app first (replay what is already open)")
    ap.add_argument("--reset", action="store_true",
                    help="`pm clear` the app before cold-starting, so replay begins from the "
                         "same fresh state the plan was mapped from (use it when the plan "
                         "includes an onboarding/login flow — otherwise a persisted login makes "
                         "the app skip those screens and replay diverges at step 0)")
    ap.add_argument("--no-verify-activity", dest="verify_activity", action="store_false", default=True,
                    help="disable the Level B foreground-activity screen check (default on; robust & "
                         "pixel-free, ~60 ms/tap; needs a plan mapped with per-step activities)")
    ap.add_argument("--verify-fingerprint", dest="verify_fp", action="store_true", default=False,
                    help="Level A: whole-screen fingerprint check on each new screen (opt-in; "
                         "unreliable on photo-heavy apps, used as a fallback when no activity is mapped)")
    ap.add_argument("--no-verify", dest="blind", action="store_true", default=False,
                    help="blind replay: disable BOTH screen checks (activity and fingerprint). The "
                         "app guard still runs, so a tap can still never land in another app.")
    ap.add_argument("--no-app-guard", dest="app_guard", action="store_false", default=True,
                    help="disable the pre-tap check that we are still in the app under test "
                         "(default on; ~60 ms/tap, stops a tap ever landing in another app)")
    ap.add_argument("--raw-taps", action="store_true",
                    help="dispatch the persona's imperfect (distorted) tap point instead of "
                         "snapping to the target — realistic but may miss and derail the walk")
    ap.add_argument("--max-distance", type=int, default=DEFAULT_MAX_DISTANCE,
                    help="fingerprint Hamming distance still counted as the same screen")
    ap.add_argument("--settle", type=float, default=0.3,
                    help="seconds to let the screen render after each action")
    ap.add_argument("--launch-wait", type=float, default=2.5, help="seconds to wait after a (re)launch")
    ap.add_argument("--on-drift", choices=["relaunch", "stop", "skip"], default="relaunch",
                    help="what to do when the live screen no longer matches the plan")
    ap.add_argument("--max-resyncs", type=int, default=3)
    ap.add_argument("--out", default="results/replay")
    ap.add_argument("--no-report", dest="report", action="store_false", default=True)
    ap.add_argument("--no-stamp", dest="stamp", action="store_false", default=True,
                    help="write straight to --out and overwrite it. By default each run gets a "
                         "timestamped name in the SAME folder (results/<name>_<ts>_*) so a replay "
                         "never overwrites a previous report.")
    args = ap.parse_args()

    # Timestamped name in the same folder, so a replay never overwrites a previous report.
    if args.stamp:
        args.out = "{}_{}".format(args.out, time.strftime("%Y%m%d-%H%M%S"))
    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(args.plan, "r", encoding="utf-8") as fh:
        plan = json.load(fh)
    package = plan.get("app_package")
    if not package:
        raise SystemExit("plan has no app_package")
    steps = plan.get("steps", [])
    print(f"[replay] plan: {args.plan} — {len(steps)} actions, "
          f"{len(plan.get('fingerprints', {}))} fingerprints, app {package}")

    bridge = ADBBridge(device_id=args.device)
    px_per_mm = args.px_per_mm or plan.get("px_per_mm")
    if not px_per_mm:
        out = bridge.device.shell("wm", "density")
        dpi = next((float(t) for t in out.replace(":", " ").split()
                    if t.replace(".", "", 1).isdigit()), None)
        px_per_mm = (dpi / 25.4) if dpi else 16.0
    print(f"[replay] px/mm = {px_per_mm:.2f}; persona = {args.profile}"
          f"{' static s=' + str(args.stress) if args.static else ''}")

    simulator, source = build_engine(args.profile, seed=args.seed, px_per_mm=px_per_mm)
    if args.static:
        source = StaticStress(args.stress)

    controller = AdaptiveFeedbackController(
        simulator=simulator,
        cognitive=source,
        probe=FrameProbe(bridge.device, package),
        dispatch=AdbDispatcher(bridge),
        run_id=f"replay-{'static' if args.static else args.profile}",
        persona_id=args.profile,
        # Land taps on their targets so the saved traversal is actually followed;
        # the timeline still records the persona's distorted aim + timing. Use
        # --raw-taps to dispatch the imperfect point (may miss and derail).
        land_taps=not args.raw_taps,
    )

    if args.reset:
        print(f"[replay] reset: pm clear {package} (match the plan's fresh start state)")
        bridge.device.run("shell", "pm", "clear", package)
    if not args.no_launch:
        print(f"[replay] cold-starting {package}")
        bridge.launch_package(package)
        # Wait for the first screen to render WITHOUT any uiautomator dump — the
        # slow dump->save->compare was the whole cost the map already paid, and
        # replay must not repeat it. Poll a cheap screenshot fingerprint until it
        # is truly stable (several equal frames, not a transient match mid-
        # animation — an onboarding splash with a moving background settles over a
        # few seconds), or we time out.
        prev, stable = "", 0
        for _ in range(20):
            time.sleep(0.5)
            try:
                cur = ahash(bridge.device.screencap(as_pil=True))
            except Exception:
                cur = ""
            if cur and cur == prev:
                stable += 1
                if stable >= 2:            # three equal frames in a row (~1s steady)
                    break
            else:
                stable = 0
            prev = cur

    def reporter(index, label, record):
        ui = f"{record.ui_delay_ms:>6.1f}ms" if record.ui_delay_ms is not None else " stalled"
        print(f"  {index:>3} {record.cognitive_state:<11} s={record.stress_s:.2f} "
              f"ui={ui} {'hit' if record.hit_flag else 'MISS'} {label[:30]}")

    engine = ReplayEngine(
        plan, controller,
        press_back=bridge.press_back,
        relaunch=lambda: bridge.launch_package(package),
        set_text=bridge.set_text,
        raw_tap=lambda x, y: bridge.execute_tap(x, y),
        fingerprint_fn=lambda: ahash(bridge.device.screencap(as_pil=True)),
        current_package=lambda: foreground_package(bridge.device),
        current_activity=lambda: foreground_activity(bridge.device),
        app_package=package,
        verify=args.verify_fp and not args.blind,
        verify_activity=args.verify_activity and not args.blind,
        app_guard=args.app_guard,
        max_distance=args.max_distance,
        settle_s=args.settle,
        launch_wait_s=args.launch_wait,
        max_resyncs=args.max_resyncs,
        on_drift=args.on_drift,
        reporter=reporter,
    )

    t0 = time.time()
    result = engine.run()
    elapsed = time.time() - t0

    log_path = f"{args.out}_replay.log"
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(result.log_lines) + "\n")
    controller.timeline.write_json(f"{args.out}_timeline.json")

    # A reliability sidecar next to the timeline: build_report reads it to show a
    # banner when the run was disrupted, so a stuck/relaunched replay can never
    # quietly look like a clean one. A map run writes none, so it gets no banner.
    rel = result.reliability
    rel_path = f"{args.out}_reliability.json"
    with open(rel_path, "w", encoding="utf-8") as fh:
        json.dump(rel, fh, indent=2)

    print(f"\n[replay] {result.taps} taps, {result.backs} backs, {result.relaunches} relaunches, "
          f"{result.verified} verified, {result.drifts} drifts, {result.resyncs} resyncs "
          f"in {elapsed:.1f}s ({elapsed / max(1, result.taps):.2f}s/tap)")
    print(f"[replay] stopped: {result.stop_reason}")
    print(f"[replay] reliability: {rel.get('level', '?').upper()} — {rel.get('message', '')}")
    print(f"wrote {log_path}, {args.out}_timeline.json and {rel_path}")

    if controller.timeline.records:
        ref = steps[0]["target"] if steps and steps[0].get("kind") == "tap" else None
        if ref is None:
            ref = next((s["target"] for s in steps if s.get("kind") == "tap"), None)
        if ref is not None:
            plot_timeline(controller.timeline, ref,
                          path=f"{args.out}_timeline.png", title=f"Replay ({args.profile})")
        if args.report:
            try:
                from engine.interactive_report import build_report
                rp = build_report(f"{args.out}_timeline.json", reliability=rel)
                print(f"wrote {rp}")
            except Exception as exc:
                print(f"[replay] report skipped: {exc}")


if __name__ == "__main__":
    main()
