"""
HEART Desktop Studio - Main Application Launcher
Enables running via: python heart_desktop.py
Seamlessly forwards execution to c1_desktop_app.py
"""

import sys
import runpy
from pathlib import Path

if __name__ == "__main__":
    app_script = Path(__file__).resolve().parent / "c1_desktop_app.py"
    if not app_script.exists():
        print(f"[!] Error: Cannot find c1_desktop_app.py at {app_script}")
        sys.exit(1)
    runpy.run_path(str(app_script), run_name="__main__")
