"""Recursive, cache-pruned traversal of a live app — exhaust every screen.

The adaptive loop (`AdaptiveFeedbackController`) decides *how* a touch is
performed; it does not decide *which* element to touch next. Running it over a
fixed list of one screen's targets therefore never leaves that screen: once a
tap navigates away, those fixed coordinates land on whatever is now in front,
and the run is stuck re-tapping a screen it has already left. This driver sits
*above* the controller and supplies the missing *which / when*: a depth-first
walk that taps every reachable target once, recognises navigation by a change
in the screen's structural signature, and climbs back out with the Android Back
control — because an in-app "back" could be any element, but the system Back
always means back.

Every real touch still goes through `controller.act`, so the biometric
distortion, cognitive-state feedback, rage bursts and timeline all behave
exactly as before; this only chooses the order. C2's contribution — adapting
*how* a touch is performed — is untouched. Choosing *which* element is a
coverage concern, not a scientific claim, which is why it lives here and not in
the controller.

Two caches make the walk finite and non-redundant, which is the entire point:

  * ``exhausted`` — screens whose every target has been tapped. Re-reaching one
    triggers an immediate Back instead of re-exploring it, so two buttons that
    lead to the same screen cost that screen once.
  * ``tried``     — per screen signature, the element keys already tapped. A
    screen's targets are tapped once *in total*, however often it is re-reached,
    which is what stops a cycle (A→B→A) looping forever.

When Back leaves the app with targets still unexhausted, the app is relaunched
and the walk resumes (the caches persist, so nothing is re-done); when nothing
is left to exhaust, it stops. Both are bounded by the action budget and a
relaunch cap, so the walk always terminates.

Documented limits (by design, not defects):
  * Screen identity is the structural signature, so structurally-identical pages
    (a list-detail template) collapse to one screen on purpose.
  * Back is assumed to return to the screen a tap left. If it does not, the walk
    does not guess a recovery path — it reports losing its place and relaunches
    (if work remains) or stops. Path-replay recovery is a possible later step.
  * Off-screen targets are not scrolled into view in this version.
"""
import time
from dataclasses import dataclass, field

from bridge.hierarchy import parse_hierarchy, structural_signature, tappable_targets


