import time
from orchestrator import PerturbationOrchestrator

def run_themis_benchmark_test(package_name="com.themis.benchmark.ecommerce"):
    """Demonstrates Component 1 stress injection against a Themis benchmark app flow."""
    print("=" * 80)
    print("  THEMIS BENCHMARK ROBUSTNESS TEST: ENVIRONMENTAL PERTURBATION SUITE")
    print(f"  Target Application: {package_name}")
    print("=" * 80)

    orchestrator = PerturbationOrchestrator(log_path="themis_test_event_log.json")

    try:
        # Step 1: Pre-Condition Check
        print("\n[Step 1] Initializing target app in nominal environment...")
        orchestrator.reset_all()
        time.sleep(1.0)

        # Step 2: Register semantic perturbation hooks
        print("\n[Step 2] Hooking context-aware stressors to transaction lifecycle:")
        print("  - [PRE_INPUT]: Battery drop to 5% alert")
        print("  - [MID_TRANSACTION]: WiFi -> Cellular Data handover + 1800ms latency spike")
        print("  - [ASYNC_WAIT]: Incoming GSM call ringing")

        orchestrator.scheduler.register_step_hook(
            "PRE_INPUT",
            orchestrator.system.set_battery,
            {"level": 5, "unplugged": True}
        )
        orchestrator.scheduler.register_step_hook(
            "MID_TRANSACTION",
            orchestrator.network.simulate_handover,
            {"from_mode": "wifi_only", "to_mode": "data_only", "transition_delay_sec": 0.5}
        )
        orchestrator.scheduler.register_step_hook(
            "MID_TRANSACTION",
            orchestrator.network.inject_latency,
            {"latency_ms": 1800}
        )
        orchestrator.scheduler.register_step_hook(
            "ASYNC_WAIT",
            orchestrator.interruption.trigger_incoming_call,
            {"phone_number": "15550192831"}
        )

        # Step 3: Simulate test flow execution
        print("\n[Step 3] Simulating automated test flow execution:")
        print("  -> App Launched. Entering user credentials...")
        orchestrator.scheduler.trigger_step("PRE_INPUT")
        time.sleep(1.5)

        print("  -> Tapping 'Place Order' button. Processing payment tokenization...")
        orchestrator.scheduler.trigger_step("MID_TRANSACTION")
        time.sleep(2.0)

        print("  -> Awaiting payment gateway webhook acknowledgment...")
        orchestrator.scheduler.trigger_step("ASYNC_WAIT")
        time.sleep(1.5)

        # Step 4: Detect and attribute simulated failure
        print("\n[Step 4] Correlating observed non-crash defect with injected stressors:")
        detected_defects = [
            {
                "id": "THEMIS_BUG_42",
                "type": "PAYMENT_GATEWAY_TIMEOUT",
                "description": "PaymentGatewayService: Read timed out during token verification handshake.",
                "component": "CheckoutActivity.OrderPaymentFragment",
                "epoch_ms": int(time.time() * 1000) - 1500
            }
        ]
        attribution = orchestrator.correlate_failures(detected_defects)
        for a in attribution["attributions"]:
            print(f"  * Failure ID: {a['failure_id']}")
            print(f"    Attributed Trigger: {a['primary_trigger']} ({a['confidence']*100:.1f}% confidence)")
            print(f"    Root Cause: {a['root_cause_explanation']}")
            print(f"    Mitigation: {a['recommended_mitigation']}")

    finally:
        print("\n[Step 5] Reverting environment back to baseline nominal state...")
        orchestrator.reset_all()
        print("\n[+] Themis benchmark test run complete.")

if __name__ == "__main__":
    run_themis_benchmark_test()
