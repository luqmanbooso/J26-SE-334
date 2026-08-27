#!/usr/bin/env python3
# Automated Regression Test Script - Build v1.0.0 (Legacy)
# Simulates standard strict-locator automated test execution

import os
import sys
import xml.etree.ElementTree as ET

# Ensure project root is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.adb_client import ADBClient

TEST_PIPELINE = [
    {
        "step": 1,
        "name": "Launch Phone Application",
        "target_locator": "Dial Phone Keypad",
        "legacy_resource_id": "com.android.contacts:id/btn_make_call",
        "action": "TAP"
    },
    {
        "step": 2,
        "name": "Launch SMS Chat Application",
        "target_locator": "Send SMS Chat",
        "legacy_resource_id": "com.android.mms:id/compose_new_message",
        "action": "TAP"
    },
    {
        "step": 3,
        "name": "Launch Web Browser Application",
        "target_locator": "Web Browser Navigator",
        "legacy_resource_id": "com.android.browser:id/url_bar_launch",
        "action": "TAP"
    }
]

def find_strict_element(xml_path: str, text: str, res_id: str):
    """Simulates strict Appium/Selenium locator lookup."""
    tree = ET.parse(xml_path)
    for node in tree.getroot().iter("node"):
        n_text = node.attrib.get("text", "").strip()
        n_id = node.attrib.get("resource-id", "").strip()
        if (text and n_text.lower() == text.lower()) or (res_id and n_id.lower() == res_id.lower()):
            return node
    return None

def run_broken_test():
    adb = ADBClient()
    print("=" * 70)
    print("RUNNING LEGACY REGRESSION TEST SUITE (STRICT LOCATORS)")
    print("=" * 70)

    xml_path = adb.dump_hierarchy("window_dump.xml")

    passed = 0
    failed = 0

    for item in TEST_PIPELINE:
        step = item["step"]
        name = item["name"]
        target = item["target_locator"]
        res_id = item["legacy_resource_id"]

        print(f"\n[Step {step}] Executing: '{name}'")
        print(f"    Searching for Text: '{target}' | ID: '{res_id}'")

        node = find_strict_element(xml_path, target, res_id)

        if node is not None:
            print(f"    -> [PASS] Element located successfully.")
            passed += 1
        else:
            print(f"    -> [FAIL] ElementNotFoundError: Unable to locate element on screen.")
            failed += 1

    print("\n" + "=" * 70)
    print(f"TEST EXECUTION SUMMARY: {passed} Passed | {failed} Failed")
    if failed > 0:
        print("RESULT: FAILED (Test suite broke due to outdated/mutated UI locators)")
    else:
        print("RESULT: PASSED")
    print("=" * 70)

if __name__ == "__main__":
    run_broken_test()
