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
            # On real Android shell: launch background CPU worker
            worker_cmd = "sh -c 'for i in 1 2 3; do (while true; do :; done &); done; echo PID:$!'"
            output = self.adb.run_shell(worker_cmd)
            for line in output.splitlines():
                if "PID:" in line:
                    pid = line.split("PID:")[-1].strip()
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

        # Broadcast Android trim memory intent
        self.adb.run_shell(f"am send-trim-memory {target} {trim_level}")
        self.logger.record("SYSTEM_RAM", "LMK_MEMORY_PRESSURE", {
            "ram_pct": pressure_pct,
            "trim_level": trim_level,
            "target_package": target
        })

    def inject_disk_io_bottleneck(self, duration_mb: int = 30) -> None:
        """Induces disk I/O saturation by writing unbuffered blocks to device tmpfs."""
        cmd = f"dd if=/dev/zero of={self.io_stress_file} bs=1M count={duration_mb} conv=fsync"
        self.adb.run_shell(cmd)
        self.logger.record("SYSTEM_IO", "DISK_IO_BOTTLENECK", {"bytes_mb": duration_mb})

    def set_battery(self, level: int = 5, unplugged: bool = True) -> None:
        """Forces simulated battery level and charging state."""
        self.current_state["battery_level"] = level
        self.current_state["battery_unplugged"] = unplugged

        if unplugged:
            self.adb.run_shell("dumpsys battery unplug")
        self.adb.run_shell(f"dumpsys battery set level {level}")
        self.logger.record("SYSTEM_POWER", "BATTERY_PRESSURE", {"level": level, "unplugged": unplugged})

    def set_thermal_state(self, state: str = "Warn") -> None:
        """Triggers thermal throttling profiles: 'Normal' (35°C), 'Warn' (55°C), 'Critical' (80°C)."""
        temp_map = {
            "Normal": 35.0,
            "Warn": 55.0,
            "Critical": 80.0
        }
        temp_c = temp_map.get(state, 55.0)
        raw_temp = int(temp_c * 10)

        self.current_state["thermal_state"] = state
        self.adb.run_shell(f"dumpsys battery set temp {raw_temp}")
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

    def reset(self) -> None:
        """Alias for revert() for backwards compatibility."""
        self.revert()
