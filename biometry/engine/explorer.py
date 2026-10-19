"""Recursive, cache-pruned traversal of a live app — exhaust every screen.

The adaptive loop (`AdaptiveFeedbackController`) decides *how* a touch is
performed; it does not decide *which* element to touch next. Running it over a
fixed list of one screen's targets never leaves that screen: once a tap
navigates away, those fixed coordinates land on whatever is now in front. This
driver sits *above* the controller and supplies the missing *which / when* — a
depth-first walk that taps every reachable target once, recognises navigation by
a change in the screen's identity, and climbs back out with the Android Back
control (an in-app "back" could be any element; the system Back always means
back). Every real touch still goes through `controller.act`, so the biometrics,
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
  * Replay assumes the recorded route is deterministic; a route gated behind a
    content state it can't reproduce is marked unreachable and skipped.
  * Off-screen targets are not scrolled into view.
"""
import time
from dataclasses import dataclass, field

from bridge.hierarchy import parse_hierarchy, structural_signature, tappable_targets


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
                 min_side=20.0, max_side=900.0, ready_tries=12, ready_interval=1.0,
                 stable_tries=3, stable_interval=0.4):
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
        self.max_side = max_side
        self.ready_tries = ready_tries
        self.ready_interval = ready_interval
        self.stable_tries = stable_tries
        self.stable_interval = stable_interval

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
        return tappable_targets(parse_hierarchy(root), self.min_side, self.max_side)

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

    def _go_back(self):
        self.press_back()
        self.sleep(self.settle_s)
        if self._left_the_app():
            raise _LostPlace("Back left the app")

    def _ensure_on(self, expected_frame):
        root = self._stable_dump()
        actual = self._identity(root)
        if actual != expected_frame:
            raise _LostPlace("Back did not restore {} (now on {})".format(
                self._name(expected_frame), self._name(actual)))
        return root

    def _await_ready(self):
        """After a (cold) launch, the app shows a splash and then loads its first
        screen progressively. Poll until the screen has tappable targets *and*
        has stopped changing (two equal signatures in a row), so the walk reads a
        fully-loaded screen, not a splash or a half-rendered one."""
        root = self.dump()
        prev = None
        for _ in range(self.ready_tries):
            sig = self.base_signature(root)
            if self._targets(root) and sig == prev:
                return root
            prev = sig
            self.sleep(self.ready_interval)
            root = self.dump()
        return root

    def _stable_dump(self):
        """Dump, then wait until the screen stops changing — progressive content
        loading or an animation can otherwise give the same screen a different
        signature depending on how far it had rendered, which splits one screen
        into several and breaks the cache. Returns the first settled dump."""
        root = self.dump()
        prev = self.base_signature(root)
        for _ in range(self.stable_tries):
            self.sleep(self.stable_interval)
            nxt = self.dump()
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
        reason = "completed"
        root = self._await_ready()
        while True:
            try:
                self._explore(root, 0, [])
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
                self._stack = []
                root = self._await_ready()   # poll past the cold-start splash

    def _explore(self, root, depth, path):
        frame = self._identity(root)
        if frame in self.exhausted:
            return                       # already fully done; caller backs out
        self.visited.add(frame)
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
                record = self.controller.act(nxt.as_target())
                self.actions_used += 1
                index = self.actions_used - 1
                label = (nxt.element_id or nxt.resource_id or "?")[:30]
                self.sleep(self.settle_s)

                new_root = self._stable_dump()
                new_base = self.base_signature(new_root)
                new_frame = self._canon.get(new_base, new_base)

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
                    self._go_back()
                    root = self._ensure_on(frame)
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
                    self._go_back()
                    root = self._ensure_on(frame)
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
                self._go_back()
                root = self._ensure_on(frame)
        finally:
            if self._stack and self._stack[-1] == frame:
                self._stack.pop()

    # --- replay recovery ----------------------------------------------------

    def _replay(self, path, start=None):
        """Relaunch leaves us at the root; re-tap `path`'s keys to reach a screen
        again. Returns the root we land on, or None if a key is no longer there."""
        root = start if start is not None else self.dump()
        for key in path:
            if not self._budget_left():
                return None
            element = next((e for e in self._targets(root)
                            if _element_key(e) == key), None)
            if element is None:
                return None
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
        )
