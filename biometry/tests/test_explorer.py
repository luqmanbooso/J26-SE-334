"""The recursive explorer, end to end, with no device attached.

The explorer's job is coverage: tap every reachable target once, descend into
every screen a tap opens, climb back out, and never loop. These tests stand a
fake app graph behind the *real* controller, the *real* hierarchy parser and the
*real* structural signature — only the device (dump / tap / Back / package /
relaunch) is faked — so what is exercised is the traversal logic itself, on the
very screen shapes the plan is written against.
"""
import json
import xml.etree.ElementTree as ET

from bridge.adb_bridge import ADBBridge
from bridge.device import foreground_package
from bridge.hierarchy import full_signature, structural_signature
from engine.controller import AdaptiveFeedbackController
from engine.explorer import AppExplorer
from models.cognitive import StaticStress
from simulation.simulator import BiometricSimulator

APP_PKG = "com.fake.app"

#: a target destination meaning "dismiss/pop back up to the parent" (a dialog's
#: OK, an up control) rather than "open a child screen".
POP = object()


# --- a fake app: a graph of screens the walk discovers one dump at a time ----

def _bounds(i):
    """The i-th button: a 400x120 box, rows 300 px apart — far enough that the
    simulator's small touch distortion still lands on the intended target."""
    y1 = 200 + i * 300
    return (300, y1, 700, y1 + 120)


def _node(label, rid, bounds):
    x1, y1, x2, y2 = bounds
    return ('<node class="android.widget.Button" package="{pkg}" '
            'resource-id="{pkg}:id/{rid}" text="{label}" content-desc="" '
            'clickable="true" bounds="[{x1},{y1}][{x2},{y2}]"/>').format(
        pkg=APP_PKG, rid=rid, label=label, x1=x1, y1=y1, x2=x2, y2=y2)


def _screen_xml(buttons):
    inner = "".join(_node(lbl, rid, b) for (lbl, rid, b, _dest) in buttons)
    return ('<hierarchy rotation="0"><node class="android.widget.FrameLayout" '
            'package="{pkg}" bounds="[0,0][1080,2400]">{inner}</node>'
            '</hierarchy>').format(pkg=APP_PKG, inner=inner)


class FakeAppGraph:
    """A screen graph driven through the same calls a real device would get.

    A screen is a list of ``(label, resource_id, bounds, dest_screen_or_None)``.
    A tap on a target with a destination pushes that screen; Back pops it — or,
    for a screen named in ``exit_on_back`` (or at the root), leaves the app.
    """

    def __init__(self, screens, root, exit_on_back=()):
        self.screens = screens
        self.root = root
        self.stack = [root]
        self.exit_on_back = set(exit_on_back)
        self.exited = False
        self.taps = 0
        self.backs = 0

    @property
    def current(self):
        return self.stack[-1]

    def dump(self):
        return ET.fromstring(_screen_xml(self.screens[self.current]))

    def tap(self, x, y, pre_delay=0.0):
        self.taps += 1
        if self.exited:
            return
        buttons = self.screens[self.current]
        if not buttons:
            return
        # Nearest target centre: robust to the simulator's small distortion,
        # which is biometric realism and not what these tests are about.
        def centre(button):
            _l, _r, (x1, y1, x2, y2), _d = button
            return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

        _lbl, _rid, _b, dest = min(
            buttons, key=lambda bt: (centre(bt)[0] - x) ** 2 + (centre(bt)[1] - y) ** 2)
        if dest is POP:
            if len(self.stack) > 1:          # dismiss up to the parent
                self.stack.pop()
        elif dest is not None:
            self.stack.append(dest)          # open a child screen

    def press_back(self):
        self.backs += 1
        if self.exited:
            return
        if self.current in self.exit_on_back:
            self.exited = True          # Back here leaves the app, it does not pop
        elif len(self.stack) > 1:
            self.stack.pop()
        else:
            self.exited = True          # Back at the root leaves the app

    def current_package(self):
        return "com.android.launcher" if self.exited else APP_PKG

    def relaunch(self):
        self.stack = [self.root]
        self.exited = False


class _CalmProbe:
    """Reports a snappy, responsive app, so the cognitive state stays calm and
    the walk is deterministic (no rage bursts re-tapping a point)."""

    class _Obs:
        ui_delay_ms = 12.0
        changed = True
        contended = False

    def read_signature(self):
        return None

    def observe(self, before=None):
        return self._Obs()

    def provocation(self, observation):
        return 0.0


def _controller(fake, seed=7):
    return AdaptiveFeedbackController(
        simulator=BiometricSimulator(seed=seed),
        cognitive=StaticStress(0.0),
        probe=_CalmProbe(),
        dispatch=lambda x, y, d=0.0: fake.tap(x, y, d),
        run_id="test-explore",
    )


