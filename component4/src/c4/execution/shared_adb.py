"""Adapter around the repository-wide serialized ADB device."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from c4.config import TargetAppConfig


class SharedAdbUnavailable(RuntimeError):
    """Raised when the repository shared ADB module cannot be imported."""


class SharedAdb:
    """Expose the shared ``common.adb.AdbDevice`` through Component 4."""

    def __init__(self, target: TargetAppConfig) -> None:
        try:
            from common.adb import AdbDevice
        except ImportError as error:
            raise SharedAdbUnavailable(
                "The shared ADB module is unavailable. Run Component 4 from "
                "the repository environment where common.adb is importable."
            ) from error
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
