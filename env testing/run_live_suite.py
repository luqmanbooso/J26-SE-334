import time
from orchestrator import PerturbationOrchestrator

def main():
    orchestrator = PerturbationOrchestrator()

    print("\n" + "=" * 70)
    print("EXECUTING COMPONENT 1: FULL MULTI-FACTOR PERTURBATION SUITE")
    print("=" * 70)

    try:
        # ---------------------------------------------------------
        # STAGE 1: DEVICE POWER & THERMAL STRESS
        # ---------------------------------------------------------
        print("\n[Stage 1] Battery & Thermal Stress: Dropping to 3% (Unplugged) & 47.5°C...")
        orchestrator.device.set_battery(level=3, unplugged=True)
        orchestrator.device.simulate_thermal_throttling(temp_celsius=47.5)
        print("          -> Look at the battery icon in top-right corner.")
        time.sleep(4)

        # ---------------------------------------------------------
        # STAGE 2: UI THEME & ORIENTATION CONTEXT
        # ---------------------------------------------------------
        print("\n[Stage 2] Context Switch: Enabling Dark Mode & Landscape Orientation...")
        orchestrator.context.set_dark_mode(enabled=True)
        orchestrator.context.set_orientation(mode="landscape")
        print("          -> Screen is now horizontal with dark UI styling.")
        time.sleep(4)

        # ---------------------------------------------------------
        # STAGE 3: NETWORK PERTURBATION (AIRPLANE / OFFLINE)
        # ---------------------------------------------------------
        print("\n[Stage 3] Network Loss: Enabling Airplane Mode (Cutting WiFi & Data)...")
        orchestrator.network.set_mode("offline")
        print("          -> Look at the airplane icon on the status bar.")
        time.sleep(4)

        print("\n[Stage 3b] Network Recovery: Restoring WiFi & Cell Data...")
        orchestrator.network.set_mode("normal")
        time.sleep(2)

        # ---------------------------------------------------------
        # STAGE 4: INTERRUPTIONS (CALLS)
        # ---------------------------------------------------------
        print("\n[Stage 4a] Call Success: Ringing -> Answering -> Active Call...")
        orchestrator.interruption.trigger_incoming_call(phone_number="15555215554")
        time.sleep(3)
        orchestrator.interruption.accept_call()
        print("          -> Call accepted! Call timer is ticking...")
        time.sleep(3)
        orchestrator.interruption.dismiss_call(phone_number="15555215554")
        time.sleep(2)

        print("\n[Stage 4b] Call Fail: Ringing -> Immediately Declined...")
        orchestrator.interruption.trigger_incoming_call(phone_number="18009999999")
        time.sleep(2)
        orchestrator.interruption.dismiss_call(phone_number="18009999999")
        time.sleep(2)

        # ---------------------------------------------------------
        # STAGE 5: INTERRUPTIONS (SMS)
        # ---------------------------------------------------------
        print("\n[Stage 5a] SMS Success: Heads-up Push Banner Triggered...")
        orchestrator.interruption.send_sms_banner(
            sender="15555215554",
            message="Your OTP is 492019. Valid for 5 minutes.",
            force_fail=False
        )
        time.sleep(4)

        print("\n[Stage 5b] SMS Fail: Testing Modem Error Handling (Alphanumeric Sender)...")
        orchestrator.interruption.send_sms_banner(
            sender="SecurityAlert",
            message="Purposely invalid sender format test.",
            force_fail=True
        )
        time.sleep(2)

    finally:
        # Restore normal settings and output log
        orchestrator.reset_all()
        print("=" * 70)
        print("FULL PERTURBATION TEST RUN COMPLETED & LOGGED")
        print("=" * 70)

if __name__ == "__main__":
    main()
