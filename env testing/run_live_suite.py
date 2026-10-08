import time
from orchestrator import PerturbationOrchestrator

def main():
    print("=" * 80)
    print("  HEART FRAMEWORK - COMPONENT 1: CONTEXT-AWARE ENVIRONMENTAL PERTURBATION ENGINE")
    print("  Lead Researcher: G.L.S. Chanlaka (IT23151260)")
    print("  Project: J26-SE-334 | Multi-Factor Mobile Robustness Testing")
    print("=" * 80)

    orchestrator = PerturbationOrchestrator()

    try:
        # ---------------------------------------------------------------------
        # STAGE 1: HARDWARE RESOURCE STARVATION (CPU, RAM, THERMAL, BATTERY)
        # ---------------------------------------------------------------------
        print("\n>>> [STAGE 1] INJECTING HARDWARE RESOURCE STARVATION")
        print("  - Inducing 88% CPU load spike...")
        orchestrator.system.set_cpu_load(target_pct=88)

        print("  - Injecting Low-Memory Killer (LMK) RUNNING_CRITICAL trim pressure...")
        orchestrator.system.set_ram_pressure(pressure_pct=85, target_package="com.android.calculator2")

        print("  - Simulating battery drop to 4% (Unplugged status)...")
        orchestrator.system.set_battery(level=4, unplugged=True)

        print("  - Simulating battery thermal throttling to 55.0°C (Warn state)...")
        orchestrator.system.set_thermal_state("Warn")
        time.sleep(2.5)

        # ---------------------------------------------------------------------
        # STAGE 2: ADVANCED NETWORK CHAOS (BANDWIDTH, LATENCY, PACKET LOSS, HANDOVER)
        # ---------------------------------------------------------------------
        print("\n>>> [STAGE 2] INJECTING ADVANCED NETWORK CHAOS")
        print("  - Throttling bandwidth profile to 2G/EDGE (236 Kbps)...")
        orchestrator.network.set_bandwidth_profile("edge")

        print("  - Injecting 1450ms network RTT latency delay...")
        orchestrator.network.inject_latency(latency_ms=1450)

        print("  - Emulating 8% stochastic packet loss...")
        orchestrator.network.inject_packet_loss(loss_pct=8)

        print("  - Simulating sudden WiFi -> Cellular Data handover transition...")
        orchestrator.network.simulate_handover(from_mode="wifi_only", to_mode="data_only", transition_delay_sec=0.5)
        time.sleep(2.0)

        # ---------------------------------------------------------------------
        # STAGE 3: REAL-WORLD INTERRUPTIONS (CALLS, SMS, APP BACKGROUNDING)
        # ---------------------------------------------------------------------
        print("\n>>> [STAGE 3] SIMULATING REAL-WORLD INTERRUPTIONS")
        print("  - Triggering incoming GSM phone call from 1-555-019-2831...")
        orchestrator.interruption.trigger_incoming_call("15550192831")
        time.sleep(1.5)

        print("  - Answering incoming call via KEYCODE_CALL...")
        orchestrator.interruption.accept_call()
        time.sleep(1.5)

        print("  - Terminating call via KEYCODE_ENDCALL...")
        orchestrator.interruption.dismiss_call("15550192831")
        time.sleep(1.0)

        print("  - Dispatching heads-up SMS notification banner...")
        orchestrator.interruption.send_sms_banner(
            sender="15554321000",
            message="Your payment verification token is 492019."
        )

        print("  - Simulating app backgrounding (Home button) and lifecycle resume...")
        orchestrator.interruption.background_app(duration_sec=1.5, package_name="com.android.calculator2")
        time.sleep(1.5)

        # ---------------------------------------------------------------------
        # STAGE 4: CONTEXT PERTURBATION (ORIENTATION, THEME, FONT ACCESSIBILITY)
        # ---------------------------------------------------------------------
        print("\n>>> [STAGE 4] INJECTING ENVIRONMENTAL CONTEXT VARIATIONS")
        print("  - Switching display orientation to Landscape...")
        orchestrator.context.set_orientation("landscape")

        print("  - Toggling System Dark Mode (Night Theme)...")
        orchestrator.context.set_dark_mode(True)

        print("  - Escalating system accessibility font scale to 1.35x (UI collision stress)...")
        orchestrator.context.set_font_scale(1.35)
        time.sleep(2.0)

        # ---------------------------------------------------------------------
        # STAGE 5: DYNAMIC SCHEDULER & PERFORMANCE FEEDBACK
        # ---------------------------------------------------------------------
        print("\n>>> [STAGE 5] TESTING DYNAMIC SCHEDULER & ADAPTIVE SIGNAL ESCALATION")
        # Hook a stressor to a semantic step
        orchestrator.scheduler.register_step_hook(
            semantic_step="MID_TRANSACTION",
            action_fn=orchestrator.network.inject_latency,
            params={"latency_ms": 2500}
        )
        print("  - Simulating execution reaching semantic step: 'MID_TRANSACTION'...")
        orchestrator.scheduler.trigger_step("MID_TRANSACTION")

        # Simulate performance signal feedback (FPS dropped to 22.4 fps)
        print("  - Ingesting runtime performance signals: FPS = 24.5, Latency = 1350ms...")
        orchestrator.evaluate_signals({"fps": 24.5, "latency_ms": 1350.0, "cpu_pct": 89.0})
        time.sleep(1.5)

        # ---------------------------------------------------------------------
        # STAGE 6: ENVIRONMENT-INDUCED FAILURE ATTRIBUTION REPORTING
        # ---------------------------------------------------------------------
        print("\n>>> [STAGE 6] GENERATING ENVIRONMENT-TO-FAILURE ATTRIBUTION REPORT")
        sample_failures = [
            {
                "id": "FAIL_001",
                "type": "PAYMENT_GATEWAY_TIMEOUT",
                "description": "Checkout service encountered HTTP 504 Gateway Timeout during tokenization.",
                "component": "PaymentSDK.CheckoutActivity",
                "epoch_ms": int(time.time() * 1000) - 2000
            },
            {
                "id": "FAIL_002",
                "type": "GUI_OVERFLOW_COLLISION",
                "description": "Confirm button text overlapped by 42px beneath bottom navigation bar.",
                "component": "OrderSummaryFragment",
                "epoch_ms": int(time.time() * 1000) - 1000
            }
        ]
        attribution_report = orchestrator.correlate_failures(sample_failures)
        print(f"  - Attribution Analysis Completed: {attribution_report['attributed_failures_count']} of {len(sample_failures)} failures attributed to environmental triggers.")
        for attr in attribution_report["attributions"]:
            print(f"    * [{attr['failure_id']}] -> Trigger: {attr['primary_trigger']} (Confidence: {attr['confidence']*100:.1f}%)")
            print(f"      Root Cause: {attr['root_cause_explanation']}")
            print(f"      Recommendation: {attr['recommended_mitigation']}")

    finally:
        # ---------------------------------------------------------------------
        # STAGE 7: NOMINAL REVERT & TELEMETRY SAVE
        # ---------------------------------------------------------------------
        print("\n>>> [STAGE 7] REVERTING ALL ENVIRONMENTAL STRESSORS TO NOMINAL BASELINE")
        orchestrator.reset_all()
        print("\n" + "=" * 80)
        print("  MULTI-FACTOR PERTURBATION TEST RUN SUCCESSFULLY FINISHED & LOGGED")
        print("=" * 80)

if __name__ == "__main__":
    main()
