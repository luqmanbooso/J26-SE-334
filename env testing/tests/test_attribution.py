import time
import pytest
from attribution_engine import EnvironmentAttributionEngine

def test_failure_attribution_temporal_and_causal():
    engine = EnvironmentAttributionEngine()

    now_ms = int(time.time() * 1000)

    # Injected perturbations
    perturbation_events = [
        {
            "epoch_ms": now_ms - 2000,
            "category": "NETWORK_THROTTLE",
            "action": "BANDWIDTH_PROFILE_SET",
            "parameters": {"profile": "edge"}
        },
        {
            "epoch_ms": now_ms - 1500,
            "category": "NETWORK_LATENCY",
            "action": "LATENCY_INJECTED",
            "parameters": {"latency_ms": 2200}
        },
        {
            "epoch_ms": now_ms - 500,
            "category": "CONTEXT_ORIENTATION",
            "action": "ORIENTATION_CHANGED",
            "parameters": {"mode": "landscape"}
        }
    ]

    # Observed failures
    failures = [
        {
            "id": "F_NET_01",
            "type": "PAYMENT_GATEWAY_TIMEOUT",
            "description": "Network socket timeout during checkout commit.",
            "component": "CheckoutActivity",
            "epoch_ms": now_ms - 1400
        },
        {
            "id": "F_GUI_01",
            "type": "GUI_OVERFLOW_COLLISION",
            "description": "Button collided and clipped below screen border.",
            "component": "OrderSummaryFragment",
            "epoch_ms": now_ms - 400
        }
    ]

    report = engine.correlate(failures, perturbation_events, time_window_sec=2.5)

    assert report["total_failures_analyzed"] == 2
    assert report["attributed_failures_count"] == 2

    attr1 = report["attributions"][0]
    assert attr1["failure_id"] == "F_NET_01"
    assert attr1["confidence"] > 0.85
    assert "LATENCY" in attr1["primary_trigger"] or "BANDWIDTH" in attr1["primary_trigger"]

    attr2 = report["attributions"][1]
    assert attr2["failure_id"] == "F_GUI_01"
    assert attr2["confidence"] > 0.85
    assert "ORIENTATION" in attr2["primary_trigger"]
