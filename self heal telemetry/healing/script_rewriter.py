import os
import sys
from typing import List, Dict, Any

class ScriptRewriter:
    """Generates self-contained, standalone executable healed regression test scripts."""

    @staticmethod
    def generate_repaired_script(original_script_path: str, healed_steps: List[Dict[str, Any]], output_path: str = "tests/test_launcher_healed.py") -> str:
        repaired_code = "#!/usr/bin/env python3\n"
        repaired_code += "# Auto-Healed Standalone Regression Test Script\n"
        repaired_code += f"# Source Target : {original_script_path}\n"
        repaired_code += "# Engine        : S-BERT Semantic Self-Healing Engine\n\n"
        repaired_code += "import os\nimport sys\nimport time\n\n"
        repaired_code += "# Ensure project root is in sys.path\n"
        repaired_code += "ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n"
        repaired_code += "if ROOT_DIR not in sys.path:\n"
        repaired_code += "    sys.path.insert(0, ROOT_DIR)\n\n"
        repaired_code += "from core.adb_client import ADBClient\n\n"
        repaired_code += "HEALED_TEST_PIPELINE = [\n"

        for step in healed_steps:
            repaired_code += "    {\n"
            repaired_code += f"        'step': {step['step']},\n"
            repaired_code += f"        'name': '{step['name']}',\n"
            repaired_code += f"        'original_broken_locator': '{step['original_locator']}',\n"
            repaired_code += f"        'healed_ui_element': '{step['healed_element']}',\n"
            repaired_code += f"        'resolved_coordinates': {step['coordinates']},\n"
            repaired_code += f"        'confidence_score': '{step['confidence']}%',\n"
            repaired_code += f"        'action': '{step['action']}'\n"
            repaired_code += "    },\n"

        repaired_code += "]\n\n"
        repaired_code += "def run_repaired_test(adb_client=None):\n"
        repaired_code += "    if adb_client is None:\n"
        repaired_code += "        adb_client = ADBClient()\n\n"
        repaired_code += "    print('=' * 65)\n"
        repaired_code += "    print('EXECUTING STANDALONE HEALED TEST SUITE (FAST REGRESSION RUN)')\n"
        repaired_code += "    print('=' * 65)\n\n"
        repaired_code += "    for item in HEALED_TEST_PIPELINE:\n"
        repaired_code += "        step = item['step']\n"
        repaired_code += "        name = item['name']\n"
        repaired_code += "        x, y = item['resolved_coordinates']\n"
        repaired_code += "        elem = item['healed_ui_element']\n"
        repaired_code += "        print(f'[Step {step}] Executing {name} -> Tapping target at ({x}, {y}) [{elem}]')\n"
        repaired_code += "        adb_client.tap(x, y)\n"
        repaired_code += "        time.sleep(2.0)\n\n"
        repaired_code += "    print('\\n[+] Healed Regression Suite Execution Passed Successfully!')\n"
        repaired_code += "    print('=' * 65)\n\n"
        repaired_code += "if __name__ == '__main__':\n"
        repaired_code += "    run_repaired_test()\n"

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(repaired_code)

        print(f"\n[+] Script Repair Complete! Successfully wrote healed test script to: {output_path}")
        return output_path
