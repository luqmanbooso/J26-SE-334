"""
Unit tests for BinaryConfusionMatrix and ConfusionMatrixCalculator.
"""

import json
import pytest
from pathlib import Path

from local_vision_oracle.confusion_matrix import (
    BinaryConfusionMatrix,
    ConfusionMatrixCalculator,
)
from local_vision_oracle.cli import build_parser


def test_confusion_matrix_calculation():
    # C3 Proposed numbers (N=600)
    mat = ConfusionMatrixCalculator.from_counts(
        tp=288, fp=3, tn=297, fn=12, model_name="C3_Test"
    )

    assert mat.total_samples == 600
    assert mat.accuracy == 0.975
    assert mat.precision == 0.9897
    assert mat.recall == 0.96
    assert mat.f1_score == 0.9746
    assert mat.false_positive_rate == 0.01
    assert mat.false_negative_rate == 0.04


def test_ascii_and_latex_export():
    mat = ConfusionMatrixCalculator.from_counts(
        tp=288, fp=3, tn=297, fn=12, model_name="C3_Test"
    )
    ascii_out = mat.to_ascii_table()
    assert "TP = 288" in ascii_out
    assert "FP = 3" in ascii_out
    assert "F1-Score : 97.46%" in ascii_out

    latex_out = mat.to_latex_table()
    assert "\\begin{tabular}" in latex_out
    assert "288" in latex_out
    assert "\\end{tabular}" in latex_out


def test_compare_c3_vs_owleye():
    c3, owleye, mcnemar = ConfusionMatrixCalculator.compare_c3_vs_owleye()

    # C3 outperforms OwlEye significantly
    assert c3.f1_score > owleye.f1_score + 0.40  # +49.7% F1 gain
    assert c3.false_positive_rate < owleye.false_positive_rate  # 1.0% vs 45.8%

    # McNemar test must be highly significant
    assert mcnemar["significant"] is True
    assert mcnemar["p_value"] < 0.001
    assert mcnemar["chi2"] > 100.0


def test_export_comparison_json(tmp_path):
    out_file = tmp_path / "exp-01" / "test_matrices.json"
    res = ConfusionMatrixCalculator.export_comparison_json(output_path=out_file)

    assert out_file.exists()
    assert "c3_oracle" in res
    assert "owleye_baseline" in res
    assert "mcnemar_significance" in res

    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["c3_oracle"]["f1_score"] == res["c3_oracle"]["f1_score"]
    assert data["owleye_baseline"]["f1_score"] == res["owleye_baseline"]["f1_score"]
    assert data["c3_oracle"]["accuracy"] == 0.975



def test_cli_confusion_matrix_subparser():
    parser = build_parser()
    args = parser.parse_args([
        "confusion-matrix",
        "--samples", "600",
        "--output", "custom_matrices.json",
        "--latex",
    ])
    assert args.subcommand == "confusion-matrix"
    assert args.samples == 600
    assert args.latex is True
