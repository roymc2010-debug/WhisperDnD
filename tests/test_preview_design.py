"""Safety checks for isolated design data snapshots."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import pytest
spec = spec_from_file_location('preview_design', Path(__file__).parents[1] / 'scripts' / 'preview_design.py')
preview = module_from_spec(spec)
spec.loader.exec_module(preview)

def test_snapshot_never_overwrites_or_copies_credentials(tmp_path):
    source = tmp_path / 'lab'
    (source / 'data' / 'campaigns').mkdir(parents=True)
    (source / 'outputs').mkdir()
    (source / 'data' / 'campaigns' / 'mesa.json').write_text('{"last_session": 2}')
    (source / 'outputs' / 'apuntes_demo.md').write_text('# Apuntes')
    (source / 'outputs' / 'voice.wav').write_bytes(b'audio')
    (source / 'outputs' / 'token.json').write_text('private')
    (source / '.env').write_text('GROQ_API_KEY=private')
    target = tmp_path / 'preview'
    assert preview.prepare_snapshot(source, target) == 2
    (target / 'campaigns' / 'mesa.json').write_text('preview edit')
    assert preview.prepare_snapshot(source, target) == 0
    assert (target / 'campaigns' / 'mesa.json').read_text() == 'preview edit'
    assert (source / 'data' / 'campaigns' / 'mesa.json').read_text() == '{"last_session": 2}'
    assert not (target / 'output' / 'voice.wav').exists()
    assert not (target / 'output' / 'token.json').exists()
    assert not (target / '.env').exists()

def test_snapshot_rejects_source_as_destination(tmp_path):
    with pytest.raises(ValueError):
        preview.prepare_snapshot(tmp_path, tmp_path)

def test_preview_environment_does_not_reuse_external_paths_or_cloud_tokens(tmp_path, monkeypatch):
    for key in ('PYTHON_DOTENV_DISABLED', 'WHISPER_INPUT_DIR', 'WHISPER_OUTPUT_DIR'):
        monkeypatch.setenv(key, 'test-original')
    monkeypatch.setenv('WHISPER_CAMPAIGNS_DIR', '/original')
    monkeypatch.setenv('GOOGLE_TOKEN_JSON', 'private')
    monkeypatch.setenv('GOOGLE_CREDENTIALS_JSON', 'private')
    monkeypatch.setenv('GROQ_API_KEY', 'private')
    preview.configure_environment(tmp_path)
    import os
    assert os.environ['WHISPER_CAMPAIGNS_DIR'] == str((tmp_path / 'campaigns').resolve())
    assert os.environ['PYTHON_DOTENV_DISABLED'] == '1'
    assert 'GOOGLE_TOKEN_JSON' not in os.environ
    assert 'GOOGLE_CREDENTIALS_JSON' not in os.environ
    assert 'GROQ_API_KEY' not in os.environ


def test_preview_uses_a_free_port_when_requested_port_belongs_to_another_copy():
    import socket
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        occupied.listen()
        old_port = occupied.getsockname()[1]
        with preview.bind_preview_socket(old_port) as selected:
            assert selected.getsockname()[0] == '127.0.0.1'
            assert selected.getsockname()[1] != old_port
            assert selected.fileno() >= 0

@pytest.mark.parametrize('started,exiting', [(False, False), (True, True)])
def test_browser_does_not_open_an_old_server_when_preview_startup_fails(started, exiting, monkeypatch):
    from types import SimpleNamespace
    opened = []
    monkeypatch.setattr(preview.webbrowser, 'open', lambda url: opened.append(url))
    assert preview.open_preview_browser(SimpleNamespace(started=started, should_exit=exiting), 'http://127.0.0.1:8082') is False
    assert opened == []

def test_browser_opens_the_actual_preview_url_only_after_startup(monkeypatch):
    from types import SimpleNamespace
    opened = []
    monkeypatch.setattr(preview.webbrowser, 'open', lambda url: opened.append(url) or True)
    assert preview.open_preview_browser(SimpleNamespace(started=True, should_exit=False), 'http://127.0.0.1:8082') is True
    assert opened == ['http://127.0.0.1:8082']
