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
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import xml.etree.ElementTree as ET

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

    def verify(self):
        found = self.list_devices(self.adb)
        if not found:
            raise NoDeviceError(
                "no Android device or emulator is attached. Connect one and "
                "enable USB debugging; this will not silently simulate.")
        if self.serial and self.serial not in found:
            raise NoDeviceError(f"device {self.serial!r} not attached; have {found}")
        if self.serial is None and len(found) > 1:
            raise NoDeviceError(
                f"{len(found)} devices attached {found} — pass serial= to choose one.")
        self.serial = self.serial or found[0]
        return self.serial

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

    def shell(self, *args, **kw):
        return self.run("shell", *args, **kw).stdout

    def tap(self, x, y):
        self.run("shell", "input", "tap", str(int(round(x))), str(int(round(y))))

    def swipe(self, x1, y1, x2, y2, duration_ms=300):
        """One straight swipe. `input swipe` cannot replay a curved path —
        a caller with a multi-point gesture sends its endpoints and keeps the
        full path in its own record."""
        self.run("shell", "input", "swipe",
                 str(int(round(x1))), str(int(round(y1))),
                 str(int(round(x2))), str(int(round(y2))),
                 str(int(round(duration_ms))))

    # --- hierarchy, cached --------------------------------------------------

    def dump_hierarchy(self, max_age_s=0.0):
        """Current UI hierarchy as XML text.

        With `max_age_s > 0` a dump younger than that is reused instead of
        issuing another. `uiautomator dump` costs a few hundred milliseconds and
        blocks the device, so sharing one across callers in a polling cycle is
        the difference between measuring the app and measuring ourselves.
        """
        if self._cache and (time.monotonic() - self._cache[0]) <= max_age_s:
            return self._cache[1]
        with DeviceLock(self.serial, self._lock_timeout):
            subprocess.run(self._argv(["shell", "uiautomator", "dump",
                                       "/sdcard/window_dump.xml"]),
                           capture_output=True, text=True, timeout=60)
            raw = subprocess.run(self._argv(["exec-out", "cat", "/sdcard/window_dump.xml"]),
                                 capture_output=True, text=True, errors="ignore",
                                 timeout=60).stdout
        self._dumps += 1
        text = raw.replace("\r\r\n", "\n").replace("\r\n", "\n")
        match = re.search(r"(<hierarchy[\s\S]*?</hierarchy>)", text)
        if not match:
            raise RuntimeError("no <hierarchy> element in the device dump")
        xml = match.group(1).strip()
        self._cache = (time.monotonic(), xml)
        return xml

    def hierarchy_root(self, max_age_s=0.0):
        return ET.fromstring(self.dump_hierarchy(max_age_s))

    @property
    def dump_count(self):
        """Real dumps issued — the cost this instance imposed on the device."""
        return self._dumps
