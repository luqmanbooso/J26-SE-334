import time
from typing import Optional, Dict, Any, List
from core.adb_client import ADBClient
from core.event_logger import EventLogger
from core.scheduler import PerturbationScheduler
from stressors.system_stressor import SystemStressor
from stressors.network_stressor import NetworkStressor
from stressors.interruption_stressor import InterruptionStressor
from stressors.context_stressor import ContextStressor
from attribution_engine import EnvironmentAttributionEngine

class PerturbationOrchestrator:
    """Coordinates multi-factor environmental stressors, dynamic scheduling, and failure attribution."""

    def __init__(self, log_path: str = "perturbation_event_log.json", force_simulation: bool = False):
        self.adb = ADBClient(force_simulation=force_simulation)
        self.logger = EventLogger(log_path)
        self.scheduler = PerturbationScheduler(logger=self.logger)

        self.system = SystemStressor(self.adb, self.logger)
        self.device = self.system  # Backward-compatible alias
        self.network = NetworkStressor(self.adb, self.logger)
        self.interruption = InterruptionStressor(self.adb, self.logger)
        self.context = ContextStressor(self.adb, self.logger)
        self.attribution_engine = EnvironmentAttributionEngine(perturbation_log_path=log_path)

    def apply_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Applies compound stress profile from frontend or test suite config."""
        profile_name = profile.get("name", "Custom Perturbation Profile")
        print(f"\n[+] Applying Perturbation Profile: '{profile_name}'")

        # 1. Hardware Resource Knobs
        if "cpuStress" in profile:
            self.system.set_cpu_load(int(profile["cpuStress"]))
        if "ramStress" in profile:
            self.system.set_ram_pressure(int(profile["ramStress"]))
        if "thermalState" in profile and profile["thermalState"] != "None":
            self.system.set_thermal_state(profile["thermalState"])

        # 2. Network Perturbation Knobs
        if "latency" in profile:
            self.network.inject_latency(int(profile["latency"]))
        if "packetLoss" in profile:
            self.network.inject_packet_loss(int(profile["packetLoss"]))
        if profile.get("dnsFailure"):
            self.network.simulate_dns_failure(True)
        if "networkProfile" in profile:
            net_prof = profile["networkProfile"].lower()
            if "edge" in net_prof or "2g" in net_prof:
                self.network.set_bandwidth_profile("edge")
            elif "cellular dead zone" in net_prof or "offline" in net_prof:
                self.network.set_mode("offline")
            elif "4g" in net_prof:
                self.network.set_bandwidth_profile("lte")

        # 3. Interruption Triggers
        itype = profile.get("interruptionType", "")
        if "Call" in itype:
            self.interruption.trigger_incoming_call("15555215554")
        if "Low Battery" in itype:
            self.system.set_battery(level=3, unplugged=True)
        if "LMK" in itype:
            self.system.set_ram_pressure(95)

        self.logger.record("ORCHESTRATOR", "PROFILE_APPLIED", {
            "profile_name": profile_name,
            "chaos_score": self.calculate_chaos_score(profile)
        })
        return self.get_telemetry_snapshot()

    def calculate_chaos_score(self, profile: Dict[str, Any]) -> int:
        """Calculates aggregate environmental severity index (0 - 100)."""
        cpu = profile.get("cpuStress", 0)
        ram = profile.get("ramStress", 0)
        lat = min(profile.get("latency", 0), 2000)
        return int((cpu * 0.4) + (ram * 0.3) + (lat / 2000 * 30))

    def evaluate_signals(self, signals: Dict[str, float]) -> bool:
        """Adapts perturbation intensity according to runtime telemetry (FPS, Latency)."""
        def _handle_escalation(escalation_type: str):
            if escalation_type == "HARDWARE_ESCALATION":
                self.system.set_cpu_load(95)
            elif escalation_type == "NETWORK_ESCALATION":
                self.network.inject_packet_loss(12)

        return self.scheduler.evaluate_performance_signals(signals, on_escalate=_handle_escalation)

    def get_telemetry_snapshot(self) -> Dict[str, Any]:
        """Gathers real-time performance and environmental telemetry."""
        dev_info = self.adb.get_device_info()
        return {
            "timestamp_ms": int(time.time() * 1000),
            "device": dev_info,
            "system_state": self.system.get_state(),
            "network_state": self.network.get_state(),
            "context_state": self.context.get_state(),
            "interruption_state": self.interruption.get_state(),
            "event_count": len(self.logger.events)
        }

    def correlate_failures(self, failures: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generates failure attribution report from recorded perturbation event stream."""
        report = self.attribution_engine.correlate(failures, self.logger.events)
        self.attribution_engine.export_report(report)
        return report

    def reset_all(self) -> None:
        """Restores device, network, context, and interruption states back to nominal baseline."""
        print("\n[+] Resetting all environmental stressors back to baseline...")
        self.system.revert()
        self.network.revert()
        self.interruption.revert()
        self.context.revert()
        self.scheduler.reset()
        self.logger.record("SYSTEM", "ENVIRONMENT_FULL_RESET", {})
        self.logger.save()
