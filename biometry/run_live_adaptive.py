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
import time

from bridge.adb_bridge import ADBBridge
from bridge.oracle_client import OracleNotifier
from bridge.device import AdbDispatcher, foreground_activity, foreground_package
from bridge.frame_probe import FrameProbe
from bridge.hierarchy import (frame_signature, full_signature, parse_hierarchy,
                              structural_signature, tappable_targets)
from engine.controller import AdaptiveFeedbackController
from engine.explorer import AppExplorer
from engine.fingerprint import ahash
from engine.visualise import plot_timeline
from models.cognitive import StaticStress
from models.profiles import PROFILES, build_engine


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--actions", type=int, default=None,
                    help="number of taps; omit for unlimited — explore until the "
                         "whole reachable app is exhausted (default)")
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
    ap.add_argument("--accurate", action="store_true",
                    help="MAP MODE: tap calmly and accurately regardless of --profile/--stress "
                         "so taps land and the whole app is discovered. Use this when the run's "
                         "only job is to produce a plan for replay_live.py; the persona is then "
                         "chosen at replay, not here.")
    ap.add_argument("--oracle-url", default=None,
                    help="C3 oracle base URL (e.g. http://127.0.0.1:8000); "
                         "when set, every completed action triggers a capture "
                         "(IF-C2-to-C3)")
    ap.add_argument("--sequential", action="store_true",
                    help="legacy mode: cycle the initial screen's targets in "
                         "place instead of exploring (parity with run_exp02)")
    ap.add_argument("--max-depth", type=int, default=None,
                    help="deepest screen to descend to; omit for unlimited (default)")
    ap.add_argument("--signature", choices=["auto", "structural", "frame", "full"],
                    default="auto",
                    help="screen identity for the cache: 'auto' tells screens "
                         "apart by layout and merges in-place chip/tab swaps "
                         "(default), 'structural' makes every content state its "
                         "own screen, 'frame' uses the control set, 'full' hashes "
                         "the whole dump")
    ap.add_argument("--no-launch", action="store_true",
                    help="do not bring --package to the foreground first; explore "
                         "whatever is already on screen")
    ap.add_argument("--reset", action="store_true",
                    help="`pm clear` the app before launching, so the run starts from a "
                         "fresh install state (logged out, onboarding shown). Use the same "
                         "flag on replay_live so the saved onboarding/login flow matches — "
                         "otherwise mapping the login *logs you in*, and a later replay that "
                         "cold-starts straight to home diverges from the plan at step 0.")
    ap.add_argument("--no-relaunch", action="store_true",
                    help="do not relaunch the app if Back leaves it; just stop")
    ap.add_argument("--max-relaunches", type=int, default=5,
                    help="how many times the app may be relaunched to continue")
    ap.add_argument("--fill-forms", action="store_true",
                    help="type a placeholder into text fields on each screen "
                         "before tapping, so a login/sign-up whose submit only "
                         "needs non-empty boxes is passed instead of looping")
    ap.add_argument("--settle", type=float, default=None,
                    help="seconds to wait for the UI to settle after each tap/back "
                         "(default 0.4, or 0.6 under --fast)")
    ap.add_argument("--stable-tries", type=int, default=None,
                    help="max re-dumps to confirm a screen stopped changing; lower = "
                         "faster but a slow-rendering app may split a screen "
                         "(default 3, or 2 under --fast)")
    ap.add_argument("--stable-interval", type=float, default=None,
                    help="seconds between those stability re-dumps "
                         "(default 0.4, or 0.2 under --fast)")
    ap.add_argument("--dump-retries", type=int, default=3,
                    help="retries on a transient empty/failed dump before giving up")
    ap.add_argument("--fast", action="store_true",
                    help="speed preset for watching a run: settle 0.6, stable-tries 2, "
                         "stable-interval 0.2 (overridden by any explicit value)")
    ap.add_argument("--confirm-stay", dest="confirm_stay", action="store_true", default=True,
                    help="re-check an apparent no-op tap after a grace delay before trusting "
                         "it — rescues slow (async / Jetpack Compose) navigations that would "
                         "otherwise be dropped, making the app look exhausted after only a few "
                         "taps. On by default for fuller whole-app coverage.")
    ap.add_argument("--no-confirm-stay", dest="confirm_stay", action="store_false",
                    help="disable the confirm-stay re-check (faster; for snappy apps)")
    ap.add_argument("--stay-grace", type=float, default=None,
                    help="seconds to wait before re-checking an apparent no-op tap "
                         "(default: max(1.0, 2*settle); raise it for a very slow app)")
    ap.add_argument("--out", default="results/live_run")
    args = ap.parse_args()

    # Resolve speed knobs: explicit value wins, else the --fast preset, else normal.
    def _pick(value, fast_value, normal):
        return value if value is not None else (fast_value if args.fast else normal)
    args.settle = _pick(args.settle, 0.6, 0.4)
    args.stable_tries = _pick(args.stable_tries, 2, 3)
    args.stable_interval = _pick(args.stable_interval, 0.2, 0.4)

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

    # The traversal reads whatever screen is in front, so a named package has to
    # be brought to the foreground first — otherwise the run explores the
    # launcher (or whatever happened to be open) instead of the app asked for.
    # An auto-detected run skips this: it means "explore what is already here".
    if args.reset and package:
        print(f"[live] reset: pm clear {package} (fresh state)")
        bridge.device.run("shell", "pm", "clear", package)
    # Cold-start when a package was named, or whenever --reset was used: a reset
    # pm-clears the app, so without a relaunch the foreground is the *launcher* and
    # the crawl would map the home screen. Only an explicit --no-launch (or a plain
    # auto-detected run with no reset) means "explore what is already open".
    if package and not args.no_launch and (args.package or args.reset):
        print(f"[live] launching {package} to the foreground (cold start)")
        bridge.launch_package(package)
        # Wait until the app under test is *itself* foreground AND has tappable
        # targets — not the launcher (foreground right after a pm clear, and it has
        # its own tappable icons) and not a bare splash with nothing to tap.
        for _ in range(15):
            if (foreground_package(bridge.device) == package
                    and tappable_targets(parse_hierarchy(bridge.dump_ui_hierarchy()))):
                break
            time.sleep(1.0)
        landed = foreground_package(bridge.device)
        if landed and landed != package:
            print(f"[live] warning: foreground is {landed}, not {package} "
                  f"(launch may have failed or the device is locked)")

    simulator, source = build_engine(args.profile, seed=args.seed, px_per_mm=px_per_mm)
    if args.static:
        source = StaticStress(args.stress)
    if args.accurate:
        # Mapping must land its taps to discover the app, so ignore the persona
        # entirely — both the cognitive stress (→ 0.0) *and* the profile's motor
        # params (tremor etc.) → the default simulator. The plan stores clean
        # target centres, so the chosen persona is re-applied later by
        # replay_live.py, never baked into the map.
        simulator, _ = build_engine("default", seed=args.seed, px_per_mm=px_per_mm)
        source = StaticStress(0.0)
        print("[live] accurate map mode: persona ignored, tapping calmly (stress 0.0, default motor)")
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
        # Cycling a fixed list "unlimited" times is meaningless, so legacy mode
        # keeps a concrete count (the historical default when --actions is omitted).
        seq_actions = args.actions if args.actions is not None else 60
        print(f"[live] sequential over {len(targets)} targets on screen "
              f"({seq_actions} taps)")
        for i in range(seq_actions):
            target = targets[i % len(targets)]
            record = controller.act(target.as_target())
            _row(i, record.cognitive_state, record.stress_s, record.ui_delay_ms,
                 record.hit_flag, target.element_id[:30])
        ref_target = targets[0].as_target()
        title = "Live adaptive run"
    else:
        base_signature = {"auto": structural_signature,
                          "structural": structural_signature,
                          "frame": frame_signature, "full": full_signature}[args.signature]
        merge_swaps = args.signature == "auto"

        def reporter(index, label, record, event, depth):
            _row(index, record.cognitive_state, record.stress_s, record.ui_delay_ms,
                 record.hit_flag, label, suffix=f"  d{depth} {event}")

        explorer = AppExplorer(
            controller=controller,
            dump=bridge.dump_ui_hierarchy,
            press_back=bridge.press_back,
            base_signature=base_signature,
            merge_swaps=merge_swaps,
            current_package=lambda: foreground_package(bridge.device),
            app_package=package,
            relaunch=(None if args.no_relaunch
                      else (lambda: bridge.launch_package(package))),
            max_actions=args.actions,
            max_depth=args.max_depth,
            max_relaunches=args.max_relaunches,
            settle_s=args.settle,
            stable_tries=args.stable_tries,
            stable_interval=args.stable_interval,
            dump_retries=args.dump_retries,
            reporter=reporter,
            type_text=bridge.set_text,
            fill_forms=args.fill_forms,
            confirm_stay=args.confirm_stay,
            stay_grace_s=args.stay_grace,
            # Snapshot a cheap screen fingerprint per screen so the run also
            # emits a compiled plan that replay_live.py can walk fast later.
            fingerprint=lambda: ahash(bridge.device.screencap(as_pil=True)),
            # ...and the foreground activity per tap, so replay can verify the
            # screen by activity name (robust, pixel-free) rather than a screenshot.
            activity=lambda: foreground_activity(bridge.device),
        )
        print("[live] exploring "
              f"(actions={'unlimited' if args.actions is None else args.actions}, "
              f"max-depth={'unlimited' if args.max_depth is None else args.max_depth}, "
              f"signature={args.signature}, "
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

        # Compiled plan: the ordered device-action stream + a fingerprint per
        # screen, so `replay_live.py` can re-walk this traversal fast (no dumps)
        # as any persona. See [[ReplayEngine]].
        plan_doc = {
            "app_package": package,
            "px_per_mm": px_per_mm,
            "map": {"profile": args.profile, "seed": args.seed,
                    "signature": args.signature, "stop_reason": result.stop_reason,
                    "taps": result.actions},
            "fingerprints": result.fingerprints,
            "steps": result.plan,
        }
        with open(f"{args.out}_plan.json", "w", encoding="utf-8") as fh:
            json.dump(plan_doc, fh, indent=2)
        print(f"wrote {args.out}_plan.json "
              f"({len(result.plan)} actions, {len(result.fingerprints)} fingerprints)")

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
