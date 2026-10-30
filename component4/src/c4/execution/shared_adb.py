"""Adapter around the repository-wide serialized ADB device."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from c4.config import TargetAppConfig


class SharedAdbUnavailable(RuntimeError):
    """Raised when the repository shared ADB module cannot be imported."""


def _import_adb_device() -> Any:
    """Import ``common.adb.AdbDevice``, falling back to this checkout's repository root."""
    try:
        from common.adb import AdbDevice
        return AdbDevice
    except ImportError as error:
        root = Path(__file__).resolve().parents[4]
        if (root / "common" / "adb.py").is_file() and str(root) not in sys.path:
            # Appended, so it can never shadow a package that is already installed.
            sys.path.append(str(root))
            try:
                from common.adb import AdbDevice
                return AdbDevice
            except ImportError:
                pass
        raise SharedAdbUnavailable(
            "The shared ADB module is unavailable. Run Component 4 from "
            "the repository environment where common.adb is importable."
        ) from error


class SharedAdb:
    """Expose the shared ``common.adb.AdbDevice`` through Component 4."""

    def __init__(self, target: TargetAppConfig) -> None:
        AdbDevice = _import_adb_device()
        self._device = AdbDevice(
            serial=target.udid,
            adb=target.adb_path,
            verify=False,
        )

    @property
    def serial(self) -> str | None:
        """Return the selected device serial, if one was configured."""
        return self._device.serial

    def run(self, args: Sequence[str]) -> Any:
        """Run an ADB argument list through the shared device lock."""
        return self._device.run(*args)

    def verify(self) -> str:
        """Verify and select an attached device using the shared implementation."""
        return self._device.verify()
