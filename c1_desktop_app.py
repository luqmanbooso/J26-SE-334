"""
HEART Mobile Diagnostics Studio - Compatibility Entry Point
Forwards execution to heart_desktop_app.py
"""
import sys
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from heart_desktop_app import HeartSimpleApp
except ImportError:
    HeartSimpleApp = None

if __name__ == "__main__":
    if HeartSimpleApp:
        app = HeartSimpleApp()
        app.mainloop()
