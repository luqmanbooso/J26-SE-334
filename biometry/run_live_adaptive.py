"""Run the adaptive loop against a real app on an attached device.

Everything here is the same engine the offline demonstration runs; only the two
adapters differ — touches go out over ADB and the screen signature is read from
the device instead of a stub.

    python run_live_adaptive.py --package com.google.android.dialer --actions 60

By default the run *explores*: it taps every reachable target, follows
navigations into new screens, and uses Android Back to climb out, exhausting
the app recursively. `--sequential` restores the old behaviour of cycling the
first screen's targets in place (kept for parity with the ablation harness).
"""
import argparse
import json

from bridge.adb_bridge import ADBBridge
from bridge.oracle_client import OracleNotifier
from bridge.device import AdbDispatcher, foreground_package
from bridge.frame_probe import FrameProbe
from bridge.hierarchy import (full_signature, parse_hierarchy,
                              structural_signature, tappable_targets)
from engine.controller import AdaptiveFeedbackController
from engine.explorer import AppExplorer
from engine.visualise import plot_timeline
from models.cognitive import StaticStress
from models.profiles import PROFILES, build_engine


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--actions", type=int, default=60)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--device", default=None, help="adb device serial")
    ap.add_argument("--static", action="store_true",
                    help="use a fixed stress level — the ablation's control arm")
    ap.add_argument("--stress", type=float, default=0.05, help="level for --static")
    ap.add_argument("--px-per-mm", type=float, default=None,
                    help="device scale; read from the device when omitted")
    ap.add_argument("--package", default=None,
                    help="app under test; read from the foreground window when omitted")
    ap.add_argument("--profile", default="default", choices=sorted(PROFILES),
                    help="named behaviour profile (IF-Orchestrator-to-C2)")
    ap.add_argument("--oracle-url", default=None,
                    help="C3 oracle base URL (e.g. http://127.0.0.1:8000); "
                         "when set, every completed action triggers a capture "
                         "(IF-C2-to-C3)")
    ap.add_argument("--sequential", action="store_true",
                    help="legacy mode: cycle the initial screen's targets in "
                         "place instead of exploring (parity with run_exp02)")
    ap.add_argument("--max-depth", type=int, default=16,
                    help="deepest screen the explorer descends to")
    ap.add_argument("--signature", choices=["structural", "full"],
                    default="structural",
                    help="screen identity for the visited/exhausted cache: "
                         "'structural' ignores volatile text (default), 'full' "
                         "hashes the whole dump")
    ap.add_argument("--no-relaunch", action="store_true",
                    help="do not relaunch the app if Back leaves it; just stop")
    ap.add_argument("--max-relaunches", type=int, default=5,
                    help="how many times the app may be relaunched to continue")
    ap.add_argument("--settle", type=float, default=0.4,
                    help="seconds to wait for the UI to settle after each tap/back")
    ap.add_argument("--out", default="results/live_run")
    args = ap.parse_args()

    bridge = ADBBridge(device_id=args.device)

    # The spatial model is calibrated in millimetres against published data, so
    # the pixel scale has to be this device's, not an assumed one. Android
    # reports density in dpi; 25.4 mm to the inch.
    px_per_mm = args.px_per_mm
    if px_per_mm is None:
        out = bridge.device.shell("wm", "density")
        dpi = next((float(tok) for tok in out.replace(":", " ").split()
                    if tok.replace(".", "", 1).isdigit()), None)
        if dpi is None:
            raise SystemExit("could not read device density; pass --px-per-mm")
        px_per_mm = dpi / 25.4
        print(f"[live] device density {dpi:.0f} dpi -> {px_per_mm:.2f} px/mm")

    package = args.package or foreground_package(bridge.device)
    if not package:
        raise SystemExit("could not determine the foreground package; pass --package")
    print(f"[live] app under test: {package}")

    simulator, source = build_engine(args.profile, seed=args.seed, px_per_mm=px_per_mm)
    if args.static:
        source = StaticStress(args.stress)
    print(f"[live] behaviour profile: {args.profile}")

    notify = None
    if args.oracle_url:
        notify = OracleNotifier(args.oracle_url,
                                session_id=f"live-{args.profile}-{args.seed}",
                                device_serial=bridge.device_id)
        print(f"[live] triggering C3 oracle at {notify.url}")

    controller = AdaptiveFeedbackController(
        simulator=simulator,
        cognitive=source,
        probe=FrameProbe(bridge.device, package),
        dispatch=AdbDispatcher(bridge),
        notify=notify,
        run_id=f"live-{'static' if args.static else 'adaptive'}",
        persona_id=args.profile,
    )

    def _row(index, state, stress_s, ui_delay_ms, hit, label, suffix=""):
        ui = f"{ui_delay_ms:>7.1f}ms" if ui_delay_ms is not None else "  stalled"
        print(f"  {index:>3} {state:<11} s={stress_s:.2f} ui={ui} "
              f"{'hit' if hit else 'MISS'} {label:<30}{suffix}")

    if args.sequential:
        # Legacy control path: cycle the first screen's targets in place. Keeps
        # byte-for-byte parity with the ablation harness (run_exp02) which does
        # the same, so the two runs stay directly comparable.
        targets = tappable_targets(parse_hierarchy(bridge.dump_ui_hierarchy()))
        if not targets:
            raise SystemExit("no tappable elements on the current screen")
        print(f"[live] sequential over {len(targets)} targets on screen")
        for i in range(args.actions):
            target = targets[i % len(targets)]
            record = controller.act(target.as_target())
            _row(i, record.cognitive_state, record.stress_s, record.ui_delay_ms,
                 record.hit_flag, target.element_id[:30])
        ref_target = targets[0].as_target()
        title = "Live adaptive run"
    else:
        signature_fn = structural_signature if args.signature == "structural" else full_signature

        def reporter(index, label, record, event, depth):
            _row(index, record.cognitive_state, record.stress_s, record.ui_delay_ms,
                 record.hit_flag, label, suffix=f"  d{depth} {event}")

        explorer = AppExplorer(
            controller=controller,
            dump=bridge.dump_ui_hierarchy,
            press_back=bridge.press_back,
            signature_fn=signature_fn,
            current_package=lambda: foreground_package(bridge.device),
            app_package=package,
            relaunch=(None if args.no_relaunch
                      else (lambda: bridge.launch_package(package))),
            max_actions=args.actions,
            max_depth=args.max_depth,
            max_relaunches=args.max_relaunches,
            settle_s=args.settle,
            reporter=reporter,
        )
        print(f"[live] exploring (signature={args.signature}, "
              f"max-depth={args.max_depth}, "
              f"relaunch={'off' if args.no_relaunch else 'on'})")
        result = explorer.run()
        ref_target = result.first_target

        log_path = f"{args.out}_traversal.log"
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(result.log_lines) + "\n")
        graph = result.to_dict()
        graph["app_package"] = package
        with open(f"{args.out}_traversal.json", "w", encoding="utf-8") as fh:
            json.dump(graph, fh, indent=2)

        print(f"\n[explore] {result.screens_discovered} screens discovered, "
              f"{result.screens_exhausted} exhausted, {result.actions} taps, "
              f"{result.navigations} navigations, {result.relaunches} relaunches")
        print(f"[explore] stopped: {result.stop_reason}")
        print(f"wrote {log_path} and {args.out}_traversal.json")
        title = "Live adaptive run (recursive exploration)"

    controller.timeline.write_json(f"{args.out}_timeline.json")
    if controller.timeline.records and ref_target is not None:
        plot_timeline(controller.timeline, ref_target,
                      path=f"{args.out}_timeline.png", title=title)
        print(f"wrote {args.out}_timeline.json and {args.out}_timeline.png")
    else:
        print(f"wrote {args.out}_timeline.json (no actions recorded; figure skipped)")


if __name__ == "__main__":
    main()
