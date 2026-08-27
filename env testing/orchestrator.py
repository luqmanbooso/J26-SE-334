from core.adb_client import ADBClient
from core.event_logger import EventLogger
from stressors.network_stressor import NetworkStressor
from stressors.device_stressor import DeviceStressor
from stressors.interruption_stressor import InterruptionStressor
from stressors.context_stressor import ContextStressor

class PerturbationOrchestrator:
    """Coordinates and schedules multi-factor environmental stress."""

    def __init__(self, log_path: str = "perturbation_event_log.json"):
        self.adb = ADBClient()
        self.logger = EventLogger(log_path)

        self.network = NetworkStressor(self.adb, self.logger)
        self.device = DeviceStressor(self.adb, self.logger)
        self.interruption = InterruptionStressor(self.adb, self.logger)
        self.context = ContextStressor(self.adb, self.logger)

    def reset_all(self) -> None:
        """Restores emulator environment back to standard state."""
        print("\n[+] Resetting all emulator environmental conditions to baseline...")
        self.device.reset()
        self.context.reset()
        self.network.set_mode("normal")
        self.logger.record("SYSTEM", "ENVIRONMENT_FULL_RESET", {})
        self.logger.save()
