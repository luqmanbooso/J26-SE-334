"""Backend contract regressions; test doubles do not measure model accuracy."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock
import sys

import pytest
from PIL import Image

from local_vision_oracle.engine import TransformersInferenceBackend


@pytest.mark.parametrize("adapter", [None, "local-adapter"])
@pytest.mark.parametrize("temperature", [0.0, 0.4])
def test_backend_preserves_messages_and_decodes_only_completion(monkeypatch, adapter, temperature):
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(no_grad=nullcontext))

    class Inputs(dict):
        input_ids = [[10, 20, 30]]

        def to(self, device):
            assert device == "cpu"
            return self

    inputs = Inputs(input_ids=Inputs.input_ids)
    processor = Mock()
    processor.apply_chat_template.return_value = "rendered caller prompt"
    processor.return_value = inputs
    processor.batch_decode.return_value = ['{"has_defect": false}']
    model = Mock(device="cpu")
    model.generate.return_value = [[10, 20, 30, 40, 50]]
    backend = TransformersInferenceBackend(adapter_dir=adapter)
    backend.processor = processor
    backend.model = model
    messages = [
        {"role": "system", "content": "Return the required JSON schema."},
        {"role": "user", "content": [
            {"type": "image"},
            {"type": "text", "text": "Hierarchy: checkout button clipped."},
        ]},
    ]
    image = Image.new("RGB", (1080, 2400))

    output = backend.generate(messages, image, temperature=temperature)

    processor.apply_chat_template.assert_called_once_with(
        messages, tokenize=False, add_generation_prompt=True,
    )
    assert processor.call_args.kwargs["text"] == ["rendered caller prompt"]
    assert processor.call_args.kwargs["images"][0].size == (576, 1280)
    assert image.size == (1080, 2400)
    options = model.generate.call_args.kwargs
    assert options["max_new_tokens"] == 256
    assert options["do_sample"] is (temperature > 0)
    if temperature:
        assert options["temperature"] == temperature
    else:
        assert "temperature" not in options
    processor.batch_decode.assert_called_once_with(
        [[40, 50]], skip_special_tokens=True, clean_up_tokenization_spaces=False,
    )
    assert output == '{"has_defect": false}'
