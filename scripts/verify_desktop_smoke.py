"""Start the actual desktop entry in a temporary profile; only local read-only requests."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def temporary_profile():
    directory = tempfile.TemporaryDirectory(prefix='whisperdnd-desktop-smoke-')
    root = Path(directory.name).resolve()
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith('whisperdnd-desktop-smoke-'):
        raise RuntimeError('La carpeta temporal no coincide con la raíz prevista.')
    try:
        yield str(root)
    finally:
        # Windows may release the final process/file handles just after wait() returns.
        for attempt in range(20):
            try:
                directory.cleanup()
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.1)


def main():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with temporary_profile() as temporary:
        profile = Path(temporary) / 'Perfil temporal María'
        log = Path(temporary) / 'smoke.log'
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        command = [sys.executable, '-X', 'utf8', str(ROOT / 'desktop.py'), '--manual', '--no-browser',
                   '--data-dir', str(profile), '--port', str(port)]
        environment = dict(os.environ, WHISPER_ENV='test', TESTING='1',
                           WHISPER_NATIVE_AUDIO_TEST='0', PYTHON_DOTENV_DISABLED='1')
        with log.open('wb') as output:
            process = subprocess.Popen(command, cwd=temporary, env=environment,
                                       stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                deadline = time.monotonic() + 60
                identity = None
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError('El arranque temporal terminó antes de responder.')
                    try:
                        with opener.open(f'http://127.0.0.1:{port}/api/health', timeout=0.5) as response:
                            data = json.loads(response.read(4096))
                            identity = data.get('instance_id')
                            if data.get('application') == 'WhisperDnD' and identity:
                                break
                    except (OSError, ValueError):
                        pass
                    time.sleep(0.2)
                if not identity:
                    raise RuntimeError('No respondió el arranque temporal dentro del plazo.')
                with opener.open(f'http://127.0.0.1:{port}/', timeout=3) as response:
                    assert response.status == 200
                    assert b'btnDownloadSupportReport' in response.read()
                with opener.open(f'http://127.0.0.1:{port}/api/support/report', timeout=3) as response:
                    report = response.read().decode('utf8')
                    assert 'Modo: escritorio' in report
                    assert str(profile) not in report
                with opener.open(f'http://127.0.0.1:{port}/api/campaigns', timeout=3) as response:
                    campaigns = json.loads(response.read())
                    assert isinstance(campaigns, list) and not campaigns, 'El perfil temporal debe empezar sin campañas.'
                # A second launch must return without creating a different server.
                second = subprocess.run(command, cwd=temporary, env=environment,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                assert second.returncode == 0
                with opener.open(f'http://127.0.0.1:{port}/api/health', timeout=3) as response:
                    assert json.loads(response.read())['instance_id'] == identity
                assert not (profile / 'config/token.json').exists()
                assert not (profile / 'models').exists()
            finally:
                # Only the subprocess created above, after read-only checks with no active work.
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=15)
    print('PASS: arranque real desde otra carpeta; perfil temporal vacío; HTML y reporte; segunda apertura reutiliza la instancia.')
    print('Proceso y perfil temporal cerrados. Sin navegador, grabaciones, descargas de modelos ni servicios externos.')


if __name__ == '__main__':
    main()
