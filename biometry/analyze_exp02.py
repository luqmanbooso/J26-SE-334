"""EXP-02 analysis: turn a session's raw timelines into comparable evidence.

    ../.venv/bin/python analyze_exp02.py results/exp-02/mon-3g

Reads the session's manifest and per-arm timelines, aligns them against C1's
perturbation log when one is present (epoch_ms in his events vs each arm's
started_epoch_ms + t_ms here), and writes analysis.json + analysis.png back
into the session folder.

The script computes; it does not conclude. Whether the numbers support,
partially support or refute the coupling pillar of CLAIM-01 is written by the
researcher into the experiment note, from these outputs.

Pre-registered expectations (written 2026-10-17, before any session ran):
  - full-adaptive: stress should RISE while the app degrades under C1's
    profile and track it — misses, bursts and stalls increasing with it.
  - static arms: by construction their stress cannot move; any behavioural
    drift there measures the environment, not the model.
  - REFUTATION: if full-adaptive's behaviour is indistinguishable from
    noise-only under degradation, the coupling pillar fails. Say so.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

RESET_ACTIONS = {"ENVIRONMENT_FULL_RESET", "SYSTEM_RESET_NOMINAL",
                 "NETWORK_RESET_NOMINAL", "CONTEXT_RESET_DEFAULTS",
                 "INTERRUPTIONS_CLEARED", "CALL_TERMINATED"}


def load_arm(path):
    data = json.loads(Path(path).read_text())
    return data["records"]


def arm_metrics(records):
    ui = [r["ui_delay_ms"] for r in records if r.get("ui_delay_ms") is not None]
    stresses = [r["stress_s"] for r in records]
    return {
        "actions": len(records),
        "mean_stress": round(statistics.fmean(stresses), 3),
        "final_stress": round(stresses[-1], 3),
        "miss_rate": round(sum(not r["hit_flag"] for r in records) / len(records), 3),
        "mean_error_px": round(statistics.fmean(r["error_px"] for r in records), 1),
        "stalls": sum(not r["responded"] for r in records),
        "rage_bursts": sum(1 for r in records if r.get("rage_taps", 0)),
        "rage_extra_taps": sum(r.get("rage_taps", 0) for r in records),
        "hesitations": sum(1 for r in records if r.get("hesitation_s", 0) > 0),
        "mean_ui_delay_ms": round(statistics.fmean(ui), 1) if ui else None,
        "contended": sum(1 for r in records if r.get("contended")),
    }


def c1_events_during(events, start_ms, end_ms):
    """C1 log entries whose epoch falls inside one arm's run window."""
    return [e for e in events if start_ms <= e.get("epoch_ms", 0) <= end_ms]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("session", help="session folder, e.g. results/exp-02/mon-3g")
    args = ap.parse_args()

    session = Path(args.session)
    manifest = json.loads((session / "manifest.json").read_text())

    # C1's log: prefer the copy inside the session folder (provenance), fall
    # back to the repo-root live file with a warning.
    events = []
    for cand in (session / "perturbation_event_log.json",
                 Path(__file__).resolve().parent.parent / "perturbation_event_log.json"):
        if cand.exists():
            events = json.loads(cand.read_text())
            if cand.parent != session:
                print(f"[warn] using repo-root C1 log ({cand}) — copy it into "
                      f"the session folder for provenance")
            break
    if not events:
        print("[warn] no C1 perturbation log found — arm comparison only")

    arms, series = {}, {}
    for arm in manifest["arms"]:
        name = arm["arm"]
        records = load_arm(session / Path(arm["timeline"]).name)
        arms[name] = arm_metrics(records)
        arms[name]["fixed_stress"] = arm.get("fixed_stress")
        series[name] = [r["stress_s"] for r in records]

        start = arm.get("started_epoch_ms")
        if start is not None and events:
            end = start + int(arm.get("elapsed_s", 0) * 1000) + 1000
            during = c1_events_during(events, start, end)
            arms[name]["c1_events_during_arm"] = [
                {"t_offset_s": round((e["epoch_ms"] - start) / 1000, 1),
                 "action": e["action"], "category": e["category"]}
                for e in during]
            arms[name]["c1_resets_during_arm"] = sum(
                e["action"] in RESET_ACTIONS for e in during)

    # The comparisons the pre-registration names.
    comparison = {}
    if "full-adaptive" in arms and "noise-only" in arms:
        a, n = arms["full-adaptive"], arms["noise-only"]
        comparison["adaptive_vs_noise"] = {
            "stress_separation": round(a["mean_stress"] - n["mean_stress"], 3),
            "miss_rate_delta": round(a["miss_rate"] - n["miss_rate"], 3),
            "error_px_delta": round(a["mean_error_px"] - n["mean_error_px"], 1),
            "bursts_delta": a["rage_bursts"] - n["rage_bursts"],
        }
        try:  # effect evidence, not a verdict
            from scipy.stats import mannwhitneyu
            ea = [r["error_px"] for r in load_arm(
                session / "full-adaptive_timeline.json")]
            en = [r["error_px"] for r in load_arm(
                session / "noise-only_timeline.json")]
            stat, pval = mannwhitneyu(ea, en, alternative="two-sided")
            comparison["adaptive_vs_noise"]["error_mannwhitney_p"] = float(f"{pval:.4g}")
        except Exception as exc:
            comparison["adaptive_vs_noise"]["error_mannwhitney_p"] = f"unavailable: {exc}"

    out = {"experiment": "EXP-02 coupling ablation",
           "session": manifest.get("session"),
           "stressor": manifest.get("stressor"),
           "package": manifest.get("package"),
           "device": manifest.get("device"),
           "seed": manifest.get("seed"),
           "arms": arms,
           "comparison": comparison}
    (session / "analysis.json").write_text(json.dumps(out, indent=2))

    # --- figure: stress trajectories + behaviour counts --------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colours = {"noise-only": "#9aa0a6", "static-stress": "#e8a33d",
               "full-adaptive": "#0E7C86"}
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(11, 8))
    for name, s in series.items():
        top.plot(range(len(s)), s, label=name,
                 color=colours.get(name), linewidth=2)
    top.set_ylabel("stress $s$"); top.set_xlabel("action #")
    top.set_ylim(-0.02, 1.02); top.legend()
    top.set_title(f"EXP-02 {manifest.get('session')} — {manifest.get('stressor')}")

    names = list(arms)
    keys = ["miss_rate", "mean_stress"]
    for i, key in enumerate(keys):
        bottom.bar([x + i * 0.35 for x in range(len(names))],
                   [arms[n][key] for n in names], width=0.35,
                   label=key, color=["#0E7C86", "#e8a33d"][i])
    bottom.set_xticks([x + 0.17 for x in range(len(names))])
    bottom.set_xticklabels(names); bottom.legend()
    fig.tight_layout()
    fig.savefig(session / "analysis.png", dpi=130)

    print(json.dumps(out, indent=2))
    print(f"\nwrote {session}/analysis.json and {session}/analysis.png")


if __name__ == "__main__":
    main()
