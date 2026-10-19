from __future__ import annotations

import json

from evaluation.make_settings_journeys import make_payload
from evaluation.run_synthesis_eval import CSV_FIELDS, build_summary, write_outputs


def _row(
    journey_id: str,
    *,
    status: str = "generated",
    attempts: int = 1,
    grounded: float = 1.0,
    execution: str = "passed",
    first_passed: bool = True,
    signature: tuple = (("tap", (("text", "Network & internet"),), None),),
) -> dict:
    return {
        "journey_id": journey_id,
        "reproducible_flag": True,
        "synthesis_status": status,
        "attempts": attempts,
        "steps_count": 1,
        "grounded_steps_ratio": grounded,
        "script_compiles": status == "generated",
        "llm_seconds": float(attempts),
        "execution_status": execution,
        "failure_kind": "",
        "failed_step_index": "",
        "execution_seconds": 0.1,
        "_first_execution_passed": first_passed,
        "_step_signature": signature,
    }


def test_summary_rates_and_stability() -> None:
    rows = [
        _row("a"),
        _row("a", attempts=2, first_passed=False),
        _row("b", execution="", first_passed=False),
        _row("c", status="failed", execution=""),
    ]
    summary = build_summary(rows, model="fake", prompt_version="v1", repeats=2)

    assert summary["generation_success_rate"] == 0.75
    assert summary["first_attempt_success_rate"] == 0.5
    assert summary["mean_attempts"] == 1.25
    assert summary["grounded_step_rate"] == 1.0
    assert summary["script_valid_rate"] == 1.0
    assert summary["execution_success_rate"] == 0.5
    assert summary["replay_success_rate"] == 1.0
    assert summary["stability"] == 1.0
    assert summary["model"] == "fake"
    assert summary["prompt_version"] == "v1"


def test_csv_columns_and_outputs_are_deterministic(tmp_path) -> None:
    rows = [_row("a")]
    summary = build_summary(rows, repeats=1)
    write_outputs(rows, summary, tmp_path)

    header = (tmp_path / "results.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header.split(",") == list(CSV_FIELDS)
    assert json.loads((tmp_path / "summary.json").read_text())["repeats"] == 1
    assert "replay_success_rate" in (tmp_path / "summary.md").read_text()
    assert "Failure reproduction" in (
        tmp_path / "summary.md"
    ).read_text(encoding="utf-8")


def test_settings_payload_has_deterministic_sentry_shape() -> None:
    payload = make_payload(["Network & internet", "Connected devices"], 1)

    assert payload["event_id"].startswith("synthetic-settings-0001-")
    assert payload["release"] == "synthetic"
    assert [item["data"]["text"] for item in payload["breadcrumbs"]] == [
        "Network & internet",
        "Connected devices",
    ]
