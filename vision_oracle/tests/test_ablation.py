"""
Unit tests for View Hierarchy Pruning Ablation & Latency Decomposition Suite (EXP-02 & EXP-04).
"""

import json
import pytest
from pathlib import Path
from local_vision_oracle.ablation_runner import (
    AblationRunner,
    AblationConfigResult,
    AblationStudySummary,
    LatencyStageProfile,
    LatencyDecompositionSummary,
)
from local_vision_oracle.cli import build_parser


@pytest.fixture
def sample_ablation_csv(tmp_path: Path) -> Path:
    csv_file = tmp_path / "test_ablation.csv"
    content = (
        "Configuration,Input_Tokens,Token_Reduction_Pct,Pipeline_Latency_ms,F1_Score,Precision,Recall\n"
        "Full_Unpruned_XML,8120,0.0%,4850.0,85.20%,88.10%,82.50%\n"
        "Heuristic_Depth_Capped,1850,77.2%,2340.0,91.40%,93.00%,89.85%\n"
        "AST_Deterministic_Pruner_C3,420,94.8%,1400.2,97.46%,98.97%,96.00%\n"
        "Vision_Only_No_DOM,0,100.0%,1250.0,77.91%,81.20%,74.88%\n"
    )
    csv_file.write_text(content, encoding="utf-8")
    return csv_file


@pytest.fixture
def sample_latency_csv(tmp_path: Path) -> Path:
    csv_file = tmp_path / "test_latency.csv"
    content = (
        "Stage,Mean_Latency_ms,Std_Latency_ms,Percentage_Total,Meets_Sub_SLA\n"
        "Screen_Hierarchy_Capture,125.0,8.5,8.93%,True\n"
        "Image_Preprocessing_PatchAlign,38.2,3.1,2.73%,True\n"
        "AST_ViewHierarchy_Pruning,15.0,1.8,1.07%,True\n"
        "AWQ_W4A16_Model_Inference,1222.0,40.8,87.27%,True\n"
        "Total_End_to_End_Pipeline,1400.2,54.2,100.00%,True\n"
    )
    csv_file.write_text(content, encoding="utf-8")
    return csv_file


def test_parse_ablation_csv(sample_ablation_csv: Path):
    summary = AblationRunner.parse_ablation_csv(sample_ablation_csv)
    assert len(summary.configs) == 4
    c3 = summary.proposed_result
    assert c3 is not None
    assert c3.configuration == "AST_Deterministic_Pruner_C3"
    assert c3.input_tokens == 420
    assert c3.pipeline_latency_ms == 1400.2
    assert c3.meets_latency_sla is True

    raw = summary.baseline_result
    assert raw is not None
    assert raw.input_tokens == 8120
    assert raw.meets_latency_sla is False


def test_parse_latency_csv(sample_latency_csv: Path):
    summary = AblationRunner.parse_latency_csv(sample_latency_csv)
    assert len(summary.stages) == 4
    assert summary.total_mean_latency_ms == pytest.approx(1400.2, rel=1e-2)
    assert summary.meets_proposal_sla is True


def test_ablation_summary_properties(sample_ablation_csv: Path):
    summary = AblationRunner.parse_ablation_csv(sample_ablation_csv)
    # Token reduction vs 8120 -> 420: (8120 - 420) / 8120 = 94.83%
    assert summary.token_reduction_pct == pytest.approx(94.83, rel=1e-2)
    # Latency reduction vs 4850 -> 1400.2: (4850 - 1400.2) / 4850 = 71.13%
    assert summary.latency_reduction_pct == pytest.approx(71.13, rel=1e-2)
    # F1 boost over vision-only: 97.46 - 77.91 = +19.55%
    assert summary.f1_boost_over_vision_only == pytest.approx(19.55, rel=1e-2)


def test_latex_and_ascii_export(sample_ablation_csv: Path, sample_latency_csv: Path):
    ablation = AblationRunner.parse_ablation_csv(sample_ablation_csv)
    ascii_tbl = ablation.to_ascii_table()
    assert "VIEW HIERARCHY PRUNING ABLATION STUDY" in ascii_tbl
    assert "AST_Deterministic_Pruner_C3" in ascii_tbl

    latex_tbl = ablation.to_latex_table()
    assert "\\begin{table}" in latex_tbl
    assert "AST\\_Deterministic\\_Pruner\\_C3" in latex_tbl

    latency = AblationRunner.parse_latency_csv(sample_latency_csv)
    lat_ascii = latency.to_ascii_table()
    assert "PIPELINE LATENCY DECOMPOSITION" in lat_ascii
    assert "AWQ_W4A16_Model_Inference" in lat_ascii


def test_export_full_ablation_report(tmp_path: Path, sample_ablation_csv: Path, sample_latency_csv: Path):
    out_json = tmp_path / "ablation_report.json"
    data = AblationRunner.export_full_ablation_report(
        ablation_csv=sample_ablation_csv,
        latency_csv=sample_latency_csv,
        output_json=out_json,
    )
    assert out_json.exists()
    assert "ablation_study" in data
    assert "latency_decomposition" in data
    assert data["ablation_study"]["proposed_config"] == "AST_Deterministic_Pruner_C3"
    assert data["latency_decomposition"]["meets_proposal_sla"] is True


def test_cli_ablate_subparser():
    parser = build_parser()
    args = parser.parse_args([
        "ablate",
        "--ablation-csv", "results/exp-02/ablation_results.csv",
        "--latency-csv", "results/exp-04/latency_profile.csv",
        "--latex"
    ])
    assert args.ablation_csv == "results/exp-02/ablation_results.csv"
    assert args.latex is True
