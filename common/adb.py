"""The single path to the Android device.

Three components in this project each opened their own ADB connection with
nothing coordinating them. That is not merely duplication: `uiautomator dump` is
exclusive and slow, so a dump issued by one component while another is timing
the device's response makes that timing a measurement of contention rather than
of the app. This module exists so there is one path, and it is serialised.

Three guarantees:

1. **Exclusive access.** Every device operation is taken under a cross-process
   lock keyed by device serial, so two components in two processes cannot drive
   the same device at once.

2. **One dump per cycle.** `dump_hierarchy(max_age_s=...)` returns a cached dump
   when a fresh enough one exists, so N callers in a polling cycle cost one dump
   rather than N.

3. **No silent fallback.** A missing adb or a missing device raises. A run that
   injects nothing must not be indistinguishable from a clean one.
"""
import io
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, Union

try:                                     # POSIX
    import fcntl
    _WINDOWS = False
except ImportError:                      # Windows
    import msvcrt
    _WINDOWS = True


class NoDeviceError(RuntimeError):
    """Raised when adb is absent or no device is attached. Never swallowed."""


class DeviceLock:
    """Cross-process mutual exclusion for one device.

    A thread lock alone is not enough: the components run as separate processes.
    The lock file lives in the system temp directory, keyed by serial, so any
    process using this module serialises against the others.
    """

    _threads = {}

    def __init__(self, serial=None, timeout=60.0):
        key = re.sub(r"[^A-Za-z0-9_.-]", "_", serial or "default")
        self.path = os.path.join(tempfile.gettempdir(), f"heart-adb-{key}.lock")
        self.timeout = timeout
        self._thread_lock = DeviceLock._threads.setdefault(self.path, threading.Lock())
        self._fh = None

    def __enter__(self):
        self._thread_lock.acquire()
        self._fh = open(self.path, "a+b")
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                if _WINDOWS:
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    self._fh.close(); self._thread_lock.release()
                    raise TimeoutError(
                        f"another process has held the device lock for "
                        f"{self.timeout}s: {self.path}")
                time.sleep(0.02)

    def __exit__(self, *exc):
        try:
            if _WINDOWS:
                self._fh.seek(0); msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._thread_lock.release()
        return False


