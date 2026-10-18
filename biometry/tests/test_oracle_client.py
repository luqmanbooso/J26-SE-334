"""IF-C2-to-C3 producer side: the trigger fires correctly and never breaks the loop."""
import json

import pytest

from bridge.oracle_client import OracleNotifier
from engine.controller import AdaptiveFeedbackController
from models.cognitive import StaticStress
from simulation.simulator import BiometricSimulator

TARGET = {"id": "btn_submit", "x": 540, "y": 1200, "width": 300, "height": 120}


class StubProbe:
    def read_signature(self):
        return "s"
    def observe(self, before=None):
        class Obs:
            ui_delay_ms = 12.0; changed = True; contended = False
            consecutive_unchanged = 0
        return Obs()
    def provocation(self, obs):
        return 0.0


def build(notify):
    return AdaptiveFeedbackController(
        simulator=BiometricSimulator(seed=7),
        cognitive=StaticStress(0.9),            # high stress -> bursts occur
        probe=StubProbe(),
        dispatch=lambda x, y, d=0.0: None,
        notify=notify,
        clock=iter(range(10 ** 6)).__next__,
    )


def test_one_trigger_per_action_even_with_bursts():
    calls = []
    c = build(notify=calls.append)
    timeline = c.run([TARGET] * 40)
    assert len(calls) == 40                      # bursts never double-fire
    assert any(r.rage_taps for r in timeline.records), "reseed: no burst seen"


def test_notifier_posts_the_agreed_payload_after_settling():
    sent, slept = [], []

    class FakeResp:
        status = 202
        def __enter__(self): return self
        def __exit__(self, *a): return False

    n = OracleNotifier("http://oracle:8000/", session_id="t", settle_ms=200,
                       sleep=slept.append, device_serial="SER123")
    import bridge.oracle_client as oc
    orig = oc.urllib.request.urlopen
    oc.urllib.request.urlopen = lambda req, timeout: (sent.append(req), FakeResp())[1]
    try:
        record = build(notify=None).act(TARGET)
        assert n(record) is True
    finally:
        oc.urllib.request.urlopen = orig

    assert n.url == "http://oracle:8000/api/oracle/trigger"
    assert slept == [0.2]                        # the settle wait, in seconds
    body = json.loads(sent[0].data.decode())
    assert set(body) == {"action_id", "session_id", "target_element_id",
                         "stress_level", "delay_ms", "device_serial"}
    assert body["stress_level"] == 0.9
    assert body["delay_ms"] == 200
    assert body["target_element_id"] == "btn_submit"


def test_a_dead_oracle_never_breaks_the_loop():
    n = OracleNotifier("http://127.0.0.1:1", settle_ms=0, timeout_s=0.05)
    c = build(notify=n)
    timeline = c.run([TARGET] * 5)               # must not raise
    assert len(timeline.records) == 5
    assert n.failed == 5 and n.sent == 0
