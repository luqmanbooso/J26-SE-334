"""Run a frozen, visually reviewed diagnostic selection with base OR adapter.

Run each arm in a separate process to release GPU memory between models.
The selection is diagnostic evidence, not an untouched accuracy benchmark.
"""

import argparse
import json
import time
from pathlib import Path

from PIL import Image

from local_vision_oracle.engine import TransformersInferenceBackend
from local_vision_oracle.prompt import PromptBuilder
from local_vision_oracle.evaluation_accounting import (
    file_digest, parse_prediction, summarize_records,
)


def run(selection_path, base_model, adapter, output):
    selection_path, output = Path(selection_path), Path(output)
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite diagnostic evidence: {output}")
    for sample in selection["samples"]:
        if file_digest(sample["image"]) != sample["image_sha256"]:
            raise ValueError(f"Image changed after review: {sample['id']}")
        parse_prediction(json.dumps(sample["reviewed_target"]))
    identity = {
        "selection_sha256": file_digest(selection_path),
        "base_model": str(Path(base_model).resolve()),
        "adapter": str(Path(adapter).resolve()) if adapter else None,
        "adapter_sha256": file_digest(Path(adapter) / "adapter_model.safetensors") if adapter else None,
        "base_weight_sha256": {p.name: file_digest(p) for p in sorted(Path(base_model).glob("*.safetensors"))},
        "generation": {"max_new_tokens": 256, "temperature": 0.0, "quantization_bit": 4},
        "coverage": "global_only",
        "engine_sha256": file_digest(Path(__file__).with_name("engine.py")),
        "prompt_sha256": file_digest(Path(__file__).with_name("prompt.py")),
        "review_scope": selection["scope"],
    }
    print("Loading " + ("adapter" if adapter else "base") + " model", flush=True)
    tick = time.perf_counter()
    backend = TransformersInferenceBackend(
        model_name_or_path=base_model, adapter_dir=adapter,
        quantization_bit=4, device="cuda",
    )
    backend._load_model()
    identity["load_seconds"] = time.perf_counter() - tick
    import torch
    identity["torch_version"] = torch.__version__
    identity["device_map"] = {k: str(v) for k, v in getattr(backend.model, "hf_device_map", {}).items()}
    builder = PromptBuilder()
    records = []
    output.parent.mkdir(parents=True, exist_ok=True)
    for sample in selection["samples"]:
        target = sample["reviewed_target"]
        record = {
            "id": sample["id"], "index": len(records), "split": sample["split"],
            "true_has_defect": target["has_defect"], "true_defect_type": target["defect_type"],
            "true_bbox": target.get("bounding_box"), "pred_has_defect": None,
            "pred_defect_type": None, "pred_bbox": None, "status": "inference_error",
            "raw_output": None, "error": None,
        }
        print(f"Starting {sample['id']}", flush=True)
        torch.cuda.reset_peak_memory_stats()
        tick = time.perf_counter()
        try:
            with Image.open(sample["image"]) as source:
                image = source.convert("RGB")
            messages = builder.build_qwen_chat_input(image_content=image)
            raw = backend.generate(messages, image, max_new_tokens=256, temperature=0.0)
            record["raw_output"] = raw
            record["status"] = "invalid_output"
            pred = parse_prediction(raw)
            record.update(status="valid", pred_has_defect=pred["has_defect"],
                          pred_defect_type=pred["defect_type"], pred_bbox=pred.get("bounding_box"))
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        torch.cuda.synchronize()
        record["latency_ms"] = round((time.perf_counter() - tick) * 1000, 2)
        record["peak_allocated_vram_bytes"] = torch.cuda.max_memory_allocated()
        records.append(record)
        result = {
            "identity": identity, "records": records,
            "by_split": {
                split: summarize_records([r for r in records if r["split"] == split])
                for split in sorted({r["split"] for r in records})
            },
            "completed": len(records) == len(selection["samples"]),
        }
        temporary = output.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
        temporary.replace(output)
        print(json.dumps(record), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--adapter", default=None)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.selection, args.base_model, args.adapter, args.output)
