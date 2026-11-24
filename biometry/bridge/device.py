"""Wiring between the engine and a real device.

The controller takes `dispatch` and the probe takes `read_signature` as plain
callables, so every test runs with stubs and no hardware. These are the two
adapters that put a real phone behind those callables.
"""
from bridge.latency_probe import LatencyProbe, hierarchy_signature


class AdbDispatcher:
    """Performs the engine's touches on an attached device."""

    def __init__(self, bridge):
        self.bridge = bridge
        self.dispatched = 0

    def __call__(self, x, y, pre_delay=0.0):
        self.bridge.execute_tap(x, y, pre_delay)
        self.dispatched += 1

    def swipe(self, path, duration_s, pre_delay=0.0):
        self.bridge.execute_swipe(path, duration_s, pre_delay)
        self.dispatched += 1


def live_probe(bridge, **kwargs):
    """A LatencyProbe reading the real screen over ADB."""
    return LatencyProbe(lambda: hierarchy_signature(bridge), **kwargs)


def foreground_package(device):
    """Package owning the current foreground window, or None if undetermined.

    Reads `dumpsys window`. `mFocusedApp` is the fallback because a system
    window (notification shade, keyguard) can hold `mCurrentFocus` without
    owning an app. The explorer uses this to tell when Back has left the app
    under test; the runner uses it to auto-detect the app when `--package` is
    omitted. One parser, both call sites.
    """
    focus = device.shell("dumpsys", "window")
    for key in ("mCurrentFocus", "mFocusedApp"):
        for line in focus.splitlines():
            if key in line and "/" in line:
                token = next((t for t in reversed(line.split()) if "/" in t), None)
                if token:
                    return token.split("/")[0].strip().lstrip("{").strip()
    return None


def foreground_activity(device):
    """The ``package/Activity`` of the current foreground activity, or None.

    Like :func:`foreground_package` but keeps the activity component, so replay can
    verify it is on the expected *screen* without a screenshot — which a stuck
    notification shade (or any photo-heavy screen) would corrupt. Reads the same
    ``dumpsys window``, preferring ``mCurrentFocus`` and falling back to
    ``mFocusedApp`` when a system window holds the focus (so the shade does not
    hide the real activity). Returns e.g. ``com.example.app/.MainActivity``.
    """
    focus = device.shell("dumpsys", "window")
    for key in ("mCurrentFocus", "mFocusedApp"):
        for line in focus.splitlines():
            if key in line and "/" in line:
                token = next((t for t in reversed(line.split()) if "/" in t), None)
                if token:
                    tok = token.strip().strip("{},")
                    return tok if "/" in tok else None
    return None
