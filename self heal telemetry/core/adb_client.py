import subprocess
import os
import time
import re

class ADBClient:
    """ADB bridge for live screen capture, hierarchy dumping, and event dispatch."""
    def __init__(self):
        self.verify_connection()

    def run_cmd(self, cmd: str) -> str:
        full_cmd = f"adb {cmd}"
        res = subprocess.run(full_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res.stdout.strip()

    def wake_and_unlock(self):
        self.run_cmd("shell input keyevent KEYCODE_WAKEUP")
        self.run_cmd("shell wm dismiss-keyguard")

    def dump_hierarchy(self, output_path: str = "window_dump.xml") -> str:
        self.wake_and_unlock()

        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass

        # Execute dump to standard Android sdcard path
        remote_file = "/sdcard/window_dump.xml"
        out = self.run_cmd(f"shell uiautomator dump {remote_file}")
        
        # Check if Android outputted a specific destination
        if "dumped to" in out.lower():
            match = re.search(r"dumped to:?\s*([^\s]+)", out, re.IGNORECASE)
            if match:
                remote_file = match.group(1).strip()
        elif "error" in out.lower() or not out:
            # Fallback attempt with default arguments
            out = self.run_cmd("shell uiautomator dump")
            match = re.search(r"dumped to:?\s*([^\s]+)", out, re.IGNORECASE)
            if match:
                remote_file = match.group(1).strip()

        time.sleep(0.5)

        # Pull dumped XML file to local workspace
        self.run_cmd(f"pull {remote_file} {output_path}")

        # Fallback: Stream directly via cat if adb pull returned 0 bytes
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raw_xml = self.run_cmd(f"shell cat {remote_file}")
            if "<hierarchy" in raw_xml or "<?xml" in raw_xml:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(raw_xml)

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise FileNotFoundError(f"[-] UI dump failed. Make sure an app is open and visible on the emulator.")

        print(f"[+] Successfully captured UI hierarchy: {output_path} ({os.path.getsize(output_path)} bytes)")
        return output_path

    def tap(self, x: int, y: int):
        self.run_cmd(f"shell input tap {x} {y}")

    def verify_connection(self):
        devices = self.run_cmd("devices")
        lines = [d for d in devices.splitlines() if d and not d.startswith("List of")]
        if not lines:
            raise ConnectionError("[-] No running Android emulator found via ADB.")
        print(f"[ADB Bridge] Connected target: {lines[0]}")
