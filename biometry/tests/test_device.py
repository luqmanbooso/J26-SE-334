"""The two adapters that put a real phone behind the engine's callables."""
from bridge.device import AdbDispatcher, live_probe


class FakeBridge:
    def __init__(self):
        self.taps = []
        self.dumps = 0

    def execute_tap(self, x, y, pre_delay=0.0):
        self.taps.append((x, y, pre_delay))

    def dump_ui_hierarchy(self):
        self.dumps += 1
        import xml.etree.ElementTree as ET
        return ET.fromstring(f'<hierarchy><node bounds="[0,0][{self.dumps},1]"/></hierarchy>')


def test_the_dispatcher_forwards_the_touch_to_the_bridge():
    bridge = FakeBridge()
    AdbDispatcher(bridge)(123.4, 567.8, 0.25)
    assert bridge.taps == [(123.4, 567.8, 0.25)]


def test_the_dispatcher_counts_what_it_sent():
    bridge = FakeBridge()
    dispatch = AdbDispatcher(bridge)
    for _ in range(4):
        dispatch(1.0, 2.0)
    assert dispatch.dispatched == 4


def test_a_live_probe_reads_the_screen_through_the_bridge():
    bridge = FakeBridge()
    probe = live_probe(bridge, timeout=0.1, poll_interval=0.01)
    first = probe.read_signature()
    assert bridge.dumps == 1
    assert first != probe.read_signature()  # the fake screen changes every dump


def test_a_signature_is_a_stable_digest_of_the_screen():
    """Two reads of an unchanged screen must agree, or everything reads as a change."""
    import xml.etree.ElementTree as ET

    from bridge.latency_probe import hierarchy_signature

    class StillBridge:
        def dump_ui_hierarchy(self):
            return ET.fromstring('<hierarchy><node bounds="[0,0][10,10]"/></hierarchy>')

    bridge = StillBridge()
    assert hierarchy_signature(bridge) == hierarchy_signature(bridge)
