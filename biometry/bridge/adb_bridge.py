"""C2's view of the device, over the one shared connection.

This used to open its own ADB connection. It now delegates to common.adb, so
C2's traffic is serialised against C1's and C4's and shares their dump cache.
The public surface is unchanged.
"""
import os
import sys

from bridge.hierarchy import parse_bounds

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from common.adb import AdbDevice, NoDeviceError  # noqa: E402


class ADBBridge:
    """Element lookup and tap injection for C2.

    `dump_max_age` lets a caller reuse a recent hierarchy rather than forcing a
    fresh dump. The probe polls far faster than a dump costs, so sharing one
    across a cycle is what keeps the measurement about the app.
    """

    def __init__(self, device_id=None, device=None, dump_max_age=0.0):
        adb_std_path = os.path.expanduser(r"~\AppData\Local\Android\Sdk\platform-tools")
        if os.path.exists(adb_std_path) and adb_std_path not in os.environ.get("PATH", ""):
            os.environ["PATH"] = adb_std_path + os.pathsep + os.environ.get("PATH", "")
        self.device = device if device is not None else AdbDevice(serial=device_id)
        self.dump_max_age = dump_max_age
        print(f"[ADB] using device {self.device.serial}")

    @property
    def device_id(self):
        return self.device.serial

    def dump_ui_hierarchy(self):
        """Current hierarchy as an ElementTree root."""
        return self.device.hierarchy_root(max_age_s=self.dump_max_age)

    def find_element_by_text(self, text_query: str) -> dict:
        """Locate an element by text, content-desc or resource-id."""
        needle = text_query.lower()
        for node in self.dump_ui_hierarchy().iter("node"):
            text = node.get("text", "")
            desc = node.get("content-desc", "")
            res_id = node.get("resource-id", "")
            if needle in text.lower() or needle in desc.lower() or needle in res_id.lower():
                return self._parse_bounds(node.get("bounds", ""), text or desc, res_id)
        raise ValueError(f"UI element matching {text_query!r} not found on the current screen.")

    @staticmethod
    def _parse_bounds(bounds_str: str, text: str, res_id: str) -> dict:
        x1, y1, x2, y2 = parse_bounds(bounds_str)
        width, height = x2 - x1, y2 - y1
        return {"x": x1 + width // 2, "y": y1 + height // 2,
                "width": width, "height": height, "bounds": (x1, y1, x2, y2),
                "text": text, "resource_id": res_id}

    def execute_tap(self, x: float, y: float, pre_delay: float = 0.0):
        """Wait out the simulated human delay, then dispatch the tap."""
        if pre_delay > 0:
            import time
            time.sleep(pre_delay)
        self.device.tap(x, y)

    def execute_swipe(self, path, duration_s: float, pre_delay: float = 0.0):
        """Dispatch a synthesized gesture.

        `input swipe` replays only a straight endpoint-to-endpoint line, so
        the distorted path's curvature reaches the device as its endpoints
        and the (stress-distorted) duration; the full path is preserved in
        the timeline and the IF-C2-to-Driver events. Replaying the curve
        itself needs a uiautomator2/sendevent driver — a known, post-PP1 gap.
        """
        if pre_delay > 0:
            import time
            time.sleep(pre_delay)
        (x1, y1), (x2, y2) = path[0][:2], path[-1][:2]
        self.device.swipe(x1, y1, x2, y2, duration_ms=duration_s * 1000.0)


__all__ = ["ADBBridge", "NoDeviceError"]
