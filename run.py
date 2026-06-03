"""
MCSI Tender Monitor — Local development launcher.
"""
import subprocess
import sys
import os
import socket

def kill_port(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                print(f"[run.py] Port {port} busy — freeing...")
                subprocess.call(
                    f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :{port} ^| findstr LISTEN\') do taskkill /F /PID %a',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
    except Exception:
        pass

def main():
    here = os.path.dirname(os.path.abspath(__file__))

    print("=" * 55)
    print("  MCSI Tender Monitor — Local")
    print("  http://localhost:8000")
    print("=" * 55)

    # Install deps if needed
    try:
        import fastapi, uvicorn, httpx, bs4, asyncpg, apscheduler
    except ImportError:
        print("\nInstalling dependencies...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r",
                               os.path.join(here, "requirements.txt")])
        print("Done.\n")

    kill_port(8000)

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
