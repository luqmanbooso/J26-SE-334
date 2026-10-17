"""Conversion from normalized targets to Appium locator expressions."""

from __future__ import annotations


ALLOWED_TARGET_KEYS = {
    "resource_id",
    "accessibility_id",
    "content_desc",
    "text",
    "xpath",
}


def to_appium_locator(target: dict[str, str]) -> tuple[str, str]:
    """Return an AppiumBy constant name and locator value."""
    if not target:
        raise ValueError("A locator target is required")
    unknown = set(target) - ALLOWED_TARGET_KEYS
    if unknown:
        raise ValueError(f"Unsupported locator keys: {sorted(unknown)}")
    if target.get("resource_id"):
        return "ID", target["resource_id"]
    if target.get("accessibility_id"):
        return "ACCESSIBILITY_ID", target["accessibility_id"]
    if target.get("content_desc"):
        return "ACCESSIBILITY_ID", target["content_desc"]
    if target.get("text"):
        text = target["text"].replace("\\", "\\\\").replace('"', '\\"')
        return "ANDROID_UIAUTOMATOR", f'new UiSelector().text("{text}")'
    if target.get("xpath"):
        return "XPATH", target["xpath"]
    raise ValueError("A locator target must contain a non-empty value")
