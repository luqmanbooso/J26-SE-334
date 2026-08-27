import os
import time
from core.adb_client import ADBClient
from healing.sbert_matcher import SBERTSemanticMatcher
from healing.locator_healer import LocatorHealer
from healing.script_rewriter import ScriptRewriter
from tests.test_launcher_broken import TEST_PIPELINE

def main():
    print("=" * 75)
    print("EXECUTING COMPONENT 4: AUTONOMOUS TEST SCRIPT HEALING & REWRITING")
    print("=" * 75)

    adb = ADBClient()
    matcher = SBERTSemanticMatcher(model_name="all-MiniLM-L6-v2")
    healer = LocatorHealer(matcher)

    # 1. Capture current live layout
    print("\n[Step 1] Inspecting Live UI Screen Layout...")
    xml_path = adb.dump_hierarchy("window_dump.xml")

    healed_test_records = []

    print("\n[Step 2] Evaluating Test Script for Broken Locators...")
    for step in TEST_PIPELINE:
        step_id = step["step"]
        name = step["name"]
        broken_locator = step["target_locator"]
        legacy_id = step["legacy_resource_id"]
        action = step["action"]

        print(f"\n---> Evaluating Step {step_id}: '{name}'")
        print(f"     Target Locator : '{broken_locator}' (Legacy ID: {legacy_id})")

        # Resolve locator against live screen
        locator_query = {"text": broken_locator, "resource_id": legacy_id, "content_desc": broken_locator}
        node, confidence, status = healer.resolve_locator(locator_query, xml_path, threshold=0.35)

        if node:
            cx, cy = node["center"]
            print(f"     Detection      : [LOCATOR BROKEN / OUTDATED]")
            print(f"     Self-Healing   : Remapped to '{node['descriptor']}' (Confidence: {confidence * 100:.2f}%)")
            print(f"     Target Bounds  : Center=({cx}, {cy}) | Box={node['bounds']}")

            # Save healed data for script regeneration
            healed_test_records.append({
                "step": step_id,
                "name": name,
                "original_locator": broken_locator,
                "healed_element": node["descriptor"],
                "coordinates": (cx, cy),
                "confidence": f"{confidence * 100:.2f}",
                "action": action
            })

            # Execute the repaired action on the emulator
            print(f"     [ADB Dispatch] Executing live test tap at ({cx}, {cy})...")
            adb.tap(cx, cy)
            time.sleep(2.0)
        else:
            print(f"     Detection      : [HEALING FAILED] -> No matching UI candidate found.")

    # 3. Rewrite the test script on disk
    print("\n[Step 3] Rewriting & Fixing Test Script Code...")
    ScriptRewriter.generate_repaired_script("tests/test_launcher_broken.py", healed_test_records, "tests/test_launcher_healed.py")

    print("=" * 75)
    print("TEST SUITE EXECUTION & SELF-HEALING COMPLETE")
    print("=" * 75)

if __name__ == "__main__":
    main()