def _explorer(fake, **overrides):
    params = dict(
        controller=_controller(fake),
        dump=fake.dump,
        press_back=fake.press_back,
        current_package=fake.current_package,
        app_package=APP_PKG,
        relaunch=fake.relaunch,
        settle_s=0.0,
        sleep=lambda s: None,
        max_actions=100,
        max_depth=16,
        max_relaunches=5,
    )
    params.update(overrides)
    return AppExplorer(**params)


# --- the worked example from the plan: A -> B -> (C, D) ----------------------

TREE = {
    "A": [("A-Call", "a1", _bounds(0), None),
          ("A-Msg", "a2", _bounds(1), None),
          ("A-More", "a3", _bounds(2), "B")],
    "B": [("B-Home", "b1", _bounds(0), None),
          ("B-Cfg", "b2", _bounds(1), "C"),
          ("B-Info", "b3", _bounds(2), "D")],
    "C": [("C-One", "c1", _bounds(0), None),
          ("C-Two", "c2", _bounds(1), None)],
    "D": [("D-One", "d1", _bounds(0), None),
          ("D-Two", "d2", _bounds(1), None)],
}


def test_exhausts_the_whole_tree_once_and_returns_home():
    fake = FakeAppGraph(TREE, root="A")
    result = _explorer(fake).run()
    # 3 (A) + 3 (B) + 2 (C) + 2 (D) targets, each tapped exactly once.
    assert result.actions == 10
    assert result.screens_discovered == 4
    assert result.screens_exhausted == 4
    assert result.navigations == 3          # A->B, B->C, B->D
    assert result.stop_reason.startswith("exhausted")
    assert fake.current == "A"              # climbed all the way back out


def test_every_target_is_tapped_and_none_twice():
    fake = FakeAppGraph(TREE, root="A")
    result = _explorer(fake).run()
    tapped = [r.target_element_id for r in result.timeline.records]
    assert len(tapped) == 10
    assert sorted(tapped) == sorted(set(tapped))   # no target tapped twice
    for screen in TREE.values():
        for label, _rid, _b, _dest in screen:
            assert label[:30] in tapped


def test_a_shared_child_screen_is_explored_only_once():
    shared = {
        "A": [("A-1", "a1", _bounds(0), "X"),
              ("A-2", "a2", _bounds(1), "X"),
              ("A-3", "a3", _bounds(2), None)],
        "X": [("X-1", "x1", _bounds(0), None),
              ("X-2", "x2", _bounds(1), None)],
    }
    fake = FakeAppGraph(shared, root="A")
    result = _explorer(fake).run()
    # If X were re-explored, X-1/X-2 would be tapped twice -> 7 taps, not 5.
    assert result.actions == 5
    assert result.screens_discovered == 2
    assert result.screens_exhausted == 2
    assert result.navigations == 2         # both A buttons navigate to X...
    tapped = [r.target_element_id for r in result.timeline.records]
    assert tapped.count("X-1") == 1 and tapped.count("X-2") == 1   # ...but once


def test_a_tap_returning_to_an_ancestor_unwinds_without_backing_out():
    # B's only control dismisses back up to A (a dialog's OK) — exactly the
    # toolkit case. The walk must not loop, must NOT press Back (from root A that
    # quits the app), and must carry on with A's remaining target.
    cycle = {
        "A": [("A->B", "a1", _bounds(0), "B"),
              ("A-leaf", "a2", _bounds(1), None)],
        "B": [("B-dismiss", "b1", _bounds(0), POP)],
    }
    fake = FakeAppGraph(cycle, root="A")
    result = _explorer(fake).run()
    assert result.stop_reason.startswith("exhausted")
    assert fake.exited is False            # never backed out of the app
    assert result.relaunches == 0
    tapped = [r.target_element_id for r in result.timeline.records]
    assert tapped == ["A->B", "B-dismiss", "A-leaf"]   # unwound to A, then continued


def test_action_budget_stops_the_walk_cleanly():
    fake = FakeAppGraph(TREE, root="A")
    result = _explorer(fake, max_actions=4).run()
    assert result.actions == 4
    assert "budget" in result.stop_reason


def test_max_depth_bounds_the_descent():
    fake = FakeAppGraph(TREE, root="A")
    result = _explorer(fake, max_depth=1).run()
    # From A (depth 0) we may enter B (depth 1), but C/D (depth 2) are capped.
    assert result.screens_discovered == 2   # A and B only
    assert result.actions == 6              # 3 on A + 3 on B; C/D never entered


# --- leaving the app: relaunch only if work remains, else stop ---------------

