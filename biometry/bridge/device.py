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
