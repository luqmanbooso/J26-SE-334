import os
import pytest
from core.profile_parser import ProfileParser, ProfileValidationError
from orchestrator import PerturbationOrchestrator

def test_parse_valid_yaml_string():
    raw_yaml = """
name: "Test 3G Drop"
cpuStress: 30
ramStress: 40
latency: 1500
packetLoss: 5
thermalState: "Warn"
networkProfile: "3G Slow"
"""
    parsed = ProfileParser.parse_yaml_string(raw_yaml)
    assert parsed["name"] == "Test 3G Drop"
    assert parsed["latency"] == 1500
    assert parsed["thermalState"] == "Warn"

def test_parse_invalid_ranges():
    invalid_yaml = "cpuStress: 150\n"
    with pytest.raises(ProfileValidationError) as exc:
        ProfileParser.parse_yaml_string(invalid_yaml)
    assert "cpuStress" in str(exc.value)

def test_parse_invalid_thermal():
    invalid_yaml = "thermalState: 'SuperHot'\n"
    with pytest.raises(ProfileValidationError) as exc:
        ProfileParser.parse_yaml_string(invalid_yaml)
    assert "thermalState" in str(exc.value)

def test_all_packaged_templates():
    profiles_dir = os.path.join(os.path.dirname(__file__), "..", "profiles")
    assert os.path.exists(profiles_dir)
    files = [f for f in os.listdir(profiles_dir) if f.endswith((".yaml", ".yml"))]
    assert len(files) >= 5

    for f in files:
        path = os.path.join(profiles_dir, f)
        parsed = ProfileParser.parse_file(path)
        assert "name" in parsed
        assert 0 <= parsed["cpuStress"] <= 100
        assert 0 <= parsed["latency"] <= 10000

def test_orchestrator_template_listing_and_metrics():
    orch = PerturbationOrchestrator(force_simulation=True)
    templates = orch.list_templates()
    assert len(templates) >= 5

    # Test applying a template
    first = templates[0]
    telem = orch.apply_profile(first["profile"])
    assert telem["performance"]["total_events"] >= 1
    assert telem["performance"]["latency_target_ms"] == 100.0
