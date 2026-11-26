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

    stressor.set_brightness(15)
    assert stressor.current_state.get("brightness") == 15

    stressor.revert()
    assert stressor.is_active is False
    assert stressor.current_state == {}


def test_relational_telemetry_store_roundtrip(tmp_path):
    from core.event_logger import EventLogger
    from core.telemetry_store import TelemetryStore

    db_path = str(tmp_path / "telemetry.db")
    store = TelemetryStore(sqlite_path=db_path)
    assert store.backend == "sqlite"
    logger = EventLogger(output_path=str(tmp_path / "log.json"), store=store)
    logger.record("NETWORK_LATENCY", "LATENCY_INJECTED", {"latency_ms": 1200}, injection_latency_ms=12.5)
    rows = store.query_events(limit=10)
    assert len(rows) == 1
    assert rows[0]["action"] == "LATENCY_INJECTED"
    assert rows[0]["injection_latency_ms"] == 12.5

    store.insert_attribution_report({
        "analysis_timestamp": "2026-11-26T16:00:00Z",
        "attributions": [{
            "failure_id": "F-100",
            "failure_type": "TIMEOUT",
            "primary_trigger": "LATENCY_INJECTED",
            "confidence": 0.91,
        }],
    })


def test_event_logger_does_not_count_inter_event_idle_time(tmp_path):
    import time
    from core.event_logger import EventLogger

    logger = EventLogger(output_path=str(tmp_path / "events.json"))
    logger.record("SYSTEM", "FIRST_OP", {})
    time.sleep(0.12)
    second = logger.record("SYSTEM", "SECOND_OP", {})
    assert second["injection_latency_ms"] == 0.0
    assert second["latency_compliant"] is True

    logger.begin_action()
    time.sleep(0.02)
    third = logger.record("SYSTEM", "TIMED_OP", {})
    assert 15.0 <= third["injection_latency_ms"] < 100.0

    # Latency provider supplies real ADB duration when stressor calls record() without explicit args
    sample_vals = iter([18.4, 22.1])
    provided_logger = EventLogger(output_path=str(tmp_path / "provided.json"), latency_provider=lambda: next(sample_vals, 0.0))
    ev_p = provided_logger.record("NETWORK", "STATE_TRANSITION", {"mode": "offline"})
    assert ev_p["injection_latency_ms"] == 18.4
    assert ev_p["latency_compliant"] is True

    logger.events[0]["host_overhead"]["cpu_percent"] = 25.0
    logger.events[1]["host_overhead"]["cpu_percent"] = 25.0
    logger.events[2]["host_overhead"]["cpu_percent"] = 25.0
    summary = logger.get_performance_summary()
    assert summary["overhead_compliant"] is False


def test_corpus_findings_markdown_stays_synced(tmp_path):
    from run_corpus_benchmark import write_findings_markdown

    findings_doc = {
        "project_metadata": {
            "export_timestamp": "2026-11-24T13:59:40Z",
            "target_device": {"active_package": "org.fdroid.fdroid", "model": "Pixel_9_Pro", "device_id": "emulator-5554", "type": "Virtual AVD"},
        },
        "kpi_benchmarks": {"last_measured_latency_ms": 24.5, "rq1_compliant": True, "total_perturbations_recorded": 12},
        "attribution_summary": {"total_failures_analyzed": 0, "attributed_failures_count": 0, "attributions": []},
    }
    corpus_out = {
        "mode": "LIVE_DEVICE",
        "packages": ["org.fdroid.fdroid"],
        "regimes": {"1_BASELINE_NOMINAL": {"mean_latency_ms": 40.0, "mean_fps": 58.0, "jank_frame_drop_pct": 2.1, "failure_rate_pct": 0.0, "p_value_mann_whitney": 1.0}},
    }
    out_md = tmp_path / "findings.md"
    write_findings_markdown(findings_doc, corpus_out, str(out_md))
    text = out_md.read_text(encoding="utf-8")
    assert "2026-11-24T13:59:40Z" in text
    assert "org.fdroid.fdroid" in text
    assert "1_BASELINE_NOMINAL" in text
