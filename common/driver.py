"""
Common Test Execution Driver Layer for Android App Robustness and Defect Crawling.
Shared execution harness usable across Component 2, Component 3, and Component 4.
Fulfills:
- Proposal FR2/FR6: Common driver layer dispatching actions under cross-process ADB lock.
- Requirement R2: Autonomous UI crawler exploring interactive nodes, awaiting settle windows,
  capturing live screen bundles, and feeding them directly to C3 Oracle.
"""

from __future__ import annotations

import re
import time
import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image

from common.adb import AdbDevice, NoDeviceError

logger = logging.getLogger("common.driver")


class CommonTestDriver:
    """
    Unified test execution driver and autonomous UI crawler.
    Orchestrates device gestures, UI hierarchy parsing, screen capture,
    and visual defect oracle evaluation under cross-process arbitration.
    """

    def __init__(
        self,
        serial: Optional[str] = None,
        package_name: str = "com.solvance.android",
        settle_delay_s: float = 0.8,
        oracle_service: Optional[Any] = None,
    ):
        self.device = AdbDevice(serial=AdbDevice.resolve_serial(serial), verify=True)
        self.package_name = package_name
        self.settle_delay_s = settle_delay_s
        self._oracle_service = oracle_service
        self._visited_elements: set[str] = set()

    @property
    def oracle_service(self) -> Any:
        if self._oracle_service is None:
            try:
                from vision_oracle.services.oracle_service import get_oracle_service
                self._oracle_service = get_oracle_service()
            except Exception as exc:
                logger.warning("Oracle service unavailable: %s", exc)
        return self._oracle_service

    def launch_app(self, activity: Optional[str] = None) -> bool:
        """Launches the target application and awaits UI settle."""
        try:
            if activity:
                component = f"{self.package_name}/{activity}"
                self.device.shell("am", "start", "-n", component)
            else:
                self.device.shell("monkey", "-p", self.package_name, "-c", "android.intent.category.LAUNCHER", "1")
            time.sleep(self.settle_delay_s)
            return True
        except Exception as exc:
            logger.error("Failed to launch application '%s': %s", self.package_name, exc)
            return False

    def stop_app(self) -> None:
        """Force stops target application package."""
        try:
            self.device.shell("am", "force-stop", self.package_name)
        except Exception as exc:
            logger.warning("Failed force-stop for '%s': %s", self.package_name, exc)

    def extract_interactive_nodes(self, max_nodes: int = 25) -> List[Dict[str, Any]]:
        """
        Parses live UI hierarchy to find clickable, checkable, or editable widgets.
        Returns list of target dicts with center coordinates (cx, cy) and bounds.
        """
        xml_text = self.device.dump_hierarchy()
        if not xml_text:
            return []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        targets: List[Dict[str, Any]] = []
        bounds_pattern = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")

        for elem in root.iter("node"):
            clickable = elem.get("clickable") == "true"
            checkable = elem.get("checkable") == "true"
            cls_name = elem.get("class", "")
            is_interactive_class = any(
                k in cls_name for k in ("Button", "EditText", "CheckBox", "RadioButton", "ImageView")
            )

            if not (clickable or checkable or is_interactive_class):
                continue

            raw_bounds = elem.get("bounds", "")
            match = bounds_pattern.match(raw_bounds)
            if not match:
                continue

            x1, y1, x2, y2 = [int(v) for v in match.groups()]
            w = x2 - x1
            h = y2 - y1
            if w <= 10 or h <= 10:
                continue

            cx = x1 + (w // 2)
            cy = y1 + (h // 2)
            res_id = elem.get("resource-id", "")
            text_val = elem.get("text", "")
            key = f"{res_id}|{text_val}|{x1},{y1},{x2},{y2}"

            targets.append(
                {
                    "key": key,
                    "resource_id": res_id,
                    "text": text_val,
                    "class": cls_name,
                    "bounds": [x1, y1, x2, y2],
                    "center": (cx, cy),
                }
            )
            if len(targets) >= max_nodes:
                break

        return targets

    def dispatch_tap(self, x: int, y: int) -> None:
        """Dispatches touch tap under device lock and awaits UI settle."""
        self.device.tap(x, y)
        time.sleep(self.settle_delay_s)

    def dispatch_swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        """Dispatches touch swipe under device lock and awaits UI settle."""
        self.device.shell("input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))
        time.sleep(self.settle_delay_s)

    def execute_and_evaluate_step(
        self,
        target: Optional[Dict[str, Any]] = None,
        action_type: str = "tap",
        session_id: str = "autonomous_driver_session",
    ) -> Dict[str, Any]:
        """
        Dispatches gesture, captures resulting device state, and passes to C3 Oracle.
        Returns unified step report with action metadata and visual oracle verdict.
        """
        step_id = f"step_{int(time.time() * 1000)}"
        action_desc = "initial_screen"

        if target is not None:
            cx, cy = target["center"]
            action_desc = f"{action_type} on {target.get('text') or target.get('resource_id') or 'widget'}"
            if action_type == "tap":
                self.dispatch_tap(cx, cy)
            self._visited_elements.add(target["key"])

        # Capture post-action screen and hierarchy
        image = self.device.screencap(as_pil=True)
        raw_xml = self.device.dump_hierarchy()

        verdict_data = {}
        if self.oracle_service is not None:
            verdict_data = self.oracle_service.evaluate(
                image_input=image,
                raw_hierarchy=raw_xml,
                screen_id=step_id,
                action_context=action_desc,
                action_id=step_id,  # lets C3 hand a finding to C4 as reproducible
                enable_sahi=False,  # tiles flagged 29/29 clean validation screens (C3 audit 2026-10-21)
                session_id=session_id,
            )

        return {
            "step_id": step_id,
            "action": action_desc,
            "target": target,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "oracle_verdict": verdict_data,
        }

    def crawl(
        self,
        max_steps: int = 5,
        session_id: str = "autonomous_crawl_session",
    ) -> List[Dict[str, Any]]:
        """
        Autonomously explores interactive widgets across screen states,
        evaluating each reached screen with C3 Vision Oracle.
        """
        self.launch_app()
        trace: List[Dict[str, Any]] = []

        # Step 0: Initial Screen
        initial_step = self.execute_and_evaluate_step(target=None, session_id=session_id)
        trace.append(initial_step)

        for step_idx in range(1, max_steps):
            targets = self.extract_interactive_nodes()
            unvisited = [t for t in targets if t["key"] not in self._visited_elements]

            if not unvisited:
                # Swipe up to reveal more content if no unvisited targets visible
                metrics = self.device.get_display_metrics()
                w, h = metrics.get("width", 1080), metrics.get("height", 2400)
                self.dispatch_swipe(w // 2, int(h * 0.7), w // 2, int(h * 0.3))
                targets = self.extract_interactive_nodes()
                unvisited = [t for t in targets if t["key"] not in self._visited_elements]
                if not unvisited:
                    logger.info("Crawl exhausted: no more interactive widgets found.")
                    break

            next_target = unvisited[0]
            step_record = self.execute_and_evaluate_step(
                target=next_target,
                action_type="tap",
                session_id=session_id,
            )
            trace.append(step_record)

        return trace

    @staticmethod
    def compile_summary_report(trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compiles end-to-end inspection report from execution trace."""
        total_steps = len(trace)
        defects_found = 0
        defect_breakdown: Dict[str, int] = {}
        findings_list = []

        for item in trace:
            verdict_info = item.get("oracle_verdict", {})
            c4_v = verdict_info.get("c4_verdict", {})
            if c4_v.get("has_gui_defect"):
                defects_found += 1
                dtype = c4_v.get("defect_type", "unknown")
                defect_breakdown[dtype] = defect_breakdown.get(dtype, 0) + 1
                findings_list.append(
                    {
                        "step_id": item.get("step_id"),
                        "action": item.get("action"),
                        "defect_type": dtype,
                        "regions": c4_v.get("regions", []),
                    }
                )

        return {
            "total_steps": total_steps,
            "clean_steps": total_steps - defects_found,
            "defects_detected": defects_found,
            "defect_taxonomy_breakdown": defect_breakdown,
            "defect_findings": findings_list,
        }
