import subprocess
from typing import Optional

class ADBClient:
    """Low-level wrapper for Android Debug Bridge and Emulator commands."""

    def __init__(self, device_id: Optional[str] = None):
        self.device_id = device_id
        self.verify_connection()

    def run_cmd(self, cmd: str) -> str:
        """Executes an ADB command and returns standard output."""
        device_flag = f"-s {self.device_id} " if self.device_id else ""
        full_cmd = f"adb {device_flag}{cmd}"
        res = subprocess.run(
            full_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode != 0 and "error" in res.stderr.lower():
            raise RuntimeError(f"ADB execution failed: {res.stderr.strip()}")
        return res.stdout.strip()

    def run_shell(self, shell_cmd: str) -> str:
        """Executes an 'adb shell' command."""
        return self.run_cmd(f"shell {shell_cmd}")

    def run_emulator_cmd(self, emu_cmd: str) -> str:
        """Executes an 'adb emu' console command."""
        return self.run_cmd(f"emu {emu_cmd}")

    def verify_connection(self) -> None:
        """Verifies that at least one emulator/device is connected."""
        devices = self.run_cmd("devices")
        lines = [d for d in devices.splitlines() if d and not d.startswith("List of")]
        if not lines:
            raise ConnectionError("No running Android emulator/device detected via ADB.")
        print(f"[ADB Bridge] Connected target: {lines[0]}")
