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


class StrandWorld:
    """A tap on the 'share' coordinate opens another app that Back cannot dismiss
    (a chooser, or a cold external app), so recovery needs a cold relaunch — which
    reopens our app at its login screen, not where we were. Only fast-forwarding
    the recorded prefix (past login again) gets the walk back on track; a blind
    replay that just resumes would keep tapping onto login (the TrippyGo bug)."""

    def __init__(self):
        self.cur = "login"
        self.pkg = "com.app"
        self.relaunches = 0

    def tap(self, x, y):
        if self.cur == "login" and (x, y) == (10, 10):
            self.cur = "home"                 # pass the login
        elif self.cur == "home" and (x, y) == (50, 50):
            self.pkg = "com.chooser"          # share opened something Back won't close
        elif self.cur == "home" and (x, y) == (30, 30):
            self.cur = "detail"               # the tap we must still reach

    def back(self):
        pass                                  # cannot dismiss the external chooser

    def relaunch(self):
        self.relaunches += 1
        self.pkg = "com.app"
        self.cur = "login"                    # cold start lands back at login

    def fg(self):
        return self.pkg


def test_recovery_relaunch_fast_forwards_past_login_instead_of_stranding():
    w = StrandWorld()
    c = FakeController(w)
    plan = {"fingerprints": {}, "steps": [
        _tap(0, "login", "SignIn", 10, 10),   # login -> home
        _tap(1, "home", "Share", 50, 50),     # opens a chooser Back can't close
        _tap(2, "home", "Open", 30, 30)]}     # must still be reached after recovery
    eng = ReplayEngine(plan, c, press_back=w.back, relaunch=w.relaunch,
                       raw_tap=lambda x, y: w.tap(x, y), fingerprint_fn=None,
                       current_package=w.fg, app_package="com.app",
                       verify=False, sleep=lambda *a: None)
    res = eng.run()
    assert w.relaunches >= 1                   # Back failed, so it had to relaunch
    assert w.pkg == "com.app"                  # ended back inside the app, not stranded out
    assert w.cur == "detail"                   # fast-forward restored us; the final tap landed
    assert res.taps == 3                       # all three taps dispatched


def test_reliability_flags_blind_relaunch_as_unreliable():
    w = StrandWorld()
    c = FakeController(w)
    plan = {"fingerprints": {}, "steps": [
        _tap(0, "login", "SignIn", 10, 10),
        _tap(1, "home", "Share", 50, 50),
        _tap(2, "home", "Open", 30, 30)]}
    eng = ReplayEngine(plan, c, press_back=w.back, relaunch=w.relaunch,
                       raw_tap=lambda x, y: w.tap(x, y), fingerprint_fn=None,
                       current_package=w.fg, app_package="com.app",
                       verify=False, sleep=lambda *a: None)
    res = eng.run()
    assert res.reliability["level"] == "unreliable"   # blind + relaunched → not trustworthy
    assert res.reliability["relaunches"] >= 1
    assert res.reliability["verify_enabled"] is False


def test_reliability_clean_walk_is_ok():
    w = World()
    eng, _ = _engine(w, _plan([_tap(0, "home", "toA", 10, 10)]), verify=False)
    res = eng.run()
    assert res.reliability["level"] == "ok"           # no relaunch, no drift → anchored
    assert res.reliability["relaunches"] == 0 and res.reliability["drifts"] == 0


# ---- Level A: per-transition verify + proactive app guard -------------------

class StayScreenWorld:
    """home --tap--> a, then taps on a stay on a. So of three taps the screens are
    [home, a, a]: two transitions, one in-place tap."""

    def __init__(self):
        self.cur = "home"
        self.fp_calls = 0

    def tap(self, x, y):
        if self.cur == "home":
            self.cur = "a"
    def back(self): self.cur = "home"
    def relaunch(self): self.cur = "home"
    def fp(self):
        self.fp_calls += 1
        return "0" * 64 if self.cur == "home" else "1" * 64


def test_verify_runs_per_transition_not_per_tap():
    w = StayScreenWorld()
    c = FakeController(w)
    plan = {"fingerprints": {"home": "0" * 64, "a": "1" * 64}, "steps": [
        _tap(0, "home", "toA", 10, 10),     # transition (None -> home): verify
        _tap(1, "a", "onA1", 20, 20),       # transition (home -> a): verify
        _tap(2, "a", "onA2", 30, 30)]}      # same screen (a -> a): NO verify
    eng = ReplayEngine(plan, c, press_back=w.back, relaunch=w.relaunch,
                       raw_tap=lambda x, y: w.tap(x, y), fingerprint_fn=w.fp,
                       sleep=lambda *a: None)
    res = eng.run()
    assert res.taps == 3
    assert res.verified == 2                 # only the two screen arrivals were verified
    assert w.fp_calls == 2, "a screenshot was taken per transition, not per tap"


