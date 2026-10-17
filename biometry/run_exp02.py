"""EXP-02 — coupling ablation, on a device under C1's stressors.

Three arms of the same engine, identical seed, identical starting screen:

    noise-only      stress pinned at 0.00 — distortion floor, no coupling
    static-stress   stress pinned at 0.45 — coupled, but blind to the app
    full-adaptive   the Markov chain driven by the frame probe

If full-adaptive looks like noise-only on a misbehaving app, the coupling
pillar of CLAIM-01 is refuted; this harness exists to make that answer cheap
to obtain and honest to report either way.

Run it while C1's perturbation engine is stressing the app under test:

    ../.venv/bin/python run_exp02.py --actions 60 --seed 2026 \\
        --stressor "C1 cpu+latency preset B" --session pilot-1

Each arm writes its timeline JSON and figure into results/exp-02/<session>/,
plus one manifest.json recording device, package, density, stressor label,
arm order and timing — so the analysis can state its own provenance.
"""
import argparse
import json
import time
from pathlib import Path

from bridge.adb_bridge import ADBBridge
from bridge.device import AdbDispatcher
from bridge.frame_probe import FrameProbe
from bridge.hierarchy import parse_hierarchy, tappable_targets
from engine.controller import AdaptiveFeedbackController
from engine.visualise import plot_timeline
from models.cognitive import StaticStress
from models.profiles import build_engine

ARMS = {
    # name -> fixed stress level, or None for the adaptive chain
    "noise-only": 0.0,
    "static-stress": 0.45,
    "full-adaptive": None,
}


def read_px_per_mm(bridge):
    out = bridge.device.shell("wm", "density")
    dpi = next((float(tok) for tok in out.replace(":", " ").split()
                if tok.replace(".", "", 1).isdigit()), None)
    if dpi is None:
        raise SystemExit("could not read device density; pass --px-per-mm")
    return dpi / 25.4


def foreground_package(bridge):
    """The app under test. Falls back to mFocusedApp when a system window
    (notification shade, keyguard) holds focus without owning an app."""
    out = bridge.device.shell("dumpsys", "window")
    for key in ("mCurrentFocus", "mFocusedApp"):
        for line in out.splitlines():
            if key in line and "/" in line:
                token = next(t for t in reversed(line.split()) if "/" in t)
                return token.split("/")[0]
    raise SystemExit("could not determine the foreground package; pass --package")


def run_arm(name, level, args, bridge, package, px_per_mm, out_dir):
    """One arm: same seed, same profile, only the stress source differs."""
    simulator, cognitive = build_engine(args.profile, seed=args.seed,
                                        px_per_mm=px_per_mm)
    if level is not None:
        cognitive = StaticStress(level)

    targets = tappable_targets(parse_hierarchy(bridge.dump_ui_hierarchy()))
    if not targets:
        raise SystemExit(f"[{name}] no tappable elements on the current screen")

    controller = AdaptiveFeedbackController(
        simulator=simulator,
        cognitive=cognitive,
        probe=FrameProbe(bridge.device, package),
        dispatch=AdbDispatcher(bridge),
        run_id=f"exp02-{name}",
        persona_id=args.profile,
    )

    started = time.time()
    for i in range(args.actions):
        target = targets[i % len(targets)]
        record = controller.act(target.as_target())
        ui = "stalled" if record.ui_delay_ms is None else f"{record.ui_delay_ms:6.1f}ms"
        print(f"[{name:>13}] {i:3d} {record.cognitive_state:<10} "
              f"s={record.stress_s:.2f} ui={ui} "
              f"{'hit ' if record.hit_flag else 'MISS'} {target.element_id[:20]}")
    elapsed = time.time() - started

    stem = out_dir / f"{name}_timeline"
    controller.timeline.write_json(f"{stem}.json")
    try:
        plot_timeline(controller.timeline, targets[0].as_target(),
                      path=f"{stem}.png",
                      title=f"EXP-02 {name} — {args.stressor}")
    except Exception as exc:                      # a figure must never lose a run
        print(f"[{name}] figure skipped: {exc}")
    return {"arm": name, "fixed_stress": level, "actions": args.actions,
            "targets_on_screen": len(targets), "elapsed_s": round(elapsed, 1),
            "timeline": f"{stem}.json"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--actions", type=int, default=60)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--device", default=None)
    ap.add_argument("--package", default=None)
    ap.add_argument("--px-per-mm", type=float, default=None)
    ap.add_argument("--profile", default="default")
    ap.add_argument("--stressor", required=True,
                    help="what C1 is doing to the app, verbatim — goes in the manifest")
    ap.add_argument("--session", required=True,
                    help="subfolder under results/exp-02/, e.g. pilot-1")
    ap.add_argument("--arms", default=",".join(ARMS),
                    help="comma list; default runs all three")
    ap.add_argument("--settle", type=float, default=5.0,
                    help="seconds between arms, letting the app settle")
    args = ap.parse_args()

    bridge = ADBBridge(device_id=args.device)
    px_per_mm = args.px_per_mm or read_px_per_mm(bridge)
    package = args.package or foreground_package(bridge)

    out_dir = Path("results/exp-02") / args.session
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"{out_dir} already holds results — pick a new --session "
                         "rather than overwriting evidence")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[exp02] device {bridge.device_id} · {package} · "
          f"{px_per_mm:.2f} px/mm · stressor: {args.stressor}")

    manifest = {
        "experiment": "EXP-02 coupling ablation",
        "session": args.session,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "device": bridge.device_id,
        "package": package,
        "px_per_mm": round(px_per_mm, 3),
        "seed": args.seed,
        "profile": args.profile,
        "stressor": args.stressor,
        "arms": [],
    }
    for name in [a.strip() for a in args.arms.split(",") if a.strip()]:
        if name not in ARMS:
            raise SystemExit(f"unknown arm {name!r}; choose from {', '.join(ARMS)}")
        manifest["arms"].append(
            run_arm(name, ARMS[name], args, bridge, package, px_per_mm, out_dir))
        time.sleep(args.settle)

    manifest["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(out_dir / "manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"[exp02] session {args.session} complete -> {out_dir}/manifest.json")
    print("[exp02] reminder: copy C1's perturbation_event_log.json into the "
          "session folder for failure attribution.")


if __name__ == "__main__":
    main()
