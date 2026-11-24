"""
Empirical Evaluation Harness for C3 Vision-Semantic Oracle.
Loads fine-tuned LoRA weights (from Downloads or custom path) and evaluates against
the held-out test split from colab_c3_dataset.zip (or extracted dataset).
"""

import os
import io
import time
import json
import zipfile
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image


from local_vision_oracle.prompt import PromptBuilder
from local_vision_oracle.engine import TransformersInferenceBackend
from local_vision_oracle.evaluation_accounting import (
    parse_prediction, file_digest, summarize_records, restore_records,
)


def find_default_weights_dir(preferred_path: Optional[str] = None) -> Path:
    """Auto-detects fine-tuned LoRA weights directory."""
    if preferred_path:
        path = Path(preferred_path)
        if not (path.is_dir() and (path / "adapter_config.json").is_file()):
            raise FileNotFoundError(f"Invalid requested adapter directory: {path}")
        return path

    candidates = [
        Path(__file__).resolve().parents[1] / "models/c3_qwen2vl_2b_lora_step246",
        Path(r"D:\university\Resesarch\results\c3_lora_final"),
        Path(r"C:\Users\hp\Downloads\Downloads\c3_lora_run3_weights"),
        Path(r"C:\Users\hp\Downloads\c3_lora_run3_weights"),
        Path(r"D:\university\Resesarch\results\llama_factory_lora"),
    ]
    for c in candidates:
        if c.exists() and (c / "adapter_config.json").exists():
            return c

    # Recursive scan in user Downloads folder
    dl_root = Path(r"C:\Users\hp\Downloads")
    if dl_root.exists():
        for root, dirs, files in os.walk(dl_root):
            if "adapter_config.json" in files:
                return Path(root)

    raise FileNotFoundError(
        "Could not auto-locate fine-tuned LoRA weights in Downloads or results. "
        "Please specify path with --weights."
    )


def find_default_dataset_path(preferred_path: Optional[str] = None) -> Path:
    """Auto-detects dataset zip or json test manifest."""
    if preferred_path:
        path = Path(preferred_path)
        if not path.exists():
            raise FileNotFoundError(f"Requested dataset does not exist: {path}")
        return path

    candidates = [
        Path(r"D:\university\Resesarch\dataset\eval_rico_owleye_prepared_120.json"),
        Path(r"D:\university\Resesarch\dataset\eval_rico_owleye_prepared_full.json"),
        Path(r"dataset\eval_rico_owleye_prepared_120.json"),
        Path(r"dataset\eval_rico_owleye_prepared_full.json"),
        Path(r"D:\university\Resesarch\colab_c3_dataset.zip"),
        Path(r"D:\university\Resesarch\dataset\test.json"),
        Path(r"colab_c3_dataset.zip"),
    ]
    for c in candidates:
        if c.exists():
            return c

    raise FileNotFoundError(
        "Could not auto-locate dataset archive or test.json. "
        "Please specify path with --dataset."
    )


def find_default_base_model(preferred_path: Optional[str] = None) -> str:
    """Resolve local model files; never silently replace a requested model."""
    if preferred_path:
        if not Path(preferred_path).is_dir():
            raise FileNotFoundError(f"Requested local base model does not exist: {preferred_path}")
        return preferred_path

    bundled = Path(__file__).resolve().parents[1] / "models/Qwen2-VL-2B-Instruct"
    if bundled.is_dir():
        return str(bundled)

    local_path = Path(r"D:\university\Resesarch\RD\models\Qwen2-VL-2B-Instruct")
    if local_path.exists():
        return str(local_path)

    raise FileNotFoundError("Specify --base-model with a local Qwen2-VL model directory")