class OutOfAppWorld:
    """We are in another app at the start of a tap; a Back returns us to the app."""

    def __init__(self):
        self.pkg = "com.other"               # start OUT of the app under test
        self.backs = 0
        self.tapped_pkg = []                 # the app we were in when each tap fired

    def tap(self, x, y):
        self.tapped_pkg.append(self.pkg)
    def back(self):
        self.backs += 1
        self.pkg = "com.app"
    def fg(self): return self.pkg


def test_proactive_app_guard_recovers_before_tapping():
    w = OutOfAppWorld()
    c = FakeController(w)
    plan = {"fingerprints": {}, "steps": [_tap(0, "home", "firstTap", 10, 10)]}
    eng = ReplayEngine(plan, c, press_back=w.back, relaunch=lambda: None,
                       raw_tap=lambda x, y: w.tap(x, y), fingerprint_fn=None,
                       current_package=w.fg, app_package="com.app",
                       verify=False, sleep=lambda *a: None)
    res = eng.run()
    assert res.taps == 1
    assert w.backs >= 1                       # recovered BEFORE tapping
    assert w.tapped_pkg == ["com.app"], "the tap fired only after we were back in the app"


class StuckOutWorld:
    """Stuck in another app that Back cannot dismiss, and no relaunch available."""

    def __init__(self):
        self.pkg = "com.other"
        self.taps = 0

    def tap(self, x, y): self.taps += 1
    def back(self): pass                      # cannot return
    def fg(self): return self.pkg


def test_app_guard_stops_rather_than_tap_in_another_app():
    w = StuckOutWorld()
    c = FakeController(w)
    plan = {"fingerprints": {}, "steps": [_tap(0, "home", "x", 10, 10)]}
    eng = ReplayEngine(plan, c, press_back=w.back, relaunch=None,
                       raw_tap=None, fingerprint_fn=None,
                       current_package=w.fg, app_package="com.app",
                       verify=False, sleep=lambda *a: None)
    res = eng.run()
    assert res.taps == 0                      # never tapped
    assert w.taps == 0                        # the device was never tapped either
    assert "could not return to the app" in res.stop_reason


class DriftToLoginWorld:
    """tap0 should go home->deep, but the app silently falls back to login. The
    next tap expects 'deep' and must be caught, never tapped onto login."""

    def __init__(self):
        self.cur = "home"
        self.deep_button_tapped = False

    def tap(self, x, y):
        if self.cur == "home":
            self.cur = "login"               # drops to login instead of deep
        elif self.cur == "deep" and (x, y) == (50, 50):
            self.deep_button_tapped = True
    def back(self): self.cur = "home"
    def relaunch(self): self.cur = "home"
    def fp(self):
        return {"home": "0" * 64, "deep": "1" * 64, "login": "f" * 64}[self.cur]


def test_drift_to_login_is_caught_at_transition_not_blind_tapped():
    w = DriftToLoginWorld()
    c = FakeController(w)
    plan = {"fingerprints": {"home": "0" * 64, "deep": "1" * 64}, "steps": [
        _tap(0, "home", "enter", 10, 10),     # on home (verified), navigates (we think) to deep
        _tap(1, "deep", "DeepButton", 50, 50)]}  # expects deep; live is login -> must be caught
    eng = ReplayEngine(plan, c, press_back=w.back, relaunch=w.relaunch,
                       raw_tap=lambda x, y: w.tap(x, y), fingerprint_fn=w.fp,
                       on_drift="stop", sleep=lambda *a: None)
    res = eng.run()
    assert res.taps == 1                      # only the home tap fired
    assert res.drifts == 1
    assert w.deep_button_tapped is False, "the deep button was never tapped while on login"
    assert "drift" in res.stop_reason


# ---- Level B: activity-name verify (robust, pixel-free) ---------------------

def _atap(n, activity, tid, x, y):
    s = _tap(n, activity, tid, x, y)   # reuse; screen_sig unused by activity verify
    s["activity"] = activity
    return s


class ActivityWorld:
    """Screens are activities. A tap at (10,10) on Main drifts to Login; a tap at
    (20,20) on Main navigates to Detail; the deep button is (50,50) on Detail."""

    def __init__(self, start="com.app/.MainActivity"):
        self.act = start
        self.deep_button_tapped = False

    def tap(self, x, y):
        if self.act == "com.app/.MainActivity" and (x, y) == (10, 10):
            self.act = "com.app/.LoginActivity"       # silent drift to login
        elif self.act == "com.app/.MainActivity" and (x, y) == (20, 20):
            self.act = "com.app/.DetailActivity"
        elif self.act == "com.app/.DetailActivity" and (x, y) == (50, 50):
            self.deep_button_tapped = True
    def back(self): self.act = "com.app/.MainActivity"
    def relaunch(self): self.act = "com.app/.MainActivity"
    def activity(self): return self.act


def _activity_engine(w, plan, **kw):
    c = FakeController(w)
    defaults = dict(press_back=w.back, relaunch=w.relaunch,
                    raw_tap=lambda x, y: w.tap(x, y), fingerprint_fn=None,
                    current_activity=w.activity, app_package="com.app",
                    current_package=lambda: w.activity().split("/")[0],
                    sleep=lambda *a: None)
    defaults.update(kw)
    return ReplayEngine(plan, c, **defaults), c


