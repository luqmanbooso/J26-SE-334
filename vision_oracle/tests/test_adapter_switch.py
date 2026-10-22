"""Adapter discovery and runtime switching. Uses fake adapter folders; no model is ever loaded."""

import json

import pytest

import vision_oracle.services.oracle_service as svc


@pytest.fixture
def adapters(tmp_path, monkeypatch):
    for name in ("c3_v3_vision_1ep", "c3_v3_fusion_1ep", "my_custom_run", "no_contract", "no_weights"):
        folder = tmp_path / name
        folder.mkdir()
        if name != "no_weights":
            (folder / "adapter_model.safetensors").write_bytes(b"x")
        if name not in ("no_contract", "no_weights"):
            (folder / "inference_contract.json").write_text(json.dumps({"image_max_pixels": 1}), encoding="utf-8")
    monkeypatch.setattr(svc, "LORA_WEIGHTS_PATH", tmp_path / "c3_v3_vision_1ep")
    monkeypatch.setattr(svc, "_ADAPTER_OVERRIDE", None)
    monkeypatch.setattr(svc, "_ORACLE_SERVICE", object())
    return tmp_path


def test_lists_only_adapters_with_weights_and_contract_known_ones_first(adapters):
    labels = [label for label, _ in svc.available_adapters()]
    assert labels[:2] == ["Vision (default): screenshot only", "Fusion (experimental): screenshot + layout"]
    assert "my_custom_run" in labels
    assert "no_contract" not in labels and "no_weights" not in labels


def test_active_adapter_defaults_to_configured_one(adapters):
    assert svc.active_adapter().name == "c3_v3_vision_1ep"


def test_switch_changes_active_adapter_and_drops_the_loaded_service(adapters):
    assert svc._ORACLE_SERVICE is not None
    svc.switch_adapter(adapters / "c3_v3_fusion_1ep")
    assert svc.active_adapter().name == "c3_v3_fusion_1ep"
    assert svc._ORACLE_SERVICE is None  # next get_oracle_service() builds a service with the new adapter


def test_switch_refuses_a_folder_without_weights(adapters):
    with pytest.raises(FileNotFoundError):
        svc.switch_adapter(adapters / "no_weights")
    assert svc.active_adapter().name == "c3_v3_vision_1ep"


def test_new_service_is_built_from_the_override(adapters, monkeypatch):
    seen = {}

    def fake_engine(adapter_dir=None):
        seen["adapter"] = adapter_dir
        return object()

    monkeypatch.setattr(svc, "create_default_engine", fake_engine)
    monkeypatch.setattr(svc, "get_repository", lambda: object())
    svc.switch_adapter(adapters / "c3_v3_fusion_1ep")
    svc.OracleService()
    assert seen["adapter"].name == "c3_v3_fusion_1ep"


def test_switch_closes_the_old_service_so_its_model_is_unloaded(adapters, monkeypatch):
    class Old:
        closed = 0

        def close(self):
            Old.closed += 1

    monkeypatch.setattr(svc, "_ORACLE_SERVICE", Old())
    svc.switch_adapter(adapters / "c3_v3_fusion_1ep")
    assert Old.closed == 1 and svc._ORACLE_SERVICE is None


def test_service_close_stops_its_worker_and_unloads_the_backend():
    class Backend:
        unloaded = 0

        def unload(self):
            Backend.unloaded += 1

    service = svc.OracleService.__new__(svc.OracleService)
    service._job_queue = svc.queue.Queue(maxsize=20)
    service._inference_lock = svc.threading.Lock()
    service._engine = type("E", (), {"backend": Backend()})()
    service.close()
    assert service._job_queue.get_nowait() is None  # the worker's stop signal
    assert Backend.unloaded == 1
