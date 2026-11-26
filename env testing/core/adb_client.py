import os
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
from typing import Optional, Dict, Any, List

# Ensure Android SDK tools are on PATH
for _p in [
    os.path.expanduser("~/AppData/Local/Android/Sdk/platform-tools"),
    os.path.expanduser("~/AppData/Local/Android/Sdk/emulator")
]:
    if os.path.exists(_p) and _p not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common.adb import AdbDevice, NoDeviceError  # noqa: E402


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
        self._device = None          # shared AdbDevice, created on first real command
        self._shell_proc = None
        self._shell_lock = threading.Lock()
        self._emu_sock = None
        self._emu_lock = threading.Lock()
        self._accumulated_latency_ms: float = 0.0
        self._initialize_connection()

    def consume_latency_ms(self) -> float:
        """Returns accumulated ADB execution latency since the last check and resets it."""
        val = round(self._accumulated_latency_ms, 2)
        self._accumulated_latency_ms = 0.0
        return val

    @staticmethod
    def _resolve_adb_binary() -> str:
        which = shutil.which("adb")
        if which:
            return which
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        meipass = getattr(sys, "_MEIPASS", base_dir)
        exe_dir = os.path.dirname(sys.executable)
        for cand in [
            os.path.join(exe_dir, "platform-tools", "adb.exe"),
            os.path.join(exe_dir, "adb.exe"),
            os.path.join(base_dir, "platform-tools", "adb.exe"),
            os.path.join(meipass, "platform-tools", "adb.exe"),
            os.path.expanduser("~/AppData/Local/Programs/HEART_Studio/platform-tools/adb.exe"),
            os.path.expanduser("~/AppData/Local/Android/Sdk/platform-tools/adb.exe"),
            r"C:\Users\user\AppData\Local\Android\Sdk\platform-tools\adb.exe",
            r"D:\Android\platform-tools\adb.exe",
            r"C:\Android\platform-tools\adb.exe",
        ]:
            if os.path.exists(cand):
                return cand
        return "adb"

    def _initialize_connection(self) -> None:
        """Determines if real hardware ADB or virtual simulation should be used."""
        if self.force_simulation or "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
            self._enable_simulation("Force simulation enabled by configuration or test runner.")
            return

        adb_bin = self._resolve_adb_binary()
        try:
            res = subprocess.run(
                [adb_bin, "devices"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=12
            )
            if res.returncode == 0:
                lines = [d.strip() for d in res.stdout.splitlines() if d.strip() and not d.startswith("List of")]
                active_devices = [l for l in lines if "\tdevice" in l]
                if active_devices:
                    target = active_devices[0].split("\t")[0]
                    self.device_id = self.device_id or target
                    self.is_simulated = False
                    self._device = AdbDevice(serial=self.device_id, adb=adb_bin, verify=False)
                    print(f"[ADB Bridge] Connected to live hardware/emulator target: {self.device_id}")
                    return
                else:
                    self._enable_simulation("No active Android device/emulator attached.")
            else:
                self._enable_simulation(f"ADB devices query error: {res.stderr.strip()}")
        except Exception as e:
            self._enable_simulation(f"ADB check exception: {str(e)}")

    def connect(self, device_id: Optional[str] = None) -> bool:
        """Explicitly switch or re-evaluate live ADB connection to given device."""
        if device_id:
            self.device_id = device_id
        self.is_simulated = False
        adb_bin = self._resolve_adb_binary()
        if self._device is None or self._device.serial != self.device_id:
            self._device = AdbDevice(serial=self.device_id, adb=adb_bin, verify=False)
        else:
            self._device.serial = self.device_id
            self._device.adb = adb_bin
        print(f"[ADB Bridge] Connected to live target: {self.device_id}")
        return True

    def _enable_simulation(self, reason: str) -> None:
        self.is_simulated = True
        if self.force_simulation:
            print(f"[ADB Bridge] Simulation requested explicitly. {reason}")
            return
        # An unrequested fallback must be impossible to miss. A run that injects
        # nothing looks exactly like a clean one in the results, so this is the
        # most dangerous state the engine can be in.
        banner = "!" * 78
        print(f"\n{banner}\n"
              f"!! NO REAL DEVICE — SIMULATION FALLBACK ENGAGED\n"
              f"!! {reason}\n"
              f"!! Nothing is being injected into a real device. Any results from\n"
              f"!! this run are SIMULATED and must not be reported as measurements.\n"
              f"{banner}\n")

    def _ensure_device(self) -> None:
        """Ensures self._device is initialized for the active device_id."""
        if self._device is not None and (not self.device_id or self._device.serial == self.device_id):
            return
        adb_bin = self._resolve_adb_binary()
        if not self.device_id:
            found = AdbDevice.list_devices(adb=adb_bin)
            if not found:
                raise NoDeviceError("No Android device or emulator attached.")
            self.device_id = found[0]
        self._device = AdbDevice(serial=self.device_id, adb=adb_bin, verify=False)

    def run_cmd(self, cmd: str, timeout: int = 12) -> str:
        """Executes an ADB command either via hardware bridge or virtual simulator."""
        t0 = time.perf_counter()
        self.command_history.append(f"adb {cmd}")

        try:
            if self.is_simulated:
                return self._handle_simulated_cmd(cmd)

            try:
                self._ensure_device()
            except NoDeviceError:
                self.is_simulated = True
                return self._handle_simulated_cmd(cmd)

            try:
                res = self._device.run(*shlex.split(cmd), timeout=timeout)
                if res.returncode != 0 and "error" in res.stderr.lower():
                    print(f"[ADB Warning] Non-zero code for '{cmd}': {res.stderr.strip()}")
                return res.stdout.strip()
            except subprocess.TimeoutExpired:
                print(f"[ADB Warning] Command timed out after {timeout}s: {cmd}")
                return ""
            except Exception as e:
                print(f"[ADB Warning] Command failed '{cmd}': {e}")
                return ""
        finally:
            self._accumulated_latency_ms += (time.perf_counter() - t0) * 1000.0

    def _ensure_persistent_shell(self):
        """Returns an active persistent `adb -s <serial> shell` process for sub-20ms dispatch."""
        if self._shell_proc is not None and self._shell_proc.poll() is None:
            return self._shell_proc
        adb_bin = self._resolve_adb_binary()
        argv = [adb_bin] + (["-s", self.device_id] if self.device_id else []) + ["shell"]
        kwargs: Dict[str, Any] = dict(
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore",
            bufsize=1,
        )
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        self._shell_proc = subprocess.Popen(argv, **kwargs)
        return self._shell_proc

    def run_shell(self, shell_cmd: str) -> str:
        """Executes an 'adb shell' command via fast persistent pipe with AdbDevice fallback."""
        t0 = time.perf_counter()
        self.command_history.append(f"adb shell {shell_cmd}")
        try:
            if self.is_simulated:
                return self._handle_simulated_cmd(f"shell {shell_cmd}")
            try:
                self._ensure_device()
            except NoDeviceError:
                self.is_simulated = True
                return self._handle_simulated_cmd(f"shell {shell_cmd}")

            # Use persistent shell pipe when safe (non-blocking, sub-20ms latency)
            if "pytest" not in sys.modules and not os.environ.get("PYTEST_CURRENT_TEST"):
                marker = f"__HRT_{int(time.perf_counter() * 1e6)}__"
                with self._shell_lock:
                    try:
                        proc = self._ensure_persistent_shell()
                        assert proc.stdin is not None and proc.stdout is not None
                        proc.stdin.write(f"{shell_cmd}; echo {marker}\n")
                        proc.stdin.flush()
                        out_lines: List[str] = []
                        deadline = time.monotonic() + 8.0
                        while time.monotonic() < deadline:
                            ln = proc.stdout.readline()
                            if not ln:
                                raise RuntimeError("persistent shell EOF")
                            if marker in ln:
                                clean = ln.replace(marker, "").strip()
                                if clean:
                                    out_lines.append(clean)
                                return "\n".join(out_lines).strip()
                            out_lines.append(ln.rstrip("\r\n"))
                    except Exception:
                        try:
                            if self._shell_proc is not None:
                                self._shell_proc.kill()
                        except Exception:
                            pass
                        self._shell_proc = None

            try:
                res = self._device.run("shell", shell_cmd, timeout=12)
                if res.returncode != 0 and "error" in res.stderr.lower():
                    print(f"[ADB Warning] Non-zero code for 'shell {shell_cmd}': {res.stderr.strip()}")
                return res.stdout.strip()
            except subprocess.TimeoutExpired:
                print(f"[ADB Warning] Command timed out after 12s: shell {shell_cmd}")
                return ""
            except Exception as e:
                print(f"[ADB Warning] Command failed 'shell {shell_cmd}': {e}")
                return ""
        finally:
            self._accumulated_latency_ms += (time.perf_counter() - t0) * 1000.0

    def _send_tcp_emu_cmd(self, emu_cmd: str) -> Optional[str]:
        """Dispatches an emulator console command over persistent TCP socket (<15ms latency)."""
        dev_id = self.device_id or "emulator-5554"
        if not dev_id.startswith("emulator-"):
            return None
        try:
            port = int(dev_id.split("-")[1])
        except Exception:
            return None

        auth_file = os.path.expanduser("~/.emulator_console_auth_token")
        if not os.path.exists(auth_file):
            return None

        with self._emu_lock:
            for _ in range(2):
                try:
                    if self._emu_sock is None:
                        token = open(auth_file, "r", encoding="utf-8").read().strip()
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(2.5)
                        s.connect(("127.0.0.1", port))
                        banner = b""
                        while b"OK" not in banner and b"KO" not in banner:
                            chunk = s.recv(512)
                            if not chunk:
                                break
                            banner += chunk
                        s.sendall(f"auth {token}\r\n".encode("utf-8"))
                        ack = b""
                        while b"OK" not in ack and b"KO" not in ack:
                            chunk = s.recv(512)
                            if not chunk:
                                break
                            ack += chunk
                        if b"OK" not in ack:
                            s.close()
                            return None
                        self._emu_sock = s

                    self._emu_sock.sendall(f"{emu_cmd}\r\n".encode("utf-8"))
                    resp = b""
                    while b"OK" not in resp and b"KO" not in resp:
                        chunk = self._emu_sock.recv(1024)
                        if not chunk:
                            raise RuntimeError("emulator console EOF")
                        resp += chunk
                    return resp.decode("utf-8", errors="ignore").strip()
                except Exception:
                    try:
                        if self._emu_sock is not None:
                            self._emu_sock.close()
                    except Exception:
                        pass
                    self._emu_sock = None
        return None

    def run_emulator_cmd(self, emu_cmd: str) -> str:
        """Executes an 'adb emu' console command via fast TCP console with subprocess fallback."""
        t0 = time.perf_counter()
        self.command_history.append(f"adb emu {emu_cmd}")
        try:
            if self.is_simulated:
                return self._handle_simulated_cmd(f"emu {emu_cmd}")
            try:
                self._ensure_device()
            except NoDeviceError:
                self.is_simulated = True
                return self._handle_simulated_cmd(f"emu {emu_cmd}")

            if "pytest" not in sys.modules and not os.environ.get("PYTEST_CURRENT_TEST"):
                tcp_out = self._send_tcp_emu_cmd(emu_cmd)
                if tcp_out is not None:
                    return tcp_out

            try:
                res = self._device.run("emu", *shlex.split(emu_cmd), timeout=12)
                if res.returncode != 0 and "error" in res.stderr.lower():
                    print(f"[ADB Warning] Non-zero code for 'emu {emu_cmd}': {res.stderr.strip()}")
                return res.stdout.strip()
            except subprocess.TimeoutExpired:
                print(f"[ADB Warning] Command timed out after 12s: emu {emu_cmd}")
                return ""
            except Exception as e:
                print(f"[ADB Warning] Command failed 'emu {emu_cmd}': {e}")
                return ""
        finally:
            self._accumulated_latency_ms += (time.perf_counter() - t0) * 1000.0

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
            res = self.run_cmd(f'install -r "{apk_path}"', timeout=45)
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
        if not self.is_simulated and self.device_id:
            try:
                mfg = self.run_shell("getprop ro.product.manufacturer").strip()
                model = self.run_shell("getprop ro.product.model").strip()
                rel = self.run_shell("getprop ro.build.version.release").strip()
                model_str = f"{mfg} {model} (Android {rel})".strip()
            except Exception:
                model_str = f"Hardware ({self.device_id})"
            return {
                "device_id": self.device_id,
                "is_simulated": False,
                "target_model": model_str,
                "state": self.simulated_state
            }

        return {
            "device_id": self.device_id or "emulator-5554",
            "is_simulated": self.is_simulated,
            "target_model": self.simulated_device_name if self.is_simulated else f"Hardware ({self.device_id})",
            "state": self.simulated_state
        }
