"""
End-to-End Cross-Component Integration Test for HEART Framework (J26-SE-334).
Tests the integration chain:
Component 2 (biometric stress action trigger) ->
Component 3 (multimodal oracle inspection & verdict ledger) ->
Component 4 (C3LiveClient & PromptBuilder self-healing test synthesis).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

from vision_oracle.server import app, set_engine
from local_vision_oracle.engine import OracleEngine, MockInferenceBackend
from local_vision_oracle.schemas import DefectType, C3OracleResult, LatencyBreakdown, Verdict
from c4.c3_interface import C3LiveClient, C3Verdict
from c4.schemas import EventKind, EventSource, FailureJourney, NormalizedEvent
from c4.synthesis.prompt_builder import PromptBuilder


def test_full_c2_c3_c4_integration_flow(tmp_path: Path):
    # 1. Setup C3 service with Mock backend returning a known UI defect
    defect_json = json.dumps({
        "has_defect": True,
        "defect_type": "component_overlap",
        "confidence": 0.92,
        "bounding_box": [100, 150, 300, 450],
        "affected_element_id": "com.shop:id/btn_checkout",
        "explanation": "Overlapping buttons detected on Checkout screen under stress",
    })
    mock_backend = MockInferenceBackend(default_response=defect_json, simulated_latency_ms=0.0)
    c3_engine = OracleEngine(backend=mock_backend)
    set_engine(c3_engine)
    client = TestClient(app)


    # 2. C2 dispatches trigger to C3
    c2_payload = {
        "action_id": "c2_act_stress_swipe_01",
        "session_id": "heart_session_e2e_42",
        "target_element_id": "com.shop:id/btn_checkout",
        "stress_level": 0.85,
        "delay_ms": 220.0,
    }
    trigger_resp = client.post("/api/oracle/trigger", json=c2_payload)
    assert trigger_resp.status_code == 202
    assert trigger_resp.json()["status"] == "enqueued"

    # 3. Simulate C3 evaluated screen for this session
    img_path = tmp_path / "screen_after_c2_stress.png"
    Image.new("RGB", (360, 640), (240, 240, 240)).save(img_path)

    eval_resp = client.post(
        "/api/oracle/evaluate",
        json={
            "image_path": str(img_path),
            "hierarchy_xml": '<hierarchy><node class="android.widget.Button" bounds="[10,20][100,60]"/></hierarchy>',
            "screen_id": "CheckoutActivity",
            "session_id": "heart_session_e2e_42",
            "action_context": "C2 Stress Swipe",
        },
    )
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["c4_verdict"]["has_gui_defect"] is True
    assert eval_data["c4_verdict"]["defect_type"] == "component_overlap"

    # 4. C4 Live Client retrieves C3 visual verdict for the failure journey
    c4_failure = NormalizedEvent(
        event_id="evt-crash-checkout-99",
        session_id="heart_session_e2e_42",
        source=EventSource.SENTRY,
        kind=EventKind.ERROR,
        timestamp=datetime.now(timezone.utc),
        name="IllegalStateException",
        screen="CheckoutActivity",
        attributes={"screenshot_path": str(img_path)},
    )
    c4_journey = FailureJourney(
        journey_id="journey_e2e_checkout",
        session_id="heart_session_e2e_42",
        failure=c4_failure,
        events=[c4_failure],
        metadata={"failing_screen": "CheckoutActivity"},
    )

    c3_live = C3LiveClient(mode="in_process", engine=c3_engine)
    c4_verdict = c3_live.get_verdict(
        session_id="heart_session_e2e_42",
        failure=c4_failure,
        journey=c4_journey,
    )

    assert isinstance(c4_verdict, C3Verdict)
    assert c4_verdict.has_gui_defect is True
    assert c4_verdict.defect_type == "component_overlap"
    assert c4_verdict.confidence == 0.92

    # 5. C4 PromptBuilder builds synthesis prompt enriched with C3 visual evidence
    builder = PromptBuilder(include_c3=True)
    prompt = builder.build(c4_journey, c4_verdict)

    assert "C3 evidence:" in prompt
    assert '"has_gui_defect": true' in prompt
    assert '"defect_type": "component_overlap"' in prompt
    assert "CheckoutActivity" in prompt
