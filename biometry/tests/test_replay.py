"""Replay engine: deterministic stub tests (no device).

A tiny world drives screen state from taps so the fingerprint check sees the
same thing replay does. Fingerprints are valid 64-hex strings so the real
Hamming-distance matcher is exercised, not mocked.
"""
from types import SimpleNamespace

import pytest

from engine.replay import ReplayEngine

FP = {"home": "0" * 64, "a": "1" * 64, "b": "2" * 64, "elsewhere": "f" * 64}


class World:
    """Screen state driven by tap coordinates and back/relaunch."""

    def __init__(self, start="home"):
        self.cur = start
        self.T = {("home", (10, 10)): "a", ("home", (30, 30)): "b", ("a", (20, 20)): "home"}
        self.relaunches = 0

    def tap(self, x, y):
        self.cur = self.T.get((self.cur, (x, y)), self.cur)

    def back(self):
        self.cur = "home"

    def relaunch(self):
        self.cur = "home"
        self.relaunches += 1

    def fp(self):
        return FP[self.cur]


class FakeController:
    def __init__(self, world):
        self.world = world
        self.timeline = SimpleNamespace(records=[])

    def act(self, target):
        self.world.tap(target["x"], target["y"])
        rec = SimpleNamespace(cognitive_state="calm", stress_s=0.1,
                              ui_delay_ms=10.0, hit_flag=True)
        self.timeline.records.append(rec)
        return rec


def _tap(n, sig, tid, x, y):
    return {"n": n, "kind": "tap", "screen_sig": sig, "label": tid,
            "target": {"id": tid, "x": x, "y": y, "width": 4, "height": 4}}


def _plan(steps):
    return {"fingerprints": {"home": FP["home"], "a": FP["a"], "b": FP["b"]}, "steps": steps}


def _engine(world, plan, **kw):
    c = FakeController(world)
    defaults = dict(
        press_back=world.back,
        relaunch=world.relaunch,
        raw_tap=lambda x, y: world.tap(x, y),
        fingerprint_fn=world.fp,
        sleep=lambda *a: None,
    )
    defaults.update(kw)
    return ReplayEngine(plan, c, **defaults), c


def test_happy_path_executes_every_tap_and_verifies():
    w = World()
    plan = _plan([_tap(0, "home", "toA", 10, 10), {"n": 1, "kind": "back"},
                  _tap(2, "home", "toB", 30, 30)])
    eng, c = _engine(w, plan)
    res = eng.run()
    assert res.taps == 2 and res.backs == 1
    assert res.drifts == 0 and res.resyncs == 0
    assert res.verified == 2                    # both taps confirmed on the right screen
    assert len(c.timeline.records) == 2
    assert "replayed the compiled plan" in res.stop_reason


def test_blind_mode_skips_verification():
    w = World()
    plan = _plan([_tap(0, "home", "toA", 10, 10)])
    eng, _ = _engine(w, plan, verify=False)
    res = eng.run()
    assert res.taps == 1 and res.verified == 0 and res.drifts == 0


def test_drift_stop_ends_gracefully_without_crashing():
    w = World(start="elsewhere")               # app is NOT where the plan expects
    plan = _plan([_tap(0, "home", "toA", 10, 10), _tap(1, "a", "toHome", 20, 20)])
    eng, c = _engine(w, plan, on_drift="stop")
    res = eng.run()
    assert res.taps == 0                        # never tapped on the wrong screen
    assert res.drifts == 1
    assert "drift" in res.stop_reason
    assert len(c.timeline.records) == 0


def test_drift_relaunch_resyncs_then_completes():
    w = World(start="elsewhere")               # transient: relaunch returns us home
    plan = _plan([_tap(0, "home", "toA", 10, 10), {"n": 1, "kind": "back"},
                  _tap(2, "home", "toB", 30, 30)])
    eng, c = _engine(w, plan, on_drift="relaunch")
    res = eng.run()
    assert res.resyncs >= 1 and w.relaunches >= 1
    assert res.taps == 2                        # resynced, then finished the plan
    assert len(c.timeline.records) == 2


class LoginWorld:
    """A login screen whose fingerprint changes once text is typed in (as a real
    filled form does), then submits to home."""

    def __init__(self):
        self.cur = "login"
        self.filled = False

    def tap(self, x, y):
        if self.cur == "login" and (x, y) == (10, 10):
            self.cur = "home"

    def settext(self, x, y, t):
        self.filled = True

    def fp(self):
        if self.cur == "login":
            return "f" * 64 if self.filled else "0" * 64   # filled looks different
        return "1" * 64                                     # home


def test_form_submit_tap_is_not_false_drifted_after_fill():
    w = LoginWorld()
    c = FakeController(w)
    plan = {"fingerprints": {"login": "0" * 64, "home": "1" * 64},
            "steps": [
                {"n": 0, "kind": "settext", "x": 5, "y": 5, "text": "user"},
                _tap(1, "login", "Submit", 10, 10),   # fingerprint now "f"*64 != login "0"*64
                _tap(2, "home", "AfterLogin", 99, 99)]}
    eng = ReplayEngine(plan, c, press_back=lambda: None, relaunch=lambda: None,
                       raw_tap=lambda x, y: w.tap(x, y), fingerprint_fn=w.fp,
                       set_text=lambda x, y, t: w.settext(x, y, t), sleep=lambda *a: None)
    res = eng.run()
    assert res.taps == 2, "submit tap should fire despite the filled-form fingerprint"
    assert res.drifts == 0
    assert w.cur == "home"


class LeaveWorld:
    """A tap on the 'share' coordinate bounces to another app; Back returns."""

    def __init__(self):
        self.cur = "home"
        self.pkg = "com.app"
        self.backs = 0

    def tap(self, x, y):
        if (x, y) == (50, 50):
            self.pkg = "com.truecaller"      # share/call opened another app

    def back(self):
        self.backs += 1
        self.pkg = "com.app"                 # Back dismisses it, back in the app

    def fg(self):
        return self.pkg


def test_tap_that_opens_another_app_is_recovered():
    w = LeaveWorld()
    c = FakeController(w)
    plan = {"fingerprints": {}, "steps": [
        _tap(0, "home", "share", 50, 50),    # opens com.truecaller
        _tap(1, "home", "next", 10, 10)]}
    eng = ReplayEngine(plan, c, press_back=w.back, relaunch=lambda: None,
                       raw_tap=lambda x, y: w.tap(x, y), fingerprint_fn=None,
                       current_package=w.fg, app_package="com.app",
                       verify=False, sleep=lambda *a: None)
    res = eng.run()
    assert res.taps == 2
    assert w.backs >= 1                       # it pressed Back to return
    assert w.pkg == "com.app"                 # ended back inside the app


def test_relaunch_and_settext_steps_are_executed():
    w = World()
    plan = _plan([{"n": 0, "kind": "relaunch"},
                  {"n": 1, "kind": "settext", "x": 5, "y": 5, "text": "hi"},
                  _tap(2, "home", "toA", 10, 10)])
    calls = []
    eng, _ = _engine(w, plan, set_text=lambda x, y, t: calls.append((x, y, t)))
    res = eng.run()
    assert res.relaunches == 1 and res.taps == 1
    assert calls == [(5, 5, "hi")]
