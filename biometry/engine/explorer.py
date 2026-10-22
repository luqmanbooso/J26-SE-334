"""Recursive, cache-pruned traversal of a live app — exhaust every screen.

The adaptive loop (`AdaptiveFeedbackController`) decides *how* a touch is
performed; it does not decide *which* element to touch next. Running it over a
fixed list of one screen's targets never leaves that screen: once a tap
navigates away, those fixed coordinates land on whatever is now in front. This
driver sits *above* the controller and supplies the missing *which / when* — a
depth-first walk that taps every reachable target once, recognises navigation by
a change in the screen's identity, and climbs back out with the Android Back
control — tried, then *verified* against the screen it should restore, and
repaired by relaunch-and-replay when the app's Back is not LIFO (see below).
Every real touch still goes through `controller.act`, so the biometrics,
cognitive feedback and timeline are unchanged; this only chooses the order.

Three things make the walk cover an app well rather than stall on one screen:

  * **Screen identity with swap-merging.** A screen is identified by its layout
    signature (which tells screens apart by position even in a Compose app whose
    controls carry no resource-ids), and a tap is recognised as an in-place
    content swap — a filter chip, a tab — when the tapped control is *still on
    screen* afterward (chips and tabs persist; navigation controls and dialog
    buttons vanish). Swap states are merged onto one screen, so the explorer taps
    all the chips/tabs in place instead of treating each as a new screen.
  * **Exits tapped last.** A control whose tap lands on an already-visited
    screen is a back/up/home control; those are *learned* as it goes (and guessed
    on first sight from label/position) and tapped **last**, so a screen finishes
    its real content before any control that would leave it.
  * **Replay recovery.** If a screen is still left with untried targets after the
    main walk (a back control fired early, say), the app is relaunched and the
    recorded route to that screen is replayed to go back and finish it.

Two caches keep it finite and non-redundant: `exhausted` screens trigger an
immediate Back instead of re-exploration, and a per-screen `tried` set taps each
target once in total, so cycles (A→B→A) cannot loop. `max_actions`/`max_depth`
default to unlimited; termination comes from the caches (finite screens and
targets), not the caps.

Documented limits (by design):
  * Swap-merging assumes a control that stays on screen after the content changed
    belongs to that screen; a different screen reached by a control that happens
    to persist would be merged too. --signature structural turns merging off
    (every content state is its own screen); --signature frame uses a coarse
    control-set identity instead.
  * A tap returning *up* to a screen on the path unwinds to it without a Back.
  * Climbing back out is Back-first but verified: if the system Back does not
    restore the screen it should (a non-LIFO Back that goes Home or exits the
    app), the walk relaunches and replays that screen's recorded route to it
    rather than trusting the back-stack. The DFS context is kept — the walk
    carries on where it was, it does not restart from the root.
  * Replay assumes the recorded route is deterministic; a route gated behind a
    content state it can't reproduce is marked unreachable and skipped.
  * Off-screen targets are not scrolled into view.
"""
import time
from dataclasses import dataclass, field

from bridge.hierarchy import (parse_hierarchy, placeholder_for, structural_signature,
                              tappable_targets, text_fields)


class _LostPlace(Exception):
    """The walk no longer knows which screen it is on — Back left the app, a tap
    opened another app, or Back did not restore the expected screen."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class _BudgetSpent(Exception):
    """The action budget is used up: unwind and stop immediately."""


class _UnwindTo(Exception):
    """A tap returned *up* to a screen already on the DFS path. The app is on
    that ancestor now, so pressing Back would pop past it; instead we unwind the
    recursion to that ancestor's frame, without any Back, and carry on."""

    def __init__(self, sig):
        super().__init__(sig)
        self.sig = sig


