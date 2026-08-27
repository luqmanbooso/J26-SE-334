import time
import subprocess
from bridge.adb_bridge import ADBBridge
from models.stress import StressModel
from simulation.simulator import BiometricSimulator


def launch_calculator():
    """Detects and launches the calculator installed on the emulator."""
    print("[Android] Detecting installed calculator package...")
    
    # 1. Try launching via system Category Intent
    res = subprocess.run(
        ["adb", "shell", "am", "start", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.APP_CALCULATOR"],
        capture_output=True,
        text=True
    )
    if res.returncode == 0:
        time.sleep(1.5)
        return

    # 2. Check for known calculator packages
    pkg_check = subprocess.run(
        ["adb", "shell", "pm", "list", "packages", "calc"],
        capture_output=True,
        text=True
    ).stdout

    known_packages = ["com.google.android.calculator", "com.android.calculator2"]
    for pkg in known_packages:
        if pkg in pkg_check:
            print(f"[Android] Found package: {pkg}. Launching...")
            subprocess.run(["adb", "shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"], capture_output=True)
            time.sleep(1.5)
            return

    # 3. Fallback: launch using general intent
    subprocess.run(["adb", "shell", "am", "start", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER"], capture_output=True)
    time.sleep(1.5)


def find_calc_button(bridge: ADBBridge, key: str):
    """
    Finds calculator keys across different Android OS variants:
    Checks text labels, content descriptions, and resource-id tags.
    """
    aliases = {
        "7": ["7", "digit_7", "seven"],
        "+": ["+", "plus", "op_add", "add"],
        "5": ["5", "digit_5", "five"],
        "=": ["=", "equal", "equals", "eq"]
    }
    
    search_terms = aliases.get(key, [key])
    for term in search_terms:
        try:
            return bridge.find_element_by_text(term)
        except ValueError:
            continue

    raise ValueError(f"Could not locate button for key '{key}' on screen.")


def main():
    launch_calculator()

    bridge = ADBBridge()
    # Initialize simulator with Rotational Dual Gaussian Spatial Model[cite: 1]
    simulator = BiometricSimulator(base_sigma=12.0, base_time=0.3)

    # Sequence of buttons to tap: '7', '+', '5', '='
    test_sequence = ["7", "+", "5", "="]
    stress_levels = [0.0, 0.4, 0.8, 1.0]

    print("\n" + "=" * 65)
    print("STARTING BIOMETRIC TOUCH INJECTION ON ANDROID EMULATOR")
    print("=" * 65)

    finger_pos = (500, 1500)  # Simulated resting finger position

    for btn_key, stress_val in zip(test_sequence, stress_levels):
        stress_model = StressModel(stress=stress_val)
        current_stress = stress_model.get_stress()

        print(f"\n[Step] Target Key: '{btn_key}' | Modeled Stress: {current_stress}")

        # 1. Locate button in live UI Hierarchy[cite: 1]
        target = find_calc_button(bridge, btn_key)
        print(f"  -> Target Center: ({target['x']}, {target['y']}), Bounds: {target['width']}x{target['height']}px")

        # 2. Generate Rotational Dual Gaussian Coordinates & Delay[cite: 1]
        sim_result = simulator.simulate_tap(
            target_x=target["x"],
            target_y=target["y"],
            width=target["width"],
            height=target["height"],
            stress=current_stress,
            prev_x=finger_pos[0],
            prev_y=finger_pos[1]
        )

        actual_x = sim_result["actual"]["x"]
        actual_y = sim_result["actual"]["y"]
        delay = sim_result["delay"]
        hit_status = "INSIDE BOUNDS" if sim_result["is_hit"] else "MISSED EDGE!"

        print(f"  -> Approach Vector (θ): {sim_result['approach_angle_deg']}°")
        print(f"  -> Dispatched Point: ({actual_x}, {actual_y}) [{hit_status}]")
        print(f"  -> Motor Movement Delay: {delay}s")

        # 3. Dispatch distorted tap to emulator screen via ADB[cite: 1]
        bridge.execute_tap(actual_x, actual_y, pre_delay=delay)

        # Update resting finger position for the next approach vector
        finger_pos = (actual_x, actual_y)

    print("\n" + "=" * 65)
    print("CALCULATOR SEQUENCE COMPLETED ON LIVE EMULATOR")
    print("=" * 65)


if __name__ == "__main__":
    main()