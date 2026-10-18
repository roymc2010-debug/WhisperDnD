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

# Auto-hide console window on Windows if launched without SHOW_CONSOLE
if sys.platform == "win32" and not os.environ.get("SHOW_CONSOLE"):
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # 0 = SW_HIDE
    except Exception:
        pass

# Setup unified persistent rotating file logging to outputs/server.log
import logging
from logging.handlers import RotatingFileHandler

log_dir = project_root / "outputs"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "server.log"

# Mantiene un tamaño máximo de 2 MB y solo los 2 respaldos más recientes (server.log.1, server.log.2)
# Los logs antiguos de hace días, semanas o meses se eliminan solos automáticamente.
logging.captureWarnings(True)
file_handler = RotatingFileHandler(
    str(log_file),
    maxBytes=2 * 1024 * 1024,  # Máximo 2 MB por archivo
    backupCount=2,             # Solo conserva los 2 respaldos más recientes
    encoding="utf-8",
)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
    root_logger.addHandler(file_handler)

def _unhandled_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    root_logger.critical("Excepción no capturada:", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = _unhandled_exception_handler

# Under pythonw.exe on Windows, sys.stdout and sys.stderr are None.
# Uvicorn requires sys.stdout to have .isatty() or it raises AttributeError.
if sys.stdout is None:
    try:
        sys.stdout = open(str(log_file), "a", encoding="utf-8")
    except Exception:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")

if sys.stderr is None:
    try:
        sys.stderr = open(str(log_file), "a", encoding="utf-8")
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