@dataclass
class ExplorationResult:
    """What a traversal did: the biometric timeline plus the coverage record."""

    timeline: object
    stop_reason: str
    screens_discovered: int
    screens_exhausted: int
    actions: int
    navigations: int
    relaunches: int
    first_target: dict = None
    log_lines: list = field(default_factory=list)
    screens: list = field(default_factory=list)   # structured screen graph
    plan: list = field(default_factory=list)       # ordered device-action stream (for replay)
    fingerprints: dict = field(default_factory=dict)  # frame sig -> screen fingerprint

    def to_dict(self):
        return {
            "stop_reason": self.stop_reason,
            "counters": {
                "screens_discovered": self.screens_discovered,
                "screens_exhausted": self.screens_exhausted,
                "taps": self.actions,
                "navigations": self.navigations,
                "relaunches": self.relaunches,
            },
            "screens": self.screens,
        }


def _element_key(element):
    """A target's identity within a screen, stable across re-dumps."""
    return (element.resource_id, element.element_id,
            int(round(element.x)), int(round(element.y)),
            int(round(element.width)), int(round(element.height)))


_EXIT_WORDS = ("back", "up", "home", "close", "cancel", "dismiss",
               "navigate", "return", "previous", "arrow")


def _looks_like_exit(element):
    """A first-sight guess that a control leaves the screen (back/up/home).

    Only a hint for the first visit — the real signal is learned (a tap that
    lands on an already-visited screen). Matches a back-ish label/resource-id,
    or a small icon parked in the top-left corner (the usual up affordance).
    """
    text = (element.element_id or "").lower()
    rid = (element.resource_id or "").lower()
    if any(w in text for w in _EXIT_WORDS) or any(w in rid for w in _EXIT_WORDS):
        return True
    return (element.width <= 160 and element.height <= 160
            and element.x <= 160 and element.y <= 280)


