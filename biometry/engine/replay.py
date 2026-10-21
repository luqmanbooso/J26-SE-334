"""Compiled-path replay: re-walk a mapped traversal fast, as any persona.

`run_live_adaptive.py` writes a ``<out>_plan.json`` — the ordered device-action
stream (tap / back / relaunch / settext) plus one cheap fingerprint per screen.
This module walks that plan again on the device **without a single
`uiautomator dump`** (the ~2.5 s/step cost that makes a live crawl slow). Every
tap still goes through the same `AdaptiveFeedbackController`, so the biometric
distortion and the timeline are produced exactly as in a live run — only the
expensive *discovery* is skipped, because the plan already knows what to tap.

Robustness (still no `uiautomator dump` — only a screencap and a foreground-package
read, both cheap):
  * **App guard** — before every tap, confirm the foreground app is the app under
    test (~60 ms). If a stray chooser/external app has the foreground, recover
    *first*; a tap never lands in another app.
  * **Activity verify (preferred, Level B)** — before every tap, confirm the
    foreground *activity name* matches the one the map recorded for it (~60 ms,
    pixel-free). Robust where a screenshot is not — photo-heavy screens, a stuck
    notification shade — but coarse: it only distinguishes screens that are
    different activities. Needs a plan mapped with per-step ``activity``.
  * **Per-transition fingerprint verify (fallback, Level A)** — when no activity is
    available, and only when the plan says this tap is on a new screen
    (``screen_sig`` changed), confirm it with a screenshot fingerprint (~0.5 s).
    Taps that stay on a confirmed screen skip the screenshot. Unreliable on
    photo-heavy screens, so it is opt-in.
  * On drift it relaunches and fast-forwards the prefix with raw taps to resync,
    and if it still cannot, it stops cleanly instead of tapping blindly.
So it does not "break every time" on a non-deterministic app; worst case it ends
early and says so. ``verify=False`` is the fast blind mode; the app guard still
runs unless ``app_guard=False``.
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
    reliability: dict = field(default_factory=dict)


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
                 current_package=None, app_package=None, current_activity=None,
                 await_ready=None, verify=True, verify_activity=True, app_guard=True,
                 max_distance=DEFAULT_MAX_DISTANCE, settle_s=0.3,
                 fast_forward_settle_s=None,
                 verify_grace_s=None, verify_tries=6, launch_wait_s=2.0,
                 tap_retries=2, max_resyncs=3, on_drift="relaunch",
                 sleep=time.sleep, reporter=None):
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
        self.current_activity = current_activity  # () -> "pkg/Activity", or None
        self.await_ready = await_ready
        self.verify = verify and fingerprint_fn is not None
        # Level B screen check: verify the foreground *activity name* matches the
        # one the map recorded for this tap (~60 ms, pixel-free). Robust where the
        # whole-screen fingerprint is not — photo-heavy screens, a stuck shade — but
        # coarse: it only tells apart screens that are different activities. Needs a
        # plan mapped with per-step `activity` and the `current_activity` callable.
        self.verify_activity = bool(verify_activity) and current_activity is not None
        # Proactive guard: read the foreground package (~60 ms) *before* every tap
        # and recover first if we are not in the app under test, so a tap can never
        # land in another app (a share/chooser that earlier pulled the walk into
        # TrueCaller). Needs both callables; the post-tap check stays as a backstop.
        self.app_guard = bool(app_guard) and current_package is not None and app_package is not None
        self.max_distance = max_distance
        self.settle_s = settle_s
        # Fast-forward re-walks an already-mapped, known-good route with raw taps,
        # so it does not need the full render-settle the first discovery paid — a
        # shorter pause keeps a recovery from re-walking a long prefix at full cost
        # (that was O(prefix)·settle per recovery and dominated long frustrated runs).
        self.ff_settle_s = (fast_forward_settle_s if fast_forward_settle_s is not None
                            else max(0.15, settle_s * 0.5))
        # A screen may not have finished rendering/animating when we first look
        # (e.g. an onboarding splash with a moving background settles over a few
        # seconds), so an apparent mismatch is re-sampled a few times before it
        # counts as drift. verify_grace_s bounds that total wait.
        self.verify_grace_s = (verify_grace_s if verify_grace_s is not None
                               else max(4.0, 5.0 * settle_s))
        self.verify_tries = max(2, verify_tries)
        # A tap that should advance the screen can be *dropped* on a slow device
        # (button drawn but not yet interactive). When the activity check shows we
        # are still on the screen the last tap was made from, re-send that tap up to
        # this many times before treating it as drift — a dropped tap just needs
        # re-sending, not a relaunch.
        self.tap_retries = max(0, tap_retries)
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
        # screen_sig of the last tap executed. The screenshot verify is the one
        # relatively expensive step, so it runs only when the plan says we have
        # moved to a new screen (this sig differs) — not on every tap that stays on
        # the same screen. Reset on any back/relaunch, which change the screen.
        self._last_screen_sig = None
        self._last_tap_step = None         # last tap executed, for dropped-tap retry

    def _line(self, text):
        self._log.append(text)

    # --- device actions -----------------------------------------------------
    def _do_back(self):
        self.press_back()
        self._backs += 1
        self._last_screen_sig = None      # a Back changes the screen -> verify next tap
        self.sleep(self.settle_s)

    def _do_relaunch(self):
        if self.relaunch is None:
            return
        self._just_filled = False         # fresh launch — nothing typed yet
        self._last_screen_sig = None      # cold start -> verify the next tap's screen
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

    def _at_transition(self, step):
        """True when the plan expects this tap to be on a *new* screen (its
        ``screen_sig`` differs from the last tap executed). The screenshot verify
        then runs only on arrival at a screen — not on every tap that stays on it —
        which is what keeps verification cheap without a per-tap UI dump. A plan
        with no ``screen_sig`` falls back to verifying every tap."""
        sig = step.get("screen_sig")
        if sig is None:
            return True
        return sig != self._last_screen_sig

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

    @staticmethod
    def _activity_matches(live, want):
        """True if the live 'pkg/Activity' is the screen the plan expects. Compares
        the package exactly and the activity *class name* (last dotted component),
        so a relative '.Main' and an absolute 'com.x.Main' still match."""
        def parts(tok):
            pkg, _, act = (tok or "").partition("/")
            return pkg, act.rsplit(".", 1)[-1]
        lp, la = parts(live)
        wp, wa = parts(want)
        return bool(lp) and lp == wp and bool(la) and la == wa

    def _grab_activity(self):
        try:
            return self.current_activity() or ""
        except Exception:
            return ""                      # a failed read must not abort the run

    def _on_expected_activity(self, step):
        """Level B verify: confirm we are on the activity the plan recorded for this
        tap (pixel-free, ~60 ms). Re-sampled through a transition animation before it
        counts as drift. No recorded activity (older plan) -> trust the plan."""
        want = step.get("activity")
        if not self.verify_activity or not want:
            return True
        last = ""
        for _ in range(self.verify_tries):
            live = self._grab_activity()
            if live and self._activity_matches(live, want):
                self._verified += 1
                return True
            last = live or last
            self.sleep(self.verify_grace_s / self.verify_tries)
        self._line("  activity drift at step {}: want {}, saw {}".format(
            step.get("n"), want, last or "?"))
        return False

    def _activity_now_matches(self, step):
        """One cheap read: are we on the activity ``step`` expects? (no logging)."""
        want = step.get("activity")
        if not want:
            return True
        live = self._grab_activity()
        return bool(live) and self._activity_matches(live, want)

    def _retry_dropped_tap(self, step):
        """Recover a *dropped* tap. If the activity check for ``step`` failed only
        because we are still on the screen the **last tap** was made from (the tap
        was drawn-but-not-interactive and got dropped), re-send that tap up to
        ``tap_retries`` times — far cheaper and more correct than a relaunch, which
        would just hit the same timing. Returns True once we reach ``step``'s screen.
        Does nothing (returns False) if we are on some *other* screen (a real drift)
        or if the last tap was on the same activity (so 'still there' is expected)."""
        last = self._last_tap_step
        if (not self.verify_activity or last is None or self.raw_tap is None
                or not last.get("activity") or last.get("activity") == step.get("activity")):
            return False
        live = self._grab_activity()
        if not (live and self._activity_matches(live, last.get("activity"))):
            return False                   # on another screen -> a real drift, not a dropped tap
        t = last["target"]
        for attempt in range(self.tap_retries):
            self._line("  dropped tap before step {}: re-tapping {} to advance (try {})".format(
                step.get("n"), last.get("label", "?"), attempt + 1))
            self.raw_tap(t["x"], t["y"])
            for _ in range(self.verify_tries):
                self.sleep(self.verify_grace_s / self.verify_tries)
                if self._activity_now_matches(step):
                    self._verified += 1
                    return True
        return False

    def _arrived_ok(self, step):
        """Did a resync land us where ``step`` expects? Uses whichever screen check
        is active (activity preferred, else fingerprint)."""
        if self.verify_activity:
            return self._on_expected_activity(step)
        if self.verify:
            return self._on_expected_screen(step)
        return True

    def _fast_forward(self, upto_index):
        """Relaunch and re-walk the recorded prefix with raw (unrecorded) taps so
        the device returns to the screen step ``upto_index`` expects. Taps known to
        leave the app (``exits_app`` in the plan, or learned at replay time) are
        skipped — they navigate *out* of the app, not within it, so re-tapping them
        would only bounce out again. Navigation only — the repair is not recorded as
        biometrics, so the timeline is not polluted."""
        if self.relaunch is None or self.raw_tap is None:
            return False
        self._do_relaunch()
        for step in self.steps[:upto_index]:
            k = step["kind"]
            if k == "tap":
                if step.get("exits_app"):
                    continue
                t = step["target"]
                self.raw_tap(t["x"], t["y"])
                self.sleep(self.ff_settle_s)
            elif k == "back":
                self.press_back(); self.sleep(self.ff_settle_s)
            elif k == "settext":
                self._do_settext(step)
        return True

    def _resync_to(self, upto_index):
        """Relaunch and fast-forward the tap prefix so the device is back on the
        screen this step expects (drift recovery). Returns True on success."""
        if self.relaunch is None or self.raw_tap is None:
            return False
        self._resyncs += 1
        self._line("  resync #{}: relaunch + fast-forward to step {}".format(
            self._resyncs, upto_index))
        self._fast_forward(upto_index)
        # confirm we actually arrived (activity check if active, else fingerprint)
        return self._arrived_ok(self.steps[upto_index]) \
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

    def _return_to_app(self, resume_index):
        """Get back into the app after a tap opened something else: Back a couple
        of times to dismiss the chooser/external app. If a Back restores us we are
        on the same in-app screen as before the tap, so the walk resumes directly.
        But if Back cannot dismiss it and we have to cold-relaunch, the app reopens
        at its start/login screen — not where we were — so fast-forward the recorded
        prefix to ``resume_index`` (skipping the app-leaving taps) to restore our
        position. Without this, a blind replay would spend the rest of the walk
        tapping onto the login screen (which is exactly how it stranded on TrippyGo)."""
        for _ in range(2):
            if not self._left_the_app():
                return True
            self.press_back()
            self.sleep(self.settle_s)
        if self._left_the_app() and self.relaunch is not None:
            self._line("  left the app; relaunch + fast-forward to step {} to recover".format(
                resume_index))
            self._fast_forward(resume_index)
        return not self._left_the_app()

    def _reliability(self):
        """Plain-language verdict on whether the recorded taps can be trusted to
        describe the screens they name. Blind replay never checks the live screen,
        so any relaunch/drift means a tap may have fired onto the app's start/login
        screen after a cold restart — the data then looks rich but is *unanchored*.
        A clean walk (no relaunch, no drift) is anchored; a verify run that recovered
        is re-anchored; a blind run that was disrupted is flagged unreliable so a
        stuck replay can never quietly pass for a clean one."""
        disruptions = self._relaunches + self._drifts
        if disruptions == 0:
            level = "ok"
            msg = "Clean walk — no relaunches or drift; taps landed on the mapped screens."
        elif (self.verify or self.verify_activity) and self._verified > 0:
            level = "caution"
            msg = ("Recovered {} disruption(s) with screen verification ({} screens confirmed); "
                   "taps were re-anchored, though a few may be approximate.".format(
                       disruptions, self._verified))
        else:
            level = "unreliable"
            msg = ("Blind replay hit {} relaunch(es)/drift(s) with NO screen verification. After a "
                   "cold relaunch the app reopens at its start/login screen, so recorded taps and "
                   "their element labels may not match what was actually on screen — treat the "
                   "per-tap metrics as unanchored. Re-run with verify, or re-watch the device.".format(
                       disruptions))
        return {
            "level": level, "message": msg, "taps": self._taps,
            "relaunches": self._relaunches, "drifts": self._drifts,
            "resyncs": self._resyncs, "verified": self._verified,
            "verify_enabled": bool(self.verify or self.verify_activity),
        }

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
            # (1) Proactive app guard — confirm we are in the app under test BEFORE
            # tapping, so a stray chooser/external app can never receive this tap.
            # If we cannot get back in, stop rather than tap somewhere unknown.
            if self.app_guard and self._left_the_app():
                self._line("  not in {} before step {}; recovering before tapping".format(
                    self.app_package, i))
                self._return_to_app(i)
                if self._left_the_app():
                    reason = "stopped: could not return to the app before step {}".format(i)
                    self._line("  " + reason)
                    break
            # (2) Screen verify. Level B (activity name) is preferred — robust and
            # pixel-free, so it runs every tap; Level A (whole-screen fingerprint)
            # is the fallback and runs only on arrival at a new screen (the screenshot
            # is the costly check). On a mismatch: resync or stop, never blind-tap.
            if self._just_filled:
                # The tap right after a form-fill is the submit; its screen looks
                # different from the captured (empty) fingerprint, so trust it and
                # let the *next* step catch any real failure.
                self._just_filled = False
            elif self.verify_activity:
                if not self._on_expected_activity(step):
                    # A dropped tap (still on the last screen) is re-sent, not
                    # relaunched; only a genuine wrong-screen drift falls through.
                    if not self._retry_dropped_tap(step):
                        outcome = self._handle_drift(i)
                        if outcome == "stop":
                            reason = "stopped on activity drift at step {} (plan diverged from the live app)".format(i)
                            break
                        if outcome == "skip":
                            i += 1; continue
                    # re-tap or resync put us on the right screen -> fall through and tap
            elif self.verify and self._at_transition(step) and not self._on_expected_screen(step):
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
            self._last_screen_sig = step.get("screen_sig")   # this screen is now confirmed/occupied
            self._last_tap_step = step                        # for dropped-tap retry at the next step
            self.sleep(self.settle_s)
            # If that tap opened another app (a share/call button → TrueCaller, a
            # chooser, the browser), come back before the next tap lands there. The
            # plan did not flag it exits_app, so learn that now: it stops the
            # fast-forward from re-tapping it and resume positioning from treating
            # its (non-)destination as a real in-app screen.
            if self._left_the_app():
                step["exits_app"] = True
                self._return_to_app(i + 1)
            i += 1

        self._line("=== replay: {} taps, {} backs, {} relaunches, {} verified, "
                   "{} drifts, {} resyncs; {}".format(
                       self._taps, self._backs, self._relaunches, self._verified,
                       self._drifts, self._resyncs, reason))
        rel = self._reliability()
        self._line("=== reliability: {} — {}".format(rel["level"].upper(), rel["message"]))
        return ReplayResult(
            timeline=self.controller.timeline,
            stop_reason=reason,
            taps=self._taps, backs=self._backs, relaunches=self._relaunches,
            drifts=self._drifts, resyncs=self._resyncs, verified=self._verified,
            log_lines=self._log, reliability=rel,
        )
