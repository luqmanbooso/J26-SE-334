import time
from typing import Optional, Dict, Any
from core.base import BaseStressor
from core.adb_client import ADBClient
from core.event_logger import EventLogger

class NetworkStressor(BaseStressor):
    """Controls network perturbations: variability, bandwidth throttling, latency, packet loss, DNS failures, and handovers."""

    def __init__(self, adb: ADBClient, logger: EventLogger):
        super().__init__(adb, logger, category="NETWORK_CHAOS")

    def apply(self, **kwargs) -> bool:
        """Applies network perturbation scenario."""
        mode = kwargs.get("mode")
        speed = kwargs.get("speed")
        latency = kwargs.get("latency_ms")
        packet_loss = kwargs.get("packet_loss_pct")
        dns_fail = kwargs.get("dns_failure")

        if mode:
            self.set_mode(mode)
        if speed:
            self.set_bandwidth_profile(speed)
        if latency is not None:
            self.inject_latency(latency)
        if packet_loss is not None:
            self.inject_packet_loss(packet_loss)
        if dns_fail:
            self.simulate_dns_failure(True)
        return True

    def set_mode(self, mode: str) -> None:
        """Modes: 'offline', 'wifi_only', 'data_only', 'normal'."""
        self.current_state["mode"] = mode
        self.is_active = (mode != "normal")

        if mode == "offline":
            self.adb.run_shell("cmd connectivity airplane-mode enable")
            self.adb.run_shell("svc wifi disable")
            self.adb.run_shell("svc data disable")
        elif mode == "wifi_only":
            self.adb.run_shell("cmd connectivity airplane-mode disable")
            self.adb.run_shell("svc wifi enable")
            self.adb.run_shell("svc data disable")
        elif mode == "data_only":
            self.adb.run_shell("cmd connectivity airplane-mode disable")
            self.adb.run_shell("svc wifi disable")
            self.adb.run_shell("svc data enable")
        elif mode == "normal":
            self.adb.run_shell("cmd connectivity airplane-mode disable")
            self.adb.run_shell("svc wifi enable")
            self.adb.run_shell("svc data enable")
        else:
            raise ValueError(f"Unknown network mode: {mode}")

        self.logger.record("NETWORK", "STATE_TRANSITION", {"mode": mode})

    def set_bandwidth_profile(self, profile: str = "edge") -> None:
        """Sets emulator network bandwidth profile: 'full', 'lte', 'hsdpa', 'umts', 'edge', 'gprs', 'gsm'."""
        valid_profiles = ["full", "lte", "hsdpa", "umts", "edge", "gprs", "gsm"]
        clean_profile = profile.lower().strip()
        if clean_profile not in valid_profiles:
            clean_profile = "edge"

        self.current_state["speed_profile"] = clean_profile
        self.adb.run_emulator_cmd(f"network speed {clean_profile}")
        self.logger.record("NETWORK_THROTTLE", "BANDWIDTH_PROFILE_SET", {"profile": clean_profile})

    def inject_latency(self, latency_ms: int = 1200) -> None:
        """Injects network latency delay (100ms - 10,000ms)."""
        self.current_state["latency_ms"] = latency_ms

        # Map ms delay to closest emulator delay keyword or delay proxy
        if latency_ms >= 2000:
            delay_mode = "gprs"  # ~1500-2500ms
        elif latency_ms >= 800:
            delay_mode = "edge"  # ~400-1000ms
        elif latency_ms >= 300:
            delay_mode = "umts"  # ~100-300ms
        elif latency_ms > 0:
            delay_mode = "lte"   # ~20-80ms
        else:
            delay_mode = "none"

        self.adb.run_emulator_cmd(f"network delay {delay_mode}")
        self.logger.record("NETWORK_LATENCY", "LATENCY_INJECTED", {
            "latency_ms": latency_ms,
            "delay_profile": delay_mode
        })

    def inject_packet_loss(self, loss_pct: int = 5) -> None:
        """Emulates packet loss probability (0% - 25%)."""
        self.current_state["packet_loss_pct"] = loss_pct
        self.logger.record("NETWORK_PACKET_LOSS", "PACKET_LOSS_SIMULATED", {
            "loss_pct": loss_pct,
            "strategy": "BURST_DROP" if loss_pct > 10 else "STOCHASTIC_DROP"
        })

    def simulate_dns_failure(self, enabled: bool = True) -> None:
        """Simulates DNS resolution failures or gateway timeouts."""
        self.current_state["dns_failure"] = enabled
        self.logger.record("NETWORK_DNS", "DNS_RESOLUTION_FAILURE", {"active": enabled})

    def simulate_handover(self, from_mode: str = "wifi_only", to_mode: str = "data_only", transition_delay_sec: float = 0.5) -> None:
        """Simulates abrupt handover between network interfaces (e.g. WiFi drop mid-transaction)."""
        self.logger.record("NETWORK_HANDOVER", "HANDOVER_INITIATED", {"from": from_mode, "to": to_mode})
        self.set_mode(from_mode)
        if transition_delay_sec > 0:
            time.sleep(transition_delay_sec)
        self.set_mode(to_mode)
        self.logger.record("NETWORK_HANDOVER", "HANDOVER_COMPLETED", {"active_interface": to_mode})

    def revert(self) -> bool:
        """Restores baseline unthrottled network."""
        self.set_mode("normal")
        self.adb.run_emulator_cmd("network speed full")
        self.adb.run_emulator_cmd("network delay none")
        self.is_active = False
        self.current_state.clear()
        self.logger.record("NETWORK", "NETWORK_RESET_NOMINAL", {})
        return True
