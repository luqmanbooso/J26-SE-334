from pathlib import Path

import pytest

from c4.healing import (
    ElementDescriptor,
    HealingConfig,
    HealingEngine,
    HealingStatus,
    LexicalEmbedder,
    parse_hierarchy,
)
from c4.healing.hierarchy import HierarchyParseError, node_to_descriptor
from c4.healing.policy import build_unique_locator, decide
from c4.healing.script_ast import StepNotFoundError, extract_step, rewrite_step_locator
from c4.healing.narrowing import StructuralNarrower


FIXTURES = Path(__file__).parents[1] / "fixtures" / "healing"


SCRIPT = """from appium.webdriver.common.appiumby import AppiumBy

def step_0(driver) -> None:
    # preserve this comment
    driver.find_element(AppiumBy.ID, "com.example:id/btn_pay").click()

def step_1(driver) -> None:
    driver.find_element(AppiumBy.ID, "email").send_keys("user@example.com")
"""


def test_hierarchy_parses_page_source_and_locators() -> None:
    hierarchy = parse_hierarchy(
        '<hierarchy><node class="android.widget.Button" resource-id="pkg:id/pay" '
        'text="Pay" content-desc="Pay button" bounds="[1,2][20,30]" '
        'clickable="true" enabled="true" /></hierarchy>'
    )

    assert hierarchy.count_matches("id", "pay") == 1
    assert hierarchy.count_matches("id", "pkg:id/pay") == 1
    assert hierarchy.count_matches("accessibility id", "Pay button") == 1
    assert hierarchy.count_matches(
        "-android uiautomator", 'new UiSelector().text("Pay")'
    ) == 1
    assert hierarchy.nodes[1].bounds == (1, 2, 20, 30)


def test_hierarchy_rejects_malformed_xml() -> None:
    with pytest.raises(HierarchyParseError):
        parse_hierarchy("<hierarchy>")


def test_ast_extracts_and_rewrites_only_locator() -> None:
    info = extract_step(SCRIPT, 0)
    assert info.action == "tap"
    assert info.by == "ID"
    assert info.value == "com.example:id/btn_pay"

    healed = rewrite_step_locator(
        SCRIPT, 0, "ID", "com.example:id/btn_pay_now_v2", "unique semantic match"
    )
    assert healed.startswith("# healed: ID=com.example:id/btn_pay")
    assert "# preserve this comment" in healed
    assert "com.example:id/btn_pay_now_v2" in healed
    assert 'AppiumBy.ID, "email"' in healed
    compile(healed, "<healed>", "exec")


def test_ast_rejects_missing_step_and_non_literal_locator() -> None:
    with pytest.raises(StepNotFoundError):
        extract_step(SCRIPT, 99)
    with pytest.raises(StepNotFoundError):
        extract_step(
            "def step_0(driver):\n    driver.find_element(AppiumBy.ID, value).click()\n",
            0,
        )


def test_narrower_applies_enabled_visible_package_action_and_identity_rules() -> None:
    hierarchy = parse_hierarchy(
        '<hierarchy><node class="android.widget.Button" package="pkg" '
        'resource-id="pkg:id/ok" text="OK" clickable="true" enabled="true" bounds="[0,0][20,20]" />'
        '<node class="android.widget.Button" package="other" resource-id="other:id/no" '
        'text="No" clickable="true" enabled="true" bounds="[0,0][20,20]" /></hierarchy>'
    )
    descriptor = ElementDescriptor(
        class_name="android.widget.Button", package="pkg", text="OK"
    )
    candidates, stats = StructuralNarrower().narrow(hierarchy, descriptor, "tap")
    assert [node.resource_id for node in candidates] == ["pkg:id/ok"]
    assert stats["R2"] == 1


