import os
import sys
import time
import urllib.request
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_dir = os.path.join(root_dir, "env testing")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{root_dir}{os.pathsep}{env_dir}"
    
    print("[+] Launching live Uvicorn FastAPI server on 127.0.0.1:8000...")
    cmd = [
        sys.executable, "-m", "uvicorn", "server:app",
        "--app-dir", env_dir,
        "--host", "127.0.0.1",
        "--port", "8000",
        "--log-level", "info"
    ]
    
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    
    endpoints = [
        "http://127.0.0.1:8000/",
        "http://127.0.0.1:8000/api/status",
        "http://127.0.0.1:8000/api/perturbation/telemetry"
    ]
    
    success = False
    try:
        # Wait up to 15 seconds for server to be responsive
        server_ready = False
        for attempt in range(15):
            if proc.poll() is not None:
                out, _ = proc.communicate()
                print(f"[!] Server terminated prematurely with code {proc.returncode}:\n{out}")
                sys.exit(1)
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000/", timeout=2) as r:
                    if r.status == 200:
                        server_ready = True
                        break
            except Exception:
                time.sleep(1)
        
        if not server_ready:
            proc.terminate()
            out, _ = proc.communicate(timeout=3)
            print(f"[!] Server did not respond within timeout:\n{out}")
            sys.exit(1)
        
        print("[OK] Server online. Probing core API endpoints:")
        for url in endpoints:
            with urllib.request.urlopen(url, timeout=3) as response:
                status = response.status
                body = response.read().decode("utf-8")
                print(f"  [OK] {url} -> HTTP {status} (Length: {len(body)})")
                assert status == 200, f"Expected 200, got {status}"
        
        print("[OK] All live REST API endpoints verified successfully (100% PASS)!")
        success = True
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
