import pytest
from core.adb_client import ADBClient
from core.event_logger import EventLogger
from stressors.system_stressor import SystemStressor
from stressors.network_stressor import NetworkStressor
from stressors.interruption_stressor import InterruptionStressor
from stressors.context_stressor import ContextStressor

@pytest.fixture
def mock_context():
    adb = ADBClient(force_simulation=True)
    logger = EventLogger(output_path="test_event_log.json")
    return adb, logger

def test_system_stressor_cpu_and_thermal(mock_context):
    adb, logger = mock_context
    stressor = SystemStressor(adb, logger)

    stressor.set_cpu_load(target_pct=85)
    assert stressor.is_active is True
    assert stressor.current_state.get("cpu_pct") == 85

    stressor.set_thermal_state("Warn")
    assert stressor.current_state.get("thermal_state") == "Warn"

    stressor.set_ram_pressure(pressure_pct=90)
    assert stressor.current_state.get("ram_pct") == 90

    # Revert back to nominal
    stressor.revert()
    assert stressor.is_active is False
    assert "cpu_pct" not in stressor.current_state

def test_network_stressor_modes_and_latency(mock_context):
    adb, logger = mock_context
    stressor = NetworkStressor(adb, logger)

    stressor.set_mode("offline")
    assert stressor.current_state.get("mode") == "offline"

    stressor.inject_latency(latency_ms=1500)
    assert stressor.current_state.get("latency_ms") == 1500

    stressor.inject_packet_loss(loss_pct=10)
    assert stressor.current_state.get("packet_loss_pct") == 10

    stressor.set_bandwidth_profile("edge")
    assert stressor.current_state.get("speed_profile") == "edge"

    stressor.revert()
    assert stressor.is_active is False
    assert stressor.current_state == {}

def test_interruption_stressor_calls_and_sms(mock_context):
    adb, logger = mock_context
    stressor = InterruptionStressor(adb, logger)

    stressor.trigger_incoming_call("15550192831")
    assert stressor.is_active is True
    assert stressor.active_call_number == "15550192831"

    stressor.accept_call()
    stressor.dismiss_call("15550192831")
    assert stressor.active_call_number is None

    stressor.send_sms_banner("Test SMS Verification Code: 994812")
    stressor.revert()
    assert stressor.is_active is False

def test_context_stressor_rotation_and_theme(mock_context):
    adb, logger = mock_context
    stressor = ContextStressor(adb, logger)

    stressor.set_orientation("landscape")
    assert stressor.current_state.get("orientation") == "landscape"

    stressor.set_dark_mode(True)
    assert stressor.current_state.get("dark_mode") is True

    stressor.set_font_scale(1.35)
    assert stressor.current_state.get("font_scale") == 1.35

    stressor.revert()
    assert stressor.is_active is False
    assert stressor.current_state == {}
