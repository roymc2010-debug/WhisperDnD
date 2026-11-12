"""Bounded support history. Accept fixed metadata, never exception/request text."""
from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
import sys
import threading
from src.runtime_paths import is_desktop_runtime

from starlette.concurrency import run_in_threadpool

MODULES = {'audio', 'transcription', 'campaigns', 'drive', 'application', 'processing'}
METHODS = {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'TASK'}
KINDS = {'HTTPFailure', 'ProcessingFailure', 'GeminiUnavailable', 'GeminiProviderTimeout',
         'GeminiQuotaError', 'GeminiAccessError', 'GeminiConnectTimeout', 'GeminiSendTimeout',
         'GeminiTimeout', 'GeminiConnectionBusy', 'GeminiConnectionError', 'GeminiAPIError',
         'GeminiGenerationError', 'InsufficientSessionContent', 'ServerError'}
LIMIT = 200
MAX_BYTES = 65536


def valid_event(value):
    if not isinstance(value, dict):
        return False
    return (value.get('module') in MODULES and value.get('method') in METHODS
            and type(value.get('status')) is int and 400 <= value['status'] <= 599
            and isinstance(value.get('time'), str)
            and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value['time']) is not None)


class SupportHistory:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.events = deque(maxlen=LIMIT)
        self.storage_issue = False
        try:
            with self.path.open('rb') as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('oversize history')
            values = json.loads(raw)
            if not isinstance(values, list):
                raise ValueError('invalid history')
            for value in values[-LIMIT:]:
                if valid_event(value):
                    # Do not retain additional fields from a malformed/edited file.
                    self.events.append({k: value[k] for k in ('time', 'module', 'method', 'status')})
                    self.events[-1]['kind'] = value.get('kind') if isinstance(value.get('kind'), str) and value['kind'] in KINDS else 'HTTPFailure'
        except FileNotFoundError:
            pass
        except (OSError, ValueError, UnicodeError, TypeError):
            self.storage_issue = True

    def record(self, module, method, status, kind='HTTPFailure'):
        event = {'time': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                 'module': module, 'method': method, 'status': status,
                 'kind': kind if isinstance(kind, str) and kind in KINDS else 'ProcessingFailure'}
        if not valid_event(event):
            return
        with self.lock:
            self.events.append(event)
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix('.tmp')
                temporary.write_text(json.dumps(list(self.events)), encoding='utf8')
                temporary.replace(self.path)
            except OSError:
                # Diagnostics must not turn a successful operation into a failure.
                self.storage_issue = True

    def render(self, version):
        system = platform.system()
        if system not in {'Windows', 'Linux', 'Darwin'}:
            system = 'Otro'
        machine = platform.machine().lower()
        if machine not in {'amd64', 'x86_64', 'arm64', 'aarch64', 'x86', 'i386', 'i686'}:
            machine = 'no identificada'
        lines = ['WhisperDnD — Reporte de errores', f'Versión: {version}',
                 f'Generado (UTC): {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}',
                 f'Sistema: {system} | Arquitectura: {machine}',
                 f'Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}',
                 'Modo: ' + ('escritorio' if is_desktop_runtime() else 'desarrollo/web'),
                 '', 'Últimos fallos registrados (máximo 200; horas UTC):']
        with self.lock:
            events = list(self.events)
            storage_issue = self.storage_issue
        for e in events:
            result = 'Fallo de tarea' if e['method'] == 'TASK' else f'HTTP {e["status"]}'
            lines.append(f'{e["time"]} | {e["module"]} | {e["method"]} | {result} | {e["kind"]}')
        if not events:
            lines.append('Sin fallos registrados en este historial.')
        if storage_issue:
            lines.append('Parte del historial no pudo guardarse o leerse; puede estar incompleto.')
        lines.extend(['', 'Incluye fallos HTTP y tareas de procesamiento registrados desde esta versión.',
                      'No incluye el registro completo, errores anteriores ni todos los fallos del navegador o arranque.',
                      'No incluye claves, tokens, rutas, nombres de campañas, audio ni texto de sesiones.',
                      'El archivo no se envía automáticamente. Puedes revisarlo antes de compartirlo.',
                      'Al enviarlo, describe qué intentabas hacer y la hora aproximada del problema.'])
        return '\n'.join(lines) + '\n'


class SupportReportMiddleware:
    def __init__(self, app, history_provider):
        self.app = app
        self.history_provider = history_provider

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        status = None
        state = getattr(scope.get('app'), 'state', None) if is_desktop_runtime() and scope['method'] != 'GET' else None
        if state is not None:
            state.desktop_active_requests = getattr(state, 'desktop_active_requests', 0) + 1

        async def capture(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
            await send(message)

        try:
            await self.app(scope, receive, capture)
        except Exception:
            status = 500
            raise
        finally:
            if state is not None:
                state.desktop_active_requests = max(0, state.desktop_active_requests - 1)
            if status is not None and status >= 400:
                # Only route templates are inspected; actual URL/body/headers are never saved.
                route = getattr(scope.get('route'), 'path', '')
                parts = route.split('/')
                module = parts[2] if len(parts) > 2 and parts[1] == 'api' and parts[2] in MODULES else 'application'
                try:
                    await run_in_threadpool(self.history_provider().record, module, scope['method'], status)
                except Exception:
                    pass
