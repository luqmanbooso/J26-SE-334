"""
Real-time Android Debug Bridge (ADB) Device Interface for C3 Vision-Semantic Oracle.
Captures live mobile screen framebuffers and UI accessibility hierarchies (window_dump.xml)
for streaming evaluation through the AST Pruner and Universal SAHI Dynamic Slicing engine.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image


@dataclass
class AndroidDevice:
    serial: str
    state: str
    model: str = "Unknown"
    product: str = "Unknown"
    is_emulator: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "serial": self.serial,
            "state": self.state,
            "model": self.model,
            "product": self.product,
            "is_emulator": self.is_emulator,
        }


@dataclass
class LiveScreenState:
    screenshot: Image.Image
    raw_bytes: bytes
    hierarchy_xml: Optional[str]
    device_serial: str
    timestamp: str
    resolution: Tuple[int, int]  # (width, height)


class AdbBridgeError(Exception):
    """Base exception for ADB bridge errors."""
    pass


class AdbBridge:
    """
    High-performance ADB wrapper for live test automation and oracle evaluation.
    Utilizes binary streaming (exec-out) to avoid disk I/O on Android host devices.
    """

    KNOWN_ADB_LOCATIONS = [
        r"D:\Android\platform-tools\adb.exe",
        r"C:\Android\platform-tools\adb.exe",
        r"C:\Users\hp\AppData\Local\Android\Sdk\platform-tools\adb.exe",
    ]

    KNOWN_EMULATOR_LOCATIONS = [
        r"D:\Android\emulator\emulator.exe",
        r"C:\Android\emulator\emulator.exe",
        r"C:\Users\hp\AppData\Local\Android\Sdk\emulator\emulator.exe",
    ]

    def __init__(self, adb_path: Optional[str] = None, emulator_path: Optional[str] = None):
        self.adb_path = self._resolve_binary("adb", adb_path, self.KNOWN_ADB_LOCATIONS)
        self.emulator_path = self._resolve_binary("emulator", emulator_path, self.KNOWN_EMULATOR_LOCATIONS)

    @staticmethod
    def _resolve_binary(name: str, explicit_path: Optional[str], candidate_paths: List[str]) -> str:
        if explicit_path and Path(explicit_path).exists():
            return explicit_path

        # Check system PATH
        path_in_env = shutil.which(name)
        if path_in_env:
            return path_in_env

        # Check well-known local paths
        for cand in candidate_paths:
            if Path(cand).exists():
                return cand

        return name  # Fallback to system command call

    def run_adb(self, args: List[str], timeout: float = 15.0, binary: bool = False) -> Union[str, bytes]:
        """Runs an ADB command and captures stdout."""
        cmd = [self.adb_path] + args
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                text=not binary,
            )
            if res.returncode != 0:
                err_msg = res.stderr.decode("utf-8", errors="replace") if binary else res.stderr
                raise AdbBridgeError(f"ADB command failed ({res.returncode}): {' '.join(cmd)}\n{err_msg}")
            return res.stdout
        except subprocess.TimeoutExpired as e:
            raise AdbBridgeError(f"ADB command timed out ({timeout}s): {' '.join(cmd)}") from e
        except FileNotFoundError as e:
            raise AdbBridgeError(f"ADB binary not found at '{self.adb_path}'") from e

    def list_devices(self) -> List[AndroidDevice]:
        """Lists all attached physical and emulated Android devices."""
        raw = self.run_adb(["devices", "-l"], timeout=5.0)
        assert isinstance(raw, str)
        lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]

        devices: List[AndroidDevice] = []
        for line in lines[1:]:  # Skip "List of devices attached"
            parts = line.split()
            if len(parts) >= 2:
                serial = parts[0]
                state = parts[1]
                model = "Unknown"
                product = "Unknown"
                for p in parts[2:]:
                    if p.startswith("model:"):
                        model = p.split(":", 1)[1]
                    elif p.startswith("product:"):
                        product = p.split(":", 1)[1]
                
                is_emu = serial.startswith("emulator-") or "sdk" in product.lower()
                devices.append(AndroidDevice(
                    serial=serial,
                    state=state,
                    model=model,
                    product=product,
                    is_emulator=is_emu,
                ))
        return devices

    def get_default_device(self) -> Optional[AndroidDevice]:
        """Returns the first online/authorized device, or None."""
        devs = [d for d in self.list_devices() if d.state == "device"]
        return devs[0] if devs else None

    def list_available_avds(self) -> List[str]:
        """Lists available Android Virtual Devices (AVDs) configured on the host."""
        if not self.emulator_path or not Path(self.emulator_path).exists():
            return []
        try:
            res = subprocess.run(
                [self.emulator_path, "-list-avds"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5.0,
            )
            if res.returncode == 0:
                return [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        except Exception:
            pass
        return []

    def start_avd(self, avd_name: str, wait_for_boot: bool = False, timeout_sec: int = 60) -> subprocess.Popen:
        """Launches an Android Virtual Device in the background."""
        cmd = [self.emulator_path, "-avd", avd_name, "-no-snapshot-load", "-gpu", "host"]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if wait_for_boot:
            self.wait_for_device_boot(timeout_sec=timeout_sec)
        return proc

    def wait_for_device_boot(self, serial: Optional[str] = None, timeout_sec: int = 60) -> bool:
        """Blocks until the device finishes booting and sys.boot_completed is 1."""
        prefix = ["-s", serial] if serial else []
        t0 = time.time()
        while time.time() - t0 < timeout_sec:
            try:
                out = self.run_adb(prefix + ["shell", "getprop", "sys.boot_completed"], timeout=2.0)
                if isinstance(out, str) and out.strip() == "1":
                    return True
            except Exception:
                pass
            time.sleep(2.0)
        return False

    def capture_screenshot(self, serial: Optional[str] = None) -> Image.Image:
        """
        Captures the current screen framebuffer via high-speed binary stream (`exec-out screencap -p`).
        Runs in ~150-250ms without writing to device storage.
        """
        prefix = ["-s", serial] if serial else []
        raw_bytes = self.run_adb(prefix + ["exec-out", "screencap", "-p"], timeout=10.0, binary=True)
        assert isinstance(raw_bytes, bytes)
        
        # Windows adb carriage-return normalization fix (strip CR if shell injected \r\n for \n)
        if raw_bytes.startswith(b"\x89PNG\r\r\n"):
            raw_bytes = raw_bytes.replace(b"\r\r\n", b"\r\n")

        try:
            image = Image.open(io.BytesIO(raw_bytes))
            image.load()
            return image
        except Exception as e:
            # Fallback to file-based capture if exec-out unsupported
            remote_tmp = "/sdcard/_heart_oracle_tmp.png"
            self.run_adb(prefix + ["shell", "screencap", "-p", remote_tmp])
            pulled_bytes = self.run_adb(prefix + ["exec-out", "cat", remote_tmp], binary=True)
            self.run_adb(prefix + ["shell", "rm", "-f", remote_tmp])
            assert isinstance(pulled_bytes, bytes)
            img = Image.open(io.BytesIO(pulled_bytes))
            img.load()
            return img

    def capture_hierarchy(self, serial: Optional[str] = None) -> Optional[str]:
        """
        Dumps and retrieves the active UI Accessibility hierarchy XML via uiautomator.
        """
        prefix = ["-s", serial] if serial else []
        remote_xml = "/sdcard/_heart_window_dump.xml"
        try:
            # Dump UI hierarchy
            self.run_adb(prefix + ["shell", "uiautomator", "dump", remote_xml], timeout=5.0)
            # Retrieve content
            xml_raw = self.run_adb(prefix + ["exec-out", "cat", remote_xml], timeout=5.0, binary=True)
            assert isinstance(xml_raw, bytes)
            # Cleanup remote file in background
            try:
                self.run_adb(prefix + ["shell", "rm", "-f", remote_xml], timeout=2.0)
            except Exception:
                pass
            return xml_raw.decode("utf-8", errors="replace")
        except Exception:
            return None

    def capture_screen_state(
        self,
        serial: Optional[str] = None,
        include_hierarchy: bool = True,
    ) -> LiveScreenState:
        """
        Captures fused multimodal screen state (Screenshot + Accessibility XML) from active device.
        """
        screenshot = self.capture_screenshot(serial=serial)
        hierarchy_xml = self.capture_hierarchy(serial=serial) if include_hierarchy else None
        
        # Convert screenshot to bytes for payload transport
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        raw_bytes = buf.getvalue()

        resolved_serial = serial or (self.get_default_device().serial if self.get_default_device() else "unknown_device")

        return LiveScreenState(
            screenshot=screenshot,
            raw_bytes=raw_bytes,
            hierarchy_xml=hierarchy_xml,
            device_serial=resolved_serial,
            timestamp=datetime.now(timezone.utc).isoformat(),
            resolution=screenshot.size,
        )
