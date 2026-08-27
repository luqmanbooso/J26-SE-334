from core.adb_client import ADBClient
from core.event_logger import EventLogger

class DeviceStressor:
    """Injects device-level constraints: battery status, power drain, and thermal levels."""

    def __init__(self, adb: ADBClient, logger: EventLogger):
        self.adb = adb
        self.logger = logger

    def set_battery(self, level: int = 5, unplugged: bool = True) -> None:
        """Forces battery percentage and unplugged status."""
        if unplugged:
            self.adb.run_shell("dumpsys battery unplug")
        self.adb.run_shell(f"dumpsys battery set level {level}")
        self.logger.record("DEVICE_POWER", "BATTERY_PRESSURE", {"level": level, "unplugged": unplugged})

    def simulate_thermal_throttling(self, temp_celsius: float = 48.0) -> None:
        """Sets simulated battery temperature (value in tenths of a degree Celsius)."""
        raw_temp = int(temp_celsius * 10)
        self.adb.run_shell(f"dumpsys battery set temp {raw_temp}")
        self.logger.record("DEVICE_THERMAL", "THERMAL_THROTTLE", {"temperature_c": temp_celsius})

    def reset(self) -> None:
        """Restores hardware battery and thermal state."""
        self.adb.run_shell("dumpsys battery reset")
        self.logger.record("DEVICE_POWER", "RESET_DEFAULT", {})
