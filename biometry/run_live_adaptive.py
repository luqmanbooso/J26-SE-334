"""Run the adaptive loop against a real app on an attached device.

Everything here is the same engine the offline demonstration runs; only the two
adapters differ — touches go out over ADB and the screen signature is read from
the device instead of a stub.

    python run_live_adaptive.py --package com.google.android.dialer --actions 60
"""
import argparse

import numpy as np

from bridge.adb_bridge import ADBBridge
from bridge.device import AdbDispatcher, live_probe
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
    ap.add_argument("--out", default="results/live_run")
    args = ap.parse_args()

    bridge = ADBBridge(device_id=args.device)
    targets = tappable_targets(parse_hierarchy(bridge.dump_ui_hierarchy()))
    if not targets:
        raise SystemExit("no tappable elements on the current screen")
    print(f"[live] {len(targets)} tappable targets on screen")

    source = (StaticStress(args.stress) if args.static
              else CognitiveStateModel(rng=np.random.default_rng(args.seed)))

    controller = AdaptiveFeedbackController(
        simulator=BiometricSimulator(seed=args.seed),
        cognitive=source,
        probe=live_probe(bridge, poll_interval=0.08, timeout=2.5),
        dispatch=AdbDispatcher(bridge),
        run_id=f"live-{'static' if args.static else 'adaptive'}",
    )

    for i in range(args.actions):
        target = targets[i % len(targets)]
        record = controller.act(target.as_target())
        print(f"  {i:>3} {record.cognitive_state:<11} s={record.stress_s:.2f} "
              f"ui={record.ui_delay_ms:>7.1f}ms {'hit' if record.hit_flag else 'MISS'} "
              f"{target.element_id[:24]}")

    controller.timeline.write_json(f"{args.out}_timeline.json")
    plot_timeline(controller.timeline, targets[0].as_target(),
                  path=f"{args.out}_timeline.png",
                  title="Live adaptive run")
    print(f"\nwrote {args.out}_timeline.json and {args.out}_timeline.png")


if __name__ == "__main__":
    main()
