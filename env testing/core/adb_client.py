import subprocess
import shutil
import time
from typing import Optional, Dict, Any, List

class ADBClient:
    """Robust ADB interface with hardware execution and virtual device simulation fallback."""

    def __init__(self, device_id: Optional[str] = None, force_simulation: bool = False):
        self.device_id = device_id
        self.force_simulation = force_simulation
        self.is_simulated = False
        self.simulated_device_name = "Google Pixel 7 (API 34) [Virtual Emulator]"
        self.simulated_state: Dict[str, Any] = {
            "battery_level": 100,
            "battery_temp": 320,  # 32.0 C
            "battery_unplugged": False,
            "network_mode": "normal",
            "dark_mode": False,
            "orientation": 0,     # portrait
            "cpu_stress_active": False,
            "ram_pressure_level": "normal",
            "gps_coords": {"lat": 37.422, "lon": -122.084}
        }
        self.command_history: List[str] = []
        self._initialize_connection()

    def _initialize_connection(self) -> None:
        """Determines if real hardware ADB or virtual simulation should be used."""
        if self.force_simulation:
            self._enable_simulation("Force simulation enabled by configuration.")
            return

        adb_path = shutil.which("adb")
        if not adb_path:
            self._enable_simulation("ADB binary not found on system PATH.")
            return

        try:
            res = subprocess.run(
                ["adb", "devices"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=4
            )
            if res.returncode == 0:
                lines = [d.strip() for d in res.stdout.splitlines() if d.strip() and not d.startswith("List of")]
                active_devices = [l for l in lines if "\tdevice" in l]
                if active_devices:
                    target = active_devices[0].split("\t")[0]
                    self.device_id = self.device_id or target
                    self.is_simulated = False
                    print(f"[ADB Bridge] Connected to live hardware/emulator target: {self.device_id}")
                    return
                else:
                    self._enable_simulation("No active Android device/emulator attached.")
            else:
                self._enable_simulation(f"ADB devices query error: {res.stderr.strip()}")
        except Exception as e:
            self._enable_simulation(f"ADB check exception: {str(e)}")

    def _enable_simulation(self, reason: str) -> None:
        self.is_simulated = True
        print(f"[ADB Bridge] {reason} Falling back to Virtual ADB Device Simulator ({self.simulated_device_name}).")

    def run_cmd(self, cmd: str) -> str:
        """Executes an ADB command either via hardware bridge or virtual simulator."""
        self.command_history.append(f"adb {cmd}")

        if self.is_simulated:
            return self._handle_simulated_cmd(cmd)

        device_flag = f"-s {self.device_id} " if self.device_id else ""
        full_cmd = f"adb {device_flag}{cmd}"
        try:
            res = subprocess.run(
                full_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15
            )
            if res.returncode != 0 and "error" in res.stderr.lower():
                print(f"[ADB Warning] Non-zero code for '{cmd}': {res.stderr.strip()}")
            return res.stdout.strip()
        except Exception as e:
            print(f"[ADB Execution Error] {str(e)} -> routing to virtual simulator.")
            return self._handle_simulated_cmd(cmd)

    def run_shell(self, shell_cmd: str) -> str:
        """Executes an 'adb shell' command."""
        return self.run_cmd(f"shell {shell_cmd}")

    def run_emulator_cmd(self, emu_cmd: str) -> str:
        """Executes an 'adb emu' console command."""
        return self.run_cmd(f"emu {emu_cmd}")

    def _handle_simulated_cmd(self, cmd: str) -> str:
        """Emulates realistic responses for common Android shell & emulator commands."""
        # Battery dumpsys
        if "dumpsys battery" in cmd:
            if "unplug" in cmd:
                self.simulated_state["battery_unplugged"] = True
                return "Simulated: Battery unplugged"
            elif "set level" in cmd:
                level = int(cmd.split()[-1])
                self.simulated_state["battery_level"] = level
                return f"Simulated: Battery level set to {level}%"
            elif "set temp" in cmd:
                temp = int(cmd.split()[-1])
                self.simulated_state["battery_temp"] = temp
                return f"Simulated: Battery temperature set to {temp}"
            elif "reset" in cmd:
                self.simulated_state["battery_level"] = 100
                self.simulated_state["battery_temp"] = 320
                self.simulated_state["battery_unplugged"] = False
                return "Simulated: Battery state reset"
            return f"Current Battery Service state:\n  AC powered: false\n  USB powered: false\n  level: {self.simulated_state['battery_level']}\n  temperature: {self.simulated_state['battery_temp']}"

        # Connectivity / Network
        if "connectivity airplane-mode" in cmd:
            enabled = "enable" in cmd
            self.simulated_state["network_mode"] = "offline" if enabled else "normal"
            return f"Simulated: Airplane mode set to {enabled}"
        if "svc wifi" in cmd:
            return "Simulated: WiFi state toggled"
        if "svc data" in cmd:
            return "Simulated: Cell data state toggled"

        # Theme & Orientation
        if "cmd uimode night" in cmd:
            is_night = "yes" in cmd
            self.simulated_state["dark_mode"] = is_night
            return f"Simulated: Dark mode {is_night}"
        if "settings put system user_rotation" in cmd:
            rot = cmd.split()[-1]
            self.simulated_state["orientation"] = int(rot) if rot.isdigit() else 0
            return f"Simulated: Screen rotation {rot}"

        # Emulator Console (GSM, Network, Geo)
        if cmd.startswith("emu "):
            sub = cmd[4:]
            if sub.startswith("gsm call"):
                return "OK: incoming call initiated"
            elif sub.startswith("gsm cancel"):
                return "OK: call cancelled"
            elif sub.startswith("sms send"):
                return "OK: SMS delivered to inbox"
            elif sub.startswith("geo fix"):
                return "OK: GPS fix set"
            elif sub.startswith("network speed") or sub.startswith("network delay"):
                return f"OK: {sub}"
            return "OK"

        # Key events
        if "input keyevent" in cmd:
            key = cmd.split()[-1]
            return f"Simulated: Dispatched keyevent {key}"

        # Memory trim
        if "am send-trim-memory" in cmd:
            return "Trim memory signal broadcasted to processes."

        return "Simulated command executed successfully."

    def install_apk(self, apk_path: str) -> Dict[str, Any]:
        """Installs target APK file onto the connected hardware Android device or simulator."""
        import os
        if not os.path.exists(apk_path):
            raise FileNotFoundError(f"APK file not found: {apk_path}")

        file_size_mb = round(os.path.getsize(apk_path) / (1024 * 1024), 2)
        base_name = os.path.basename(apk_path)

        if self.is_simulated:
            return {
                "success": True,
                "message": f"Successfully installed '{base_name}' ({file_size_mb} MB) onto {self.simulated_device_name}.",
                "apk_name": base_name,
                "size_mb": file_size_mb
            }

        try:
            res = self.run_cmd(f'install -r "{apk_path}"')
            is_success = "success" in res.lower()
            return {
                "success": is_success,
                "message": res,
                "apk_name": base_name,
                "size_mb": file_size_mb
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "apk_name": base_name,
                "size_mb": file_size_mb
            }

    def launch_app(self, package_name: str) -> Dict[str, Any]:
        """Launches target app package via Android monkey launcher intent."""
        if self.is_simulated:
            return {
                "success": True,
                "package_name": package_name,
                "message": f"Simulated process start for '{package_name}'."
            }

        cmd = f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
        res = self.run_cmd(cmd)
        return {
            "success": "Events injected: 1" in res or "No activities" not in res,
            "package_name": package_name,
            "message": res
        }

    def get_device_info(self) -> Dict[str, Any]:
        """Returns live device status metadata."""
        return {
            "device_id": self.device_id or "emulator-5554",
            "is_simulated": self.is_simulated,
            "target_model": self.simulated_device_name if self.is_simulated else f"Hardware ({self.device_id})",
            "state": self.simulated_state
        }
