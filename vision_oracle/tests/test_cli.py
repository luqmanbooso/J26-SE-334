"""
Unit Tests for C3 Oracle CLI commands.
"""

import json
import pytest
from pathlib import Path
from PIL import Image

from local_vision_oracle.cli import build_parser, cmd_inspect, cmd_mcnemar, cmd_benchmark


def test_cli_parser_build():
    parser = build_parser()
    assert parser.prog == "c3-oracle"


def test_cli_mcnemar(capsys):
    parser = build_parser()
    args = parser.parse_args(["mcnemar", "-b", "50", "-c", "5"])
    ret = args.func(args)
    assert ret == 0

    out = capsys.readouterr().out
    assert "Chi-Square Statistic" in out
    assert "Statistically Significant (p < 0.05)   : True" in out


def test_cli_inspect_mock(tmp_path, capsys):
    img_path = tmp_path / "screen.png"
    Image.new("RGB", (1080, 2400), color=(255, 255, 255)).save(img_path)

    parser = build_parser()
    args = parser.parse_args(["inspect", "--image", str(img_path), "--mock"])
    ret = args.func(args)
    assert ret == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert "screen_id" in data
    assert "verdict" in data
    assert data["verdict"]["has_defect"] is False


def test_cli_benchmark_mock(tmp_path, capsys):
    img_path = tmp_path / "screen.png"
    Image.new("RGB", (1080, 2400), color=(255, 255, 255)).save(img_path)

    dataset_file = tmp_path / "dataset.json"
    dataset_content = [
        {
            "screen_id": "test_01",
            "image_path": str(img_path),
            "expected_has_defect": False,
        }
    ]
    dataset_file.write_text(json.dumps(dataset_content), encoding="utf-8")

    out_csv = tmp_path / "metrics_summary.csv"

    parser = build_parser()
    args = parser.parse_args(["benchmark", "-d", str(dataset_file), "-o", str(out_csv), "--mock"])
    ret = args.func(args)
    assert ret == 0
    assert out_csv.exists()

    out = capsys.readouterr().out
    assert "Benchmark finished" in out
