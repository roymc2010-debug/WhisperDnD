"""Use synthetic files only: independent chunk jobs and recoverable campaign removal."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.storage.campaign_manager import CampaignManager
from src.transcription.groq_whisper import clean_groq_chunks, slice_audio_for_groq, split_dual_channel_audio


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    for key in ("INPUT", "OUTPUT", "CAMPAIGNS", "QUOTA"):
        monkeypatch.setenv(f"WHISPER_{key}_DIR", str(tmp_path / key.lower()))


def synthetic_ffmpeg(command, **kwargs):
    destination = Path(command[-1].replace("%03d", "000"))
    destination.write_bytes(b"synthetic chunk")


def test_segmenting_another_recording_preserves_first_jobs_chunks(tmp_path, monkeypatch):
    monkeypatch.setattr("src.transcription.groq_whisper.subprocess.run", synthetic_ffmpeg)
    monkeypatch.setattr("src.transcription.groq_whisper.shutil.which", lambda _: "ffmpeg")
    audio = tmp_path / "large.m4a"
    with audio.open("wb") as stream:
        stream.truncate(25 * 1024 * 1024)
    first = slice_audio_for_groq(str(audio))
    second = slice_audio_for_groq(str(audio))
    assert first != second
    assert Path(first[0]).read_bytes() == b"synthetic chunk"
    clean_groq_chunks(second)
    assert Path(first[0]).is_file()
    assert not Path(second[0]).exists()
    assert audio.stat().st_size == 25 * 1024 * 1024


def test_chunk_cleanup_cannot_delete_original_audio(tmp_path):
    audio = tmp_path / "original.wav"
    audio.write_bytes(b"original")
    clean_groq_chunks([str(audio)])
    assert audio.read_bytes() == b"original"


def test_reprocessing_the_same_stereo_recording_uses_independent_channel_files(tmp_path, monkeypatch):
    audio = tmp_path / "original.wav"
    audio.write_bytes(b"synthetic stereo source")
    def fake_split(command, **kwargs):
        for argument in command:
            if str(argument).endswith(("_ch0_mic.mp3", "_ch1_discord.mp3")):
                Path(argument).write_bytes(b"synthetic channel")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr("src.transcription.groq_whisper.subprocess.run", fake_split)
    first = split_dual_channel_audio(str(audio))
    second = split_dual_channel_audio(str(audio))
    assert set(first).isdisjoint(second)
    assert all(Path(file).read_bytes() == b"synthetic channel" for file in first + second)
    assert audio.read_bytes() == b"synthetic stereo source"


def test_unspecified_cleanup_does_not_delete_another_jobs_fragments(tmp_path):
    chunk = tmp_path / "input" / "chunks" / "chunk_000.mp3"
    chunk.parent.mkdir(parents=True)
    chunk.write_bytes(b"unowned legacy fragment")
    clean_groq_chunks()
    assert chunk.read_bytes() == b"unowned legacy fragment"


def test_deleted_campaign_is_absent_from_both_active_formats_and_recoverable():
    manager = CampaignManager()
    manager.record_session("Mesa", {"chronicle_text": "Encontramos una llave."}, session_number=1)
    recording = manager.get_campaign_dir("Mesa") / "recordings" / "original.wav"
    recording.write_bytes(b"original recording")
    mirror_bytes = manager.get_campaign_path("Mesa").read_bytes()
    session_bytes = manager.get_modular_paths("Mesa")["sessions_dir"].joinpath("session_1.json").read_bytes()
    assert manager.delete_campaign("Mesa", delete_exports=False)
    assert not manager.get_campaign_path("Mesa").exists()
    assert not manager.get_campaign_dir("Mesa").exists()
    assert manager.list_campaigns() == []
    archives = list((manager.campaigns_dir / "backups" / "deleted_campaigns").iterdir())
    assert len(archives) == 1
    archive = archives[0]
    assert (archive / "mesa.json").read_bytes() == mirror_bytes
    assert (archive / "mesa" / "sessions" / "session_1.json").read_bytes() == session_bytes
    assert (archive / "mesa" / "recordings" / "original.wav").read_bytes() == b"original recording"


def test_campaign_removal_does_not_touch_unrelated_exports():
    manager = CampaignManager()
    manager.save_campaign(manager.load_campaign("Mesa"))
    unrelated = manager.output_dir / "otra_mesa_grimorio.md"
    unrelated.write_text("Otra campaña", encoding="utf8")
    assert manager.delete_campaign("Mesa")
    assert unrelated.read_text(encoding="utf8") == "Otra campaña"


def test_campaign_removal_rejects_parent_directory_name():
    manager = CampaignManager()
    with pytest.raises(ValueError):
        manager.delete_campaign("..")