class AppExplorer:
    """Depth-first, cache-pruned traversal driver over the adaptive controller.

    All collaborators are injected so it runs with no device: ``dump`` returns
    the current hierarchy (an ElementTree root), ``press_back`` performs the
    system Back, ``identity_fn`` reduces a dump to a screen identity (default
    `frame_signature`), ``current_package`` (optional) reports the foreground app
    for the "left the app" guard, and ``relaunch`` (optional) brings the app back
    and powers replay recovery.
    """

    def __init__(self, controller, dump, press_back,
                 base_signature=structural_signature, merge_swaps=True,
                 current_package=None,
                 app_package=None, relaunch=None, max_actions=None, max_depth=None,
                 max_relaunches=5, settle_s=0.4, sleep=time.sleep, reporter=None,
                 min_side=20.0, max_frac=0.95, ready_tries=12, ready_interval=1.0,
                 stable_tries=3, stable_interval=0.4, dump_retries=3,
                 type_text=None, fill_forms=False,
                 confirm_stay=False, stay_grace_s=None, fingerprint=None, activity=None):
        # max_actions / max_depth default to None = unlimited: the walk runs
        # until the reachable app is exhausted. Termination holds on a finite
        # app regardless — each (screen, target) is tapped once and exhausted
        # screens are not re-entered — so a cap is only a budget.
        self.controller = controller
        self.dump = dump
        self.press_back = press_back
        self.base_signature = base_signature
        self.merge_swaps = merge_swaps
        self.current_package = current_package
        self.app_package = app_package
        self.relaunch = relaunch
        self.max_actions = max_actions
        self.max_depth = max_depth
        self.max_relaunches = max_relaunches
        self.settle_s = settle_s
        self.sleep = sleep
        self.reporter = reporter
        self.min_side = min_side
        self.max_frac = max_frac
        self.type_text = type_text          # callable(x, y, text) or None
        self.fill_forms = fill_forms
        self._filled = set()                # frames whose text fields we filled
        # A slow / async screen (e.g. a Jetpack Compose app that renders content
        # seconds after the tap) can still be showing the *old* screen when the
        # post-tap dump samples, so a real navigation reads as a no-op "stay".
        # That branch is then pruned and the app looks "exhausted" after only a
        # few taps (the Business/Learn tabs get dropped). With confirm_stay on,
        # an apparent stay is re-sampled after `stay_grace_s` before it is
        # trusted. The grace scales with settle_s (the user's slowness hint).
        self.confirm_stay = confirm_stay
        self.stay_grace_s = (stay_grace_s if stay_grace_s is not None
                             else max(1.0, 2.0 * settle_s))
        self.ready_tries = ready_tries
        self.ready_interval = ready_interval
        self.stable_tries = stable_tries
        self.stable_interval = stable_interval
        self.dump_retries = dump_retries

        self._canon = {}              # base signature -> canonical frame id (swap merging)
        self.visited = set()          # frame ids entered at least once
        self.exhausted = set()        # frame ids with every target tapped
        self.tried = {}               # frame -> set(element keys tapped)
        self.seen = {}                # frame -> set(element keys ever enumerated)
        self.exits = set()            # (frame, key) learned to leave the screen
        self.paths = {}               # frame -> route of keys from root (for replay)
        self.actions_used = 0
        self.navigations = 0
        self.relaunches = 0
        self.first_target = None

        self._stack = []              # frames on the current DFS path (cycle guard)
        self._log = []
        self._screen_no = {}          # frame -> small integer id, discovery order
        self._screens = {}            # frame -> structured record for the graph

        # Compiled-path capture (for fast replay later). `fingerprint()` returns
        # a cheap screen fingerprint (see engine/fingerprint.py); it is sampled
        # once per screen so replay can verify it is on the right screen without
        # a full dump. `_plan` is the ordered device-action stream.
        self.fingerprint = fingerprint
        # `activity()` returns the current 'pkg/Activity' (see bridge.device
        # .foreground_activity). Recorded per tap so replay can verify the screen by
        # activity name — robust and pixel-free, unlike the screenshot fingerprint,
        # which is unreliable on photo-heavy screens (and a stuck shade corrupts).
        self.activity = activity
        self._plan = []               # ordered actions: tap / back / relaunch / settext
        self._fingerprints = {}       # frame -> fingerprint string

    def _record(self, kind, **data):
        """Append one device action to the compiled plan (order == execution)."""
        step = {"n": len(self._plan), "kind": kind}
        step.update(data)
        self._plan.append(step)

    def _fp_now(self):
        """Fingerprint the current screen (safe: None if unavailable)."""
        if self.fingerprint is None:
            return None
        try:
            return self.fingerprint() or None
        except Exception:
            return None

    def _activity_now(self):
        """Current 'pkg/Activity' for per-step replay verification (None if n/a)."""
        if self.activity is None:
            return None
        try:
            return self.activity() or None
        except Exception:
            return None

    def _snap_fingerprint(self, frame):
        if self.fingerprint is None or frame in self._fingerprints:
            return
        fp = self._fp_now()
        if fp:
            self._fingerprints[frame] = fp

    # --- naming / logging ---------------------------------------------------

    def _sid(self, frame):
        if frame not in self._screen_no:
            self._screen_no[frame] = len(self._screen_no) + 1
        return self._screen_no[frame]

    def _name(self, frame):
        return "screen#{}".format(self._sid(frame))

    def _screen(self, frame, n_targets):
        record = self._screens.get(frame)
        if record is None:
            record = {"id": self._sid(frame), "sig": frame[:10], "targets": n_targets,
                      "exhausted": False, "edges": []}
            self._screens[frame] = record
        else:
            record["targets"] = max(record["targets"], n_targets)
        return record

    def _line(self, depth, text):
        self._log.append("{}{}".format("  " * depth, text))

    def _emit(self, depth, index, label, event, record):
        self._line(depth, "tap[{:>3}] {:<30} {}".format(index, "'" + label + "'", event))
        if self.reporter is not None:
            self.reporter(index, label, record, event, depth)

    # --- guards -------------------------------------------------------------

    def _budget_left(self):
        return self.max_actions is None or self.actions_used < self.max_actions

    def _left_the_app(self):
        if self.app_package is None or self.current_package is None:
            return False
        package = self.current_package()
        return bool(package) and package != self.app_package

    def _targets(self, root):
        return tappable_targets(parse_hierarchy(root), self.min_side, self.max_frac)

    def _fill_forms(self, root, frame):
        """Type a placeholder into every text field on this screen once. Marks
        the frame filled so it is not retyped, and returns a fresh dump if it
        typed anything, else None (so the caller just proceeds to tap)."""
        self._filled.add(frame)
        if not (self.fill_forms and self.type_text):
            return None
        fields = text_fields(parse_hierarchy(root), self.min_side)
        if not fields:
            return None
        for f in fields:
            self.type_text(f.x, f.y, placeholder_for(f))
            self._record("settext", x=f.x, y=f.y, text=placeholder_for(f))
            self.sleep(0.2)
        self.press_back()          # drop the soft keyboard so the submit stays hittable
        self._record("back", note="drop-keyboard")
        self.sleep(self.settle_s)
        self._line(0, "filled {} text field(s) on {}".format(
            len(fields), self._name(frame)))
        return self._stable_dump()

    def _identity(self, root):
        """The screen a dump belongs to. Starts from the base signature (which
        distinguishes screens — by bounds even when there are no resource-ids),
        then maps any state that was learned to be a content-swap of a screen
        (`_canon`) back onto that screen, so chips/tabs don't split it apart."""
        base = self.base_signature(root)
        return self._canon.get(base, base)

    def _ordered_targets(self, root, frame):
        """This screen's targets with likely *exit* controls moved to the end, so
        a screen's real content is tapped before any control that would leave it.
        `sorted` is stable, so document order is preserved within each rank."""
        targets = self._targets(root)

        def is_exit(element):
            return ((frame, _element_key(element)) in self.exits
                    or _looks_like_exit(element))

        return sorted(targets, key=lambda e: 1 if is_exit(e) else 0)

    def _tried_total(self):
        return sum(len(v) for v in self.tried.values())

    def _work_remains(self):
        for frame in self.visited:
            if frame in self.exhausted:
                continue
            if self.seen.get(frame, set()) - self.tried.get(frame, set()):
                return True
        return False

    # --- navigation control -------------------------------------------------

    def _back_to(self, frame):
        """Climb back to `frame` after exploring below it.

        Back-first, but never trusted: issue the system Back, then *verify* we
        actually landed on `frame`. Many apps — single-activity Compose ones
        especially — do not honour a LIFO back-stack: Back can jump Home, exit
        the app, or land several screens away. When Back did not restore
        `frame`, repair deterministically by relaunching and replaying the
        recorded route to it (`_replay_back_to`), which assumes nothing about
        the back-stack. Returns the dump we land on; raises `_LostPlace` only
        when the repair itself is impossible, leaving the walk's relaunch logic
        to handle the genuinely-lost case."""
        self.press_back()
        self._record("back")
        self.sleep(self.settle_s)
        if not self._left_the_app():
            root = self._stable_dump()
            if self._identity(root) == frame:
                return root                      # the app's Back was LIFO
        return self._replay_back_to(frame)       # non-LIFO Back: repair by replay

    def _replay_back_to(self, frame):
        """Back did not restore `frame` (a non-LIFO jump, or it left the app).
        Relaunch and replay `frame`'s recorded route to stand on it again,
        without unwinding the walk or re-exploring from the root. The DFS stack
        is left untouched: logically we are still on `frame` with its ancestors
        below it."""
        if not (self.seen.get(frame, set()) - self.tried.get(frame, set())):
            # Nothing left to do on `frame` itself — we were only climbing
            # through it. Don't spend a relaunch standing back on a finished
            # screen; let the walk decide (it stops if no work remains anywhere,
            # or relaunch-recovers the specific screen that still has targets).
            raise _LostPlace("Back did not restore {} (already done)".format(
                self._name(frame)))
        if self.relaunch is None or frame not in self.paths:
            raise _LostPlace("Back did not restore {}; no replay route".format(
                self._name(frame)))
        if self.relaunches >= self.max_relaunches:
            raise _LostPlace("Back did not restore {}; relaunch cap ({}) reached".format(
                self._name(frame), self.max_relaunches))
        self.relaunches += 1
        self._line(0, "- Back missed {}; relaunch+replay to it [{}/{}]".format(
            self._name(frame), self.relaunches, self.max_relaunches))
        self.relaunch()
        self._record("relaunch")
        root = self._replay(list(self.paths[frame]), start=self._await_ready())
        if root is None or self._identity(root) != frame:
            raise _LostPlace("replay to {} failed".format(self._name(frame)))
        return root

    def _dump_once(self):
        """One dump, tolerant of a transient bad read. Right after a (re)launch
        the device can briefly return an empty or malformed hierarchy — the adb
        layer raises then ("no <hierarchy> element"). Retry a few times before
        turning it into a `_LostPlace`, which the walk recovers from by relaunch
        rather than crashing the whole run."""
        last = None
        for attempt in range(max(1, self.dump_retries)):
            try:
                return self.dump()
            except Exception as exc:          # transient adb / XML-parse failure
                last = exc
                self.sleep(self.stable_interval)
        raise _LostPlace("dump failed ({})".format(last))

    def _await_ready(self):
        """After a (cold) launch, the app shows a splash and then loads its first
        screen progressively. Poll until the screen has tappable targets *and*
        has stopped changing (two equal signatures in a row), so the walk reads a
        fully-loaded screen, not a splash or a half-rendered one."""
        root = self._dump_once()
        prev = None
        for _ in range(self.ready_tries):
            sig = self.base_signature(root)
            if self._targets(root) and sig == prev:
                return root
            prev = sig
            self.sleep(self.ready_interval)
            root = self._dump_once()
        return root

    def _stable_dump(self):
        """Dump, then wait until the screen stops changing — progressive content
        loading or an animation can otherwise give the same screen a different
        signature depending on how far it had rendered, which splits one screen
        into several and breaks the cache. Returns the first settled dump."""
        root = self._dump_once()
        prev = self.base_signature(root)
        for _ in range(self.stable_tries):
            self.sleep(self.stable_interval)
            nxt = self._dump_once()
            sig = self.base_signature(nxt)
            if sig == prev:
                return nxt
            prev, root = sig, nxt
        return root

    # --- the walk -----------------------------------------------------------

    def run(self):
        """Explore the reachable app, then replay-recover any screen left with
        untried targets. Returns a result."""
        reason = self._walk()
        reason = self._recover(reason)
        return self._result(reason)

    def _walk(self):
        while True:
            try:
                root = self._await_ready()   # inside the try: a failed first/
                self._explore(root, 0, [])   # post-relaunch dump recovers, not crash
                return "exhausted the reachable app"
            except _BudgetSpent:
                return "action budget ({}) reached".format(self.max_actions)
            except _UnwindTo:
                return "unwind target was no longer on the path"
            except _LostPlace as lost:
                if not self._budget_left():
                    return "{}; budget reached".format(lost.reason)
                if not self._work_remains():
                    return "{}; nothing left to exhaust".format(lost.reason)
                if self.relaunch is None:
                    return "{}; relaunch disabled".format(lost.reason)
                if self.relaunches >= self.max_relaunches:
                    return "{}; relaunch cap ({}) reached".format(
                        lost.reason, self.max_relaunches)
                self.relaunches += 1
                self._line(0, "- {}; relaunching app [{}/{}]".format(
                    lost.reason, self.relaunches, self.max_relaunches))
                self.relaunch()
                self._record("relaunch")
                self._stack = []
                # loop: _await_ready() runs again at the top of the try

    def _explore(self, root, depth, path):
        frame = self._identity(root)
        if frame in self.exhausted:
            return                       # already fully done; caller backs out
        self.visited.add(frame)
        self._snap_fingerprint(frame)
        self.tried.setdefault(frame, set())
        self.seen.setdefault(frame, set())
        self.paths.setdefault(frame, list(path))   # first known route from root
        self._stack.append(frame)
        self._line(depth, "enter {} [{}] depth={}".format(self._name(frame), frame[:8], depth))
        try:
            while True:
                if not self._budget_left():
                    raise _BudgetSpent
                targets = self._ordered_targets(root, frame)
                self.seen[frame].update(_element_key(e) for e in targets)
                screen = self._screen(frame, len(targets))
                if self.first_target is None and targets:
                    self.first_target = targets[0].as_target()

                # Optionally fill any text fields once before tapping, so a
                # login/sign-up screen whose submit only needs non-empty boxes
                # can be passed instead of looping (the DFS otherwise only taps).
                if self.fill_forms and frame not in self._filled:
                    filled = self._fill_forms(root, frame)
                    if filled is not None:
                        root = filled
                        continue

                nxt = next((e for e in targets
                            if _element_key(e) not in self.tried[frame]), None)
                if nxt is None:
                    self.exhausted.add(frame)
                    screen["exhausted"] = True
                    self._line(depth, "{} exhausted ({} targets)".format(
                        self._name(frame), len(targets)))
                    return

                key = _element_key(nxt)
                self.tried[frame].add(key)
                # Fingerprint the screen *as it looks right now*, before the tap.
                # A per-step fingerprint (not just one per screen) lets replay
                # verify tab/chip-swap states that share a structural signature.
                self._record("tap", screen_sig=frame,
                             label=(nxt.element_id or nxt.resource_id or "?")[:60],
                             target=nxt.as_target(), fp=self._fp_now(),
                             activity=self._activity_now())
                record = self.controller.act(nxt.as_target())
                self.actions_used += 1
                index = self.actions_used - 1
                label = (nxt.element_id or nxt.resource_id or "?")[:30]
                self.sleep(self.settle_s)

                new_root = self._stable_dump()
                new_base = self.base_signature(new_root)
                new_frame = self._canon.get(new_base, new_base)

                # An apparent no-op may be a slow navigation that had not begun
                # rendering when we sampled. Give it one more grace + stable dump
                # before trusting the "stay" — this is what stops a slow Compose
                # app's tab/section taps from being silently dropped (and the app
                # wrongly declared exhausted after a handful of taps).
                if new_frame == frame and self.confirm_stay:
                    self.sleep(self.stay_grace_s)
                    retry_root = self._stable_dump()
                    retry_base = self.base_signature(retry_root)
                    retry_frame = self._canon.get(retry_base, retry_base)
                    if retry_frame != frame:
                        new_root, new_base, new_frame = retry_root, retry_base, retry_frame

                if new_frame == frame:          # no-op, or a swap state already merged
                    self._emit(depth, index, label, "stay", record)
                    root = new_root
                    continue

                # The screen changed. If the tapped control is still on screen, it
                # was a chip/tab that swapped the content in place — persisting
                # controls stay, navigation controls and dialog buttons vanish —
                # so fold this new state into the current screen and carry on.
                if (self.merge_swaps and new_base not in self._canon
                        and any(_element_key(e) == key for e in self._targets(new_root))):
                    self._canon[new_base] = frame
                    self._emit(depth, index, label, "swap (same screen)", record)
                    root = new_root
                    continue

                if self._left_the_app():        # a tap opened another app
                    # Mark this tap in the plan so replay can skip it (never
                    # re-open the share/dialer/chooser it triggered).
                    if self._plan:
                        self._plan[-1]["exits_app"] = True
                    self._emit(depth, index, label, "left-app", record)
                    screen["edges"].append({"via": label, "to": "left-app"})
                    raise _LostPlace("a tap opened another app")

                self.navigations += 1
                if new_frame in self.visited:   # went to a screen we've seen: an exit control
                    self.exits.add((frame, key))

                if new_frame in self.exhausted:            # been there, done it
                    self._emit(depth, index, label,
                               "nav->{} (done, back)".format(self._name(new_frame)), record)
                    screen["edges"].append({"via": label, "to": self._sid(new_frame),
                                            "note": "already-exhausted"})
                    root = self._back_to(frame)
                    continue

                if new_frame in self._stack:               # returned up to an ancestor
                    self._emit(depth, index, label,
                               "nav->{} (returned to ancestor)".format(self._name(new_frame)),
                               record)
                    screen["edges"].append({"via": label, "to": self._sid(new_frame),
                                            "note": "cycle"})
                    raise _UnwindTo(new_frame)

                if self.max_depth is not None and depth + 1 > self.max_depth:  # too deep
                    self._emit(depth, index, label,
                               "nav->{} (depth cap, back)".format(self._name(new_frame)), record)
                    screen["edges"].append({"via": label, "to": self._sid(new_frame),
                                            "note": "depth-capped"})
                    root = self._back_to(frame)
                    continue

                # a genuinely new screen: descend, exhaust it, then climb back
                self._emit(depth, index, label,
                           "nav->{} (descend)".format(self._name(new_frame)), record)
                screen["edges"].append({"via": label, "to": self._sid(new_frame)})
                try:
                    self._explore(new_root, depth + 1, path + [key])
                except _UnwindTo as unwind:
                    if unwind.sig != frame:
                        raise                 # a deeper tap returned above us: keep unwinding
                    root = self._stable_dump()   # the app is back on this screen; carry on
                    continue
                root = self._back_to(frame)
        finally:
            if self._stack and self._stack[-1] == frame:
                self._stack.pop()

    # --- replay recovery ----------------------------------------------------

    def _replay(self, path, start=None):
        """Relaunch leaves us at the root; re-tap `path`'s keys to reach a screen
        again. Returns the root we land on, or None if a key is no longer there."""
        root = start if start is not None else self._dump_once()
        for key in path:
            if not self._budget_left():
                return None
            element = next((e for e in self._targets(root)
                            if _element_key(e) == key), None)
            if element is None:
                return None
            self._record("tap", label=(element.element_id or "?")[:60],
                         target=element.as_target(), fp=self._fp_now(),
                         activity=self._activity_now())
            self.controller.act(element.as_target())
            self.actions_used += 1
            self.sleep(self.settle_s)
            root = self._stable_dump()
        return root

    def _recover(self, reason):
        """Go back and finish any screen the main walk left with untried targets,
        by relaunching and replaying its recorded route. Each pass finishes a
        screen, makes some progress, or marks the screen unreachable, so it
        terminates. Needs `relaunch` to get a clean route from the root."""
        if self.relaunch is None:
            return reason
        unreachable = set()
        passes = 0
        while self._budget_left() and passes < 2 * len(self.visited) + 20:
            frame = next((f for f in sorted(self.visited, key=self._sid)
                          if f not in self.exhausted and f not in unreachable
                          and f in self.paths
                          and (self.seen.get(f, set()) - self.tried.get(f, set()))),
                         None)
            if frame is None:
                break
            passes += 1
            before = self._tried_total()
            untried = len(self.seen[frame] - self.tried[frame])
            self._line(0, "- recovery: replay to {} ({} untried target(s))".format(
                self._name(frame), untried))
            self.relaunches += 1
            self.relaunch()
            self._record("relaunch")
            self._stack = []
            root = self._replay(list(self.paths[frame]), start=self._await_ready())
            if root is None or self._identity(root) != frame:
                unreachable.add(frame)
                self._line(0, "  recovery: route to {} no longer valid; skipping".format(
                    self._name(frame)))
                continue
            try:
                self._explore(root, len(self.paths[frame]), list(self.paths[frame]))
            except _BudgetSpent:
                return "{}; recovery hit the action budget".format(reason)
            except (_LostPlace, _UnwindTo):
                pass
            if self._tried_total() == before:
                unreachable.add(frame)       # no progress — give up on this one
        if self.relaunches or passes:
            return "{} (+{} recovery pass{})".format(
                reason, passes, "" if passes == 1 else "es")
        return reason

    def _result(self, reason):
        self._line(0, "=== summary: {} screens discovered, {} exhausted, {} taps, "
                      "{} navigations, {} relaunches; stopped: {}".format(
                          len(self.visited), len(self.exhausted), self.actions_used,
                          self.navigations, self.relaunches, reason))
        screens = [self._screens[s] for s in
                   sorted(self._screens, key=lambda s: self._screens[s]["id"])]
        return ExplorationResult(
            timeline=self.controller.timeline,
            stop_reason=reason,
            screens_discovered=len(self.visited),
            screens_exhausted=len(self.exhausted),
            actions=self.actions_used,
            navigations=self.navigations,
            relaunches=self.relaunches,
            first_target=self.first_target,
            log_lines=self._log,
            screens=screens,
            plan=self._plan,
            fingerprints=self._fingerprints,
        )
