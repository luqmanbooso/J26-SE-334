import pytest
from core.scheduler import PerturbationScheduler

def test_semantic_step_registration_and_trigger():
    scheduler = PerturbationScheduler()
    executed_steps = []

    def dummy_action(**kwargs):
        executed_steps.append(kwargs)

    scheduler.register_step_hook("MID_TRANSACTION", dummy_action, {"stress_type": "handover"})
    scheduler.register_step_hook("PRE_INPUT", dummy_action, {"stress_type": "battery_drop"})

    # Trigger PRE_INPUT
    scheduler.trigger_step("PRE_INPUT")
    assert len(executed_steps) == 1
    assert executed_steps[0]["stress_type"] == "battery_drop"

    # Trigger MID_TRANSACTION
    scheduler.trigger_step("MID_TRANSACTION")
    assert len(executed_steps) == 2
    assert executed_steps[1]["stress_type"] == "handover"

def test_performance_signal_adaptive_escalation():
    scheduler = PerturbationScheduler()
    escalated_signals = []

    def on_escalate_callback(escalation_type):
        escalated_signals.append(escalation_type)

    # Signal 1: Healthy (FPS 59.5, Latency 80ms) -> No escalation
    res1 = scheduler.evaluate_performance_signals({"fps": 59.5, "latency_ms": 80.0}, on_escalate=on_escalate_callback)
    assert res1 is False
    assert len(escalated_signals) == 0

    # Signal 2: Low FPS (24.0 < 35.0) -> Triggers HARDWARE_ESCALATION
    res2 = scheduler.evaluate_performance_signals({"fps": 24.0, "latency_ms": 150.0}, on_escalate=on_escalate_callback)
    assert res2 is True
    assert "HARDWARE_ESCALATION" in escalated_signals

    # Signal 3: High Latency (1450ms > 1200ms) -> Triggers NETWORK_ESCALATION
    res3 = scheduler.evaluate_performance_signals({"fps": 55.0, "latency_ms": 1450.0}, on_escalate=on_escalate_callback)
    assert res3 is True
    assert "NETWORK_ESCALATION" in escalated_signals


def test_asyncio_timeline_and_async_step_dispatch():
    import asyncio
    scheduler = PerturbationScheduler()
    fired = []

    def rec(tag):
        fired.append(tag)

    scheduler.register_step_hook("MID_TRANSACTION", rec, {"tag": "hook_a"})
    scheduler.register_step_hook("MID_TRANSACTION", rec, {"tag": "hook_b"})
    res = asyncio.run(scheduler.trigger_step_async("MID_TRANSACTION"))
    assert len(res) == 2
    assert set(fired) == {"hook_a", "hook_b"}

    timeline_events = []
    registry = {"cpu": lambda target_pct: timeline_events.append(("cpu", target_pct))}
    dispatched = scheduler.run_timeline(
        [{"offset_ms": 5, "step": "PRE_INPUT", "action": "cpu", "params": {"target_pct": 85}}],
        action_registry=registry,
    )
    assert len(dispatched) == 1
    assert dispatched[0]["status"] == "APPLIED"
    assert ("cpu", 85) in timeline_events
