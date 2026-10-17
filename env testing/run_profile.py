"""Convenience CLI to apply a C1 environmental perturbation profile on cue and reset cleanly on exit.

Usage:
    python "env testing/run_profile.py" "env testing/profiles/3g_network_drop.yaml"
    python "env testing/run_profile.py" "env testing/profiles/compound_multi_factor_chaos.yaml" --duration 120
    python "env testing/run_profile.py" "env testing/profiles/3g_network_drop.yaml" \
        --exec "cd biometry && ../.venv/bin/python run_exp02.py --actions 60 --seed 2026 --stressor 3g_network_drop.yaml --session mon-3g"
"""
import argparse
import os
import sys
import time
import subprocess
import shutil

# Ensure workspace and env testing are on sys.path
sys_dir = os.path.dirname(os.path.abspath(__file__))
if sys_dir not in sys.path:
    sys.path.insert(0, sys_dir)

from orchestrator import PerturbationOrchestrator


def main():
    parser = argparse.ArgumentParser(description="Apply C1 Perturbation Profile on cue")
    parser.add_argument("profile", help="Path to YAML profile (e.g. env testing/profiles/3g_network_drop.yaml)")
    parser.add_argument("--duration", type=int, default=None, help="Auto-reset after N seconds (default: wait for Enter/Ctrl+C)")
    parser.add_argument("--exec", dest="exec_cmd", default=None, help="Execute command while profile is active, then automatically reset")
    parser.add_argument("--copy-log-to", default=None, help="Copy perturbation_event_log.json to target dir/file on completion")
    args = parser.parse_args()

    if not os.path.exists(args.profile):
        print(f"[!] Error: Profile not found: {args.profile}")
        sys.exit(1)

    orch = PerturbationOrchestrator(log_path="perturbation_event_log.json")

    try:
        print(f"\n=======================================================")
        print(f"  C1 Environmental Perturbation Runner")
        print(f"  Target Profile: {args.profile}")
        print(f"=======================================================")
        orch.load_profile_file(args.profile)
        print(f"[OK] Profile applied successfully. Chaos active.\n")

        if args.exec_cmd:
            print(f"[+] Running wrapped command: {args.exec_cmd}")
            proc = subprocess.run(args.exec_cmd, shell=True)
            exit_code = proc.returncode
        elif args.duration:
            print(f"[+] Holding perturbation for {args.duration} seconds...")
            time.sleep(args.duration)
        else:
            print("[+] Perturbation is active. Press ENTER or Ctrl+C to stop and revert device...")
            try:
                input()
            except EOFError:
                pass

    except KeyboardInterrupt:
        print("\n[*] Interrupted by user.")
    finally:
        orch.reset_all()
        print("[OK] All environmental stressors reverted back to nominal baseline.")

        if args.copy_log_to:
            src = "perturbation_event_log.json"
            if os.path.exists(src):
                dest = args.copy_log_to
                if os.path.isdir(dest):
                    dest = os.path.join(dest, "perturbation_event_log.json")
                shutil.copy2(src, dest)
                print(f"[OK] Copied perturbation log to: {dest}")

    if args.exec_cmd:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
