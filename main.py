#!/usr/bin/env python3
"""Main launcher for WhisperDnD Localhost Web Application."""

import os
import sys
import warnings
from pathlib import Path

# Suppress harmless WASAPI buffer boundary warnings from live audio meter polling
warnings.filterwarnings("ignore", message=".*discontinuity.*")

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Auto re-exec inside .venv interpreter if running under global python
venv_python = project_root / ".venv" / "Scripts" / "python.exe"
if sys.platform == "win32" and venv_python.is_file() and not os.environ.get("WHISPER_REEXEC"):
    current_exe = Path(sys.executable).resolve()
    target_exe = venv_python.resolve()
    is_silent = current_exe.stem.lower() == "pythonw"
    if is_silent:
        venv_pythonw = project_root / ".venv" / "Scripts" / "pythonw.exe"
        if venv_pythonw.is_file():
            target_exe = venv_pythonw.resolve()
    if current_exe != target_exe:
        import subprocess
        env = dict(os.environ)
        env["WHISPER_REEXEC"] = "1"
        creationflags = subprocess.CREATE_NO_WINDOW if is_silent else 0
        try:
            res = subprocess.call([str(target_exe)] + sys.argv, env=env, creationflags=creationflags)
            sys.exit(res)
        except Exception as _reexec_err:
            print(f"[Launcher] Warning: Could not auto-switch to venv: {_reexec_err}")

# Optional: Auto-hide console window on Windows ONLY if explicitly requested via HIDE_CONSOLE=1
if sys.platform == "win32" and os.environ.get("HIDE_CONSOLE") == "1":
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # 0 = SW_HIDE
    except Exception:
        pass

# Under pythonw.exe on Windows, sys.stdout and sys.stderr are None.
# Uvicorn requires sys.stdout to have .isatty() or it raises AttributeError.
if sys.stdout is None:
    try:
        os.makedirs(str(project_root / "outputs"), exist_ok=True)
        sys.stdout = open(str(project_root / "outputs" / "server.log"), "a", encoding="utf-8")
    except Exception:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")

if sys.stderr is None:
    try:
        os.makedirs(str(project_root / "outputs"), exist_ok=True)
        sys.stderr = open(str(project_root / "outputs" / "server.log"), "a", encoding="utf-8")
    except Exception:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(override=True)
import json

# Support Google Credentials via Environment Variable (Render Docker / Cloud Run / Local)
credentials_path = "/app/credentials.json" if (os.name != "nt" and Path("/app").is_dir()) else str(project_root / "credentials.json")
env_creds = os.environ.get("GOOGLE_CREDENTIALS_JSON")

if env_creds and not os.path.exists(credentials_path):
    try:
        os.makedirs(os.path.dirname(credentials_path), exist_ok=True)
        with open(credentials_path, "w", encoding="utf-8") as f:
            f.write(env_creds)
        print(f"Archivo {credentials_path} generado con éxito desde variable de entorno.")
    except Exception as e:
        print(f"Error escribiendo credentials.json: {e}")


def main():
    try:
        import uvicorn
    except ImportError:
        print("[!] Error: 'uvicorn' is not installed.")
        print("    Please install the dependencies: pip install -r requirements.txt")
        sys.exit(1)

    import os
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 8080))

    print("=" * 60)
    print(" WhisperDnD - Web Application Server")
    print("=" * 60)
    print(f" Starting server at: http://{host}:{port}")
    print(f" Accessible locally: http://localhost:{port}")
    print(f" Accessible on LAN:  http://127.0.0.1:{port}")
    print(" Press Ctrl+C to stop the server.")
    print("=" * 60)

    # Automatically open the browser to http://localhost:port after launching
    if not os.environ.get("NO_BROWSER"):
        import threading
        import time
        import webbrowser

        def _open_browser():
            time.sleep(1.2)
            try:
                webbrowser.open(f"http://localhost:{port}")
            except Exception:
                pass

        threading.Thread(target=_open_browser, daemon=True, name="BrowserLauncher").start()

    uvicorn.run(
        "src.api.server:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
