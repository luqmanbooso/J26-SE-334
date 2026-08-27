import os
import re
import time
import subprocess
import xml.etree.ElementTree as ET


class ADBBridge:

    def __init__(self, device_id=None):
        """
        Initializes the ADB Bridge.
        If multiple devices/emulators exist, specify device_id.
        """
        self.device_id = device_id
        self._verify_connection()

    def _build_cmd(self, command_list):
        """Constructs an ADB command with optional device targeting."""
        base = ["adb"]
        if self.device_id:
            base.extend(["-s", self.device_id])
        return base + command_list

    def _verify_connection(self):
        """Checks if ADB is running and a device is detected."""
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                check=True
            )
            lines = [line for line in result.stdout.strip().split("\n")[1:] if line.strip()]
            if not lines:
                raise ConnectionError("No Android devices or emulators detected via ADB.")
            print(f"[ADB Bridge] Connected devices found:\n{result.stdout.strip()}")
        except FileNotFoundError:
            raise EnvironmentError("ADB is not found in system PATH. Ensure Android SDK platform-tools is installed.")

    def dump_ui_hierarchy(self) -> ET.Element:
        """
        Dumps the current screen UI hierarchy to the device, reads the file,
        and isolates the XML hierarchy block to prevent trailing output parse errors.
        """
        # 1. Dump UI hierarchy to device storage
        dump_cmd = self._build_cmd(["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"])
        subprocess.run(dump_cmd, capture_output=True, text=True, check=True)

        # 2. Pull content directly via exec-out to bypass terminal carriage return mutations
        cat_cmd = self._build_cmd(["exec-out", "cat", "/sdcard/window_dump.xml"])
        result = subprocess.run(cat_cmd, capture_output=True, text=True, errors="ignore")
        raw_xml = result.stdout

        # 3. Clean Windows CRLF mutations and isolate the exact <hierarchy> root element
        normalized_xml = raw_xml.replace("\r\r\n", "\n").replace("\r\n", "\n")
        match = re.search(r"(<hierarchy[\s\S]*?</hierarchy>)", normalized_xml)

        if not match:
            # Fallback direct streaming attempt
            stream_cmd = self._build_cmd(["exec-out", "uiautomator", "dump", "/dev/tty"])
            fallback_res = subprocess.run(stream_cmd, capture_output=True, text=True, errors="ignore")
            normalized_xml = fallback_res.stdout.replace("\r\r\n", "\n").replace("\r\n", "\n")
            match = re.search(r"(<hierarchy[\s\S]*?</hierarchy>)", normalized_xml)
            if not match:
                raise ValueError("Failed to extract a valid <hierarchy> XML block from device dump.")

        cleaned_xml = match.group(1).strip()
        return ET.fromstring(cleaned_xml)

    def find_element_by_text(self, text_query: str) -> dict:
        """
        Locates an element by matching exact or partial text / content-desc / resource-id.
        Returns: { 'x': int, 'y': int, 'width': int, 'height': int, 'text': str, 'resource_id': str }
        """
        root = self.dump_ui_hierarchy()

        for node in root.iter("node"):
            node_text = node.get("text", "")
            content_desc = node.get("content-desc", "")
            res_id = node.get("resource-id", "")
            bounds_str = node.get("bounds", "")

            # Match target text, content description, or resource identifier
            if (text_query.lower() in node_text.lower() or 
                text_query.lower() in content_desc.lower() or 
                text_query.lower() in res_id.lower()):
                
                return self._parse_bounds(bounds_str, node_text or content_desc, res_id)

        raise ValueError(f"UI Element matching '{text_query}' not found on the current screen.")

    @staticmethod
    def _parse_bounds(bounds_str: str, text: str, res_id: str) -> dict:
        """
        Parses Android bounds string: '[x1,y1][x2,y2]' -> center (x, y), width, height
        """
        match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
        if not match:
            raise ValueError(f"Invalid bounds format: {bounds_str}")

        x1, y1, x2, y2 = map(int, match.groups())
        width = x2 - x1
        height = y2 - y1
        center_x = x1 + (width // 2)
        center_y = y1 + (height // 2)

        return {
            "x": center_x,
            "y": center_y,
            "width": width,
            "height": height,
            "bounds": (x1, y1, x2, y2),
            "text": text,
            "resource_id": res_id
        }

    def execute_tap(self, x: float, y: float, pre_delay: float = 0.0):
        """
        Waits for simulated human delay and dispatches tap coordinate to Android via ADB.
        """
        if pre_delay > 0:
            time.sleep(pre_delay)

        tap_x = int(round(x))
        tap_y = int(round(y))
        
        cmd = self._build_cmd(["shell", "input", "tap", str(tap_x), str(tap_y)])
        subprocess.run(cmd, check=True)
        print(f"[ADB Execution] Dispatched TAP -> ({tap_x}, {tap_y}) after {pre_delay:.3f}s delay.")

    def _execute_shell(self, shell_args):
        """Helper to run adb shell commands."""
        cmd = self._build_cmd(["shell"] + shell_args)
        subprocess.run(cmd, check=True, capture_output=True)