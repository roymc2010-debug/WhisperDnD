"""Manual desktop mode uses the same storage contract as the future EXE."""
import json
import asyncio
from pathlib import Path
import sys
from unittest.mock import Mock, patch

import pytest

from src.runtime_paths import resolve_runtime_paths


@pytest.fixture
def desktop_profile(tmp_path, monkeypatch):
    profile = tmp_path / 'Perfil de prueba María'
    monkeypatch.setenv('WHISPER_DESKTOP_MODE', '1')
    monkeypatch.setenv('WHISPER_DESKTOP_DATA_ROOT', str(profile))
    for key in ('INPUT', 'OUTPUT', 'CAMPAIGNS', 'QUOTA'):
        monkeypatch.delenv(f'WHISPER_{key}_DIR', raising=False)
    monkeypatch.delenv('WHISPER_DOWNLOAD_ROOT', raising=False)
    monkeypatch.chdir(tmp_path)
    return profile


def test_manual_profile_matches_installed_layout_without_faking_sys_frozen(desktop_profile):
    paths = resolve_runtime_paths()
    assert paths.data_dir == desktop_profile
    assert paths.config_dir == desktop_profile / 'config'
    assert paths.input_dir == desktop_profile / 'recordings'
    assert paths.models_dir == desktop_profile / 'models'
    assert not desktop_profile.exists()


def test_discord_token_is_resolved_for_each_profile(desktop_profile, monkeypatch):
    from src.transcription import discord_rpc
    assert discord_rpc.get_token_file() == desktop_profile / 'config/discord-token.json'
    monkeypatch.setenv('WHISPER_DESKTOP_DATA_ROOT', str(desktop_profile.parent / 'Otro perfil'))
    assert discord_rpc.get_token_file() != desktop_profile / 'config/discord-token.json'


def test_recorder_and_timeline_mirror_stay_in_profile(desktop_profile, monkeypatch):
    from src.transcription import audio_recorder
    thread = Mock()
    thread.is_alive.return_value = False
    monkeypatch.setattr(audio_recorder.threading, 'Thread', Mock(return_value=thread))
    monkeypatch.setattr(audio_recorder, 'discord_tracker', Mock())
    audio_recorder.discord_tracker.stop_session.return_value = []
    recorder = audio_recorder.DualChannelAudioRecorder()
    path = Path(recorder.start(campaign_name='QA', session_number=1))
    assert path.parent == desktop_profile / 'campaigns/qa/recordings'
    path.write_bytes(b'synthetic-wav')
    recorder.stop()
    assert path.with_suffix('.timeline.json').is_file()
    assert (desktop_profile / 'recordings' / path.name).is_file()
    assert not (Path.cwd() / 'data/input').exists()


def test_reporter_uses_profile_exports(desktop_profile):
    from src.transcription.test_reporter import get_transcription_tests_dir
    assert get_transcription_tests_dir() == desktop_profile / 'exports/transcription-tests'


def test_groq_chunks_use_profile_and_explicit_cleanup(desktop_profile, tmp_path, monkeypatch):
    from src.transcription import groq_whisper
    audio = tmp_path / 'synthetic.mp3'
    with audio.open('wb') as stream:
        stream.truncate(25 * 1024 * 1024)
    monkeypatch.setattr(groq_whisper.shutil, 'which', lambda name: 'synthetic-ffmpeg')
    def segment(cmd, **kwargs):
        pattern = Path(cmd[-1])
        (pattern.parent / 'chunk_000.mp3').write_bytes(b'synthetic-audio')
        return Mock(returncode=0)
    monkeypatch.setattr(groq_whisper.subprocess, 'run', segment)
    chunks = groq_whisper.slice_audio_for_groq(str(audio))
    assert all(Path(p).is_relative_to(desktop_profile / 'recordings/chunks') for p in chunks)
    assert all(Path(p).is_file() for p in chunks)
    groq_whisper.clean_groq_chunks(chunks)
    assert not any(Path(p).exists() for p in chunks)
    assert audio.is_file()


def test_drive_and_local_model_use_manual_profile(desktop_profile, tmp_path):
    from src.storage.drive_client import ensure_google_token_file
    from src.transcription.local_whisper import LocalWhisperTranscriber
    assert ensure_google_token_file(project_root=tmp_path) == desktop_profile / 'config/token.json'
    assert Path(LocalWhisperTranscriber().download_root) == desktop_profile / 'models'


def test_relative_manual_root_is_rejected(monkeypatch):
    monkeypatch.setenv('WHISPER_DESKTOP_MODE', '1')
    monkeypatch.setenv('WHISPER_DESKTOP_DATA_ROOT', 'relative-data')
    with pytest.raises(ValueError, match='absoluta'):
        resolve_runtime_paths()


def test_youtube_default_cache_stays_in_manual_profile(desktop_profile):
    from src.transcription.youtube_downloader import download_youtube_audio
    target = desktop_profile / 'recordings/dQw4w9WgXcQ.mp3'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'fake-audio' * 2000)
    assert download_youtube_audio('https://youtu.be/dQw4w9WgXcQ') == str(target)


def test_academic_read_does_not_discover_legacy_notes(desktop_profile, tmp_path, monkeypatch):
    from src.api import server
    from src.api.routers import academic
    from fastapi import HTTPException
    resources = tmp_path / 'resources'
    legacy = resources / 'outputs/apuntes_private.md'
    legacy.parent.mkdir(parents=True)
    legacy.write_text('# Private notes\n' + 'private ' * 110, encoding='utf8')
    monkeypatch.setattr(server, 'project_root', resources)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(academic.get_academic_note(legacy.name))
    assert exc.value.status_code == 404
    assert legacy.is_file()


def test_discard_does_not_delete_legacy_export(desktop_profile, tmp_path, monkeypatch):
    from src.api import server
    from src.api.routers.drive import discard_transcription_endpoint
    resources = tmp_path / 'resources'
    legacy = resources / 'outputs/private.txt'
    legacy.parent.mkdir(parents=True)
    legacy.write_text('private transcript', encoding='utf8')
    monkeypatch.setattr(server, 'project_root', resources)
    asyncio.run(discard_transcription_endpoint(server.DiscardTranscriptRequest(filename=legacy.name)))
    assert legacy.read_text(encoding='utf8') == 'private transcript'
