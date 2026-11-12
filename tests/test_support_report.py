"""Support downloads contain structured failures, never raw request/log content."""
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


def test_support_report_is_available_without_history(tmp_path):
    from src.api import server
    with patch.object(server, 'get_support_history_path', return_value=tmp_path / 'history.json'):
        response = TestClient(server.app).get('/api/support/report')
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/plain')
    assert 'attachment;' in response.headers['content-disposition']
    assert response.headers['cache-control'] == 'no-store'
    assert 'Sin fallos registrados' in response.text
    assert str(tmp_path) not in response.text


def test_failures_persist_without_private_request_content(tmp_path):
    from src.api.support_report import SupportHistory, SupportReportMiddleware
    history = SupportHistory(tmp_path / 'history.json')
    app = FastAPI()
    app.add_middleware(SupportReportMiddleware, history_provider=lambda: history)

    @app.post('/api/campaigns/{name}')
    def failure(name: str):
        raise HTTPException(422, detail='secret-token private-story C:/Users/Private/audio.wav')

    @app.get('/api/audio/crash')
    def crash():
        raise RuntimeError('secret-token private-story')

    client = TestClient(app, raise_server_exceptions=False)
    assert client.post('/api/campaigns/Markus?key=secret-token',
                       json={'text': 'private-story'}, headers={'Authorization': 'secret-token'}).status_code == 422
    assert client.get('/api/audio/crash').status_code == 500
    report = SupportHistory(history.path).render('3.0.0')
    assert 'campaigns | POST | HTTP 422' in report
    assert 'audio | GET | HTTP 500' in report
    for secret in ('secret-token', 'private-story', 'Markus', 'Private', str(tmp_path)):
        assert secret not in report


def test_history_is_bounded_and_does_not_read_raw_logs(tmp_path):
    from src.api.support_report import SupportHistory
    history = SupportHistory(tmp_path / 'history.json')
    (tmp_path / 'server.log').write_text('secret-token private-story', encoding='utf8')
    for _ in range(205):
        history.record('drive', 'GET', 503)
    report = history.render('3.0.0')
    assert report.count('HTTP 503') == 200
    assert history.path.stat().st_size < 65536
    assert 'secret-token' not in report
    history.path.write_text('[{"module":"secret-token","status":503}]', encoding='utf8')
    assert 'secret-token' not in history.render('3.0.0')


def test_history_write_failure_does_not_change_api_response(tmp_path):
    from src.api.support_report import SupportHistory, SupportReportMiddleware
    history = SupportHistory(tmp_path / 'blocked' / 'history.json')
    (tmp_path / 'blocked').write_text('not a directory', encoding='utf8')
    app = FastAPI()
    app.add_middleware(SupportReportMiddleware, history_provider=lambda: history)

    @app.get('/api/audio/failure')
    def failure():
        raise HTTPException(409, 'original error')

    assert TestClient(app).get('/api/audio/failure').status_code == 409
    assert 'audio | GET | HTTP 409' in history.render('3.0.0')
    assert 'no pudo guardarse' in history.render('3.0.0')


def test_background_task_failures_are_reported_without_content(tmp_path):
    from src.api import server
    with patch.object(server, 'get_support_history_path', return_value=tmp_path / 'history.json'):
        with patch.dict(server.task_progress_state, {}, clear=True):
            server.set_task_error('private-task-id', 'private-story secret-token',
                                  error_type='GeminiUnavailable', details='private-story')
            response = TestClient(server.app).get('/api/support/report')
    assert 'processing | TASK | Fallo de tarea' in response.text
    assert 'GeminiUnavailable' in response.text
    assert 'private-story' not in response.text
    assert 'secret-token' not in response.text
    assert 'private-task-id' not in response.text
