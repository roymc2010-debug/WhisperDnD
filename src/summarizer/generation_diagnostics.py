"""Content-free generation phases and safe provider/transport error classification."""
import json
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import httpx

PHASE_LABELS = {
    'preparing_request': 'Preparando solicitud de Gemini',
    'connecting': 'Conectando con Gemini',
    'sending_request': 'Enviando solicitud a Gemini',
    'waiting_response': 'Esperando respuesta de Gemini',
    'receiving_response': 'Recibiendo respuesta de Gemini',
    'response_received': 'Respuesta de Gemini recibida',
    'retry_wait': 'Esperando para reintentar Gemini',
    'parsing_response': 'Comprobando la respuesta de Gemini',
    'response_parsed': 'Respuesta de Gemini comprobada',
    'saving_draft': 'Guardando borrador para revisión',
    'completed': 'Borrador guardado para revisión',
    'failed': 'Generación interrumpida',
}


def classify_failure(exc):
    """Never include exception text: it may contain request content or credentials."""
    code = getattr(exc, 'code', None)
    if not isinstance(code, int):
        code = None
    if code == 503:
        kind, status, message = 'GeminiUnavailable', 503, 'Google Gemini devolvió HTTP 503: servicio temporalmente no disponible.'
    elif code == 504:
        kind, status, message = 'GeminiProviderTimeout', 504, 'Google Gemini devolvió HTTP 504: el servicio no terminó dentro de su plazo.'
    elif code == 429:
        kind, status, message = 'GeminiQuotaError', 429, 'Google Gemini devolvió HTTP 429: cuota o límite de solicitudes alcanzado.'
    elif code in (401, 403):
        kind, status, message = 'GeminiAccessError', code, 'Google Gemini rechazó el acceso. Revisa la clave y sus permisos.'
    elif isinstance(exc, httpx.ConnectTimeout):
        kind, status, message = 'GeminiConnectTimeout', 504, 'Se agotó el tiempo de espera al establecer la conexión con Gemini.'
    elif isinstance(exc, httpx.WriteTimeout):
        kind, status, message = 'GeminiSendTimeout', 504, 'Se agotó el tiempo de espera al enviar la solicitud a Gemini.'
    elif isinstance(exc, (httpx.ReadTimeout, TimeoutError)):
        kind, status, message = 'GeminiTimeout', 504, 'Se agotó el tiempo de espera al recibir la respuesta de Gemini. El resultado remoto es desconocido.'
    elif isinstance(exc, httpx.PoolTimeout):
        kind, status, message = 'GeminiConnectionBusy', 503, 'No se obtuvo una conexión libre para Gemini dentro del plazo.'
    elif isinstance(exc, (httpx.TransportError, ConnectionError)):
        kind, status, message = 'GeminiConnectionError', 502, 'La comunicación con Gemini falló o se interrumpió. Revisa la conexión de red.'
    elif code is not None:
        kind, status, message = 'GeminiAPIError', 502, f'Google Gemini devolvió HTTP {code} y no se obtuvo una crónica válida.'
    else:
        kind, status, message = 'GeminiGenerationError', 500, 'Gemini no devolvió una respuesta válida para completar la generación.'
    return {'kind': kind, 'http_status': status, 'provider_code': code, 'message': message,
            'stage': 'Comunicación con Gemini'}


def public_generation_status(data, now=None):
    if not data or not isinstance(data.get('started_at'), (int, float)) or not isinstance(data.get('phase_started_at'), (int, float)):
        return None
    now = time.time() if now is None else now
    end = data.get('finished_at') or now
    result = {key: data.get(key) for key in ('phase','label','started_at','phase_started_at','finished_at','attempt')}
    result['elapsed_seconds'] = max(0, round(end - data['started_at'], 1))
    result['phase_elapsed_seconds'] = max(0, round(end - data['phase_started_at'], 1))
    result['label'] = PHASE_LABELS.get(data.get('phase'), 'Procesando crónica')
    return result


class GenerationDiagnostics:
    def __init__(self, path, model, on_event=None):
        self.path = Path(path)
        self.on_event = on_event
        self.lock = threading.RLock()
        self.started = time.monotonic()
        self.data = {'version': 1, 'model': model, 'started_at': time.time(), 'events': []}
        self.record('preparing_request')

    def record(self, phase, **metadata):
        if phase not in PHASE_LABELS:
            return
        with self.lock:
            now = time.time()
            if phase != self.data.get('phase'):
                self.data['phase_started_at'] = now
            self.data['phase'] = phase
            if phase in ('completed', 'failed'):
                self.data['finished_at'] = now
            # Explicit numeric fields only; never arbitrary provider payloads.
            safe = {key: value for key, value in metadata.items()
                    if key in ('attempt','http_status','provider_code') and isinstance(value, int)}
            kind = metadata.get('failure_kind')
            if kind in {'GeminiUnavailable','GeminiProviderTimeout','GeminiQuotaError','GeminiAccessError',
                        'GeminiConnectTimeout','GeminiSendTimeout','GeminiTimeout','GeminiConnectionBusy',
                        'GeminiConnectionError','GeminiAPIError','GeminiGenerationError'}:
                safe['failure_kind'] = kind
            self.data.update(safe)
            self.data['events'].append({'phase': phase, 'seconds': round(time.monotonic()-self.started, 4), **safe})
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix('.tmp')
                temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf8')
                temporary.replace(self.path)
            except OSError:
                # Diagnostics cannot turn successful paid work into a retry.
                pass
            if self.on_event:
                try:
                    self.on_event(public_generation_status(self.data, now))
                except Exception:
                    pass

    def transport(self, name, info):
        if name == 'connection.connect_tcp.started' or name == 'connection.start_tls.started':
            self.record('connecting')
        elif name.endswith('send_request_headers.started'):
            self.record('sending_request')
        elif name.endswith('send_request_body.complete'):
            self.record('waiting_response')

    def request(self, request):
        request.extensions['trace'] = self.transport

    def response(self, response):
        self.record('receiving_response', http_status=response.status_code)

    @contextmanager
    def pipeline(self):
        try:
            yield
        except Exception as exc:
            failure = getattr(exc, 'failure', None)
            self.record('failed', provider_code=(failure or {}).get('provider_code'), failure_kind=(failure or classify_failure(exc)).get('kind'))
            raise
        else:
            self.record('completed')
