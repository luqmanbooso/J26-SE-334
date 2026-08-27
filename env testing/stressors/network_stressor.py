from core.adb_client import ADBClient
from core.event_logger import EventLogger

class NetworkStressor:
    """Controls network conditions: WiFi, Cellular, Airplane mode, and Handovers."""

    def __init__(self, adb: ADBClient, logger: EventLogger):
        self.adb = adb
        self.logger = logger

    def set_mode(self, mode: str) -> None:
        """Modes: 'offline', 'wifi_only', 'data_only', 'normal'"""
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

    def simulate_handover(self, from_mode: str = "wifi_only", to_mode: str = "data_only") -> None:
        """Simulates network handover (e.g., dropping WiFi mid-transaction)."""
        self.set_mode(from_mode)
        self.set_mode(to_mode)
        self.logger.record("NETWORK", "HANDOVER_PERMUTATION", {"from": from_mode, "to": to_mode})
