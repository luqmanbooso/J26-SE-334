import threading
import time
from typing import Optional, Dict, Any, List
from core.base import BaseStressor
from core.adb_client import ADBClient
from core.event_logger import EventLogger

class SystemStressor(BaseStressor):
    """Injects device hardware stress: CPU starvation, RAM/LMK memory pressure, Disk I/O, battery, and thermal throttling."""

    def __init__(self, adb: ADBClient, logger: EventLogger):
        super().__init__(adb, logger, category="DEVICE_SYSTEM")
        self.cpu_stress_pids: List[str] = []
        self._cpu_worker_threads: List[threading.Thread] = []
        self._stop_cpu_flag = threading.Event()
        self.io_stress_file = "/data/local/tmp/heart_io_stress"

    def apply(self, **kwargs) -> bool:
        """Applies compound system stress from parameters."""
        cpu = kwargs.get("cpu_pct")
        ram = kwargs.get("ram_pct")
        thermal = kwargs.get("thermal_state")
        battery = kwargs.get("battery_level")

        if cpu is not None:
            self.set_cpu_load(cpu)
        if ram is not None:
            self.set_ram_pressure(ram, kwargs.get("target_package"))
        if thermal is not None:
            self.set_thermal_state(thermal)
        if battery is not None:
            self.set_battery(battery, unplugged=kwargs.get("unplugged", True))
        return True

    def set_cpu_load(self, target_pct: int = 85, duration_sec: Optional[float] = None) -> None:
        """Induces high CPU load (up to 98%) via parallel background worker routines."""
        self.revert_cpu()
        target_pct = max(10, min(98, target_pct))
        self.current_state["cpu_pct"] = target_pct
        self.is_active = True

        if not self.adb.is_simulated:
            # On real Android shell: launch background CPU worker non-blocking
            worker_cmd = "sh -c 'nohup yes >/dev/null 2>&1 & echo PID:$!'"
            output = self.adb.run_shell(worker_cmd)
            for line in output.splitlines():
                if "PID:" in line:
                    pid = line.split("PID:")[-1].strip()
                    if pid.isdigit():
                        self.cpu_stress_pids.append(pid)
        else:
            self.adb.simulated_state["cpu_stress_active"] = True

        # Host-assisted load emulation thread to ensure host metrics also show stress
        self._stop_cpu_flag.clear()
        def _cpu_burner():
            active_ratio = target_pct / 100.0
            cycle = 0.05
            while not self._stop_cpu_flag.is_set():
                t_end = time.time() + (cycle * active_ratio)
                while time.time() < t_end:
                    _ = 3.14159 * 2.71828
                time.sleep(cycle * (1.0 - active_ratio))

        t = threading.Thread(target=_cpu_burner, daemon=True)
        t.start()
        self._cpu_worker_threads.append(t)

        self.logger.record("SYSTEM_CPU", "CPU_LOAD_INJECTED", {"target_cpu_pct": target_pct})

    def revert_cpu(self) -> None:
        """Terminates active CPU worker routines."""
        self._stop_cpu_flag.set()
        self._cpu_worker_threads.clear()

        if self.cpu_stress_pids:
            for pid in self.cpu_stress_pids:
                self.adb.run_shell(f"kill -9 {pid}")
            self.cpu_stress_pids.clear()

        if not self.adb.is_simulated:
            self.adb.run_shell("killall yes")

        if self.adb.is_simulated:
            self.adb.simulated_state["cpu_stress_active"] = False

        self.current_state.pop("cpu_pct", None)

    def set_ram_pressure(self, pressure_pct: int = 80, target_package: Optional[str] = None) -> None:
        """Simulates Low-Memory Killer (LMK) memory pressure and trim memory broadcasts."""
        self.current_state["ram_pct"] = pressure_pct
        target = target_package or "com.android.settings"

        if pressure_pct >= 85:
            trim_level = "RUNNING_CRITICAL"
        elif pressure_pct >= 60:
            trim_level = "RUNNING_LOW"
        else:
            trim_level = "RUNNING_MODERATE"

        # Broadcast Android trim memory intent non-blocking
        threading.Thread(target=self.adb.run_shell, args=(f"am send-trim-memory {target} {trim_level}",), daemon=True).start()
        self.logger.record("SYSTEM_RAM", "LMK_MEMORY_PRESSURE", {
            "ram_pct": pressure_pct,
            "trim_level": trim_level,
            "target_package": target
        })

    def inject_memory_pressure(self, trim_level: str = "RUNNING_LOW", target_package: Optional[str] = None) -> None:
        """Broadcasts arbitrary Android trim memory intent directly."""
        target = target_package or "com.android.settings"
        clean_level = trim_level if trim_level.startswith("TRIM_MEMORY_") else f"TRIM_MEMORY_{trim_level}"
        threading.Thread(target=self.adb.run_shell, args=(f"am send-trim-memory {target} {clean_level}",), daemon=True).start()
        self.logger.record("SYSTEM_RAM", "LMK_TRIM_BROADCAST", {
            "trim_level": clean_level,
            "target_package": target
        })

    def inject_disk_io_bottleneck(self, duration_mb: int = 30) -> None:
        """Induces disk I/O saturation by writing unbuffered blocks to device tmpfs."""
        cmd = f"dd if=/dev/zero of={self.io_stress_file} bs=1M count={duration_mb} conv=fsync"
        self.adb.run_shell(cmd)
        self.logger.record("SYSTEM_IO", "DISK_IO_BOTTLENECK", {"bytes_mb": duration_mb})

    def set_battery(self, level: int = 5, unplugged: bool = True) -> None:
        """Forces simulated battery level and charging state on live hardware or AVD."""
        self.current_state["battery_level"] = level
        self.current_state["battery_unplugged"] = unplugged

        if not self.adb.is_simulated:
            # Physical vs AVD handling: allow full low-battery testing down to 1-3%
            is_emu = bool(self.adb.device_id and str(self.adb.device_id).startswith("emulator-"))
            safe_level = max(1, level) if is_emu else max(2, level)
            if unplugged:
                self.adb.run_shell("dumpsys battery unplug")
                self.adb.run_shell("dumpsys battery set status 3")
            else:
                self.adb.run_shell("dumpsys battery reset")
            self.adb.run_shell(f"dumpsys battery set level {safe_level}")
        else:
            self.adb.simulated_state["battery_level"] = level
            self.adb.simulated_state["battery_unplugged"] = unplugged

        self.logger.record("SYSTEM_POWER", "BATTERY_PRESSURE", {"level": level, "unplugged": unplugged})

    def set_thermal_state(self, state: Any = "Warn") -> None:
        """Triggers thermal throttling profiles: 'Normal' (35°C), 'Warn' (55°C), 'Critical' (80°C)."""
        temp_map = {
            "Nominal": 32.0,
            "Normal": 35.0,
            "Fair": 45.0,
            "Moderate": 50.0,
            "Warn": 55.0,
            "Serious": 65.0,
            "Severe": 65.0,
            "Critical": 80.0
        }
        int_to_str = {0: "Normal", 1: "Light", 2: "Moderate", 3: "Severe", 4: "Critical"}
        if isinstance(state, (int, float)):
            state = int_to_str.get(int(state), "Warn")

        temp_c = temp_map.get(str(state), 55.0)
        raw_temp = int(temp_c * 10)

        self.current_state["thermal_state"] = state
        if not self.adb.is_simulated:
            is_emu = bool(self.adb.device_id and str(self.adb.device_id).startswith("emulator-"))
            safe_temp_c = temp_c if is_emu else min(55.0, temp_c)
            self.adb.run_shell(f"dumpsys battery set temp {int(safe_temp_c * 10)}")
            self.adb.run_shell("dumpsys battery set status 3")
        else:
            self.adb.simulated_state["battery_temp"] = raw_temp

        self.logger.record("SYSTEM_THERMAL", "THERMAL_THROTTLE_PROFILE", {
            "state": state,
            "simulated_temp_c": temp_c
        })

    def revert(self) -> bool:
        """Restores device hardware to nominal operating conditions."""
        self.revert_cpu()
        self.adb.run_shell(f"rm -f {self.io_stress_file}")
        self.adb.run_shell("dumpsys battery reset")
        self.is_active = False
        self.current_state.clear()
        self.logger.record("SYSTEM_HARDWARE", "SYSTEM_RESET_NOMINAL", {})
        return True

    def reset_battery(self) -> None:
        """Resets battery state to nominal charging baseline."""
        self.adb.run_shell("dumpsys battery reset")
        self.current_state.pop("battery_level", None)
        self.current_state.pop("battery_unplugged", None)
        if self.adb.is_simulated:
            self.adb.simulated_state["battery_level"] = 100
            self.adb.simulated_state["battery_unplugged"] = False
        self.logger.record("SYSTEM_POWER", "BATTERY_RESET", {})

    def reset(self) -> None:
        """Alias for revert() for backwards compatibility."""
        self.revert()
