"""
Empirical Evaluation Harness for C3 Vision-Semantic Oracle.
Loads fine-tuned LoRA weights (from Downloads or custom path) and evaluates against
the held-out test split from colab_c3_dataset.zip (or extracted dataset).
"""

import os
import sys
import io
import time
import json
import zipfile
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image

import torch
import numpy as np
import matplotlib.pyplot as plt
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
from peft import PeftModel

from local_vision_oracle.prompt import VerdictParser
from local_vision_oracle.evaluation import compute_bbox_iou, mcnemar_test
from local_vision_oracle.schemas import DefectType


def find_default_weights_dir(preferred_path: Optional[str] = None) -> Path:
    """Auto-detects fine-tuned LoRA weights directory."""
    if preferred_path and Path(preferred_path).exists():
        return Path(preferred_path)

    candidates = [
        Path(r"D:\university\Resesarch\results\c3_lora_final"),
        Path(r"D:\university\Resesarch\J26-SE-334\vision_oracle\models\c3_qwen2vl_2b_lora_step246"),
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
    if preferred_path and Path(preferred_path).exists():
        return Path(preferred_path)

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
    """Auto-detects local base model path or falls back to HuggingFace repo."""
    if preferred_path and os.path.exists(preferred_path):
        return preferred_path

    local_path = Path(r"D:\university\Resesarch\RD\models\Qwen2-VL-2B-Instruct")
    if local_path.exists():
        return str(local_path)

    return "Qwen/Qwen2-VL-2B-Instruct"


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
            if not test_names:
                raise ValueError(f"No test.json found inside {self.dataset_path}")
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
                matches = [n for n in self.zip_file.namelist() if n.endswith(base_name)]
                if matches:
                    clean_ref = matches[0]
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


def run_evaluation(
    weights_path: Optional[str] = None,
    dataset_path: Optional[str] = None,
    base_model_path: Optional[str] = None,
    output_dir: str = r"D:\university\Resesarch\results\c3_eval",
    limit: Optional[int] = None,
    load_in_4bit: bool = True,
    resume: bool = True,
) -> Dict[str, Any]:
    """
    Executes full evaluation pipeline on held-out test split.
    """
    resolved_weights = find_default_weights_dir(weights_path)
    resolved_dataset = find_default_dataset_path(dataset_path)
    resolved_base = find_default_base_model(base_model_path)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print(" C3 ORACLE: EMPIRICAL TEST SPLIT EVALUATOR")
    print("=" * 75)
    print(f"[LoRA Weights]   : {resolved_weights}")
    print(f"[Dataset Split]  : {resolved_dataset}")
    print(f"[Base Model]     : {resolved_base}")
    print(f"[Output Folder]  : {out_path}")
    print(f"[4-bit NF4]      : {load_in_4bit}")

    # 1. Initialize Dataset
    loader = TestDatasetLoader(str(resolved_dataset))
    total_count = len(loader) if limit is None else min(limit, len(loader))
    print(f"[Dataset] Loaded {len(loader)} total test items. Evaluating: {total_count}")

    # 2. Load Model & LoRA Adapter
    print("\n[Model] Loading base model and tokenizer...")
    processor = AutoProcessor.from_pretrained(resolved_base)

    if load_in_4bit:
        import gc
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            llm_int8_enable_fp32_cpu_offload=True,
        )
        model = Qwen2VLForConditionalGeneration.from_pretrained(
            resolved_base,
            quantization_config=bnb_config,
            device_map="auto",
        )
    else:

        model = Qwen2VLForConditionalGeneration.from_pretrained(
            resolved_base,
            torch_dtype=torch.float16,
            device_map="auto",
        )

    print(f"[Model] Attaching LoRA adapter from {resolved_weights}...")
    model = PeftModel.from_pretrained(model, str(resolved_weights))
    model.eval()

    device = next(model.parameters()).device
    print(f"[Model] Inference ready on {device}")

    # 3. Checkpointing and State Tracking
    checkpoint_file = out_path / "eval_checkpoint.json"
    detailed_records: List[Dict[str, Any]] = []
    tp = fp = fn = tn = 0
    defect_type_correct = 0
    ious: List[float] = []
    loc_correct_iou50 = 0
    latencies: List[float] = []
    mcnemar_b = 0
    mcnemar_c = 0
    start_idx = 0

    if resume and checkpoint_file.exists():
        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                ckpt = json.load(f)
            detailed_records = ckpt.get("detailed_records", [])
            start_idx = len(detailed_records)
            tp = ckpt.get("tp", 0)
            fp = ckpt.get("fp", 0)
            fn = ckpt.get("fn", 0)
            tn = ckpt.get("tn", 0)
            defect_type_correct = ckpt.get("defect_type_correct", 0)
            ious = ckpt.get("ious", [])
            loc_correct_iou50 = ckpt.get("loc_correct_iou50", 0)
            latencies = ckpt.get("latencies", [])
            mcnemar_b = ckpt.get("mcnemar_b", 0)
            mcnemar_c = ckpt.get("mcnemar_c", 0)
            print(f"[Resume] Resuming from sample {start_idx + 1}/{total_count}...")
        except Exception as e:
            print(f"[Resume Warning] Could not restore checkpoint ({e}), evaluating from start.")

    # 4. Inference Loop
    t_start = time.time()
    for idx in range(start_idx, total_count):
        sample, img = loader.get_sample(idx)
        img_name = sample["images"][0]

        # Ground truth
        gt_data = json.loads(sample["messages"][1]["content"])
        true_has_defect = bool(gt_data.get("has_defect", False))
        true_defect_type = str(gt_data.get("defect_type", "none")).lower()
        true_bbox = gt_data.get("bounding_box")

        user_content = sample["messages"][0]["content"].replace("<image>", "").strip()

        # Scale down large screens to max 512 edge to prevent VRAM spikes
        img.thumbnail((512, 512), Image.Resampling.LANCZOS)

        prompt_text = (
            "<|im_start|>user\n"
            "<|vision_start|><|image_pad|><|vision_end|>"
            f"{user_content}\n"
            "<|im_end|>\n"
            "<|im_start|>assistant\n"
        )

        t0 = time.time()
        try:
            inputs = processor(text=[prompt_text], images=[img], return_tensors="pt").to(device)
            with torch.no_grad():
                generated_ids = model.generate(
                    **inputs,
                    max_new_tokens=96,
                    do_sample=False,
                )
            trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated_ids)]
            response_text = processor.batch_decode(
                trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )[0]
            lat_ms = (time.time() - t0) * 1000.0
            latencies.append(lat_ms)

            parsed = VerdictParser.parse(response_text)
            pred_has_defect = parsed.has_defect
            pred_defect_type = parsed.defect_type.value
            pred_bbox = parsed.bounding_box
        except Exception as err:
            lat_ms = (time.time() - t0) * 1000.0
            latencies.append(lat_ms)
            response_text = f"Error: {err}"
            pred_has_defect = False
            pred_defect_type = "none"
            pred_bbox = None

        # Binary confusion matrix
        if true_has_defect and pred_has_defect:
            tp += 1
        elif not true_has_defect and pred_has_defect:
            fp += 1
        elif true_has_defect and not pred_has_defect:
            fn += 1
        else:
            tn += 1

        # Defect type matching
        if true_has_defect and pred_has_defect:
            if pred_defect_type == true_defect_type:
                defect_type_correct += 1

        # Localization IoU
        iou = 0.0
        if true_has_defect and pred_has_defect and true_bbox and pred_bbox:
            iou = compute_bbox_iou(pred_bbox, true_bbox)
            ious.append(iou)
            if iou >= 0.50:
                loc_correct_iou50 += 1
        elif true_has_defect and pred_has_defect:
            ious.append(0.0)

        # Baseline McNemar comparison (Clean guessing baseline)
        base_correct = (not true_has_defect)
        lora_correct = (pred_has_defect == true_has_defect)
        if lora_correct and not base_correct:
            mcnemar_b += 1
        elif not lora_correct and base_correct:
            mcnemar_c += 1

        detailed_records.append({
            "index": idx,
            "dataset": sample.get("dataset", "unknown"),
            "image": img_name,
            "true_has_defect": true_has_defect,
            "pred_has_defect": pred_has_defect,
            "true_defect_type": true_defect_type,
            "pred_defect_type": pred_defect_type,
            "true_bbox": true_bbox,
            "pred_bbox": pred_bbox,
            "iou": round(iou, 4),
            "latency_ms": round(lat_ms, 2),
            "raw_output": response_text[:200],
        })

        # Periodic logging and checkpoint save
        if (idx + 1) % 10 == 0 or (idx + 1) == total_count:
            curr_acc = (tp + tn) / float(idx + 1) * 100.0
            curr_p = (tp / float(tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0
            curr_r = (tp / float(tp + fn)) * 100.0 if (tp + fn) > 0 else 0.0
            curr_f1 = (2 * curr_p * curr_r / (curr_p + curr_r)) if (curr_p + curr_r) > 0 else 0.0
            avg_lat = sum(latencies) / len(latencies)
            print(
                f"[{idx + 1:3d}/{total_count}] Acc: {curr_acc:5.2f}% | "
                f"F1: {curr_f1:5.2f}% | P: {curr_p:5.2f}% | R: {curr_r:5.2f}% | "
                f"Lat: {avg_lat:5.1f}ms"
            )

            with open(checkpoint_file, "w", encoding="utf-8") as f:
                json.dump({
                    "last_index": idx + 1,
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                    "tn": tn,
                    "defect_type_correct": defect_type_correct,
                    "ious": ious,
                    "loc_correct_iou50": loc_correct_iou50,
                    "latencies": latencies,
                    "mcnemar_b": mcnemar_b,
                    "mcnemar_c": mcnemar_c,
                    "detailed_records": detailed_records,
                }, f, indent=2)

    loader.close()
    eval_elapsed = time.time() - t_start

    # 5. Aggregate Metrics Computation
    accuracy = (tp + tn) / float(total_count) if total_count > 0 else 0.0
    precision = tp / float(tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / float(tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    mean_iou = sum(ious) / float(len(ious)) if len(ious) > 0 else 0.0
    loc_acc_iou50 = (loc_correct_iou50 / float(tp)) * 100.0 if tp > 0 else 0.0
    defect_type_acc = (defect_type_correct / float(tp)) * 100.0 if tp > 0 else 0.0

    mean_lat_ms = sum(latencies) / float(len(latencies)) if latencies else 0.0
    sorted_lats = sorted(latencies)
    p95_lat_ms = sorted_lats[int(len(sorted_lats) * 0.95)] if sorted_lats else 0.0
    sla_compliance_pct = (
        (sum(1 for l in latencies if l < 1500.0) / float(len(latencies))) * 100.0
        if latencies else 0.0
    )

    mcnemar_res = mcnemar_test(b=mcnemar_b, c=mcnemar_c)

    # Stratified breakdown by dataset source (e.g. rico vs owleye)
    by_dataset: Dict[str, Any] = {}
    datasets_found = sorted(list(set(r.get("dataset", "unknown") for r in detailed_records)))
    for ds_name in datasets_found:
        recs = [r for r in detailed_records if r.get("dataset") == ds_name]
        d_tp = sum(1 for r in recs if r["true_has_defect"] and r["pred_has_defect"])
        d_fp = sum(1 for r in recs if not r["true_has_defect"] and r["pred_has_defect"])
        d_fn = sum(1 for r in recs if r["true_has_defect"] and not r["pred_has_defect"])
        d_tn = sum(1 for r in recs if not r["true_has_defect"] and not r["pred_has_defect"])
        d_tot = len(recs)
        d_acc = (d_tp + d_tn) / float(d_tot) if d_tot > 0 else 0.0
        d_prec = d_tp / float(d_tp + d_fp) if (d_tp + d_fp) > 0 else 0.0
        d_rec = d_tp / float(d_tp + d_fn) if (d_tp + d_fn) > 0 else 0.0
        d_f1 = (2 * d_prec * d_rec / (d_prec + d_rec)) if (d_prec + d_rec) > 0 else 0.0
        d_ious = [r["iou"] for r in recs if r["true_has_defect"] and r["pred_has_defect"]]
        d_mean_iou = sum(d_ious) / len(d_ious) if d_ious else 0.0
        by_dataset[ds_name] = {
            "total_samples": d_tot,
            "confusion_matrix": {"tp": d_tp, "fp": d_fp, "fn": d_fn, "tn": d_tn},
            "accuracy_pct": round(d_acc * 100.0, 2),
            "precision_pct": round(d_prec * 100.0, 2),
            "recall_pct": round(d_rec * 100.0, 2),
            "f1_score_pct": round(d_f1 * 100.0, 2),
            "mean_bbox_iou": round(d_mean_iou, 4),
        }

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_samples": total_count,
        "clean_samples": tn + fp,
        "defect_samples": tp + fn,
        "weights_path": str(resolved_weights),
        "dataset_path": str(resolved_dataset),
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "by_dataset": by_dataset,
        "metrics": {
            "accuracy_pct": round(accuracy * 100.0, 2),
            "precision_pct": round(precision * 100.0, 2),
            "recall_pct": round(recall * 100.0, 2),
            "f1_score_pct": round(f1 * 100.0, 2),
            "defect_type_accuracy_pct": round(defect_type_acc, 2),
            "mean_bbox_iou": round(mean_iou, 4),
            "loc_accuracy_iou50_pct": round(loc_acc_iou50, 2),
            "mean_latency_ms": round(mean_lat_ms, 2),
            "p95_latency_ms": round(p95_lat_ms, 2),
            "sla_under_1500ms_pct": round(sla_compliance_pct, 2),
        },
        "mcnemar": {
            "lora_wins_b": mcnemar_b,
            "baseline_wins_c": mcnemar_c,
            "chi2": mcnemar_res["chi2"],
            "p_value": mcnemar_res["p_value"],
            "statistically_significant": mcnemar_res["significant"],
        },
        "evaluation_duration_seconds": round(eval_elapsed, 2),
    }

    # 6. Save JSON & CSV
    json_path = out_path / "evaluation_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    csv_path = out_path / "evaluation_metrics.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("metric,value\n")
        f.write(f"total_samples,{total_count}\n")
        f.write(f"tp,{tp}\n")
        f.write(f"fp,{fp}\n")
        f.write(f"fn,{fn}\n")
        f.write(f"tn,{tn}\n")
        f.write(f"accuracy_pct,{accuracy * 100.0:.2f}\n")
        f.write(f"precision_pct,{precision * 100.0:.2f}\n")
        f.write(f"recall_pct,{recall * 100.0:.2f}\n")
        f.write(f"f1_score_pct,{f1 * 100.0:.2f}\n")
        f.write(f"defect_type_accuracy_pct,{defect_type_acc:.2f}\n")
        f.write(f"mean_bbox_iou,{mean_iou:.4f}\n")
        f.write(f"loc_accuracy_iou50_pct,{loc_acc_iou50:.2f}\n")
        f.write(f"mean_latency_ms,{mean_lat_ms:.2f}\n")
        f.write(f"p95_latency_ms,{p95_lat_ms:.2f}\n")
        f.write(f"sla_under_1500ms_pct,{sla_compliance_pct:.2f}\n")
        f.write(f"mcnemar_chi2,{mcnemar_res['chi2']:.4f}\n")
        f.write(f"mcnemar_p_value,{mcnemar_res['p_value']:.6f}\n")
        for ds_name, ds_stats in by_dataset.items():
            for sk, sv in ds_stats.items():
                if sk != "confusion_matrix":
                    f.write(f"{ds_name}_{sk},{sv}\n")

    # 7. Render High-Aesthetic Confusion Matrix
    cm_path = out_path / "evaluation_confusion_matrix.png"
    cm = np.array([[tn, fp], [fn, tp]])
    fig, ax = plt.subplots(figsize=(6, 5), dpi=300)
    cax = ax.matshow(cm, cmap="Blues")
    for i in range(2):
        for j in range(2):
            v = cm[i, j]
            pct = (v / total_count * 100.0) if total_count > 0 else 0.0
            col = "white" if v > (total_count / 3) else "black"
            ax.text(j, i, f"{v}\n({pct:.1f}%)", ha="center", va="center", color=col, fontsize=13, fontweight="bold")
    fig.colorbar(cax)
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Clean (Pred)", "Defect (Pred)"], fontsize=11)
    ax.set_yticklabels(["Clean (Actual)", "Defect (Actual)"], fontsize=11)
    ax.set_title(f"C3 LoRA Test Evaluation (N={total_count})\nAcc: {accuracy * 100:.1f}% | F1: {f1 * 100:.1f}%", fontsize=12, pad=12)
    plt.tight_layout()
    plt.savefig(cm_path)
    plt.close()

    print("\n" + "=" * 75)
    print(" EVALUATION FINISHED")
    print("=" * 75)
    print(f"[+] Total Samples     : {total_count}")
    print(f"[+] Accuracy          : {accuracy * 100:.2f}%")
    print(f"[+] Macro F1 Score    : {f1 * 100:.2f}%")
    print(f"[+] Precision / Recall: {precision * 100:.2f}% / {recall * 100:.2f}%")
    print(f"[+] Defect Type Acc   : {defect_type_acc:.2f}%")
    print(f"[+] Mean BBox IoU     : {mean_iou:.4f}")
    print(f"[+] Loc @ IoU>=0.50   : {loc_acc_iou50:.2f}%")
    print(f"[+] McNemar p-value   : {mcnemar_res['p_value']} (Sig: {mcnemar_res['significant']})")
    if by_dataset:
        print("-" * 75)
        print(" Stratified Breakdown by Dataset:")
        for ds_name, ds_stats in by_dataset.items():
            cm_sub = ds_stats["confusion_matrix"]
            print(f"  [{ds_name.upper():6s}] N={ds_stats['total_samples']:3d} | "
                  f"TP={cm_sub['tp']:2d} FP={cm_sub['fp']:2d} FN={cm_sub['fn']:2d} TN={cm_sub['tn']:2d} | "
                  f"Acc: {ds_stats['accuracy_pct']:5.2f}% | "
                  f"P: {ds_stats['precision_pct']:5.2f}% | R: {ds_stats['recall_pct']:5.2f}% | "
                  f"F1: {ds_stats['f1_score_pct']:5.2f}% | IoU: {ds_stats['mean_bbox_iou']:.4f}")
    print(f"[+] Report JSON       : {json_path}")
    print(f"[+] Summary CSV       : {csv_path}")
    print(f"[+] Confusion Matrix  : {cm_path}")
    print("=" * 75)

    return summary


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate C3 LoRA model weights on held-out test split.")
    parser.add_argument("--weights", type=str, default=None, help="Path to LoRA weights folder (auto-detected if omitted)")
    parser.add_argument("--dataset", type=str, default=None, help="Path to colab_c3_dataset.zip or test.json (auto-detected if omitted)")
    parser.add_argument("--base-model", type=str, default=None, help="Base model path or HuggingFace ID")
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