class _LostPlace(Exception):
    """The walk no longer knows which screen it is on — Back left the app, or a
    tap opened another app, or Back did not restore the expected screen. Caught
    at the top, where it becomes a relaunch (work remains) or a clean stop."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class _BudgetSpent(Exception):
    """The action budget is used up: unwind and stop immediately."""


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
    """A target's identity within a screen, stable across re-dumps.

    Keyed on resource-id, label and (rounded) geometry so the same button is
    recognised on a re-dump and is not tapped twice, while two genuinely
    different controls stay distinct.
    """
    return (element.resource_id, element.element_id,
            int(round(element.x)), int(round(element.y)),
            int(round(element.width)), int(round(element.height)))


class AppExplorer:
    """Depth-first, cache-pruned traversal driver over the adaptive controller.

    All collaborators are injected so the whole thing runs with no device:
    ``dump`` returns the current hierarchy (an ElementTree root), ``press_back``
    performs the system Back, ``signature_fn`` reduces a dump to a screen
    identity, ``current_package`` (optional) reports the foreground app for the
    "left the app" guard, and ``relaunch`` (optional) brings the app back.
    """

    def __init__(self, controller, dump, press_back,
                 signature_fn=structural_signature, current_package=None,
                 app_package=None, relaunch=None, max_actions=30, max_depth=16,
                 max_relaunches=5, settle_s=0.4, sleep=time.sleep, reporter=None,
                 min_side=20.0, max_side=900.0):
        self.controller = controller
        self.dump = dump
        self.press_back = press_back
        self.signature_fn = signature_fn
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

        self.visited = set()          # screen sigs entered at least once
        self.exhausted = set()        # screen sigs with every target tapped
        self.tried = {}               # sig -> set(element keys tapped)
        self.seen = {}                # sig -> set(element keys ever enumerated)
        self.actions_used = 0
        self.navigations = 0
        self.relaunches = 0
        self.first_target = None

        self._stack = []              # sigs on the current DFS path (cycle guard)
        self._log = []
        self._screen_no = {}          # sig -> small integer id, discovery order
        self._screens = {}            # sig -> structured record for the graph

    # --- naming / logging ---------------------------------------------------

    def _sid(self, sig):
        """A stable small integer id for a screen, assigned in discovery order."""
        if sig not in self._screen_no:
            self._screen_no[sig] = len(self._screen_no) + 1
        return self._screen_no[sig]

    def _name(self, sig):
        return "screen#{}".format(self._sid(sig))

    def _screen(self, sig, n_targets):
        record = self._screens.get(sig)
        if record is None:
            record = {"id": self._sid(sig), "sig": sig[:10], "targets": n_targets,
                      "exhausted": False, "edges": []}
            self._screens[sig] = record
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
        return self.actions_used < self.max_actions

    def _left_the_app(self):
        if self.app_package is None or self.current_package is None:
            return False
        package = self.current_package()
        return bool(package) and package != self.app_package

    def _targets(self, root):
        return tappable_targets(parse_hierarchy(root), self.min_side, self.max_side)

    def _work_remains(self):
        """Is there a reached screen with a target we have seen but not tapped?

        This is the precise test the user's rule turns on: relaunch only if
        screens or targets are still left to exhaust, otherwise stop.
        """
        for sig in self.visited:
            if sig in self.exhausted:
                continue
            if self.seen.get(sig, set()) - self.tried.get(sig, set()):
                return True
        return False

    # --- navigation control -------------------------------------------------

    def _go_back(self):
        self.press_back()
        self.sleep(self.settle_s)
        if self._left_the_app():
            raise _LostPlace("Back left the app")

    def _ensure_on(self, expected_sig):
        root = self.dump()
        actual = self.signature_fn(root)
        if actual != expected_sig:
            raise _LostPlace("Back did not restore {} (now on {})".format(
                self._name(expected_sig), self._name(actual)))
        return root

    # --- the walk -----------------------------------------------------------

    def run(self):
        """Explore until the reachable app is exhausted, the budget runs out, or
        the walk loses its place with nothing left to do. Returns a result."""
        reason = "completed"
        root = self.dump()
        while True:
            try:
                self._explore(root, 0)
                reason = "exhausted the reachable app"
                break
            except _BudgetSpent:
                reason = "action budget ({}) reached".format(self.max_actions)
                break
            except _LostPlace as lost:
                if not self._budget_left():
                    reason = "{}; budget reached".format(lost.reason)
                    break
                if not self._work_remains():
                    reason = "{}; nothing left to exhaust".format(lost.reason)
                    break
                if self.relaunch is None:
                    reason = "{}; relaunch disabled".format(lost.reason)
                    break
                if self.relaunches >= self.max_relaunches:
                    reason = "{}; relaunch cap ({}) reached".format(
                        lost.reason, self.max_relaunches)
                    break
                self.relaunches += 1
                self._line(0, "- {}; relaunching app [{}/{}]".format(
                    lost.reason, self.relaunches, self.max_relaunches))
                self.relaunch()
                self.sleep(self.settle_s)
                self._stack = []
                root = self.dump()
        return self._result(reason)

    def _explore(self, root, depth):
        sig = self.signature_fn(root)
        if sig in self.exhausted:
            return                       # already fully done; caller backs out
        self.visited.add(sig)
        self.tried.setdefault(sig, set())
        self.seen.setdefault(sig, set())
        self._stack.append(sig)
        self._line(depth, "enter {} [{}] depth={}".format(self._name(sig), sig[:8], depth))
        try:
            while True:
                if not self._budget_left():
                    raise _BudgetSpent
                targets = self._targets(root)
                self.seen[sig].update(_element_key(e) for e in targets)
                screen = self._screen(sig, len(targets))
                if self.first_target is None and targets:
                    self.first_target = targets[0].as_target()

                nxt = next((e for e in targets
                            if _element_key(e) not in self.tried[sig]), None)
                if nxt is None:
                    self.exhausted.add(sig)
                    screen["exhausted"] = True
                    self._line(depth, "{} exhausted ({} targets)".format(
                        self._name(sig), len(targets)))
                    return

                self.tried[sig].add(_element_key(nxt))
                record = self.controller.act(nxt.as_target())
                self.actions_used += 1
                index = self.actions_used - 1
                label = (nxt.element_id or nxt.resource_id or "?")[:30]
                self.sleep(self.settle_s)

                new_root = self.dump()
                new_sig = self.signature_fn(new_root)

                if new_sig == sig:                       # nothing navigated
                    self._emit(depth, index, label, "stay", record)
                    root = new_root
                    continue

                if self._left_the_app():                 # a tap opened another app
                    self._emit(depth, index, label, "left-app", record)
                    screen["edges"].append({"via": label, "to": "left-app"})
                    raise _LostPlace("a tap opened another app")

                self.navigations += 1
                if new_sig in self.exhausted:            # been there, done it
                    self._emit(depth, index, label,
                               "nav->{} (done, back)".format(self._name(new_sig)), record)
                    screen["edges"].append({"via": label, "to": self._sid(new_sig),
                                            "note": "already-exhausted"})
                    self._go_back()
                    root = self._ensure_on(sig)
                    continue

                if new_sig in self._stack:               # a cycle back onto our path
                    self._emit(depth, index, label,
                               "nav->{} (cycle, back)".format(self._name(new_sig)), record)
                    screen["edges"].append({"via": label, "to": self._sid(new_sig),
                                            "note": "cycle"})
                    self._go_back()
                    root = self._ensure_on(sig)
                    continue

                if depth + 1 > self.max_depth:           # too deep to descend
                    self._emit(depth, index, label,
                               "nav->{} (depth cap, back)".format(self._name(new_sig)), record)
                    screen["edges"].append({"via": label, "to": self._sid(new_sig),
                                            "note": "depth-capped"})
                    self._go_back()
                    root = self._ensure_on(sig)
                    continue

                # a genuinely new screen: descend, exhaust it, then climb back
                self._emit(depth, index, label,
                           "nav->{} (descend)".format(self._name(new_sig)), record)
                screen["edges"].append({"via": label, "to": self._sid(new_sig)})
                self._explore(new_root, depth + 1)
                self._go_back()
                root = self._ensure_on(sig)
        finally:
            if self._stack and self._stack[-1] == sig:
                self._stack.pop()

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
