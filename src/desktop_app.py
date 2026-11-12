"""Desktop entry and manual pre-EXE runner. No backend imports before profile setup."""
import importlib.metadata
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import socket
import sys
import threading
import time
import urllib.request
import uuid

from src.runtime_paths import resolve_runtime_paths
from scripts.launch_desktop import open_app_window

ROOT = Path(__file__).resolve().parents[1]
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def configure_profile(*, manual=False, data_dir=None, environ=None):
    environment = os.environ if environ is None else environ
    if data_dir is not None:
        root = Path(data_dir)
        if not root.is_absolute():
            raise ValueError('La carpeta de prueba debe ser absoluta.')
        root = root.resolve()
    else:
        local = environment.get('LOCALAPPDATA', '')
        if not local or not Path(local).is_absolute():
            raise ValueError('No se encontró una carpeta LOCALAPPDATA absoluta para tus datos.')
        root = Path(local) / ('WhisperDnD-Pruebas' if manual else 'WhisperDnD')
    if root == ROOT or root.is_relative_to(ROOT):
        raise ValueError('Los datos de escritorio deben estar fuera de la carpeta del programa.')
    # Deliberately opt into a fresh profile, not developer/Render environment secrets.
    for key in ('GROQ_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_API_KEY', 'GOOGLE_TOKEN_JSON',
                'GOOGLE_CREDENTIALS_JSON', 'RENDER_EXTERNAL_URL', 'WHISPER_DOWNLOAD_ROOT',
                'WHISPER_INPUT_DIR', 'WHISPER_OUTPUT_DIR', 'WHISPER_CAMPAIGNS_DIR', 'WHISPER_QUOTA_DIR'):
        environment.pop(key, None)
    environment.update(WHISPER_DESKTOP_MODE='1', WHISPER_DESKTOP_DATA_ROOT=str(root),
                       PYTHON_DOTENV_DISABLED='1', NO_BROWSER='1', ALLOW_SERVER_SHUTDOWN='0')
    if manual:
        environment['WHISPER_SKIP_STARTUP_DRIVE_SYNC'] = '1'
    return resolve_runtime_paths(resource_dir=ROOT, environ=environment)


class InstanceLease:
    """OS file lock survives crashes correctly; lock file existence is not ownership."""
    def __init__(self, path):
        self.path = Path(path)
        self.stream = None
        self.acquired = False

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open('a+b')
        self.stream.seek(0, 2)
        if self.stream.tell() == 0:
            self.stream.write(b'0')
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.acquired = True
        except OSError:
            pass
        return self

    def __exit__(self, *args):
        if self.stream is not None:
            if self.acquired:
                self.stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
            self.stream.close()


def reserve_listener(port):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(('127.0.0.1', port))
        listener.listen(128)
        listener.setblocking(False)
        return listener
    except OSError:
        listener.close()
        raise RuntimeError(f'El puerto {port} está ocupado. No se abrió ni se cerró otra aplicación. '
                           'Cierra esa aplicación cuando no tenga trabajos activos y vuelve a intentar.') from None


def instance_ready(port, identity):
    try:
        with HTTP.open(f'http://127.0.0.1:{port}/api/health', timeout=0.3) as response:
            data = json.loads(response.read(4096))
            return (response.status == 200 and data.get('status') == 'alive'
                    and data.get('application') == 'WhisperDnD' and data.get('instance_id') == identity)
    except (OSError, ValueError, AttributeError):
        return False


def preflight(*, environ=None, manual=False, data_dir=None):
    environment = dict(os.environ if environ is None else environ)
    paths = configure_profile(manual=manual, data_dir=data_dir, environ=environment)
    lines = ['WhisperDnD — Comprobación previa (no inicia la app)',
             f'Datos: {paths.data_dir}', 'No se descargan modelos ni se usan servicios externos.']
    for package in ('fastapi', 'uvicorn', 'faster-whisper', 'groq', 'google-genai', 'python-docx',
                    'python-dotenv', 'python-multipart', 'yt-dlp', 'soundcard', 'soundfile',
                    'numpy', 'google-api-python-client', 'google-auth-oauthlib', 'websockets'):
        try:
            version = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            version = 'FALTA'
        lines.append(f'{package}: {version}')
    for binary in ('ffmpeg', 'ffprobe'):
        lines.append(f'{binary}: ' + ('disponible' if shutil.which(binary) else 'FALTA (necesario para algunos audios/videos)'))
    for asset in ('static/index.html', 'static/vendor/tailwind.css', 'static/js/app.js', 'static/js/support-report.js'):
        lines.append(f'{asset}: ' + ('disponible' if (ROOT / asset).is_file() else 'FALTA'))
    lines.extend(['Las claves se configuran en Ajustes. Drive es opcional.',
                  'Esta comprobación no certifica captura, generación, OAuth ni una build EXE.'])
    return '\n'.join(lines)


