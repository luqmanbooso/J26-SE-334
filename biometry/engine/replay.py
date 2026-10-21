"""Compiled-path replay: re-walk a mapped traversal fast, as any persona.

`run_live_adaptive.py` writes a ``<out>_plan.json`` — the ordered device-action
stream (tap / back / relaunch / settext) plus one cheap fingerprint per screen.
This module walks that plan again on the device **without a single
`uiautomator dump`** (the ~2.5 s/step cost that makes a live crawl slow). Every
tap still goes through the same `AdaptiveFeedbackController`, so the biometric
distortion and the timeline are produced exactly as in a live run — only the
expensive *discovery* is skipped, because the plan already knows what to tap.

Robustness: before trusting a saved tap coordinate, replay optionally confirms
it is still on the screen the plan expects by comparing a fresh screenshot
fingerprint (≈0.6 s) against the saved one (cheap — see `engine/fingerprint`).
On drift it relaunches and fast-forwards the prefix with raw taps to resync, and
if it still cannot, it stops cleanly instead of tapping blindly. So it does not
"break every time" on a non-deterministic app; worst case it ends early and says
so.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from engine.fingerprint import DEFAULT_MAX_DISTANCE, distance, matches


@dataclass
class ReplayResult:
    timeline: object
    stop_reason: str
    taps: int = 0
    backs: int = 0
    relaunches: int = 0
    drifts: int = 0
    resyncs: int = 0
    verified: int = 0
    log_lines: list = field(default_factory=list)


class ReplayEngine:
    """Walk a compiled plan on the device, re-running biometrics per persona.

    Injected collaborators (so it runs headless in tests):
      - ``controller`` — the AdaptiveFeedbackController; ``controller.act(target)``
        distorts + dispatches the tap and appends to its timeline.
      - ``press_back`` / ``relaunch`` / ``set_text`` — device actions the plan
        replays verbatim (``set_text`` optional).
      - ``raw_tap(x, y)`` — a *plain* tap used only to fast-forward a prefix during
        a resync, so resync navigation is not recorded as behaviour.
      - ``fingerprint_fn()`` — returns the current screen's fingerprint (or "").
      - ``await_ready()`` — optional; called after a (re)launch to wait for the
        first screen (falls back to a fixed sleep).
    """

    def __init__(self, plan, controller, *, press_back, relaunch=None,
                 set_text=None, raw_tap=None, fingerprint_fn=None,
                 current_package=None, app_package=None,
                 await_ready=None, verify=True,
                 max_distance=DEFAULT_MAX_DISTANCE, settle_s=0.3,
                 verify_grace_s=None, verify_tries=6, launch_wait_s=2.0,
                 max_resyncs=3, on_drift="relaunch", sleep=time.sleep, reporter=None):
        self.steps = list(plan.get("steps", []))
        self.fingerprints = dict(plan.get("fingerprints", {}))
        self.controller = controller
        self.press_back = press_back
        self.relaunch = relaunch
        self.set_text = set_text
        self.raw_tap = raw_tap
        self.fingerprint_fn = fingerprint_fn
        self.current_package = current_package   # () -> foreground package, or None
        self.app_package = app_package           # the app under test
        self.await_ready = await_ready
        self.verify = verify and fingerprint_fn is not None
        self.max_distance = max_distance
        self.settle_s = settle_s
        # A screen may not have finished rendering/animating when we first look
        # (e.g. an onboarding splash with a moving background settles over a few
        # seconds), so an apparent mismatch is re-sampled a few times before it
        # counts as drift. verify_grace_s bounds that total wait.
        self.verify_grace_s = (verify_grace_s if verify_grace_s is not None
                               else max(4.0, 5.0 * settle_s))
        self.verify_tries = max(2, verify_tries)
        self.launch_wait_s = launch_wait_s
        self.max_resyncs = max_resyncs
        self.on_drift = on_drift          # "relaunch" | "stop" | "skip"
        self.sleep = sleep
        self.reporter = reporter

        self._log = []
        self._taps = self._backs = self._relaunches = 0
        self._drifts = self._resyncs = self._verified = 0
        self._tap_index = 0               # taps actually executed (for reporter)
        self._just_filled = False         # a form was just typed into (skip next verify)

    def _line(self, text):
        self._log.append(text)

    # --- device actions -----------------------------------------------------
    def _do_back(self):
        self.press_back()
        self._backs += 1
        self.sleep(self.settle_s)

    def _do_relaunch(self):
        if self.relaunch is None:
            return
        self._just_filled = False         # fresh launch — nothing typed yet
        self.relaunch()
        self._relaunches += 1
        if self.await_ready is not None:
            self.await_ready()
        else:
            self.sleep(self.launch_wait_s)

    def _do_settext(self, step):
        # Typing changes the screen's appearance, so the next tap (the form submit)
        # must not be fingerprint-verified against the empty-form screenshot the
        # mapper captured — that would false-drift and strand us on the login.
        self._just_filled = True
        if self.set_text is not None:
            self.set_text(step.get("x", 0), step.get("y", 0), step.get("text", ""))
            self.sleep(0.2)

    def _grab(self):
        try:
            return self.fingerprint_fn() or ""
        except Exception:
            return ""                      # a failed screenshot must not abort the demo

    def _on_expected_screen(self, step):
        """Cheap check that we are on the screen the plan expects for this tap.

        A mismatch is re-sampled up to `verify_tries` times over `verify_grace_s`
        before it counts as drift, so a screen that is still rendering or
        animating (an onboarding splash settles over a few seconds) is given time
        to reach the settled state the mapper fingerprinted — not misread as
        drift."""
        # Prefer the per-step fingerprint (the screen exactly as it looked right
        # before this tap during mapping — captures tab/chip-swap states); fall
        # back to the per-screen fingerprint for older plans.
        want = step.get("fp") or self.fingerprints.get(step.get("screen_sig"))
        if not self.verify or not want:
            return True                    # nothing to verify against -> trust the plan
        interval = self.verify_grace_s / self.verify_tries
        last = ""
        for attempt in range(self.verify_tries):
            live = self._grab()
            if live and matches(live, want, self.max_distance):
                self._verified += 1
                return True
            last = live or last
            self.sleep(interval)
        self._line("  drift at step {}: screen fingerprint off by {} bits (after {} tries)".format(
            step.get("n"), distance(last, want), self.verify_tries))
        return False

    def _resync_to(self, upto_index):
        """Relaunch and fast-forward the tap prefix with raw (unrecorded) taps so
        the device is back on the screen this step expects. Returns True on
        success. Taps replayed here are *navigation only* — not biometrics — so
        the timeline is not polluted by the repair."""
        if self.relaunch is None or self.raw_tap is None:
            return False
        self._resyncs += 1
        self._line("  resync #{}: relaunch + fast-forward to step {}".format(
            self._resyncs, upto_index))
        self._do_relaunch()
        for step in self.steps[:upto_index]:
            k = step["kind"]
            if k == "tap":
                t = step["target"]
                self.raw_tap(t["x"], t["y"])
                self.sleep(self.settle_s)
            elif k == "back":
                self.press_back(); self.sleep(self.settle_s)
            elif k == "settext":
                self._do_settext(step)
        # confirm we actually arrived
        return self._on_expected_screen(self.steps[upto_index]) \
            if upto_index < len(self.steps) else True

    def _handle_drift(self, i):
        self._drifts += 1
        if self.on_drift == "skip":
            self._line("  drift: skipping step {}".format(i))
            return "skip"
        if self.on_drift == "relaunch" and self._resyncs < self.max_resyncs:
            if self._resync_to(i):
                self._line("  resync ok; resuming at step {}".format(i))
                return "retry"
            self._line("  resync failed")
        return "stop"

    def _left_the_app(self):
        """True if a tap bounced us out of the app under test (e.g. a share/call
        button opened TrueCaller or a chooser)."""
        if not self.app_package or self.current_package is None:
            return False
        try:
            pkg = self.current_package()
        except Exception:
            return False
        return bool(pkg) and pkg != self.app_package

    def _return_to_app(self):
        """Get back into the app after a tap opened something else: Back a couple
        of times to dismiss the chooser/external app, then relaunch if still out.
        Keeps a blind replay from walking off into another app."""
        for _ in range(2):
            if not self._left_the_app():
                return True
            self.press_back()
            self.sleep(self.settle_s)
        if self._left_the_app() and self.relaunch is not None:
            self._line("  left the app; relaunching to recover")
            self._do_relaunch()
        return not self._left_the_app()

    # --- the walk -----------------------------------------------------------
    def run(self):
        reason = "replayed the compiled plan"
        i = 0
        while i < len(self.steps):
            step = self.steps[i]
            kind = step["kind"]
            if kind == "relaunch":
                self._do_relaunch(); i += 1; continue
            if kind == "back":
                self._do_back(); i += 1; continue
            if kind == "settext":
                self._do_settext(step); i += 1; continue
            # kind == "tap"
            if step.get("exits_app"):
                # During mapping this tap opened another app (share/dialer/chooser)
                # — skip it so replay never leaves the app under test.
                self._line("  skip step {}: opens another app ({})".format(
                    step.get("n"), step.get("label", "")))
                i += 1
                continue
            if self._just_filled:
                # The tap right after a form-fill is the submit; its screen looks
                # different from the captured (empty) fingerprint, so trust it and
                # let the *next* step catch any real failure.
                self._just_filled = False
            elif not self._on_expected_screen(step):
                outcome = self._handle_drift(i)
                if outcome == "stop":
                    reason = "stopped on screen drift at step {} (plan diverged from the live app)".format(i)
                    break
                if outcome == "skip":
                    i += 1; continue
                # "retry": fingerprint now matches, fall through and tap
            record = self.controller.act(step["target"])
            self._taps += 1
            if self.reporter is not None:
                self.reporter(self._tap_index, step.get("label", "?"), record)
            self._tap_index += 1
            self.sleep(self.settle_s)
            # If that tap opened another app (a share/call button → TrueCaller, a
            # chooser, the browser), come back before the next tap lands there.
            if self._left_the_app():
                self._return_to_app()
            i += 1

        self._line("=== replay: {} taps, {} backs, {} relaunches, {} verified, "
                   "{} drifts, {} resyncs; {}".format(
                       self._taps, self._backs, self._relaunches, self._verified,
                       self._drifts, self._resyncs, reason))
        return ReplayResult(
            timeline=self.controller.timeline,
            stop_reason=reason,
            taps=self._taps, backs=self._backs, relaunches=self._relaunches,
            drifts=self._drifts, resyncs=self._resyncs, verified=self._verified,
            log_lines=self._log,
        )