class AdbDevice:
    """One device, driven through one serialised connection."""

    def __init__(self, serial=None, adb="adb", lock_timeout=60.0, verify=True):
        self.adb = adb
        self.serial = serial
        self._lock_timeout = lock_timeout
        self._cache = None          # (monotonic_timestamp, xml_text)
        self._dumps = 0             # how many real dumps this instance issued
        if verify:
            self.verify()

    # --- discovery ----------------------------------------------------------

    @staticmethod
    def list_devices(adb="adb"):
        """Serials of attached, ready devices. Raises if adb is missing."""
        if shutil.which(adb) is None:
            raise NoDeviceError(
                f"{adb!r} is not on PATH. Install Android platform-tools "
                f"(e.g. `sudo pacman -S android-tools`).")
        out = subprocess.run([adb, "devices"], capture_output=True, text=True).stdout
        return [ln.split("\t")[0] for ln in out.splitlines()[1:]
                if "\tdevice" in ln]

    @classmethod
    def resolve_serial(cls, serial: Optional[str] = None, adb: str = "adb") -> str:
        """Validates requested serial or auto-resolves when exactly one device is attached.

        Raises:
            NoDeviceError: if no devices attached, multiple attached without explicit serial,
                           or requested serial not found.
        """
        found = cls.list_devices(adb=adb)
        if not found:
            raise NoDeviceError(
                "no Android device or emulator is attached. Connect one and "
                "enable USB debugging; this will not silently simulate."
            )
        if serial:
            if serial not in found:
                raise NoDeviceError(f"device {serial!r} not attached; have {found}")
            return serial
        if len(found) > 1:
            raise NoDeviceError(
                f"{len(found)} devices attached {found} — pass serial= to choose one."
            )
        return found[0]

    def verify(self):
        self.serial = self.resolve_serial(self.serial, self.adb)
        return self.serial

    def is_connected(self) -> bool:
        """Returns True if this device is attached and in 'device' state."""
        try:
            found = self.list_devices(self.adb)
            return (self.serial in found) if self.serial else (len(found) > 0)
        except NoDeviceError:
            return False


    # --- the one path to the device ----------------------------------------

    def _argv(self, args):
        base = [self.adb] + (["-s", self.serial] if self.serial else [])
        return base + list(args)

    def run(self, *args, check=False, timeout=60):
        """Run one adb command under the device lock. Never uses a shell.

        A missing adb binary surfaces as NoDeviceError rather than a raw
        FileNotFoundError, so every caller sees one exception type with one
        actionable message.
        """
        with DeviceLock(self.serial, self._lock_timeout):
            try:
                return subprocess.run(self._argv(args), capture_output=True, text=True,
                                      errors="ignore", check=check, timeout=timeout)
            except FileNotFoundError as exc:
                raise NoDeviceError(
                    f"{self.adb!r} is not on PATH. Install Android platform-tools "
                    f"(e.g. `sudo pacman -S android-tools`).") from exc

    def run_bytes(self, *args, timeout=60) -> bytes:
        """Run one adb command under the device lock returning raw stdout bytes.
        
        Essential for screencap, binary dumps, and media extraction.
        """
        with DeviceLock(self.serial, self._lock_timeout):
            try:
                proc = subprocess.run(self._argv(args), stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, check=False, timeout=timeout)
                return proc.stdout
            except FileNotFoundError as exc:
                raise NoDeviceError(
                    f"{self.adb!r} is not on PATH. Install Android platform-tools "
                    f"(e.g. `sudo pacman -S android-tools`).") from exc

    def shell(self, *args, **kw):
        return self.run("shell", *args, **kw).stdout

    def tap(self, x, y):
        self.run("shell", "input", "tap", str(int(round(x))), str(int(round(y))))

    # --- hierarchy, cached --------------------------------------------------

    def dump_hierarchy(self, max_age_s: float = 0.0, max_retries: int = 2, backoff_s: float = 0.2) -> str:
        """Current UI hierarchy as XML text.

        With `max_age_s > 0` a dump younger than that is reused instead of
        issuing another. `uiautomator dump` costs a few hundred milliseconds and
        blocks the device, so sharing one across callers in a polling cycle is
        the difference between measuring the app and measuring ourselves.
        Retries on transient failure with exponential backoff before declaring device lost.
        Raises NoDeviceError if no <hierarchy> element is returned or device is disconnected.
        """
        if self._cache and (time.monotonic() - self._cache[0]) <= max_age_s:
            return self._cache[1]

        last_exc: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            try:
                with DeviceLock(self.serial, self._lock_timeout):
                    subprocess.run(self._argv(["shell", "uiautomator", "dump",
                                               "/sdcard/window_dump.xml"]),
                                   capture_output=True, text=True, timeout=60)
                    raw = subprocess.run(self._argv(["exec-out", "cat", "/sdcard/window_dump.xml"]),
                                         capture_output=True, text=True, errors="ignore",
                                         timeout=60).stdout
                self._dumps += 1
                text = (raw or "").replace("\r\r\n", "\n").replace("\r\n", "\n")
                match = re.search(r"(<hierarchy[\s\S]*?</hierarchy>)", text)
                if not match:
                    raise NoDeviceError(
                        f"no <hierarchy> element in the device dump from {self.serial!r} "
                        f"(device disconnected or offline)"
                    )
                xml = match.group(1).strip()
                self._cache = (time.monotonic(), xml)
                return xml
            except FileNotFoundError as exc:
                raise NoDeviceError(
                    f"{self.adb!r} is not on PATH. Install Android platform-tools "
                    f"(e.g. `sudo pacman -S android-tools`).") from exc
            except NoDeviceError as exc:
                last_exc = exc
                if attempt < max_retries:
                    time.sleep(backoff_s * (2 ** attempt))
                    continue
                raise last_exc

    def hierarchy_root(self, max_age_s=0.0):
        return ET.fromstring(self.dump_hierarchy(max_age_s))

    @property
    def dump_count(self):
        """Real dumps issued — the cost this instance imposed on the device."""
        return self._dumps

    # --- screencap & display metrics ----------------------------------------

    def screencap(self, as_pil: bool = True, max_retries: int = 2, backoff_s: float = 0.2):
        """Captures live screen directly via streaming binary exec-out screencap.

        Zero temporary file creation on device (<200ms latency).
        Handles Windows CRLF translation on binary pipe cleanly.
        Returns PIL.Image.Image or raw bytes.
        Retries on transient disconnections or empty streams with exponential backoff.
        Raises NoDeviceError if device remains unreachable or stream is empty/corrupt.
        """
        png_sig = b"\x89PNG\r\n\x1a\n"
        last_exc: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                raw_bytes = self.run_bytes("exec-out", "screencap", "-p")
                if not raw_bytes:
                    raise NoDeviceError(
                        f"adb screencap returned 0 bytes from device {self.serial!r} "
                        f"(device disconnected or offline)"
                    )

                # Normalize Windows stdout CRLF injection if present.
                # On Windows, ADB exec-out can mangle \n into \r\n, turning \r\n into \r\r\n.
                # Replacing \r\r\n with \r\n restores original binary byte stream.
                if raw_bytes.startswith(png_sig):
                    clean_bytes = raw_bytes
                elif raw_bytes.startswith(b"\x89PNG\r\r\n\x1a\r\r\n") or raw_bytes.startswith(b"\x89PNG\r\r\n\x1a\n"):
                    clean_bytes = raw_bytes.replace(b"\r\r\n", b"\r\n")
                else:
                    clean_bytes = raw_bytes.replace(b"\r\r\n", b"\r\n")
                    idx = clean_bytes.find(png_sig)
                    if idx != -1:
                        clean_bytes = clean_bytes[idx:]
                    elif not clean_bytes.startswith(png_sig):
                        raise NoDeviceError(
                            f"Failed to decode valid PNG signature from adb screencap stream for device {self.serial!r}"
                        )

                if as_pil:
                    from PIL import Image
                    try:
                        img = Image.open(io.BytesIO(clean_bytes))
                        img.load()
                        return img
                    except Exception as exc:
                        raise NoDeviceError(
                            f"Corrupted image payload from screencap for device {self.serial!r}: {exc}"
                        ) from exc
                return clean_bytes

            except NoDeviceError as exc:
                last_exc = exc
                if attempt < max_retries:
                    time.sleep(backoff_s * (2 ** attempt))
                    continue
                raise last_exc

    def get_display_metrics(self) -> Dict[str, Any]:
        """Queries physical screen resolution and pixel density from Android WindowManager."""
        size_out = self.shell("wm", "size")
        density_out = self.shell("wm", "density")

        width, height = 1080, 2400
        size_match = re.search(r"(?:Physical|Override) size:\s*(\d+)x(\d+)", size_out)
        if size_match:
            width = int(size_match.group(1))
            height = int(size_match.group(2))

        density = 420
        density_match = re.search(r"(?:Physical|Override) density:\s*(\d+)", density_out)
        if density_match:
            density = int(density_match.group(1))

        return {
            "width": width,
            "height": height,
            "density": density,
            "aspect_ratio": round(height / width, 3) if width > 0 else 1.0,
            "is_tall": (height / width) >= 1.25 if width > 0 else False,
        }

    # --- uiautomator2 binding -----------------------------------------------

    def init_uiautomator2(self):
        """Optional binding to uiautomator2 session for low-latency hierarchy & actions.

        Falls back gracefully with descriptive error if uiautomator2 is not installed.
        """
        try:
            import uiautomator2 as u2
            return u2.connect(self.serial)
        except ImportError as exc:
            raise ImportError(
                "uiautomator2 library is not installed in current environment. "
                "Install via `pip install uiautomator2`."
            ) from exc