def desktop_is_busy(recorder, progress, state):
    return (bool(recorder and recorder.is_recording)
            or any(item.get('status') in ('running', 'queued') for item in list(progress.values()))
            or bool(getattr(state, 'desktop_active_requests', 0))
            or bool(getattr(state, 'desktop_background_tasks', set())))


def run(*, manual=False, data_dir=None, port=None, open_browser=True):
    paths = configure_profile(manual=manual, data_dir=data_dir)
    selected_port = port if port is not None else (8082 if manual else 8080)
    if not 1024 <= selected_port <= 65535:
        raise ValueError('El puerto debe estar entre 1024 y 65535.')
    metadata_path = paths.config_dir / 'desktop-instance.json'
    with InstanceLease(paths.config_dir / 'desktop.lock') as lease:
        if not lease.acquired:
            try:
                with metadata_path.open('rb') as stream:
                    metadata = json.loads(stream.read(4096))
                identity = metadata['instance_id']
                if metadata['port'] != selected_port or not isinstance(identity, str) or len(identity) != 32:
                    raise ValueError('instance mismatch')
            except (OSError, ValueError, KeyError, TypeError):
                raise RuntimeError('Ya hay otra instancia iniciando. Espera unos segundos y vuelve a abrir la prueba.') from None
            if not instance_ready(selected_port, identity):
                raise RuntimeError('La instancia existente todavía no responde. No se inició un servidor duplicado.')
            if open_browser:
                open_app_window(f'http://localhost:{selected_port}')
            return
        with reserve_listener(selected_port) as listener:
            identity = uuid.uuid4().hex
            metadata_path.write_text(json.dumps({'instance_id': identity, 'port': selected_port}), encoding='utf8')
            paths.logs_dir.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(paths.logs_dir / 'server.log', maxBytes=2*1024*1024,
                                          backupCount=2, encoding='utf8')
            handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
            logging.getLogger().addHandler(handler)
            redirected = {}
            for name in ('stdout', 'stderr'):
                if getattr(sys, name) is None:
                    stream = (paths.logs_dir / 'server.log').open('a', encoding='utf8')
                    redirected[name] = stream
                    setattr(sys, name, stream)
            app = None
            prior_state = {}
            try:
                import uvicorn
                from src.api.server import app
                prior_state = {key: getattr(app.state, key, None) for key in ('desktop_instance_id', 'desktop_profile')}
                app.state.desktop_instance_id = identity
                app.state.desktop_profile = 'manual' if manual else 'installed'
                # Reject accidental close-by-tab requests; console Ctrl+C uses uvicorn's graceful shutdown.
                from src.api import server as backend
                class GuardedServer(uvicorn.Server):
                    def handle_exit(self, sig, frame):
                        if desktop_is_busy(backend.active_recorder, backend.task_progress_state, app.state):
                            print('Hay una grabación, procesamiento o transferencia activa. Termínala antes de cerrar.', flush=True)
                            return
                        super().handle_exit(sig, frame)
                server = GuardedServer(uvicorn.Config(app, host='127.0.0.1', port=selected_port, log_level='info'))
                url = f'http://localhost:{selected_port}'
                print(f'WhisperDnD — {"PRUEBA SEPARADA" if manual else "Escritorio"}\n{url}\nDatos: {paths.data_dir}', flush=True)
                print('Mantén esta ventana abierta. Antes de cerrarla, termina grabaciones, procesamiento y sincronización.', flush=True)
                if open_browser:
                    def ready_browser():
                        deadline = time.monotonic() + 60
                        while not server.should_exit and time.monotonic() < deadline:
                            if instance_ready(selected_port, identity):
                                open_app_window(url)
                                return
                            time.sleep(0.25)
                    threading.Thread(target=ready_browser, daemon=True, name='DesktopBrowser').start()
                server.run(sockets=[listener])
            finally:
                if app is not None:
                    for key, value in prior_state.items():
                        if value is None:
                            delattr(app.state, key)
                        else:
                            setattr(app.state, key, value)
                logging.getLogger().removeHandler(handler)
                handler.close()
                for name, stream in redirected.items():
                    setattr(sys, name, None)
                    stream.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='WhisperDnD: prueba manual previa al EXE.')
    parser.add_argument('--manual', action='store_true', help='Usar perfil separado WhisperDnD-Pruebas y puerto 8082.')
    parser.add_argument('--check', action='store_true', help='Comprobar dependencias sin arrancar el backend.')
    parser.add_argument('--data-dir', type=Path, help='Carpeta absoluta de datos, fuera del programa.')
    parser.add_argument('--port', type=int)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    try:
        if args.check:
            print(preflight(manual=args.manual, data_dir=args.data_dir))
        else:
            run(manual=args.manual, data_dir=args.data_dir, port=args.port, open_browser=not args.no_browser)
    except (OSError, ValueError, RuntimeError) as exc:
        message = f'No se pudo iniciar WhisperDnD: {exc}'
        if sys.stderr is None and os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, 'WhisperDnD', 0x10)
        else:
            print(message, file=sys.stderr)
        return 1
    return 0
