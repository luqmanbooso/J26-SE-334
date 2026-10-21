"""
Command-Line Interface (CLI) for C3 Localized Multimodal Oracle.
Supports single-screen inspection, benchmark dataset evaluation, and McNemar testing.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional

from local_vision_oracle.schemas import C3OracleResult, DefectType
from local_vision_oracle.engine import OracleEngine, MockInferenceBackend
from local_vision_oracle.evaluation import (
    Evaluator,
    EvaluationItem,
    EvaluationMetrics,
    mcnemar_test,
)
from local_vision_oracle.dataset_scanner import DatasetScanner
from local_vision_oracle.dataset_splitter import DatasetSplitter
from local_vision_oracle.calibration import AWQCalibrator, AWQConfig
from local_vision_oracle.confusion_matrix import ConfusionMatrixCalculator
from local_vision_oracle.ablation_runner import AblationRunner
from local_vision_oracle.deduplicator import DatasetDeduplicator
from local_vision_oracle.dataset_compiler import DatasetCompiler


def cmd_confusion_matrix(args: argparse.Namespace) -> int:
    """
    Renders 2x2 confusion matrices comparing C3 Oracle vs OwlEye baseline.
    """
    c3_mat, owleye_mat, mcnemar_res = ConfusionMatrixCalculator.compare_c3_vs_owleye(
        total_test_samples=args.samples
    )

    print(c3_mat.to_ascii_table())
    print(owleye_mat.to_ascii_table())

    print("=== McNemar's Paired Statistical Significance Test ===")
    print(f"Chi2 Statistic : {mcnemar_res['chi2']}")
    print(f"p-value        : {mcnemar_res['p_value']}")
    print(f"Significant    : {mcnemar_res['significant']} (p < 0.05)")

    if args.latex:
        print("\n=== LaTeX Table Output ===")
        print(c3_mat.to_latex_table())

    if args.output:
        ConfusionMatrixCalculator.export_comparison_json(output_path=args.output)
        print(f"\n[+] Confusion matrices exported to: {args.output}")

    return 0


def cmd_ablate(args: argparse.Namespace) -> int:
    """
    Parses and prints DOM pruning ablation study (EXP-02) and latency profile (EXP-04).
    """
    ablation_summary = AblationRunner.parse_ablation_csv(args.ablation_csv)
    latency_summary = AblationRunner.parse_latency_csv(args.latency_csv)

    print(ablation_summary.to_ascii_table())
    print(latency_summary.to_ascii_table())

    if args.latex:
        print("\n=== LaTeX Table Output ===")
        print(ablation_summary.to_latex_table())

    if args.output:
        AblationRunner.export_full_ablation_report(
            ablation_csv=args.ablation_csv,
            latency_csv=args.latency_csv,
            output_json=args.output,
        )
        print(f"\n[+] Ablation and latency analysis exported to: {args.output}")

    return 0


def cmd_deduplicate(args: argparse.Namespace) -> int:
    """
    Executes exact SHA-256 and perceptual difference hashing (dHash) deduplication.
    """
    deduplicator = DatasetDeduplicator(hamming_threshold=args.threshold)
    input_path = Path(args.input)

    if input_path.suffix.lower() == ".json":
        report, sanitized_items = deduplicator.scan_manifest_json(
            manifest_path=input_path,
            image_key=args.image_key,
        )
    else:
        report, unique_paths = deduplicator.scan_directory(
            directory=input_path,
        )
        sanitized_items = [str(p) for p in unique_paths]

    print(report.to_ascii_table())

    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"[+] Deduplication report exported to: {args.output}")

    if args.sanitized_manifest:
        san_p = Path(args.sanitized_manifest)
        san_p.parent.mkdir(parents=True, exist_ok=True)
        with open(san_p, "w", encoding="utf-8") as f:
            json.dump(sanitized_items, f, indent=2)
        print(f"[+] Sanitized manifest exported to: {args.sanitized_manifest}")

    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    """
    Executes multimodal AWQ calibration simulation and generates memory profile.
    """
    calibrator = AWQCalibrator(
        base_params_billion=args.params_b,
        config=AWQConfig(w_bit=args.bits, q_group_size=args.group_size),
    )
    print("\n--- Running AWQ Multimodal Calibration & Memory Profiling ---")
    summary = calibrator.calibrate_and_export_summary(
        manifest_path=args.manifest,
        output_path=args.output,
        max_samples=args.samples,
    )

    print(f"\n[+] Manifest Used             : {summary.calibration_manifest}")
    print(f"[+] Samples Processed         : {summary.num_samples_calibrated}")
    print(f"[+] Average Token Length      : {summary.average_token_length} tokens/screen")
    print(f"[+] Protected Outlier Channels: {summary.channel_outlier_protection_pct}%")
    print(f"[+] Model Precision           : W{summary.awq_config.w_bit}A16 (Group Size: {summary.awq_config.q_group_size})")
    print(f"[+] FP16 Uncompressed Weights : {summary.memory_profile.fp16_weight_gb} GB")
    print(f"[+] INT4 AWQ Static Weights   : {summary.memory_profile.int4_awq_weight_gb} GB")
    print(f"[+] Total Peak Inference VRAM : {summary.memory_profile.total_peak_vram_gb} GB")
    print(f"[+] Weight Compression Ratio  : {summary.memory_profile.compression_ratio}x")
    print(f"[+] Feasible on 4GB VRAM GPU  : {summary.memory_profile.fits_4gb_vram}")
    print(f"[+] Calibration Status        : {summary.calibration_status}")
    print(f"\n[+] Calibration Audit Exported : {args.output}")
    return 0 if summary.calibration_status == "CALIBRATED" else 1


def cmd_split_data(args: argparse.Namespace) -> int:
    """
    Splits OwlEye and Rico into Train/Val/Test and calibration manifests.
    """
    splitter = DatasetSplitter(
        owleye_dir=args.owleye,
        rico_dir=args.rico,
        seed=args.seed,
    )
    print("\n--- Generating Deterministic Evaluation & Calibration Manifests ---")
    summary = splitter.export_all_manifests(
        output_dir=args.output_dir,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
    )

    print(f"\n[+] Seed Used               : {summary.seed}")
    print(f"[+] OwlEye Train Set        : {summary.train_stats.total_count} ({summary.train_stats.defect_count} defect, {summary.train_stats.clean_count} clean)")
    print(f"[+] OwlEye Validation Set   : {summary.val_stats.total_count} ({summary.val_stats.defect_count} defect, {summary.val_stats.clean_count} clean)")
    print(f"[+] OwlEye Test Set         : {summary.test_stats.total_count} ({summary.test_stats.defect_count} defect, {summary.test_stats.clean_count} clean)")
    print(f"[+] Rico AWQ Calibration    : {summary.rico_calibration_count} screens")
    print(f"[+] Rico Clean Evaluation   : {summary.rico_clean_eval_count} screens")
    print(f"[+] Data Leakage Detected   : {summary.leakage_detected}")
    print(f"\n[+] All Manifests Exported to: {args.output_dir}/")
    return 0


def cmd_scan_data(args: argparse.Namespace) -> int:
    """
    Audits physical datasets (OwlEye and Rico) and outputs JSON integrity report.
    """
    owleye_dir = args.owleye if args.owleye else None
    rico_dir = args.rico if args.rico else None
    output_path = args.output if args.output else "results/data_inspection_report.json"

    scanner = DatasetScanner(owleye_dir=owleye_dir, rico_dir=rico_dir)
    print("\n--- Auditing Physical Datasets (OwlEye & Rico) ---")
    report = scanner.generate_full_report(output_path=output_path)

    print(f"\n[+] OwlEye Location: {report.owleye.location}")
    print(f"    Bugs: {report.owleye.bug_image_count} | Clean: {report.owleye.normal_image_count} | Total: {report.owleye.total_images}")
    print(f"    Balanced: {report.owleye.is_balanced} | Verified: {report.owleye.verified}")
    print(f"    Sample resolutions: {report.owleye.sample_resolutions}")

    print(f"\n[+] Rico Location: {report.rico.location}")
    print(f"    PNG Count: {report.rico.total_png_count} | JSON Count: {report.rico.total_json_count}")
    print(f"    Paired: {report.rico.paired_count} | Orphaned PNG: {report.rico.orphaned_png_count} | Orphaned JSON: {report.rico.orphaned_json_count}")
    print(f"    Sample Pruning Reduction: {report.rico.sample_pruning_ratio}% | Verified: {report.rico.verified}")
    print(f"    Sample resolutions: {report.rico.sample_resolutions}")

    print(f"\n[+] Full Audit Verdict: {report.summary_verdict}")
    print(f"[+] Detailed Report Exported: {output_path}")
    return 0 if report.summary_verdict == "PASSED" else 1


def cmd_inspect(args: argparse.Namespace) -> int:
    """
    Evaluates a single screenshot with optional view hierarchy.
    """
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: image not found at {image_path}", file=sys.stderr)
        return 1

    hierarchy_content = None
    if args.hierarchy:
        h_path = Path(args.hierarchy)
        if not h_path.exists():
            print(f"Error: hierarchy file not found at {h_path}", file=sys.stderr)
            return 1
        if h_path.suffix == ".json":
            with open(h_path, "r", encoding="utf-8") as f:
                hierarchy_content = json.load(f)
        else:
            with open(h_path, "r", encoding="utf-8") as f:
                hierarchy_content = f.read()

    enable_sahi = bool(getattr(args, "sahi", False))
    if args.mock:
        engine = OracleEngine(backend=MockInferenceBackend())
        result: C3OracleResult = engine.evaluate(
            image_input=str(image_path),
            raw_hierarchy=hierarchy_content,
            action_context=args.action,
            enable_sahi=enable_sahi,
        )
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    # Real model: the same service and pipeline as the HEART desktop app (shipped adapter,
    # its inference contract, global-only unless --sahi). Before 2026-10-21 this command
    # loaded an older adapter (results/c3_lora_final) through the legacy engine.
    from vision_oracle.services.oracle_service import get_oracle_service

    if isinstance(hierarchy_content, dict):
        hierarchy_content = json.dumps(hierarchy_content)
    result = get_oracle_service().evaluate(
        image_input=str(image_path),
        raw_hierarchy=hierarchy_content,
        action_context=args.action,
        enable_sahi=enable_sahi,
    )
    v2 = result["verdict_v2"]
    print(json.dumps({"decision": v2["decision"], "findings": v2["findings"],
                      "metadata": {k: v2["metadata"].get(k) for k in
                                   ("defect_probability", "decision_threshold", "model_input")},
                      "timings_ms": v2["timings_ms"], "errors": v2["errors"]}, indent=2))
    return 0


def cmd_mcnemar(args: argparse.Namespace) -> int:
    """
    Computes McNemar's test from contingency counts b (A wins) and c (B wins).
    """
    res = mcnemar_test(b=args.b, c=args.c)
    print("\n--- McNemar's Paired Significance Test (Edwards Corrected) ---")
    print(f"Model A Correct, Model B Incorrect (b) : {args.b}")
    print(f"Model A Incorrect, Model B Correct (c) : {args.c}")
    print(f"Chi-Square Statistic (chi2)             : {res['chi2']}")
    print(f"p-value                                : {res['p_value']}")
    print(f"Statistically Significant (p < 0.05)   : {res['significant']}")
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    """
    Runs benchmark dataset evaluation and writes metrics CSV.
    """
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: dataset file not found at {dataset_path}", file=sys.stderr)
        return 1

    with open(dataset_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    items = [EvaluationItem(**d) for d in raw_data]
    if not args.mock:
        # OracleEngine(backend=None) silently fell back to the mock backend, so this command
        # used to report mock F1 as if it were the model's. Real benchmarks live elsewhere.
        print("Real-model benchmarking: python -m local_vision_oracle.eval_stages --stage screen "
              "(or local_vision_oracle.contract_benchmark). This command only supports --mock.",
              file=sys.stderr)
        return 2
    engine = OracleEngine(backend=MockInferenceBackend())
    evaluator = Evaluator(engine=engine)

    metrics, _ = evaluator.evaluate_dataset(items)

    out_csv = Path(args.output)
    evaluator.export_summary_csv(metrics, out_csv)
    print(f"\n[+] Benchmark finished. Total: {metrics.total_samples}, F1: {metrics.f1_score * 100:.2f}%")
    print(f"[+] Summary metrics exported to: {out_csv}")
    return 0


def cmd_compile_data(args: argparse.Namespace) -> int:
    """
    Compiles 4,000 screen balanced dataset with guaranteed zero-leakage partitions.
    """
    compiler = DatasetCompiler(
        base_dir=args.base_dir,
        rico_source_dir=args.rico_dir,
        owleye_source_dir=args.owleye_dir,
        seed=args.seed,
    )
    summary = compiler.compile_zero_leakage_corpus(
        num_clean=args.clean,
        num_mutated=args.mutated,
        num_owleye=args.owleye,
    )
    print(f"\n[+] Zero-leakage compilation finished: {summary['total_samples']} samples (Clean: {summary['clean_ratio']}%, Defect: {summary['defect_ratio']}%)")
    print(f"[+] Splits: Train={summary['train_count']}, Val={summary['val_count']}, Test={summary['test_count']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="c3-oracle",
        description="C3 Localized Multimodal Vision-Semantic Test Oracle CLI",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Subcommand: inspect
    inspect_p = subparsers.add_parser("inspect", help="Run oracle inspection on single screen")
    inspect_p.add_argument("--image", "-i", required=True, help="Path to screenshot image")
    inspect_p.add_argument("--hierarchy", "-d", help="Path to XML or JSON hierarchy")
    inspect_p.add_argument("--action", "-a", help="Action context description")
    inspect_p.add_argument("--weights", "-w", help="Path to fine-tuned LoRA weights directory")
    inspect_p.add_argument("--base-model", "-m", help="Path to base Qwen2-VL model directory")
    inspect_p.add_argument("--sahi", action="store_true", default=False, help="Add tile views (experimental, not validated with the current adapter)")
    inspect_p.add_argument("--no-sahi", action="store_true", default=False, help="Deprecated: tile views are off by default")
    inspect_p.add_argument("--mock", action="store_true", default=False, help="Use mock inference backend")
    inspect_p.set_defaults(func=cmd_inspect)

    # Subcommand: mcnemar
    mcnemar_p = subparsers.add_parser("mcnemar", help="Compute McNemar's paired test")
    mcnemar_p.add_argument("-b", type=int, required=True, help="Model A correct & Model B incorrect")
    mcnemar_p.add_argument("-c", type=int, required=True, help="Model A incorrect & Model B correct")
    mcnemar_p.set_defaults(func=cmd_mcnemar)

    # Subcommand: benchmark
    bench_p = subparsers.add_parser("benchmark", help="Run benchmark dataset evaluation")
    bench_p.add_argument("--dataset", "-d", required=True, help="Path to dataset JSON")
    bench_p.add_argument("--output", "-o", default="results/exp-01/metrics_summary.csv", help="Path to output CSV")
    bench_p.add_argument("--mock", action="store_true", default=False, help="Use mock backend")
    bench_p.set_defaults(func=cmd_benchmark)

    # Subcommand: scan-data
    scan_p = subparsers.add_parser("scan-data", help="Audit physical datasets (OwlEye & Rico)")
    scan_p.add_argument("--owleye", help="Path to OwlEye dataset directory")
    scan_p.add_argument("--rico", help="Path to Rico dataset directory")
    scan_p.add_argument("--output", "-o", default="results/data_inspection_report.json", help="Path to output JSON")
    scan_p.set_defaults(func=cmd_scan_data)

    # Subcommand: split-data
    split_p = subparsers.add_parser("split-data", help="Generate stratified Train/Val/Test and calibration manifests")
    split_p.add_argument("--owleye", help="Path to OwlEye dataset directory")
    split_p.add_argument("--rico", help="Path to Rico dataset directory")
    split_p.add_argument("--output-dir", "-o", default="results/manifests", help="Output directory for manifests")
    split_p.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    split_p.add_argument("--train-ratio", type=float, default=0.70, help="Train split ratio (default: 0.70)")
    split_p.add_argument("--val-ratio", type=float, default=0.15, help="Validation split ratio (default: 0.15)")
    split_p.add_argument("--test-ratio", type=float, default=0.15, help="Test split ratio (default: 0.15)")
    split_p.set_defaults(func=cmd_split_data)

    # Subcommand: compile-data
    comp_p = subparsers.add_parser("compile-data", help="Compile balanced zero-leakage 4,000 screen dataset")
    comp_p.add_argument("--base-dir", default="dataset", help="Output dataset directory")
    comp_p.add_argument("--rico-dir", default=r"C:\Games\rico_selected_dataset", help="Rico master dataset directory")
    comp_p.add_argument("--owleye-dir", default=r"D:\university\Resesarch\RD\OwlEye\Dataset\bug-aug\bug-aug", help="OwlEye bug dataset directory")
    comp_p.add_argument("--clean", type=int, default=2000, help="Clean Rico screens count")
    comp_p.add_argument("--mutated", type=int, default=1000, help="Mutated Rico screens count")
    comp_p.add_argument("--owleye", type=int, default=1000, help="OwlEye bug screens count")
    comp_p.add_argument("--seed", type=int, default=42, help="Random seed")
    comp_p.set_defaults(func=cmd_compile_data)

    # Subcommand: calibrate
    calib_p = subparsers.add_parser("calibrate", help="Run AWQ calibration simulation and memory profiling")
    calib_p.add_argument("--manifest", "-m", default="results/manifests/rico_calibration_256.json", help="Path to calibration manifest")
    calib_p.add_argument("--output", "-o", default="results/awq_calibration_summary.json", help="Output JSON path")
    calib_p.add_argument("--params-b", type=float, default=2.0, help="Model parameters in billions (default: 2.0)")
    calib_p.add_argument("--bits", type=int, default=4, help="Weight precision bits (default: 4)")
    calib_p.add_argument("--group-size", type=int, default=128, help="Quantization group size (default: 128)")
    calib_p.add_argument("--samples", type=int, default=256, help="Maximum calibration samples to process")
    calib_p.set_defaults(func=cmd_calibrate)

    # Subcommand: confusion-matrix
    matrix_p = subparsers.add_parser("confusion-matrix", help="Render 2x2 confusion matrices and McNemar test")
    matrix_p.add_argument("--samples", type=int, default=600, help="Total evaluation samples")
    matrix_p.add_argument("--output", "-o", default="results/exp-01/confusion_matrices.json", help="Output JSON path")
    matrix_p.add_argument("--latex", action="store_true", default=False, help="Print LaTeX table code")
    matrix_p.set_defaults(func=cmd_confusion_matrix)

    # Subcommand: ablate
    ablate_p = subparsers.add_parser("ablate", help="Analyze pruning ablation (EXP-02) and latency decomposition (EXP-04)")
    ablate_p.add_argument("--ablation-csv", default="results/exp-02/ablation_results.csv", help="Path to EXP-02 CSV")
    ablate_p.add_argument("--latency-csv", default="results/exp-04/latency_profile.csv", help="Path to EXP-04 CSV")
    ablate_p.add_argument("--output", "-o", default="results/exp-02/ablation_analysis.json", help="Output JSON path")
    ablate_p.add_argument("--latex", action="store_true", default=False, help="Print LaTeX table code")
    ablate_p.set_defaults(func=cmd_ablate)

    # Subcommand: deduplicate
    dedup_p = subparsers.add_parser("deduplicate", help="Detect exact and perceptual duplicate screens (Pillar 2)")
    dedup_p.add_argument("--input", "-i", required=True, help="Directory path or manifest JSON to scan")
    dedup_p.add_argument("--output", "-o", default="results/deduplication_report.json", help="Output report JSON path")
    dedup_p.add_argument("--threshold", "-t", type=int, default=3, help="Hamming distance threshold (default: 3)")
    dedup_p.add_argument("--image-key", default="image_path", help="Key for image path inside manifest JSON objects")
    dedup_p.add_argument("--sanitized-manifest", help="Optional path to export sanitized deduplicated manifest")
    dedup_p.set_defaults(func=cmd_deduplicate)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    exit_code = args.func(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
