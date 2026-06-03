"""
MCSI Tender Monitor — One-click launcher.
Starts backend server + ngrok tunnel automatically.
"""
import subprocess
import sys
import os
import time
import threading

NGROK_PATH = r"C:\Users\AnandbatGanbaatar\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe"

def kill_port(port):
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                print(f"[run.py] Port {port} busy — freeing...")
                subprocess.call(
                    f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :{port} ^| findstr LISTEN\') do taskkill /F /PID %a',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                time.sleep(1)
    except Exception:
        pass

def start_ngrok():
    """Start ngrok in background and print the public URL."""
    if not os.path.exists(NGROK_PATH):
        print("[ngrok] Not found — skipping tunnel")
        return
    # Kill existing ngrok
    subprocess.call("taskkill /F /IM ngrok.exe", shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    subprocess.Popen([NGROK_PATH, "http", "8000"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Wait for ngrok to start, then get URL
    for _ in range(10):
        time.sleep(1)
        try:
            import urllib.request, json
            with urllib.request.urlopen("http://localhost:4040/api/tunnels", timeout=2) as r:
                data = json.loads(r.read())
                tunnels = data.get("tunnels", [])
                if tunnels:
                    url = tunnels[0]["public_url"]
                    print("\n" + "=" * 55)
                    print("  🌐 SHARE THIS LINK WITH YOUR TEAM:")
                    print(f"  {url}")
                    print("=" * 55)
                    # Copy to clipboard
                    try:
                        subprocess.run(f'echo {url}| clip', shell=True)
                        print("  ✅ URL copied to clipboard!")
                    except Exception:
                        pass
                    print()
                    return
        except Exception:
            pass
    print("[ngrok] Could not get public URL — check ngrok window")

def main():
    here = os.path.dirname(os.path.abspath(__file__))

    print("=" * 55)
    print("  MCSI Tender Monitor")
    print("  Starting server + public link...")
    print("=" * 55)

    # Install deps if needed
    try:
        import fastapi, uvicorn, httpx, bs4, aiosqlite, apscheduler
    except ImportError:
        print("\nInstalling dependencies...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r",
                               os.path.join(here, "requirements.txt")])
        print("Done.\n")

    # Free ports
    kill_port(8000)
    kill_port(4040)

    # Start ngrok in background thread (waits for server to be up)
    ngrok_thread = threading.Thread(target=start_ngrok, daemon=True)
    ngrok_thread.start()

    # Start uvicorn (blocks)
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )

if __name__ == "__main__":
    main()
