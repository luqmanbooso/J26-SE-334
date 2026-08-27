from core.adb_client import ADBClient
from core.event_logger import EventLogger

class ContextStressor:
    """Controls environment context: display orientation, dark mode, and GPS."""

    def __init__(self, adb: ADBClient, logger: EventLogger):
        self.adb = adb
        self.logger = logger

    def set_orientation(self, mode: str = "portrait") -> None:
        """Modes: 'portrait' (0), 'landscape' (1)"""
        self.adb.run_shell("settings put system accelerometer_rotation 0")
        rot_val = "1" if mode == "landscape" else "0"
        self.adb.run_shell(f"settings put system user_rotation {rot_val}")
        self.logger.record("CONTEXT", "ORIENTATION_CHANGE", {"mode": mode})

    def set_dark_mode(self, enabled: bool = True) -> None:
        val = "yes" if enabled else "no"
        self.adb.run_shell(f"cmd uimode night {val}")
        self.logger.record("CONTEXT", "THEME_CHANGE", {"dark_mode": enabled})

    def set_gps_location(self, latitude: float, longitude: float) -> None:
        self.adb.run_emulator_cmd(f"geo fix {longitude} {latitude}")
        self.logger.record("CONTEXT", "GPS_COORDINATES", {"lat": latitude, "lon": longitude})

    def reset(self) -> None:
        self.adb.run_shell("settings put system user_rotation 0")
        self.adb.run_shell("settings put system accelerometer_rotation 1")
        self.adb.run_shell("cmd uimode night no")
        self.logger.record("CONTEXT", "RESET_DEFAULT", {})
