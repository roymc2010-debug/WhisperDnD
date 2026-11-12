"""Installed quota and local-model writes stay in a synthetic user profile."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from src.storage import quota_tracker
from src.transcription import local_whisper


@pytest.fixture
def installed(tmp_path, monkeypatch):
    resources = tmp_path / 'Program Files' / 'WhisperDnD' / '_internal'
    (resources / 'data').mkdir(parents=True)
    (resources / 'data' / 'system_quota.json').write_text('legacy-do-not-import', encoding='utf8')
    other = tmp_path / 'Otro directorio'
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(quota_tracker, '__file__', str(resources / 'src/storage/quota_tracker.py'))
    monkeypatch.setattr(local_whisper, '__file__', str(resources / 'src/transcription/local_whisper.py'))
    monkeypatch.delenv('WHISPER_QUOTA_DIR', raising=False)
    monkeypatch.delenv('WHISPER_DOWNLOAD_ROOT', raising=False)
    profile = tmp_path / 'Usuarios' / 'María' / 'AppData' / 'Local'
    monkeypatch.setenv('LOCALAPPDATA', str(profile))
    return resources, profile, other


def test_installed_quota_writes_only_own_profile(installed, monkeypatch):
    resources, profile, other = installed
    before = {p.relative_to(resources): p.read_bytes() for p in resources.rglob('*') if p.is_file()}
    quota_tracker.record_gemini_tokens(125)
    quota_tracker.record_groq_audio_seconds(42.5)
    path = profile / 'WhisperDnD/quota/system_quota.json'
    assert quota_tracker._get_ledger_path() == path
    data = json.loads(path.read_text(encoding='utf8'))
    assert data['gemini_tokens_used'] == 125
    assert data['groq_seconds_used'] == 42.5
    assert not list(other.iterdir())
    assert before == {p.relative_to(resources): p.read_bytes() for p in resources.rglob('*') if p.is_file()}
    second = profile.parent / 'Segundo usuario'
    monkeypatch.setenv('LOCALAPPDATA', str(second))
    quota_tracker.record_gemini_tokens(7)
    assert json.loads((second / 'WhisperDnD/quota/system_quota.json').read_text())['gemini_tokens_used'] == 7
    assert json.loads(path.read_text())['gemini_tokens_used'] == 125


def test_installed_model_is_lazy_and_uses_own_profile(installed, monkeypatch):
    resources, profile, other = installed
    calls = []
    def fake_model(**kwargs):
        calls.append(kwargs)
        Path(kwargs['download_root'], 'synthetic-model.bin').write_bytes(b'synthetic')
        return object()
    monkeypatch.setitem(sys.modules, 'faster_whisper', SimpleNamespace(WhisperModel=fake_model))
    transcriber = local_whisper.LocalWhisperTranscriber(device='cpu')
    expected = profile / 'WhisperDnD/models'
    assert Path(transcriber.download_root) == expected
    assert not expected.exists(), 'constructing the transcriber must not download or initialize a model'
    model = transcriber.model
    assert transcriber.model is model
    assert len(calls) == 1
    assert calls[0]['download_root'] == str(expected)
    assert (expected / 'synthetic-model.bin').is_file()
    assert not (resources / 'models').exists()
    assert not list(other.iterdir())
    monkeypatch.setenv('LOCALAPPDATA', str(profile.parent / 'Second profile'))
    assert Path(local_whisper.LocalWhisperTranscriber().download_root) != expected


def test_explicit_quota_override_still_wins(installed, tmp_path, monkeypatch):
    target = tmp_path / 'Cuotas explícitas'
    monkeypatch.setenv('WHISPER_QUOTA_DIR', str(target))
    assert quota_tracker._get_ledger_path() == target / 'system_quota.json'
    assert target.is_dir()


def test_explicit_model_overrides_still_win(installed, tmp_path, monkeypatch):
    target = tmp_path / 'Modelos explícitos'
    monkeypatch.setenv('WHISPER_DOWNLOAD_ROOT', str(target))
    assert local_whisper.LocalWhisperTranscriber().download_root == str(target)
    assert local_whisper.LocalWhisperTranscriber(download_root='custom-models').download_root == 'custom-models'
    assert not target.exists()


def test_development_quota_and_model_defaults_are_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'frozen', False, raising=False)
    monkeypatch.delenv('WHISPER_QUOTA_DIR', raising=False)
    monkeypatch.delenv('WHISPER_DOWNLOAD_ROOT', raising=False)
    monkeypatch.setattr(quota_tracker, '__file__', str(tmp_path / 'src/storage/quota_tracker.py'))
    monkeypatch.chdir(tmp_path)
    assert quota_tracker._get_ledger_path() == tmp_path / 'data/system_quota.json'
    transcriber = local_whisper.LocalWhisperTranscriber()
    assert transcriber.download_root == 'models'
    assert not (tmp_path / 'models').exists()


@pytest.mark.parametrize('component', ['quota', 'model'])
def test_installed_missing_profile_does_not_fall_back_to_resources(installed, monkeypatch, component):
    monkeypatch.delenv('LOCALAPPDATA', raising=False)
    with pytest.raises(ValueError, match='LOCALAPPDATA'):
        if component == 'quota':
            quota_tracker._get_ledger_path()
        else:
            local_whisper.LocalWhisperTranscriber()
