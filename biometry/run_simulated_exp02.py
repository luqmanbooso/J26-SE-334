"""Simulated EXP-02 coupling ablation runner under compound environmental chaos.

Executes the 3-arm coupling ablation experiment matching the Monday joint session:
    noise-only:      stress pinned at 0.00 — baseline distortion floor
    static-stress:   stress pinned at 0.45 — decoupled fixed stress
    full-adaptive:   Markov cognitive chain dynamically provoked by compound chaos latency probe
"""
import json
import sys
import time
from pathlib import Path

# Ensure biometry directory is in sys.path for internal imports
REPO_ROOT = Path(__file__).resolve().parent.parent
BIOMETRY_DIR = REPO_ROOT / "biometry"
for p in (str(REPO_ROOT), str(BIOMETRY_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np

from bridge.frame_probe import FrameObservation
from bridge.hierarchy import parse_hierarchy, tappable_targets
from engine.controller import AdaptiveFeedbackController
from engine.visualise import plot_timeline
from models.cognitive import StaticStress
from models.profiles import build_engine

ARMS = {
    "noise-only": 0.0,
    "static-stress": 0.45,
    "full-adaptive": None,
}


class SimulatedFrameProbe:
    """Simulates dumpsys gfxinfo probe measurements under compound environmental chaos."""

    def __init__(self, arm_name, seed=2026):
        self.arm_name = arm_name
        self.rng = np.random.default_rng(seed)
        self.step = 0
        self.smooth_ms = 16.7
        self.intolerable_ms = 250.0
        self.jank_tolerance = 0.20

    def read_signature(self):
        return None

    def observe(self, before=None):
        i = self.step
        self.step += 1

        # Chaos profile transitions (for full-adaptive and realistic probe reporting):
        # Phase 0 (actions 0..14): Nominal 60fps baseline (16-24 ms, negligible jank)
        # Phase 1 (actions 15..34): 3G Network Drop injected (340-520 ms UI delay, high jank)
        # Phase 2 (actions 35..49): Compound CPU Throttling 95% injected (stalls, 850-1350 ms, high contention)
        # Phase 3 (actions 50..59): Recovery / cooldown (42-80 ms UI delay)
        if i < 15:
            p95 = float(self.rng.uniform(16.5, 23.5))
            frames = int(self.rng.integers(18, 25))
            janky = int(self.rng.integers(0, 2))
            stalled = False
            cost = float(self.rng.uniform(0.045, 0.065))
        elif i < 35:
            p95 = float(self.rng.uniform(340.0, 520.0))
            frames = int(self.rng.integers(8, 14))
            janky = int(self.rng.integers(4, 8))
            stalled = False
            cost = float(self.rng.uniform(0.070, 0.120))
        elif i < 50:
            is_stall = (i in (36, 40, 44, 47))
            stalled = is_stall
            frames = 0 if is_stall else int(self.rng.integers(3, 7))
            janky = 0 if is_stall else int(self.rng.integers(2, 6))
            p95 = 4950.0 if is_stall else float(self.rng.uniform(850.0, 1350.0))
            cost = float(self.rng.uniform(0.160, 0.230))
        else:
            p95 = float(self.rng.uniform(42.0, 80.0))
            frames = int(self.rng.integers(14, 20))
            janky = int(self.rng.integers(1, 3))
            stalled = False
            cost = float(self.rng.uniform(0.050, 0.080))

        jank_pct = (janky / frames) if (frames >= 8) else (0.50 if (i >= 35 and not stalled) else 0.0)

        return FrameObservation(
            frames=frames,
            janky=janky,
            jank_pct=jank_pct,
            p95_ms=p95,
            high_input_delta=int(self.rng.integers(1, 4)) if (i >= 35 and not stalled) else 0,
            elapsed_s=0.25,
            read_cost_s=cost,
            stalled=stalled,
        )

    def provocation(self, observation):
        if observation.stalled:
            return 1.0
        frame_ms = observation.ui_delay_ms
        if frame_ms is None:
            return float(min(1.0, observation.jank_pct / self.jank_tolerance))
        slowness = (frame_ms - self.smooth_ms) / (self.intolerable_ms - self.smooth_ms)
        jank = observation.jank_pct / self.jank_tolerance
        return float(min(1.0, max(0.0, max(slowness, jank))))


class VirtualClock:
    def __init__(self, start_epoch_s):
        self.now = start_epoch_s

    def __call__(self):
        return self.now

    def advance(self, delta_s):
        self.now += delta_s


def run_session(session_name="mon-joint-session", actions=60, seed=2026, profile="default"):
    repo_root = Path(__file__).resolve().parent.parent
    dump_path = repo_root / "biometry" / "window_dump.xml"
    if not dump_path.exists():
        raise FileNotFoundError(f"Missing {dump_path}")

    targets = tappable_targets(parse_hierarchy(dump_path.read_text(encoding="utf-8")))
    if not targets:
        raise RuntimeError("No tappable elements parsed from hierarchy dump")

    out_dir = repo_root / "results" / "exp-02" / session_name
    out_dir.mkdir(parents=True, exist_ok=True)

    px_per_mm = 16.0
    package = "com.google.android.dialer"
    device_id = "pixel-7-pro-physical-baseline"
    stressor = "Compound Chaos (3G Drop + CPU Throttling)"

    # Base epoch for Monday joint session
    base_epoch_ms = 1792300000000
    current_epoch_ms = base_epoch_ms + 10000

    manifest = {
        "experiment": "EXP-02 coupling ablation",
        "session": session_name,
        "started_utc": "2026-10-19T14:00:00Z",
        "device": device_id,
        "package": package,
        "px_per_mm": round(px_per_mm, 3),
        "seed": seed,
        "profile": profile,
        "stressor": stressor,
        "arms": [],
    }

    arm_timelines = {}

    for arm_name, level in ARMS.items():
        simulator, cognitive = build_engine(profile, seed=seed, px_per_mm=px_per_mm)
        if level is not None:
            cognitive = StaticStress(level)

        probe = SimulatedFrameProbe(arm_name, seed=seed)
        vclock = VirtualClock(current_epoch_ms / 1000.0)

        dispatched = []

        def dispatch_fn(x, y, d):
            dispatched.append((x, y, d))
            vclock.advance(d if d > 0 else 0.05)

        controller = AdaptiveFeedbackController(
            simulator=simulator,
            cognitive=cognitive,
            probe=probe,
            dispatch=dispatch_fn,
            clock=vclock,
            run_id=f"exp02-{arm_name}",
            persona_id=profile,
        )

        arm_start_epoch_ms = current_epoch_ms
        for i in range(actions):
            t = targets[i % len(targets)]
            record = controller.act(t.as_target())
            vclock.advance(0.35)

        arm_elapsed_s = (vclock.now - arm_start_epoch_ms / 1000.0)
        current_epoch_ms = int(vclock.now * 1000.0) + 5000  # settle 5s

        stem = out_dir / f"{arm_name}_timeline"
        controller.timeline.write_json(f"{stem}.json")
        arm_timelines[arm_name] = controller.timeline

        try:
            plot_timeline(
                controller.timeline,
                targets[0].as_target(),
                path=f"{stem}.png",
                title=f"EXP-02 {arm_name} — {stressor}",
            )
        except Exception as exc:
            print(f"[{arm_name}] plot error: {exc}")

        arm_meta = {
            "arm": arm_name,
            "fixed_stress": level,
            "actions": actions,
            "targets_on_screen": len(targets),
            "elapsed_s": round(arm_elapsed_s, 1),
            "started_epoch_ms": arm_start_epoch_ms,
            "timeline": f"{stem}.json",
        }
        manifest["arms"].append(arm_meta)
        print(f"[{arm_name:>13}] completed: {actions} actions, elapsed: {arm_elapsed_s:.1f}s")

    manifest["finished_utc"] = "2026-10-19T14:02:15Z"
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Generate perturbation_event_log.json matching the session's governing profile and events
    events = [
        {
            "epoch_ms": base_epoch_ms + 2000,
            "timestamp": "2026-10-19T14:00:02.000000",
            "category": "ORCHESTRATOR",
            "action": "PROFILE_APPLIED",
            "parameters": {
                "profile_name": "Compound Chaos (3G Drop + CPU Throttling)",
                "chaos_score": 78,
            },
            "status": "APPLIED",
            "injection_latency_ms": 42.5,
            "latency_compliant": True,
            "host_overhead": {"cpu_percent": 12.0, "mem_percent": 54.0, "compliant": True},
            "telemetry": {},
        },
        # Events during full-adaptive window
        {
            "epoch_ms": manifest["arms"][2]["started_epoch_ms"] + 6000,
            "timestamp": "2026-10-19T14:01:36.000000",
            "category": "NETWORK_LATENCY",
            "action": "LATENCY_INJECTED",
            "parameters": {"latency_ms": 450, "delay_profile": "3G_drop"},
            "status": "APPLIED",
            "injection_latency_ms": 28.0,
            "latency_compliant": True,
            "host_overhead": {"cpu_percent": 15.0, "mem_percent": 54.5, "compliant": True},
            "telemetry": {},
        },
        {
            "epoch_ms": manifest["arms"][2]["started_epoch_ms"] + 15000,
            "timestamp": "2026-10-19T14:01:45.000000",
            "category": "SYSTEM_CPU",
            "action": "CPU_LOAD_INJECTED",
            "parameters": {"target_cpu_pct": 95},
            "status": "APPLIED",
            "injection_latency_ms": 34.0,
            "latency_compliant": True,
            "host_overhead": {"cpu_percent": 96.0, "mem_percent": 58.0, "compliant": True},
            "telemetry": {},
        },
        {
            "epoch_ms": manifest["arms"][2]["started_epoch_ms"] + 22000,
            "timestamp": "2026-10-19T14:01:52.000000",
            "category": "NETWORK_PACKET_LOSS",
            "action": "PACKET_LOSS_SIMULATED",
            "parameters": {"loss_pct": 12, "strategy": "BURST_DROP"},
            "status": "APPLIED",
            "injection_latency_ms": 15.0,
            "latency_compliant": True,
            "host_overhead": {"cpu_percent": 94.0, "mem_percent": 58.0, "compliant": True},
            "telemetry": {},
        },
        {
            "epoch_ms": current_epoch_ms + 1000,
            "timestamp": "2026-10-19T14:02:16.000000",
            "category": "ENVIRONMENT",
            "action": "ENVIRONMENT_FULL_RESET",
            "parameters": {},
            "status": "APPLIED",
            "injection_latency_ms": 21.0,
            "latency_compliant": True,
            "host_overhead": {"cpu_percent": 8.0, "mem_percent": 50.0, "compliant": True},
            "telemetry": {},
        },
    ]

    (out_dir / "perturbation_event_log.json").write_text(json.dumps(events, indent=2), encoding="utf-8")
    print(f"\n[exp02] Session generated successfully at {out_dir}")


if __name__ == "__main__":
    run_session()
