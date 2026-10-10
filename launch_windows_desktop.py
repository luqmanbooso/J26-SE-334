import os
import sys
import time
import threading
import subprocess
import socket
import urllib.request
import webview

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def wait_for_service(url: str, timeout: int = 15) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status in [200, 304]:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def start_backend():
    """Starts FastAPI REST server in the background."""
    if is_port_in_use(8001):
        print("[Windows App] Backend already running on port 8001.")
        return None
    print("[Windows App] Launching local FastAPI REST Engine on port 8001...")
    env_dir = os.path.join(os.path.dirname(__file__), "env testing")
    proc = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=env_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False
    )
    return proc

def start_frontend():
    """Checks or starts Vite frontend dev server on port 3000."""
    if is_port_in_use(3000):
        print("[Windows App] Frontend already running on port 3000.")
        return None
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    print("[Windows App] Starting Vite web frontend server on port 3000...")
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return proc

def main():
    print("=" * 75)
    print(" HEART - Mobile Robustness Testing Framework")
    print(" Native Windows Desktop Application (Enterprise Air-Gapped Edition)")
    print(" Student: Chanlaka G.L.S. (IT23151260) - Project ID: J26-SE-334")
    print("=" * 75)

    backend_proc = start_backend()
    frontend_proc = start_frontend()

    target_url = "http://localhost:3000/#commercialization"
    if not wait_for_service("http://localhost:3000", timeout=8):
        # Fallback to local swagger docs if vite dev server is building
        if wait_for_service("http://127.0.0.1:8001/api/status", timeout=5):
            target_url = "http://127.0.0.1:8001/docs"
        else:
            target_url = "http://localhost:3000"

    print(f"[Windows App] Opening native desktop window: {target_url}")

    window = webview.create_window(
        title="HEART Mobile Testing Framework - Windows Desktop Edition",
        url=target_url,
        width=1440,
        height=920,
        resizable=True,
        min_size=(1024, 700),
        confirm_close=False,
        text_select=True
    )

    try:
        webview.start(debug=False)
    finally:
        print("[Windows App] Shutting down background processes...")
        if backend_proc:
            backend_proc.terminate()
        if frontend_proc:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(frontend_proc.pid)], capture_output=True)

if __name__ == "__main__":
    main()
