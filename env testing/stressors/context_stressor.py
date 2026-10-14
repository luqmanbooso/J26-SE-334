from typing import Dict, Any, Optional
from core.base import BaseStressor
from core.adb_client import ADBClient
from core.event_logger import EventLogger

class ContextStressor(BaseStressor):
    """Controls environment context: display orientation, dark mode theme, font scale, and GPS location shifts."""

    def __init__(self, adb: ADBClient, logger: EventLogger):
        super().__init__(adb, logger, category="ENVIRONMENT_CONTEXT")

    def apply(self, **kwargs) -> bool:
        """Applies environment context settings."""
        if "orientation" in kwargs:
            self.set_orientation(kwargs["orientation"])
        if "dark_mode" in kwargs:
            self.set_dark_mode(kwargs["dark_mode"])
        if "font_scale" in kwargs:
            self.set_font_scale(kwargs["font_scale"])
        if "gps" in kwargs:
            lat, lon = kwargs["gps"]
            self.set_gps_location(lat, lon)
        return True

    def set_orientation(self, mode: str = "portrait") -> None:
        """Modes: 'portrait' (0), 'landscape' (1), 'reverse_landscape' (3)."""
        rot_val = "1" if mode == "landscape" else ("3" if mode == "reverse_landscape" else "0")
        self.current_state["orientation"] = mode
        self.adb.run_shell("settings put system accelerometer_rotation 0")
        self.adb.run_shell(f"settings put system user_rotation {rot_val}")
        self.logger.record("CONTEXT_ORIENTATION", "ORIENTATION_CHANGED", {"mode": mode, "rotation_val": rot_val})

    def set_dark_mode(self, enabled: bool = True) -> None:
        """Toggles Android system night mode (Dark Theme)."""
        val = "yes" if enabled else "no"
        self.current_state["dark_mode"] = enabled
        self.adb.run_shell(f"cmd uimode night {val}")
        self.logger.record("CONTEXT_THEME", "DARK_MODE_TOGGLED", {"dark_mode": enabled})

    def set_font_scale(self, scale: float = 1.3) -> None:
        """Sets system accessibility font scale to test dynamic layout collisions and truncation."""
        self.current_state["font_scale"] = scale
        self.adb.run_shell(f"settings put system font_scale {scale}")
        self.logger.record("CONTEXT_DISPLAY", "FONT_SCALE_CHANGED", {"font_scale": scale})

    def set_gps_location(self, latitude: float, longitude: float) -> None:
        """Sets mock GPS coordinates on emulator via geo fix."""
        self.current_state["gps"] = {"lat": latitude, "lon": longitude}
        self.adb.run_emulator_cmd(f"geo fix {longitude} {latitude}")
        self.logger.record("CONTEXT_LOCATION", "GPS_COORDINATES_SHIFTED", {"lat": latitude, "lon": longitude})

    def revert(self) -> bool:
        """Restores context settings back to standard system defaults."""
        self.adb.run_shell("settings put system user_rotation 0")
        self.adb.run_shell("settings put system accelerometer_rotation 1")
        self.adb.run_shell("cmd uimode night no")
        self.adb.run_shell("settings put system font_scale 1.0")
        self.is_active = False
        self.current_state.clear()
        self.logger.record("CONTEXT", "CONTEXT_RESET_DEFAULTS", {})
        return True

    def reset(self) -> None:
        """Alias for revert() for backwards compatibility."""
        self.revert()
