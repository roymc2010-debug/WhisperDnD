"""Explicit storage directories keep previews and tests out of live data."""

import json
import os
from unittest.mock import patch

from src.storage import quota_tracker
from src.transcription import audio_recorder
from scripts.preview_design import configure_environment


def test_recorder_timeline_mirror_respects_input_directory(tmp_path, monkeypatch):
    fake_root = tmp_path / "project"
    monkeypatch.setattr(audio_recorder, "__file__", str(fake_root / "src/transcription/audio_recorder.py"))
    input_dir = tmp_path / "isolated-input"
    monkeypatch.setenv("WHISPER_INPUT_DIR", str(input_dir))
    with patch("threading.Thread") as thread:
        thread.return_value.is_alive.side_effect = [True, False]
        recorder = audio_recorder.DualChannelAudioRecorder()
        recorder.start(str(tmp_path / "recording.wav"))
        recorder.stop()

    assert (input_dir / "recording.timeline.json").is_file()
    assert not (fake_root / "data/input/recording.timeline.json").exists()


def test_quota_writes_respect_isolated_directory(tmp_path, monkeypatch):
    fake_root = tmp_path / "project"
    monkeypatch.setattr(quota_tracker, "__file__", str(fake_root / "src/storage/quota_tracker.py"))
    quota_dir = tmp_path / "isolated-quota"
    monkeypatch.setenv("WHISPER_QUOTA_DIR", str(quota_dir))

    quota_tracker.record_audio_sample(120, 50, source="recording", workspace="dnd")

    ledger = quota_dir / "system_quota.json"
    assert ledger.is_file()
    data = json.loads(ledger.read_text(encoding="utf-8"))
    assert data["audio_samples"][0]["tokens_used"] == 50
    assert not (fake_root / "data/system_quota.json").exists()


def test_preview_keeps_quota_writes_in_its_own_storage(tmp_path):
    preview_dir = tmp_path / "preview"
    with patch.dict(os.environ, {"WHISPER_QUOTA_DIR": str(tmp_path / "other-copy")}):
        configure_environment(preview_dir)
        quota_tracker.record_audio_sample(120, 50, source="recording", workspace="dnd")

    assert (preview_dir / "quota/system_quota.json").is_file()
    assert not (tmp_path / "other-copy/system_quota.json").exists()