def test_relaunch_continues_when_targets_remain():
    graph = {
        "A": [("A->B", "a1", _bounds(0), "B"),
              ("A-leaf", "a2", _bounds(1), None)],
        "B": [("B-leaf", "b1", _bounds(0), None)],
    }
    fake = FakeAppGraph(graph, root="A", exit_on_back={"B"})
    result = _explorer(fake).run()
    # A->B, exhaust B, Back leaves the app; A-leaf still untried -> relaunch,
    # resume (A->B is cached, not repeated), tap A-leaf, done.
    assert result.relaunches == 1
    assert result.actions == 3              # a1, b1, a2 — a1 not repeated
    tapped = [r.target_element_id for r in result.timeline.records]
    assert tapped.count("A->B") == 1 and "A-leaf" in tapped
    assert result.stop_reason.startswith("exhausted")


def test_no_relaunch_when_nothing_is_left_to_exhaust():
    graph = {
        "A": [("A->B", "a1", _bounds(0), "B")],
        "B": [("B-leaf", "b1", _bounds(0), None)],
    }
    fake = FakeAppGraph(graph, root="A", exit_on_back={"B"})
    result = _explorer(fake).run()
    assert result.relaunches == 0
    assert result.actions == 2
    assert "nothing left to exhaust" in result.stop_reason


def test_relaunch_can_be_disabled():
    graph = {
        "A": [("A->B", "a1", _bounds(0), "B"),
              ("A-leaf", "a2", _bounds(1), None)],
        "B": [("B-leaf", "b1", _bounds(0), None)],
    }
    fake = FakeAppGraph(graph, root="A", exit_on_back={"B"})
    result = _explorer(fake, relaunch=None).run()
    assert result.relaunches == 0
    assert result.actions == 2              # A-leaf never reached
    assert "relaunch disabled" in result.stop_reason


# --- the traversal log and screen graph --------------------------------------

def test_traversal_log_and_graph_are_produced():
    fake = FakeAppGraph(TREE, root="A")
    result = _explorer(fake).run()
    assert any("summary" in line for line in result.log_lines)
    assert any("exhausted" in line for line in result.log_lines)

    graph = result.to_dict()
    assert json.loads(json.dumps(graph))    # round-trips as JSON
    assert graph["counters"]["taps"] == 10
    assert len(graph["screens"]) == 4
    root_screen = next(s for s in graph["screens"] if s["id"] == 1)
    assert any("to" in edge for edge in root_screen["edges"])   # A navigates onward


# --- the signature the cache is keyed on -------------------------------------

def test_structural_signature_ignores_volatile_text_but_separates_layouts():
    clock_1200 = _screen_xml([("12:00", "clock", _bounds(0), None),
                              ("Go", "go", _bounds(1), None)])
    clock_0945 = _screen_xml([("09:45", "clock", _bounds(0), None),
                              ("Go", "go", _bounds(1), None)])
    extra_row = _screen_xml([("12:00", "clock", _bounds(0), None),
                             ("Go", "go", _bounds(1), None),
                             ("More", "more", _bounds(2), None)])
    # Same structure, only the clock text differs -> same screen identity.
    assert structural_signature(clock_1200) == structural_signature(clock_0945)
    # A different layout (an extra control) -> a different screen.
    assert structural_signature(clock_1200) != structural_signature(extra_row)
    # The strict signature, by contrast, sees the clock tick as a change.
    assert full_signature(clock_1200) != full_signature(clock_0945)


# --- the device seams the explorer depends on --------------------------------

class _RecordingDevice:
    """Records the adb argv it is handed; needs no phone."""

    def __init__(self):
        self.serial = "FAKE"
        self.calls = []

    def run(self, *args, **kwargs):
        self.calls.append(args)

    def shell(self, *args, **kwargs):
        return ""


def test_press_back_and_launch_issue_the_right_adb_commands():
    device = _RecordingDevice()
    bridge = ADBBridge(device=device)
    bridge.press_back()
    assert ("shell", "input", "keyevent", "KEYCODE_BACK") in device.calls
    bridge.launch_package("com.foo.bar")
    assert any(call[:3] == ("shell", "monkey", "-p") and "com.foo.bar" in call
               for call in device.calls)


def test_foreground_package_parses_the_window_dump():
    class _Dev:
        def __init__(self, out):
            self._out = out

        def shell(self, *args, **kwargs):
            return self._out

    focused = "  mCurrentFocus=Window{abc u0 com.fake.app/com.fake.app.MainActivity}\n"
    assert foreground_package(_Dev(focused)) == "com.fake.app"
    # A system window holds mCurrentFocus; the app is on mFocusedApp.
    fallback = ("mCurrentFocus=Window{a u0 StatusBar}\n"
                "mFocusedApp=ActivityRecord{b u0 com.foo.bar/.Act t9}\n")
    assert foreground_package(_Dev(fallback)) == "com.foo.bar"
    assert foreground_package(_Dev("nothing relevant here")) is None
