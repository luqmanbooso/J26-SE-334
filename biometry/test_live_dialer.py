import time
import subprocess
from bridge.adb_bridge import ADBBridge
from models.stress import StressModel
from simulation.simulator import BiometricSimulator


def launch_dialer():
    """Opens the Phone dialer keypad on any Android device/emulator."""
    print("[Android] Launching Phone Dialer...")
    # Intent action DIAL opens the phone keypad
    subprocess.run(
        ["adb", "shell", "am", "start", "-a", "android.intent.action.DIAL"],
        check=True,
        capture_output=True
    )
    time.sleep(1.5)  # Wait for keypad animation to finish


def find_dialer_digit(bridge: ADBBridge, digit: str):
    """
    Locates dial pad digits across stock Android / Google Dialer:
    Matches by text ('7'), content-desc ('seven', '7'), or resource-id ('seven', 'digit_7').
    """
    word_map = {
        "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
        "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"
    }
    word = word_map.get(digit, "")

    queries = [digit, word, f"digit_{digit}", f"key_{digit}"]
    for query in queries:
        try:
            return bridge.find_element_by_text(query)
        except ValueError:
            continue

    raise ValueError(f"Could not locate dialer key for digit '{digit}' on screen.")


def main():
    launch_dialer()

    bridge = ADBBridge()
    # Initialize simulator with Rotational Dual Gaussian Model
    simulator = BiometricSimulator(base_sigma=12.0, base_time=0.3)

    # Sequence of digits to dial: '1', '5', '9', '0'
    dial_sequence = ["1", "5", "9", "0"]
    stress_levels = [0.0, 0.4, 0.8, 1.0]

    print("\n" + "=" * 65)
    print("STARTING BIOMETRIC DIALER TEST ON ANDROID EMULATOR")
    print("=" * 65)

    finger_pos = (500, 1800)  # Simulated resting thumb position at screen bottom

    for digit, stress_val in zip(dial_sequence, stress_levels):
        stress_model = StressModel(stress=stress_val)
        current_stress = stress_model.get_stress()

        print(f"\n[Step] Target Digit: '{digit}' | Modeled Stress: {current_stress}")

        # 1. Locate keypad button in live UI Hierarchy
        target = find_dialer_digit(bridge, digit)
        print(f"  -> Target Center: ({target['x']}, {target['y']}), Bounds: {target['width']}x{target['height']}px")

        # 2. Compute Biometric Coordinates using Rotational Dual Gaussian Model
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
        hit_status = "HIT KEY" if sim_result["is_hit"] else "MISSED BOUNDARY!"

        print(f"  -> Approach Vector (θ): {sim_result['approach_angle_deg']}°")
        print(f"  -> Dispatched Point: ({actual_x}, {actual_y}) [{hit_status}]")
        print(f"  -> Motor Movement Delay: {delay}s")

        # 3. Fire distorted tap to the emulator
        bridge.execute_tap(actual_x, actual_y, pre_delay=delay)

        # Update resting finger position for next vector
        finger_pos = (actual_x, actual_y)

    print("\n" + "=" * 65)
    print("DIALER SEQUENCE COMPLETED ON LIVE EMULATOR")
    print("=" * 65)


if __name__ == "__main__":
    main()