"""Open WhisperDnD only after its local HTTP server is ready. Standard library only."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime_paths import resolve_runtime_paths

APP_URL = 'http://localhost:8080'
_LOCAL_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def is_server_ready(url=APP_URL, timeout=0.2):
    try:
        # Probe the IPv4 listener directly; keep the browser origin localhost
        # so saved keys and other browser data remain available.
        parts = urlsplit(url)
        if parts.hostname == 'localhost':
            parts = parts._replace(netloc='127.0.0.1' + (':' + str(parts.port) if parts.port else ''))
        health_url = urlunsplit(parts).rstrip('/') + '/api/health'
        with _LOCAL_HTTP.open(health_url, timeout=timeout) as response:
            data = json.loads(response.read(4096))
            return response.status == 200 and isinstance(data, dict) and data.get('status') == 'alive'
    except (OSError, urllib.error.URLError, ValueError):
        return False


def wait_for_server(url=APP_URL, timeout=45.0, interval=0.25, process=None):
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        if is_server_ready(url, timeout=min(0.2, remaining)):
            return True
        if process is not None and process.poll() is not None:
            return False
        time.sleep(min(interval, max(0, deadline - time.monotonic())))


def open_app_window(url):
    program_files = Path(os.environ.get('ProgramFiles', r'C:\Program Files'))
    program_files_x86 = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'))
    browsers = [program_files_x86 / 'Microsoft/Edge/Application/msedge.exe',
                program_files / 'Microsoft/Edge/Application/msedge.exe',
                program_files / 'Google/Chrome/Application/chrome.exe']
    browser = next((path for path in browsers if path.is_file()), None)
    if browser:
        subprocess.Popen([str(browser), '--app=' + url])
    else:
        webbrowser.open(url)


def launch():
    if not is_server_ready(APP_URL):
        python = ROOT / '.venv/Scripts/pythonw.exe'
        if not python.is_file():
            raise RuntimeError('No se encontró Python de WhisperDnD en .venv. Revisa la instalación.')
        environment = os.environ.copy()
        environment['NO_BROWSER'] = '1'
        log_path = resolve_runtime_paths(resource_dir=ROOT).logs_dir / 'server.log'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('a', encoding='utf8') as log:
            process = subprocess.Popen([str(python), str(ROOT / 'main.py')], cwd=str(ROOT),
                                       env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if not wait_for_server(APP_URL, process=process):
            raise RuntimeError(f'El servidor de WhisperDnD no terminó de iniciar. No se abrió la ventana. Revisa {log_path} y vuelve a abrir el acceso directo.')
    open_app_window(APP_URL)


if __name__ == '__main__':
    try:
        launch()
    except Exception as exc:
        message = str(exc) if isinstance(exc, RuntimeError) else 'No se pudo iniciar WhisperDnD. Revisa la instalación y el registro de arranque.'
        if os.name == 'nt':
            ctypes.windll.user32.MessageBoxW(0, message, 'WhisperDnD', 0x10)
        else:
            raise
