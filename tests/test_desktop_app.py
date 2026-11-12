"""Desktop launch preparation without real browser, processes or cloud requests."""
import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import Mock

import pytest


def test_manual_environment_is_private_and_does_not_inherit_developer_keys(tmp_path):
    from src.desktop_app import configure_profile
    environment = {'LOCALAPPDATA': str(tmp_path), 'GROQ_API_KEY': 'private',
                   'GOOGLE_TOKEN_JSON': 'private', 'WHISPER_INPUT_DIR': 'old-data',
                   'WHISPER_OUTPUT_DIR': 'old-output', 'RENDER_EXTERNAL_URL': 'https://old'}
    paths = configure_profile(manual=True, environ=environment)
    assert paths.data_dir == tmp_path / 'WhisperDnD-Pruebas'
    assert paths.input_dir == paths.data_dir / 'recordings'
    assert environment['PYTHON_DOTENV_DISABLED'] == '1'
    assert environment['WHISPER_SKIP_STARTUP_DRIVE_SYNC'] == '1'
    assert not any(key in environment for key in ('GROQ_API_KEY', 'GOOGLE_TOKEN_JSON', 'RENDER_EXTERNAL_URL'))
    assert not paths.data_dir.exists()


def test_lease_excludes_second_instance_and_releases_after_close(tmp_path):
    from src.desktop_app import InstanceLease
    path = tmp_path / 'profile/config/desktop.lock'
    with InstanceLease(path) as first:
        assert first.acquired
        with InstanceLease(path) as second:
            assert not second.acquired
    with InstanceLease(path) as third:
        assert third.acquired


def test_occupied_port_is_not_reused_or_killed():
    from src.desktop_app import reserve_listener
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        occupied.listen()
        with pytest.raises(RuntimeError, match='ocupado'):
            reserve_listener(occupied.getsockname()[1])


def test_readiness_requires_matching_instance_and_app(monkeypatch):
    from src import desktop_app
    payload = {'status': 'alive', 'application': 'WhisperDnD', 'instance_id': 'expected'}
    response = Mock(status=200)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.side_effect = lambda n: json.dumps(payload).encode()
    monkeypatch.setattr(desktop_app.HTTP, 'open', Mock(return_value=response))
    assert desktop_app.instance_ready(8082, 'expected')
    assert not desktop_app.instance_ready(8082, 'different')
    payload['application'] = 'Other app'
    assert not desktop_app.instance_ready(8082, 'expected')


def test_failed_bind_does_not_import_backend_or_open_browser(tmp_path, monkeypatch):
    from src import desktop_app
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setattr(os, 'environ', dict(os.environ))
    monkeypatch.setattr(desktop_app, 'reserve_listener', Mock(side_effect=RuntimeError('Puerto ocupado')))
    browser = Mock()
    monkeypatch.setattr(desktop_app, 'open_app_window', browser)
    with pytest.raises(RuntimeError, match='ocupado'):
        desktop_app.run(manual=True, open_browser=True)
    browser.assert_not_called()


def test_preflight_does_not_load_backend_or_download_models(tmp_path, monkeypatch):
    from src import desktop_app
    before = set(sys.modules)
    report = desktop_app.preflight(environ={'LOCALAPPDATA': str(tmp_path)}, manual=True)
    assert 'WhisperDnD' in report
    assert 'Pruebas' in report
    assert 'src.api.server' in before or 'src.api.server' not in sys.modules
    assert not (tmp_path / 'WhisperDnD-Pruebas').exists()


def test_silent_desktop_start_provides_streams_for_uvicorn(tmp_path, monkeypatch):
    from src import desktop_app
    from src.api import server
    monkeypatch.setattr(os, 'environ', dict(os.environ, LOCALAPPDATA=str(tmp_path)))
    seen = []
    def configure(*args, **kwargs):
        seen.append(sys.stdout is not None and sys.stderr is not None)
        return Mock()
    from types import SimpleNamespace
    class FakeServer:
        def __init__(self, config):
            self.should_exit = False
        def run(self, **kwargs):
            pass
    fake = SimpleNamespace(Config=configure, Server=FakeServer)
    monkeypatch.setitem(sys.modules, 'uvicorn', fake)
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    with monkeypatch.context() as state:
        state.setattr(sys, 'stdout', None)
        state.setattr(sys, 'stderr', None)
        desktop_app.run(manual=True, port=port, open_browser=False)
    assert seen == [True]


def test_close_guard_includes_recording_processing_and_transfers():
    from types import SimpleNamespace
    from src.desktop_app import desktop_is_busy
    recorder = SimpleNamespace(is_recording=False)
    state = SimpleNamespace(desktop_active_requests=0, desktop_background_tasks=set())
    assert not desktop_is_busy(recorder, {}, state)
    recorder.is_recording = True
    assert desktop_is_busy(recorder, {}, state)
    recorder.is_recording = False
    assert desktop_is_busy(recorder, {'job': {'status': 'running'}}, state)
    state.desktop_active_requests = 1
    assert desktop_is_busy(recorder, {}, state)
    state.desktop_active_requests = 0
    state.desktop_background_tasks.add(object())
    assert desktop_is_busy(recorder, {}, state)
