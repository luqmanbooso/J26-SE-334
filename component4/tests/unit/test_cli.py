from __future__ import annotations

import subprocess
import sys


SCRIPT = """from appium.webdriver.common.appiumby import AppiumBy

def step_0(driver) -> None:
    driver.find_element(AppiumBy.ID, "com.example:id/pay").click()
"""


def test_cli_heal_returns_zero_for_healed_decision(tmp_path) -> None:
    script = tmp_path / "script.py"
    hierarchy = tmp_path / "new.xml"
    script.write_text(SCRIPT, encoding="utf-8")
    hierarchy.write_text(
        '<hierarchy><node class="android.widget.Button" '
        'resource-id="com.example:id/pay_new" text="Pay" clickable="true" '
        'enabled="true" bounds="[0,0][20,20]" /></hierarchy>',
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "c4",
            "heal",
            "--script",
            str(script),
            "--step",
            "0",
            "--new-hierarchy",
            str(hierarchy),
            "--embedder",
            "lexical",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert '"status": "healed"' in result.stdout


def test_cli_heal_returns_one_for_refusal_and_two_for_bad_input(tmp_path) -> None:
    refusal = subprocess.run(
        [
            sys.executable,
            "-m",
            "c4",
            "heal",
            "--script",
            str(tmp_path / "missing.py"),
            "--step",
            "0",
            "--new-hierarchy",
            str(tmp_path / "missing.xml"),
            "--embedder",
            "lexical",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    help_result = subprocess.run(
        [sys.executable, "-m", "c4", "run", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert refusal.returncode == 2
    assert help_result.returncode == 0
    for option in (
        "--heal",
        "--capture-baseline",
        "--baseline-dir",
        "--repo-dir",
    ):
        assert option in help_result.stdout
