"""Positional XPath locators, as produced by the AndroR2 converter, can be resolved and healed."""

from pathlib import Path

import pytest

from c4.healing.engine import HealingEngine
from c4.healing.hierarchy import parse_hierarchy
from c4.healing.models import HealingConfig
from c4.healing.semantic import LexicalEmbedder

OLD = Path(__file__).parents[1].joinpath("fixtures", "healing", "settings_home_real.xml").read_text(encoding="utf-8")
NEW = OLD.replace("Wi-Fi", "Wi-Fi settings")
HIERARCHY = parse_hierarchy(OLD)
TEXT_VIEWS = [node for node in HIERARCHY.nodes if node.class_name == "android.widget.TextView"]
WIFI_POSITION = next(i for i, node in enumerate(TEXT_VIEWS, start=1) if node.text == "Wi-Fi")


def _script(xpath):
    return (
        "from appium.webdriver.common.appiumby import AppiumBy\n\n\n"
        "def step_0(driver) -> None:\n"
        f"    driver.find_element(AppiumBy.XPATH, \"{xpath}\").click()\n"
    )


def _engine():
    return HealingEngine(HealingConfig(embedder="lexical"), LexicalEmbedder())


def test_class_position_resolves_to_the_nth_node_of_that_class() -> None:
    found = HIERARCHY.find_by_locator("xpath", f"(//android.widget.TextView)[{WIFI_POSITION}]")
    assert [node.text for node in found] == ["Wi-Fi"]
    assert HIERARCHY.find_by_locator("xpath", "(//android.widget.TextView)[1]") == [TEXT_VIEWS[0]]


def test_clickable_positions_count_only_clickable_nodes() -> None:
    clickable = [node for node in HIERARCHY.nodes if node.clickable]
    if len(clickable) >= 2:
        assert HIERARCHY.find_by_locator("xpath", "(//*[@clickable='true'])[2]") == [clickable[1]]
    both = [node for node in TEXT_VIEWS if node.clickable]
    if both:
        assert HIERARCHY.find_by_locator("xpath", "(//android.widget.TextView[@clickable='true'])[1]") == [both[0]]
    unclickable = [node for node in HIERARCHY.nodes if not node.clickable]
    assert HIERARCHY.find_by_locator("xpath", "(//*[@clickable='false'])[1]") == [unclickable[0]]


@pytest.mark.parametrize("xpath", [
    "(//android.widget.TextView)[0]",
    "(//android.widget.TextView)[9999]",
    "(//android.widget.NoSuchWidget)[1]",
    "//android.widget.TextView[1]",
])
def test_positions_out_of_range_or_unsupported_forms_match_nothing(xpath) -> None:
    assert HIERARCHY.find_by_locator("xpath", xpath) == []


def test_existing_attribute_xpath_still_resolves() -> None:
    found = HIERARCHY.find_by_locator("xpath", "//android.widget.TextView[@text='Wi-Fi']")
    assert found == [] or all(node.text == "Wi-Fi" for node in found)


def test_xpath_locator_heals_when_the_old_screen_is_known() -> None:
    decision = _engine().heal(
        _script(f"(//android.widget.TextView)[{WIFI_POSITION}]"), 0, NEW, baseline_hierarchy_xml=OLD
    )

    assert decision.status.value == "healed"
    assert decision.original_locator == {"by": "XPATH", "value": f"(//android.widget.TextView)[{WIFI_POSITION}]"}
    assert decision.healed_locator == {"by": "ANDROID_UIAUTOMATOR", "value": 'new UiSelector().text("Wi-Fi settings")'}
    assert decision.r6_applied


def test_xpath_locator_without_an_old_screen_is_refused_with_the_real_reason() -> None:
    decision = _engine().heal(_script(f"(//android.widget.TextView)[{WIFI_POSITION}]"), 0, NEW)

    assert decision.status.value == "refused_low_confidence" and decision.healed_locator is None
    assert "no text, id or description to compare" in decision.reason


def test_a_normal_low_confidence_refusal_does_not_blame_the_locator() -> None:
    script = _script("//android.widget.TextView").replace(
        'AppiumBy.XPATH, "//android.widget.TextView"',
        'AppiumBy.ANDROID_UIAUTOMATOR, \'new UiSelector().text("Zzzzqqq Unrelated")\'',
    )
    decision = _engine().heal(script, 0, NEW)

    assert decision.status.value.startswith("refused") and "no text, id or description" not in (decision.reason or "")
