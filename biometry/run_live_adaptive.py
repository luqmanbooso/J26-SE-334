"""Run the adaptive loop against a real app on an attached device.

Everything here is the same engine the offline demonstration runs; only the two
adapters differ — touches go out over ADB and the screen signature is read from
the device instead of a stub.

    python run_live_adaptive.py --package com.google.android.dialer --actions 60
"""
import argparse

from bridge.adb_bridge import ADBBridge
from bridge.oracle_client import OracleNotifier
from bridge.device import AdbDispatcher
from bridge.frame_probe import FrameProbe
from bridge.hierarchy import parse_hierarchy, tappable_targets
from engine.controller import AdaptiveFeedbackController
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

    package = args.package
    if package is None:
        focus = bridge.device.shell("dumpsys", "window")
        # mFocusedApp is the fallback: a system window (notification shade,
        # keyguard) can hold mCurrentFocus without owning an app.
        for key in ("mCurrentFocus", "mFocusedApp"):
            for line in focus.splitlines():
                if key in line and "/" in line:
                    package = next(t for t in reversed(line.split())
                                   if "/" in t).split("/")[0]
                    break
            if package:
                break
    if not package:
        raise SystemExit("could not determine the foreground package; pass --package")
    print(f"[live] app under test: {package}")

    targets = tappable_targets(parse_hierarchy(bridge.dump_ui_hierarchy()))
    if not targets:
        raise SystemExit("no tappable elements on the current screen")
    print(f"[live] {len(targets)} tappable targets on screen")

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

    for i in range(args.actions):
        target = targets[i % len(targets)]
        record = controller.act(target.as_target())
        print(f"  {i:>3} {record.cognitive_state:<11} s={record.stress_s:.2f} "
              f"ui={f'{record.ui_delay_ms:>7.1f}ms' if record.ui_delay_ms is not None else '  stalled'} "
              f"{'hit' if record.hit_flag else 'MISS'} "
              f"{target.element_id[:24]}")

    controller.timeline.write_json(f"{args.out}_timeline.json")
    plot_timeline(controller.timeline, targets[0].as_target(),
                  path=f"{args.out}_timeline.png",
                  title="Live adaptive run")
    print(f"\nwrote {args.out}_timeline.json and {args.out}_timeline.png")


if __name__ == "__main__":
    main()
