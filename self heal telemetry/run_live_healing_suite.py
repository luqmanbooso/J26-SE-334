import time
from core.adb_client import ADBClient
from core.telemetry_parser import TelemetryParser
from healing.sbert_matcher import SBERTSemanticMatcher
from healing.locator_healer import LocatorHealer

def main():
    print("=" * 70)
    print("EXECUTING COMPONENT 4: TELEMETRY SYNTHESIS & S-BERT LOCATOR SELF-HEALING")
    print("=" * 70)

    adb = ADBClient()
    matcher = SBERTSemanticMatcher(model_name="all-MiniLM-L6-v2")
    healer = LocatorHealer(matcher)

    breadcrumbs = TelemetryParser.load_trace("data/sample_telemetry.json")

    print("\n[Step 1] Capturing Live Emulator UI View Hierarchy Tree...")
    xml_path = adb.dump_hierarchy("window_dump.xml")

    print("\n[Step 2] Executing Self-Healing Test Synthesis Loop...")
    for item in breadcrumbs:
        step_no = item["step"]
        action = item["action"]
        orig_loc = item["original_locator"]

        print(f"\n--- Processing Telemetry Step {step_no}: Action={action} ---")
        print(f"    Original Locator -> Text: '{orig_loc.get('text')}' | ID: '{orig_loc.get('resource_id')}' | Desc: '{orig_loc.get('content_desc')}'")

        node, confidence, status = healer.resolve_locator(orig_loc, xml_path, threshold=0.35)

        if node:
            cx, cy = node["center"]
            print(f"    Status         : [{status}]")
            print(f"    Semantic Match : '{node['descriptor']}'")
            print(f"    Confidence     : {confidence * 100:.2f}%")
            print(f"    Resolved Pixel : Center=({cx}, {cy}) | Bounds={node['bounds']}")
            
            print(f"    [ADB Dispatch] Executing {action} at ({cx}, {cy})...")
            adb.tap(cx, cy)
            time.sleep(2.0)
        else:
            print(f"    Status: [FAILED] -> Confidence too low ({confidence * 100:.2f}%)")

    print("\n" + "=" * 70)
    print("SELF-HEALING TELEMETRY EXECUTION COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
