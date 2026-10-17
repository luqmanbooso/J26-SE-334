"""C2's side of IF-C2-to-C3: the action-complete trigger.

C3's oracle exposes `POST /api/oracle/trigger` (202, enqueued) and captures
the screen when a trigger arrives. Two timing rules make that capture worth
having, both enforced here rather than hoped for:

1. **Injection must be complete.** The controller calls the notifier only
   after the dispatcher has returned — `input swipe` blocks for the gesture's
   whole duration, and a rage burst notifies once, after its last re-tap,
   never per sub-tap.

2. **The frame must have settled.** A trigger fired the same millisecond as
   a tremor-swipe lands captures motion blur and transitional hierarchies.
   The notifier waits `settle_ms` (default 200, per the agreed 150-250 band)
   before posting, so C3 photographs the resting frame.

A capture is telemetry, not control flow: a dead or absent oracle must never
break the engine's loop, so failures are counted and reported, not raised.
"""
import json
import time
import urllib.request


class OracleNotifier:
    """Posts one C2TriggerPayload per completed action to C3's oracle."""

    def __init__(self, base_url, session_id="live_session", settle_ms=200.0,
                 timeout_s=2.0, sleep=time.sleep, device_serial=None):
        self.url = base_url.rstrip("/") + "/api/oracle/trigger"
        self.session_id = session_id
        self.settle_ms = settle_ms
        self.timeout_s = timeout_s
        self.sleep = sleep
        self.device_serial = device_serial
        self.sent = 0
        self.failed = 0
        self._action_seq = 0

    def __call__(self, record):
        """Notify C3 that one action (tap, burst or gesture) has completed."""
        self._action_seq += 1
        if self.settle_ms > 0:
            self.sleep(self.settle_ms / 1000.0)
        payload = {
            "action_id": f"{self.session_id}-{self._action_seq:04d}",
            "session_id": self.session_id,
            "target_element_id": record.target_element_id or None,
            "stress_level": record.stress_s,
            "delay_ms": self.settle_ms,     # the settle this trigger waited
            "device_serial": self.device_serial,
        }
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                ok = 200 <= resp.status < 300
        except Exception:
            ok = False
        if ok:
            self.sent += 1
        else:
            self.failed += 1
            if self.failed in (1, 10, 100):   # loud, but never fatal
                print(f"[oracle] trigger POST failing (count={self.failed}) "
                      f"-> {self.url}")
        return ok
