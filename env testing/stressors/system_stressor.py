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
            try:
                core_out = self.adb.run_shell("nproc").strip()
                cores = int(core_out) if core_out.isdigit() and int(core_out) > 0 else 4
            except Exception:
                cores = 4
            # Keep at least 2 cores free for system_server, surfaceflinger & adbd to prevent watchdog freezes
            num_workers = max(1, min(max(1, cores - 2), max(1, round(cores * (target_pct / 100.0) / 2))))
            # Run nice 19 with 60s hard TTL so workers can NEVER become runaway zombies
            worker_cmd = f"sh -c 'for i in $(seq 1 {num_workers}); do nice -n 19 timeout 60 sh -c \"while true; do :; done\" >/dev/null 2>&1 & done'"
            self.adb.run_shell(worker_cmd)
        else:
            self.adb.simulated_state["cpu_stress_active"] = True

        # Host-assisted load emulation thread (yields GIL cleanly; wait() wakes immediately on stop)
        self._stop_cpu_flag.clear()
        stop_ev = self._stop_cpu_flag
        def _cpu_burner():
            active_ratio = min(0.7, target_pct / 100.0)
            cycle = 0.05
            sleep_sec = cycle * (1.0 - active_ratio) + 0.005
            while not stop_ev.is_set():
                t_end = time.time() + (cycle * active_ratio)
                while time.time() < t_end and not stop_ev.is_set():
                    _ = 3.14159 * 2.71828
                if stop_ev.wait(timeout=sleep_sec):
                    break

        t = threading.Thread(target=_cpu_burner, daemon=True)
        t.start()
        self._cpu_worker_threads.append(t)

        self.logger.record("SYSTEM_CPU", "CPU_LOAD_INJECTED", {"target_cpu_pct": target_pct})

    def revert_cpu(self) -> None:
        """Terminates active CPU worker routines safely."""
        self._stop_cpu_flag.set()
        for t in self._cpu_worker_threads:
            if t.is_alive():
                t.join(timeout=0.5)
        self._cpu_worker_threads.clear()

        if self.cpu_stress_pids:
            for pid in self.cpu_stress_pids:
                try:
                    self.adb.run_shell(f"kill -9 {pid}")
                except Exception:
                    pass
            self.cpu_stress_pids.clear()

        if not self.adb.is_simulated:
            try:
                self.adb.run_shell("pkill -9 -f 'while true' 2>/dev/null; pkill -9 yes 2>/dev/null; killall -9 yes 2>/dev/null; true")
            except Exception:
                pass

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
            is_emu = bool(self.adb.device_id and str(self.adb.device_id).startswith("emulator-"))
            safe_level = max(3, level) if not is_emu else max(2, level)
            if unplugged:
                self.adb.run_shell(f"dumpsys battery unplug; dumpsys battery set status 3; dumpsys battery set level {safe_level}")
            else:
                self.adb.run_shell(f"dumpsys battery reset; dumpsys battery set level {safe_level}")
        else:
            self.adb.simulated_state["battery_level"] = level
            self.adb.simulated_state["battery_unplugged"] = unplugged

        self.logger.record("SYSTEM_POWER", "BATTERY_PRESSURE", {"level": level, "unplugged": unplugged})

    def set_thermal_state(self, state: Any = "Warn") -> None:
        """Triggers thermal throttling profiles: 'Normal' (35°C), 'Warn' (55°C), 'Critical' (80°C)."""
        temp_map = {
            "Nominal": 30.0,
            "Normal": 32.0,
            "Fair": 45.0,
            "Moderate": 50.0,
            "Warn": 55.0,
            "Serious": 65.0,
            "Severe": 65.0,
            "Critical": 80.0
        }
        thermal_code_map = {
            "Nominal": 0,
            "Normal": 0,
            "Fair": 1,
            "Moderate": 2,
            "Warn": 2,
            "Serious": 3,
            "Severe": 3,
            "Critical": 4
        }
        int_to_str = {0: "Normal", 1: "Fair", 2: "Moderate", 3: "Serious", 4: "Critical"}
        if isinstance(state, (int, float)):
            state = int_to_str.get(int(state), "Warn")

        temp_c = temp_map.get(str(state), 55.0)
        raw_temp = int(temp_c * 10)
        th_code = thermal_code_map.get(str(state), 2)

        self.current_state["thermal_state"] = state
        if not self.adb.is_simulated:
            # Keep battery temp <= 55.0C on both hardware and API 36 AVDs to avoid OS thermalshutdown poweroff
            safe_temp_c = min(55.0, temp_c)
            extra = "; dumpsys battery set status 3" if str(state) not in ("Nominal", "Normal") else ""
            self.adb.run_shell(f"dumpsys battery set temp {int(safe_temp_c * 10)}; cmd thermalservice override-status {th_code}{extra}")
        else:
            self.adb.simulated_state["battery_temp"] = raw_temp

        self.logger.record("SYSTEM_THERMAL", "THERMAL_THROTTLE_PROFILE", {
            "state": state,
            "simulated_temp_c": temp_c
        })

    def revert(self) -> bool:
        """Restores device hardware to nominal operating conditions."""
        self.cpu_stress_pids.clear()
        self._stop_cpu_flag.set()
        self._cpu_worker_threads.clear()
        if not self.adb.is_simulated:
            self.adb.run_shell(
                f"pkill -9 -f 'while true' 2>/dev/null; pkill -9 yes 2>/dev/null; "
                f"rm -f {self.io_stress_file}; dumpsys battery reset; cmd thermalservice reset; true"
            )
        else:
            self.adb.simulated_state["cpu_stress_active"] = False
            self.adb.simulated_state["battery_level"] = 100
            self.adb.simulated_state["battery_unplugged"] = False
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