def test_activity_matches_relative_and_absolute():
    m = ReplayEngine._activity_matches
    assert m("com.app/.Main", "com.app/.Main")
    assert m("com.app/com.app.Main", "com.app/.Main")     # absolute vs relative class
    assert m("com.app/.Main", "com.app/com.app.Main")
    assert not m("com.app/.Main", "com.app/.Other")       # different screen
    assert not m("com.other/.Main", "com.app/.Main")      # different app
    assert not m("", "com.app/.Main")


def test_activity_verify_catches_login_strand_not_blind_tapped():
    w = ActivityWorld()
    plan = {"fingerprints": {}, "steps": [
        _atap(0, "com.app/.MainActivity", "enter", 10, 10),   # drifts to Login
        _atap(1, "com.app/.DetailActivity", "DeepButton", 50, 50)]}  # expects Detail
    eng, _ = _activity_engine(w, plan, on_drift="stop")
    res = eng.run()
    assert res.taps == 1                       # only the Main tap fired
    assert w.deep_button_tapped is False       # never tapped the deep button while on Login
    assert "activity drift" in res.stop_reason


def test_activity_verify_passes_a_correct_walk():
    w = ActivityWorld()
    plan = {"fingerprints": {}, "steps": [
        _atap(0, "com.app/.MainActivity", "toDetail", 20, 20),  # Main -> Detail
        _atap(1, "com.app/.DetailActivity", "deep", 50, 50)]}
    eng, _ = _activity_engine(w, plan)
    res = eng.run()
    assert res.taps == 2
    assert res.verified == 2 and res.drifts == 0
    assert w.deep_button_tapped is True


def test_activity_verify_recovers_via_resync():
    w = ActivityWorld(start="com.app/.SomewhereElse")   # not where step 0 expects
    plan = {"fingerprints": {}, "steps": [
        _atap(0, "com.app/.MainActivity", "x", 20, 20)]}
    eng, _ = _activity_engine(w, plan, on_drift="relaunch")
    res = eng.run()
    assert res.resyncs >= 1 and res.taps == 1   # relaunch -> Main -> matched -> tapped


def test_activity_verify_is_noop_on_a_plan_without_activities():
    w = ActivityWorld()
    # steps carry NO "activity" key (older plan) -> activity verify trusts the plan
    plan = {"fingerprints": {}, "steps": [
        _tap(0, "sig", "toDetail", 20, 20), _tap(1, "sig", "deep", 50, 50)]}
    eng, _ = _activity_engine(w, plan)
    res = eng.run()
    assert res.taps == 2 and res.verified == 0   # nothing to verify, nothing false-stopped


class DroppedTapWorld:
    """Tapping 'advance' (10,10) on A should go to B, but the FIRST attempt is
    dropped (stays on A); a re-tap works. Models a slow device dropping a tap."""

    def __init__(self):
        self.act = "com.app/.A"
        self.advance_attempts = 0
    def tap(self, x, y):
        if self.act == "com.app/.A" and (x, y) == (10, 10):
            self.advance_attempts += 1
            if self.advance_attempts >= 2:      # 1st tap dropped, 2nd advances
                self.act = "com.app/.B"
    def back(self): pass
    def relaunch(self): self.act = "com.app/.A"; self.advance_attempts = 0
    def activity(self): return self.act


def test_dropped_tap_is_retried_then_continues():
    w = DroppedTapWorld()
    plan = {"fingerprints": {}, "steps": [
        _atap(0, "com.app/.A", "advance", 10, 10),   # should go A->B, but 1st tap is dropped
        _atap(1, "com.app/.B", "onB", 20, 20)]}
    eng, _ = _activity_engine(w, plan)
    res = eng.run()
    assert res.taps == 2                             # both taps executed
    assert res.relaunches == 0 and res.resyncs == 0  # recovered by RE-TAPPING, not relaunching
    assert w.act == "com.app/.B"


def test_wrong_screen_is_not_treated_as_dropped_tap():
    class WrongScreenWorld:
        def __init__(self): self.act = "com.app/.A"; self.taps = 0
        def tap(self, x, y):
            self.taps += 1
            if self.act == "com.app/.A": self.act = "com.app/.C"   # a real wrong screen
        def back(self): pass
        def relaunch(self): self.act = "com.app/.A"
        def activity(self): return self.act
    w = WrongScreenWorld()
    plan = {"fingerprints": {}, "steps": [
        _atap(0, "com.app/.A", "go", 10, 10),
        _atap(1, "com.app/.B", "deep", 20, 20)]}
    eng, _ = _activity_engine(w, plan, on_drift="stop")
    res = eng.run()
    assert res.taps == 1                   # step1 never tapped on the wrong screen
    assert w.taps == 1                     # NO re-tap fired (would be >=2 if mistaken for a drop)
    assert "activity drift" in res.stop_reason


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
