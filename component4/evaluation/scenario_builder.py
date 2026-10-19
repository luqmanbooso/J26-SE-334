"""Build deterministic mutation scenarios from hierarchy screens."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from c4.healing.hierarchy import UiNode, parse_hierarchy
from .mutations import MUTATIONS, Mutation


@dataclass(frozen=True)
class Scenario:
    """One old/new hierarchy pair and its mutation ground truth."""

    scenario_id: str
    screen_name: str
    old_xml: str
    new_xml: str
    script: str
    step_index: int
    locator_by: str
    locator_value: str
    target_node_index: int
    change_class: str
    in_scope: bool
    expected_status: str
    expected_node_index_in_new: int | None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _locator(node: UiNode, change_class: str) -> tuple[str, str]:
    if change_class in {"rename_id", "remove_id_keep_text"}:
        if not node.resource_id:
            raise ValueError("id mutation requires a resource-id")
        return "id", node.resource_id
    if change_class == "change_text":
        if not node.text:
            raise ValueError("text mutation requires text")
        escaped = node.text.replace("\\", "\\\\").replace('"', '\\"')
        return "-android uiautomator", f'new UiSelector().text("{escaped}")'
    if change_class == "change_content_desc":
        if not node.content_desc:
            raise ValueError("content-description mutation requires content-desc")
        return "accessibility id", node.content_desc
    if node.resource_id:
        return "id", node.resource_id
    if node.text:
        escaped = node.text.replace("\\", "\\\\").replace('"', '\\"')
        return "-android uiautomator", f'new UiSelector().text("{escaped}")'
    if node.content_desc:
        return "accessibility id", node.content_desc
    raise ValueError("node has no supported locator")


def _script(by: str, value: str) -> str:
    constant = {
        "id": "ID",
        "accessibility id": "ACCESSIBILITY_ID",
        "-android uiautomator": "ANDROID_UIAUTOMATOR",
    }[by]
    return (
        "from appium.webdriver.common.appiumby import AppiumBy\n\n"
        "def step_0(driver):\n"
        f"    driver.find_element(AppiumBy.{constant}, {value!r}).click()\n"
    )


def build_scenarios(
    hierarchies: list[tuple[str, str]],
    seed: int,
    targets_per_screen: int,
    skip_report: dict[str, dict[str, int]] | None = None,
) -> list[Scenario]:
    """Select eligible nodes and apply every mutation deterministically."""
    if targets_per_screen < 1:
        raise ValueError("targets_per_screen must be at least one")
    rng = random.Random(seed)
    scenarios: list[Scenario] = []
    for screen_name, old_xml in hierarchies:
        hierarchy = parse_hierarchy(old_xml)
        eligible = [
            node for node in hierarchy.nodes
            if (node.text or node.resource_id or node.content_desc)
            and (node.clickable or _clickable_parent(hierarchy, node))
        ]
        rng.shuffle(eligible)
        for target in sorted(eligible[:targets_per_screen], key=lambda item: item.index):
            for mutation in MUTATIONS:
                local_rng = random.Random(rng.randrange(2**32))
                result: Mutation | None = mutation(old_xml, target.index, local_rng)
                if result is None:
                    _skip(skip_report, mutation.__name__, "skipped_precondition")
                    continue
                try:
                    by, value = _locator(target, result.change_class)
                except ValueError:
                    _skip(skip_report, result.change_class, "skipped_precondition")
                    continue
                new_hierarchy = parse_hierarchy(result.new_xml)
                if new_hierarchy.count_matches(_hierarchy_by(by), value) != 0:
                    _skip(skip_report, result.change_class, "skipped_non_breaking")
                    continue
                script = _script(by, value)
                scenario_id = f"{Path(screen_name).stem}-{target.index:04d}-{result.change_class}"
                scenarios.append(
                    Scenario(
                        scenario_id, screen_name, old_xml, result.new_xml, script, 0,
                        by, value, target.index, result.change_class, result.in_scope,
                        result.expected_status, result.expected_node_index_in_new,
                    )
                )
    return sorted(scenarios, key=lambda item: item.scenario_id)


def write_scenarios(path: str | Path, scenarios: list[Scenario]) -> None:
    """Write stable JSONL scenario records."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        for scenario in scenarios:
            stream.write(json.dumps(scenario.as_dict(), sort_keys=True) + "\n")


def _clickable_parent(hierarchy, node: UiNode) -> bool:
    by_index = {item.index: item for item in hierarchy.nodes}
    parent = node.parent_index
    while parent is not None:
        current = by_index[parent]
        if current.clickable:
            return True
        parent = current.parent_index
    return False


def _hierarchy_by(by: str) -> str:
    return {
        "id": "id",
        "accessibility id": "accessibility id",
        "-android uiautomator": "-android uiautomator",
    }[by]


def _skip(
    report: dict[str, dict[str, int]] | None,
    change_class: str,
    reason: str,
) -> None:
    if report is None:
        return
    report.setdefault(change_class, {})
    report[change_class][reason] = report[change_class].get(reason, 0) + 1
