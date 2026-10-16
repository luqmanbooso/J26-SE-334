"""
Live Android Device Defect Inspector (HEART Component 3).
Connects to physical Android hardware or emulator via common.adb,
streams live frame through AST Pruner (<5ms) and SAHI Dynamic Slicing,
and generates structured C4 Verdict.
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Add project root and Component 4 src to path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
C4_SRC = REPO_ROOT / "component4" / "src"
if C4_SRC.exists() and str(C4_SRC) not in sys.path:
    sys.path.insert(0, str(C4_SRC))

from common.adb import AdbDevice, NoDeviceError
from local_vision_oracle.engine import OracleEngine, TransformersInferenceBackend, MockInferenceBackend


def main():
    parser = argparse.ArgumentParser(description="Live Android Screen Inspection via C3 Oracle")
    parser.add_argument("--serial", type=str, default=None, help="ADB serial of target device/emulator")
    parser.add_argument("--mock", action="store_true", help="Use MockInferenceBackend for rapid smoke testing")
    parser.add_argument("--no-sahi", action="store_true", help="Disable SAHI dynamic tiling fallback")
    try:
        from vision_oracle.core.config import BASE_MODEL_PATH, LORA_WEIGHTS_PATH
        default_base = str(BASE_MODEL_PATH) if BASE_MODEL_PATH else r"D:\university\Resesarch\RD\models\Qwen2-VL-2B-Instruct"
        default_lora = str(LORA_WEIGHTS_PATH) if LORA_WEIGHTS_PATH else r"D:\university\Resesarch\J26-SE-334\models\c3_lora_final"
    except Exception:
        default_base = r"D:\university\Resesarch\RD\models\Qwen2-VL-2B-Instruct"
        default_lora = r"D:\university\Resesarch\J26-SE-334\models\c3_lora_final"
    parser.add_argument("--base-model", type=str, default=default_base)
    parser.add_argument("--weights", type=str, default=default_lora)
    parser.add_argument("--output", type=str, default=None, help="Save C4 JSON verdict to file")
    args = parser.parse_args()

    print("=" * 65)
    print(" HEART C3 VISION-SEMANTIC ORACLE: LIVE DEVICE INSPECTOR")
    print("=" * 65)

    try:
        # Step 1: Connect to physical hardware / emulator via common.adb
        print("[1/4] Connecting to Android hardware via common.adb...")
        device = AdbDevice(serial=args.serial)
        print(f"[+] Device Connected : {device.serial}")
        metrics = device.get_display_metrics()
        print(f"[+] Viewport Metrics : {metrics['width']}x{metrics['height']} ({metrics['density']} DPI) | Tall: {metrics['is_tall']}")

        # Step 2: Initialize Edge Model Backend
        print("\n[2/4] Initializing VLM Inference Engine...")
        if args.mock:
            print("[*] Mode: Mock Backend (Testing)")
            backend = MockInferenceBackend()
        else:
            print(f"[*] Base Model : {args.base_model}")
            print(f"[*] LoRA Weights: {args.weights}")
            backend = TransformersInferenceBackend(
                model_name_or_path=args.base_model,
                adapter_dir=args.weights,
                quantization_bit=4,
            )
        oracle = OracleEngine(backend=backend)

        # Step 3: Stream Live Screen & Hierarchy
        print("\n[3/4] Streaming live screen and dumping view hierarchy...")
        result = oracle.evaluate_device(
            device=device,
            enable_sahi=not args.no_sahi,
            action_context="Live device robustness verification pass",
        )

        # Step 4: Emit Verdict
        print("\n[4/4] Evaluation Complete:")
        verdict = result.verdict
        print(f"  * Has Defect      : {verdict.has_defect}")
        print(f"  * Defect Type     : {verdict.defect_type}")
        print(f"  * Confidence      : {verdict.confidence:.2f}")
        print(f"  * Bounding Box    : {verdict.bounding_box}")
        print(f"  * Detected By     : {result.metadata.get('detected_by')}")
        print(f"  * Capture Time    : {result.latency_breakdown.capture_ms} ms")
        print(f"  * AST Prune Time  : {result.latency_breakdown.prune_ms} ms")
        print(f"  * Inference Time  : {result.latency_breakdown.inference_ms} ms")
        print(f"  * Meets SLA (<1.5s): {result.latency_breakdown.meets_sla}")

        # Map to Component 4 Contract
        c4_verdict = OracleEngine.to_c4_verdict(result)
        print("\n" + "=" * 65)
        print(" STRUCTURED C4 INTERFACE VERDICT (IF-C3-to-C4)")
        print("=" * 65)
        c4_json = json.dumps(c4_verdict.model_dump(), indent=2)
        print(c4_json)

        if args.output:
            out_p = Path(args.output)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as f:
                f.write(c4_json)
            print(f"\n[+] Saved C4 verdict to: {args.output}")

    except NoDeviceError as e:
        print(f"\n[!] DEVICE ERROR: {e}", file=sys.stderr)
        print("[!] Connect an Android device with USB debugging or start an emulator.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[!] EXECUTION ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
