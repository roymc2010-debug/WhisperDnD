"""Run the design branch with an isolated, first-run snapshot of local documents."""
from __future__ import annotations
import argparse
import errno
import json
import os
from pathlib import Path
import shutil
import sys
import socket
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {'.json', '.md', '.txt', '.docx'}
PRIVATE_NAMES = ('token', 'credential', 'secret', 'api_key', 'apikey', '.env')

def prepare_snapshot(source: Path, destination: Path) -> int:
    source, destination = source.resolve(), destination.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('La copia de prueba debe estar fuera de la carpeta original.')
    if not source.is_dir():
        raise ValueError('No existe la carpeta de origen: ' + str(source))
    destination.mkdir(parents=True, exist_ok=True)
    marker = destination / 'snapshot.json'
    if marker.exists():
        return 0
    count = 0
    for relative, target_name in [('data/campaigns', 'campaigns'), ('outputs', 'output'), ('data/output', 'output')]:
        directory = source / relative
        if not directory.is_dir() or directory.is_symlink():
            continue
        for item in directory.rglob('*'):
            if not item.is_file() or item.is_symlink():
                continue
            if not item.resolve().is_relative_to(directory.resolve()):
                continue
            if item.suffix.lower() not in ALLOWED or any(word in item.name.lower() for word in PRIVATE_NAMES):
                continue
            target = destination / target_name / item.relative_to(directory)
            if not target.resolve().is_relative_to(destination):
                raise ValueError("La carpeta de prueba contiene un enlace fuera de su ubicación.")
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            count += 1
    marker.write_text(json.dumps({'source': str(source), 'documents_copied': count}, ensure_ascii=False, indent=2), encoding='utf-8')
    return count

def configure_environment(destination: Path) -> None:
    # dotenv must not restore absolute storage paths or cloud credentials from another checkout.
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    for key in ('GOOGLE_TOKEN_JSON', 'GOOGLE_CREDENTIALS_JSON', 'GROQ_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_API_KEY', 'RENDER_EXTERNAL_URL'):
        os.environ.pop(key, None)
    for name, folder in [('INPUT', 'input'), ('OUTPUT', 'output'), ('CAMPAIGNS', 'campaigns')]:
        path = (destination / folder).resolve()
        path.mkdir(parents=True, exist_ok=True)
        os.environ['WHISPER_' + name + '_DIR'] = str(path)

def bind_preview_socket(preferred_port: int) -> socket.socket:
    """Reserve the actual loopback listener before announcing or opening a URL."""
    if not 0 <= preferred_port <= 65535:
        raise ValueError('El puerto debe estar entre 0 y 65535.')
    ports = [0] if preferred_port == 0 else range(preferred_port, min(preferred_port + 20, 65536))
    for port in ports:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind(('127.0.0.1', port))
            listener.listen(128)
            listener.setblocking(False)
            return listener
        except OSError as exc:
            listener.close()
            if exc.errno not in (errno.EADDRINUSE, errno.EACCES) and getattr(exc, 'winerror', None) not in (10048, 10013):
                raise
    raise RuntimeError('No hay un puerto libre para la vista previa. Cierra otra copia o usa --port con otro número.')

def open_preview_browser(server, url: str) -> bool:
    if not server.started or server.should_exit:
        return False
    return bool(webbrowser.open(url))

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path.home() / 'WhisperDnD-Lab')
    parser.add_argument('--empty', action='store_true', help='Start with a separate empty QA dataset.')
    parser.add_argument('--port', type=int, default=8081)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    destination = ROOT / ('.design-qa' if args.empty else '.design-preview')
    if not args.empty:
        copied = prepare_snapshot(args.source, destination)
        print('Documentos copiados en este inicio:', copied)
    configure_environment(destination)
    if args.prepare_only:
        return
    # The branch never reuses OAuth files from Laboratorio. Configure APIs in this preview's UI.
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    from dotenv import main as dotenv_main
    if not hasattr(dotenv_main, "_load_dotenv_disabled"):
        raise RuntimeError("La prueba aislada requiere python-dotenv 1.2 o posterior. Actualiza esa dependencia antes de continuar.")
    import uvicorn
    from src.api.server import app
    with bind_preview_socket(args.port) as listener:
        actual_port = listener.getsockname()[1]
        url = 'http://127.0.0.1:' + str(actual_port)
        print('\nWhisperDnD - vista previa del rediseño')
        if actual_port != args.port:
            print('El puerto solicitado está ocupado. Esta copia usará:', actual_port)
        print('URL:', url)
        print('Código del rediseño:', ROOT)
        print('Datos de prueba:', destination)
        print('Ctrl+C para cerrar. Los archivos de Laboratorio no se modifican.\n', flush=True)

        class PreviewServer(uvicorn.Server):
            async def startup(self, sockets=None):
                await super().startup(sockets=sockets)
                if not args.no_browser:
                    open_preview_browser(self, url)

        config = uvicorn.Config(app, host='127.0.0.1', port=actual_port, log_level='info')
        PreviewServer(config).run(sockets=[listener])

if __name__ == '__main__':
    main()
