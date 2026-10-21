"""Drives the real C3 workspace (Tk window) with the real model and saves screenshots of the result.

Usage (repo root):  python -m vision_oracle.frontend.gui_smoke
"""

import json
import sys
import time
from pathlib import Path

import vision_oracle.services.oracle_service  # noqa: F401  path guard first
import customtkinter as ctk
from PIL import ImageGrab

from vision_oracle.frontend.workspace import C3Workspace

OUT = Path(__file__).resolve().parents[1] / "evidence" / "14_pipeline_audit" / "gui"
CASES = [
    ("defect_null_text", "C:/Games/OwlEye/Dataset/bug-aug/bug-aug/bug.4418.jpg", None),
    ("clean_screen", "C:/Games/OwlEye/Dataset/normal-aug/normal-aug/normal.4234.jpg", None),
    ("phone_with_layout", str(Path(__file__).resolve().parents[1] / "notebooks" / "live_phone_screen.png"),
     str(Path(__file__).resolve().parents[1] / "notebooks" / "live_phone_hierarchy.xml")),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    root = ctk.CTk()
    root.geometry("1250x1000+20+20")
    root.title("C3 GUI smoke")
    ws = C3Workspace(root)
    ws.pack(fill="both", expand=True)
    report = []
    root.update()
    for name, image, layout in CASES:
        ws.image_path = image
        ws.file_label.configure(text=Path(image).name)
        ws.hierarchy_path = layout
        if layout:
            ws.hierarchy_label.configure(text=Path(layout).name)
        else:
            ws.clear_hierarchy()
        ws.run("file")
        start = time.monotonic()
        while ws.busy and time.monotonic() - start < 600:
            root.update()
            time.sleep(0.05)
        for _ in range(20):
            root.update(); time.sleep(0.05)
        view = ws.latest or {}
        summary = ws.details.get("1.0", "end").strip() if hasattr(ws.details, "get") else view.get("summary", "")
        x, y = root.winfo_rootx(), root.winfo_rooty()
        shot = ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height()))
        shot.save(OUT / f"{name}.png")
        report.append({"case": name, "image": image, "layout": layout, "title": view.get("title"),
                       "measurements": ws.measurements.cget("text"), "status": ws.status.cget("text"),
                       "summary": summary, "seconds": round(time.monotonic() - start, 1)})
        print(json.dumps(report[-1], indent=1), flush=True)
        ws.latest = None
    (OUT / "gui_smoke.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    root.destroy()


if __name__ == "__main__":
    main()