class TestDatasetLoader:
    """Loads test samples and images directly from zip archive or directory."""
    __test__ = False

    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)
        self.is_zip = self.dataset_path.suffix.lower() == ".zip"
        self.zip_file: Optional[zipfile.ZipFile] = None
        self.samples: List[Dict[str, Any]] = []

        if self.is_zip:
            self.zip_file = zipfile.ZipFile(self.dataset_path, "r")
            test_names = [n for n in self.zip_file.namelist() if n.endswith("test.json")]
            if len(test_names) != 1:
                self.zip_file.close()
                raise ValueError(f"Expected exactly one test.json inside {self.dataset_path}")
            raw = self.zip_file.read(test_names[0]).decode("utf-8")
            self.samples = json.loads(raw)
        else:
            if self.dataset_path.is_file() and self.dataset_path.suffix.lower() == ".json":
                with open(self.dataset_path, "r", encoding="utf-8") as f:
                    self.samples = json.load(f)
            else:
                test_file = self.dataset_path / "test.json"
                if not test_file.exists():
                    raise ValueError(f"test.json not found in {self.dataset_path}")
                with open(test_file, "r", encoding="utf-8") as f:
                    self.samples = json.load(f)

    def __len__(self) -> int:
        return len(self.samples)

    def get_sample(self, idx: int) -> Tuple[Dict[str, Any], Image.Image]:
        sample = self.samples[idx]
        img_ref = sample["images"][0]

        if self.is_zip:
            # Normalize path inside zip
            clean_ref = img_ref.replace("\\", "/")
            if clean_ref not in self.zip_file.namelist():
                # Try matching by filename
                base_name = Path(clean_ref).name
                matches = [n for n in self.zip_file.namelist() if Path(n).name == base_name]
                if len(matches) == 1:
                    clean_ref = matches[0]
                elif len(matches) > 1:
                    raise ValueError(f"Ambiguous image filename in zip: {base_name}")
                else:
                    raise FileNotFoundError(f"Image {clean_ref} not found in zip archive.")
            img_bytes = self.zip_file.read(clean_ref)
            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        else:
            # File system lookup
            img_path = Path(img_ref)
            if not img_path.is_absolute():
                base_dir = self.dataset_path.parent if self.dataset_path.is_file() else self.dataset_path
                img_path = base_dir / img_ref
            if not img_path.exists():
                raise FileNotFoundError(f"Image {img_path} not found on disk.")
            image = Image.open(img_path).convert("RGB")

        return sample, image

    def close(self):
        if self.zip_file:
            self.zip_file.close()


