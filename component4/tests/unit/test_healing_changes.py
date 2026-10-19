from __future__ import annotations

from pathlib import Path

from c4.healing.changes import detect_changes
from c4.healing.engine import HealingEngine
from c4.healing.models import HealingConfig, HealingStatus
from c4.healing.semantic import Embedder
from c4.healing.hierarchy import parse_hierarchy


def _hierarchy(rows: list[str]) -> str:
    nodes = "".join(
        f'<node class="android.widget.TextView" resource-id="android:id/title" '
        f'text="{row}" enabled="true" bounds="[0,{index * 20}][100,{index * 20 + 20}]" />'
        for index, row in enumerate(rows)
    )
    return f"<hierarchy>{nodes}</hierarchy>"


class FakeEmbedder:
    name = "fake"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0 if text == "SIM cards" else 0.0] for text in texts]


def test_duplicate_identity_rows_are_matched_as_a_multiset() -> None:
    changes = detect_changes(
        parse_hierarchy(_hierarchy(["SIM cards", "Battery", "Storage"])),
        parse_hierarchy(_hierarchy(["SIMs", "Battery", "Storage"])),
    )

    assert changes.modified == frozenset({1})
    assert changes.unchanged == frozenset({0, 2, 3})
    assert not changes.added
    assert not changes.removed


def test_reordered_added_removed_and_identical_rows_are_deterministic() -> None:
    old = parse_hierarchy(_hierarchy(["A", "B", "B"]))
    new = parse_hierarchy(_hierarchy(["B", "A", "B"]))
    reordered = detect_changes(old, new)
    assert reordered.unchanged == frozenset({0, 1, 2, 3})
    assert not reordered.modified

    added = detect_changes(old, parse_hierarchy(_hierarchy(["A", "B", "B", "D"])))
    removed = detect_changes(parse_hierarchy(_hierarchy(["A", "B", "B", "C"])), old)
    assert added.added == frozenset({4})
    assert removed.removed == frozenset({4})
    assert detect_changes(old, new) == reordered
    assert not detect_changes(old, old).modified


def test_r6_excludes_unchanged_rows_and_allows_modified_row_to_heal() -> None:
    script = """from appium.webdriver.common.appiumby import AppiumBy

def step_0(driver) -> None:
    driver.find_element(AppiumBy.ID, "android:id/title").click()
"""
    old_xml = """<hierarchy><node class="android.widget.LinearLayout" clickable="true"
    enabled="true" bounds="[0,0][100,100]"><node class="android.widget.TextView"
    resource-id="android:id/title" text="SIM cards" enabled="true"
    bounds="[0,0][100,20]" /><node class="android.widget.TextView"
    resource-id="android:id/title" text="Battery" enabled="true"
    bounds="[0,20][100,40]" /></node></hierarchy>"""
    new_xml = old_xml.replace("SIM cards", "SIMs")
    engine = HealingEngine(
        HealingConfig(embedder="lexical", confidence_threshold=0.0),
        embedder=FakeEmbedder(),
    )

    without_baseline = engine.heal(script, 0, new_xml)
    with_baseline = engine.heal(
        script, 0, new_xml, baseline_hierarchy_xml=old_xml
    )

    assert with_baseline.r6_applied is True
    assert with_baseline.candidates_after_narrowing < without_baseline.candidates_after_narrowing
    assert with_baseline.status is HealingStatus.HEALED


def test_settings_target_beyond_first_fifteen_is_ranked_first() -> None:
    script = """from appium.webdriver.common.appiumby import AppiumBy

def step_0(driver) -> None:
    driver.find_element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        'new UiSelector().text("Network and internet")',
    ).click()
"""
    xml = (
        Path(__file__).parents[1] / "fixtures" / "healing" / "settings_home_real.xml"
    ).read_text(encoding="utf-8")
    decision = HealingEngine(
        HealingConfig(embedder="lexical"),
    ).heal(script, 0, xml)

    assert decision.top_candidates
    assert decision.top_candidates[0].descriptor.text == "Network & internet"
    assert decision.top_candidates[0].node_index > 15
    assert decision.candidates_ranked >= 20
    assert set(decision.rule_counts) == {f"R{rule}" for rule in range(1, 8)}