def test_telemetry_tap_narrowing_uses_clickable_ancestors_and_r7() -> None:
    hierarchy = parse_hierarchy(
        '<hierarchy><node class="android.widget.FrameLayout" '
        'enabled="true" bounds="[0,0][100,100]" />'
        '<node class="android.widget.LinearLayout" clickable="true" '
        'enabled="true" bounds="[0,0][100,50]"><node class="android.widget.TextView" '
        'text="Inside row" enabled="true" bounds="[0,0][100,50]" /></node>'
        '<node class="android.widget.TextView" text="Standalone" enabled="true" '
        'bounds="[0,50][100,100]" /></hierarchy>'
    )
    candidates, counts = StructuralNarrower().narrow(
        hierarchy, ElementDescriptor(), "tap"
    )

    assert [node.text for node in candidates] == ["Inside row"]
    assert counts["R3"] >= 1
    assert counts["R7"] >= 1
    assert set(counts) == {f"R{rule}" for rule in range(1, 8)}
    assert counts["R6"] == 0


def test_engine_heals_to_unique_new_resource_id() -> None:
    xml = (FIXTURES / "checkout_new.xml").read_text(encoding="utf-8")
    baseline = ElementDescriptor(
        resource_id="com.example:id/btn_pay",
        text="Pay now",
        class_name="android.widget.Button",
        package="com.example",
        clickable=True,
    )
    decision = HealingEngine(
        HealingConfig(embedder="lexical"), embedder=LexicalEmbedder()
    ).heal(SCRIPT, 0, xml, baseline)

    assert decision.status is HealingStatus.HEALED
    assert decision.healed_locator == {
        "by": "ID",
        "value": "com.example:id/btn_pay_now_v2",
    }
    assert decision.healed_script is not None
    compile(decision.healed_script, "<healed>", "exec")


def test_engine_refuses_removed_element_without_script() -> None:
    xml = (FIXTURES / "removed_element_new.xml").read_text(encoding="utf-8")
    baseline = ElementDescriptor(
        resource_id="com.example:id/btn_pay",
        text="Pay now",
        class_name="android.widget.Button",
        package="com.example",
    )
    decision = HealingEngine(
        HealingConfig(embedder="lexical"), embedder=LexicalEmbedder()
    ).heal(SCRIPT, 0, xml, baseline)

    assert decision.status in {
        HealingStatus.REFUSED_LOW_CONFIDENCE,
        HealingStatus.REFUSED_NO_CANDIDATES,
    }
    assert decision.healed_script is None


def test_policy_threshold_boundary() -> None:
    config = HealingConfig(confidence_threshold=0.5)
    assert decide([(1, 0.5)], config)[0] == "accept"
    assert decide([(1, 0.499)], config)[0] == "refused_low_confidence"


def test_generic_id_falls_back_to_unique_text() -> None:
    hierarchy = parse_hierarchy(
        '<hierarchy><node class="android.widget.Button" resource-id="android:id/title" '
    'text="Pay" clickable="true" enabled="true" bounds="[0,0][20,20]" />'
    '<node class="android.widget.TextView" resource-id="android:id/title" '
    'text="Title" enabled="true" bounds="[0,20][20,40]" /></hierarchy>'
    )
    node = hierarchy.nodes[1]
    assert build_unique_locator(node, hierarchy) == (
        "-android uiautomator",
        'new UiSelector().text("Pay")',
    )


@pytest.mark.live_sbert
def test_live_sbert_settings_rename() -> None:
    if not __import__("os").environ.get("C4_LIVE_SBERT"):
        pytest.skip("set C4_LIVE_SBERT=1 to run")
    from c4.healing.semantic import SentenceBertEmbedder

    script = """from appium.webdriver.common.appiumby import AppiumBy

def step_0(driver) -> None:
    driver.find_element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        'new UiSelector().text("Network and internet")',
    ).click()
"""
    xml = (FIXTURES / "settings_home_real.xml").read_text(encoding="utf-8")
    decision = HealingEngine(
        HealingConfig(),
        embedder=SentenceBertEmbedder(HealingConfig().sbert_model),
    ).heal(script, 0, xml)

    print(f"confidence={decision.confidence}")
    assert decision.status is HealingStatus.HEALED
    assert decision.confidence is not None and decision.confidence >= 0.5
    assert decision.healed_locator == {
        "by": "ANDROID_UIAUTOMATOR",
        "value": 'new UiSelector().text("Network & internet")',
    }