def build_run_identity(loader, weights, base_model, load_in_4bit):
    """Hash local model, input and evaluator content before allowing resume."""
    base = Path(base_model)
    if not base.is_dir():
        raise ValueError("Evaluation requires an explicit local base model directory")
    model_files = {}
    for label, folder in (("base", base), ("adapter", Path(weights))):
        files = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix in {
            ".json", ".jinja", ".safetensors", ".bin", ".model",
        })
        if not files:
            raise ValueError(f"No model files found in {folder}")
        model_files[label] = {str(p.relative_to(folder)): file_digest(p) for p in files}
    source = loader.dataset_path
    manifest = source if source.is_file() else source / "test.json"
    images = {}
    if not loader.is_zip:
        root = source.parent if source.is_file() else source
        for sample in loader.samples:
            image_path = Path(sample["images"][0])
            if not image_path.is_absolute():
                image_path = root / image_path
            images[str(image_path.resolve())] = file_digest(image_path) if image_path.is_file() else "missing"
    code_dir = Path(__file__).parent
    from importlib.metadata import version, PackageNotFoundError
    versions = {}
    for package in ("torch", "transformers", "peft", "bitsandbytes", "Pillow"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return {
        "schema_version": 2,
        "model_files": model_files,
        "package_versions": versions,
        "dataset_sha256": file_digest(manifest),
        "image_sha256": images,
        "code_sha256": {name: file_digest(code_dir / name) for name in (
            "evaluate_test_split.py", "evaluation_accounting.py", "engine.py", "prompt.py", "schemas.py", "evaluation.py",
        )},
        "load_in_4bit": load_in_4bit,
        "coverage_policy": "global_only",
        "prompt_policy": "production_vision_only",
        "max_new_tokens": 256,
        "temperature": 0.0,
        "thumbnail_bounds": [720, 1280],
    }


def run_evaluation(
    weights_path: Optional[str] = None,
    dataset_path: Optional[str] = None,
    base_model_path: Optional[str] = None,
    output_dir: str = r"D:\university\Resesarch\results\c3_eval",
    limit: Optional[int] = None,
    load_in_4bit: bool = True,
    resume: bool = True,
) -> Dict[str, Any]:
    """Evaluate the production vision-only global pass with explicit abstentions.

    Schema v2 deliberately uses explicit metric names: valid-only statistics
    must be read alongside coverage and end-to-end recall. This is not a tiled
    production benchmark or a verification of the supplied ground truth.
    """
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    resolved_weights = find_default_weights_dir(weights_path)
    resolved_dataset = find_default_dataset_path(dataset_path)
    resolved_base = find_default_base_model(base_model_path)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    loader = TestDatasetLoader(str(resolved_dataset))
    try:
        total = len(loader) if limit is None else min(limit, len(loader))
        if not total:
            raise ValueError("Dataset is empty")
        print("Hashing local model and dataset files for checkpoint provenance...")
        identity = build_run_identity(loader, resolved_weights, resolved_base, load_in_4bit)
        checkpoint_file = out_path / "eval_checkpoint_v2.json"
        if resume and (out_path / "eval_checkpoint.json").exists() and not checkpoint_file.exists():
            raise ValueError("Legacy checkpoint cannot be resumed; use a new output directory or --no-resume")
        records = []
        if resume and checkpoint_file.exists():
            records = restore_records(json.loads(checkpoint_file.read_text(encoding="utf-8")), identity, total)

        # Validate all ground truth before any inference. Bad annotations are
        # dataset errors, never invented negative labels.
        targets = []
        for sample in loader.samples[:total]:
            answers = [m["content"] for m in sample["messages"] if m["role"] == "assistant"]
            if len(answers) != 1:
                raise ValueError("Each evaluation sample must have exactly one ground-truth answer")
            targets.append(parse_prediction(answers[0]))

        backend = TransformersInferenceBackend(
            model_name_or_path=str(resolved_base), adapter_dir=str(resolved_weights),
            quantization_bit=4 if load_in_4bit else None,
        )
        # Load outside sample timing; model-load failures abort the run, not the dataset.
        if len(records) < total:
            backend._load_model()
        builder = PromptBuilder()
        started = time.perf_counter()
        for index in range(len(records), total):
            sample, target = loader.samples[index], targets[index]
            record = {
                "index": index, "dataset": sample.get("dataset", sample.get("source_dataset", "unknown")),
                "image": sample["images"][0],
                "true_has_defect": target["has_defect"], "true_defect_type": target["defect_type"],
                "true_bbox": target.get("bounding_box"),
                "pred_has_defect": None, "pred_defect_type": None, "pred_bbox": None,
                "raw_output": None, "error": None, "status": "input_error",
            }
            tick = time.perf_counter()
            try:
                _, image = loader.get_sample(index)
                record["status"] = "inference_error"
                messages = builder.build_qwen_chat_input(image_content=image)
                raw = backend.generate(messages=messages, image=image, max_new_tokens=256, temperature=0.0)
                record["raw_output"] = raw
                record["status"] = "invalid_output"
                prediction = parse_prediction(raw)
                record.update(
                    status="valid", pred_has_defect=prediction["has_defect"],
                    pred_defect_type=prediction["defect_type"], pred_bbox=prediction.get("bounding_box"),
                )
            except Exception as error:
                record["error"] = f"{type(error).__name__}: {error}"
            record["latency_ms"] = round((time.perf_counter() - tick) * 1000, 2)
            records.append(record)
            # Atomic, per-sample checkpoints preserve full raw output on interruption.
            temporary = checkpoint_file.with_suffix(".tmp")
            temporary.write_text(json.dumps({"run_identity": identity, "detailed_records": records}, indent=2), encoding="utf-8")
            temporary.replace(checkpoint_file)
            print(f"[{index + 1}/{total}] {record['status']}")

        summary = summarize_records(records)
        summary.update(
            schema_version=2, run_identity=identity,
            weights_path=str(resolved_weights), dataset_path=str(resolved_dataset),
            base_model_path=str(resolved_base),
            current_invocation_duration_seconds=round(time.perf_counter() - started, 2),
            metric_policy={
                "confusion_matrix": "valid predictions only; abstentions reported separately",
                "binary_macro_f1": "mean of clean and defect F1; fixed two labels; zero division gives 0",
                "multiclass_macro_f1": "valid predictions only; labels are union of observed true/predicted defect types, including none",
                "localization": "all positive samples with ground-truth boxes; misses/abstentions/missing predicted boxes score zero",
                "latency": "image loading through parsing; excludes model loading; includes failures",
            },
            by_dataset={name: summarize_records([r for r in records if r["dataset"] == name])
                        for name in sorted({r["dataset"] for r in records})},
        )
        # Versioned output names preserve historical reports.
        (out_path / "evaluation_summary_v2.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (out_path / "evaluation_records_v2.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        import csv
        with (out_path / "evaluation_metrics_v2.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["metric", "value"])
            writer.writerows(summary["metrics"].items())
        print(json.dumps(summary["metrics"], indent=2))
        return summary
    finally:
        loader.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate C3 LoRA model weights on held-out test split.")
    parser.add_argument("--weights", type=str, default=None, help="Path to LoRA weights folder (auto-detected if omitted)")
    parser.add_argument("--dataset", type=str, default=None, help="Path to colab_c3_dataset.zip or test.json (auto-detected if omitted)")
    parser.add_argument("--base-model", type=str, default=None, help="Local base model directory (offline only)")
    parser.add_argument("--output-dir", type=str, default=r"D:\university\Resesarch\results\c3_eval", help="Directory to save evaluation reports and plots")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of test samples to evaluate (e.g. 10 for quick smoke test)")
    parser.add_argument("--no-quant", action="store_true", help="Disable 4-bit NF4 quantization (runs in fp16)")
    parser.add_argument("--no-resume", action="store_true", help="Start from sample 0 instead of resuming checkpoint")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_evaluation(
        weights_path=args.weights,
        dataset_path=args.dataset,
        base_model_path=args.base_model,
        output_dir=args.output_dir,
        limit=args.limit,
        load_in_4bit=not args.no_quant,
        resume=not args.no_resume,
    )
