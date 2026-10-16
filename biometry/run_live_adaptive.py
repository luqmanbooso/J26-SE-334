"""Run the adaptive loop against a real app on an attached device.

Everything here is the same engine the offline demonstration runs; only the two
adapters differ — touches go out over ADB and the screen signature is read from
the device instead of a stub.

    python run_live_adaptive.py --package com.google.android.dialer --actions 60
"""
import argparse

import numpy as np

from bridge.adb_bridge import ADBBridge
from bridge.device import AdbDispatcher
from bridge.frame_probe import FrameProbe
from bridge.hierarchy import parse_hierarchy, tappable_targets
from engine.controller import AdaptiveFeedbackController
from engine.visualise import plot_timeline
from models.cognitive import CognitiveStateModel, StaticStress
from simulation.simulator import BiometricSimulator


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
        for line in focus.splitlines():
            if "mCurrentFocus" in line and "/" in line:
                package = line.split()[-1].split("/")[0]
                break
    if not package:
        raise SystemExit("could not determine the foreground package; pass --package")
    print(f"[live] app under test: {package}")

    targets = tappable_targets(parse_hierarchy(bridge.dump_ui_hierarchy()))
    if not targets:
        raise SystemExit("no tappable elements on the current screen")
    print(f"[live] {len(targets)} tappable targets on screen")

    source = (StaticStress(args.stress) if args.static
              else CognitiveStateModel(rng=np.random.default_rng(args.seed)))

    controller = AdaptiveFeedbackController(
        simulator=BiometricSimulator(px_per_mm=px_per_mm, seed=args.seed),
        cognitive=source,
        probe=FrameProbe(bridge.device, package),
        dispatch=AdbDispatcher(bridge),
        run_id=f"live-{'static' if args.static else 'adaptive'}",
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
