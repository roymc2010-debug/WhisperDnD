"""Recording regressions: synthetic audio, isolated storage, no provider calls."""
import datetime as dt
import importlib
import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from src.api import server


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    for key in ("INPUT", "OUTPUT", "CAMPAIGNS", "QUOTA"):
        folder = tmp_path / key.lower()
        folder.mkdir()
        monkeypatch.setenv(f"WHISPER_{key}_DIR", str(folder))
    monkeypatch.setattr(server, "trigger_drive_sync_background", Mock())


def recording_module():
    spec = importlib.util.find_spec("src.transcription.recording_files")
    assert spec is not None, "Falta la gestión independiente de nombres y fecha de grabación"
    return importlib.import_module("src.transcription.recording_files")


def test_second_part_promotes_first_and_preserves_capture_date(tmp_path):
    mod = recording_module()
    folder = tmp_path / "recordings"
    first = mod.create_recording_path(folder, "Candlekeep 2.0", 4, dt.datetime(2026, 10, 12, 20, 30))
    assert first.name == "Candlekeep_2.0_Sesion_04_12-10-26.wav"
    first.write_bytes(b"first original")
    first.with_suffix(".timeline.json").write_text(json.dumps({"audio_file": first.name, "speaking_log": [{"time": 1}]}))
    second = mod.create_recording_path(folder, "Candlekeep 2.0", 4, dt.datetime(2026, 10, 13, 0, 30))
    promoted = first.with_stem(first.stem + "_Parte_01")
    assert not first.exists()
    assert promoted.read_bytes() == b"first original"
    assert second.name == "Candlekeep_2.0_Sesion_04_13-10-26_Parte_02.wav"
    assert mod.get_recorded_at(promoted).startswith("2026-10-12")
    assert json.loads(promoted.with_suffix(".timeline.json").read_text())["audio_file"] == promoted.name
    assert mod.create_recording_path(folder, "Candlekeep 2.0", 4, dt.datetime(2026, 10, 13, 1)).name.endswith("_Parte_03.wav")


def test_name_conflict_never_overwrites_unmanaged_audio(tmp_path):
    mod = recording_module()
    audio = tmp_path / "Mesa_Sesion_01_03-11-26.wav"
    audio.write_bytes(b"unmanaged original")
    with pytest.raises(FileExistsError):
        mod.create_recording_path(tmp_path, "Mesa", 1, dt.datetime(2026, 11, 3))
    assert audio.read_bytes() == b"unmanaged original"


def test_legacy_capture_date_ignores_processing_mtime(tmp_path):
    mod = recording_module()
    audio = tmp_path / "session_20261012_203000.wav"
    audio.write_bytes(b"old audio")
    assert mod.get_recorded_at(audio) == "2026-10-12T20:30:00"
    assert mod.get_recorded_at(tmp_path / "unknown.mp3") is None


@pytest.mark.parametrize("engine_fails", [False, True])
def test_processing_never_changes_original_bytes_or_date(tmp_path, monkeypatch, engine_fails):
    audio = tmp_path / "session_20261012_203000.wav"
    audio.write_bytes(b"original stereo")
    os.utime(audio, (1791837000, 1791837000))
    before = audio.stat().st_mtime_ns
    seen = []
    def normalize(path):
        Path(path).write_bytes(b"normalized derivative")
    def transcribe(path, **kwargs):
        seen.append(Path(path))
        assert Path(path).read_bytes() == b"normalized derivative"
        if engine_fails:
            raise RuntimeError("synthetic provider failure")
        return {"text": "La tripulación encuentra una llave.", "segments": [], "duration": 4, "language": "es"}
    monkeypatch.setattr("src.transcription.audio_recorder.normalize_dual_channel_audio", normalize)
    monkeypatch.setattr(server, "GroqWhisperTranscriber", lambda **kw: Mock(transcribe=transcribe))
    monkeypatch.setattr(server, "create_transcription_test_report", lambda **kw: {})
    if engine_fails:
        with pytest.raises(RuntimeError):
            server.transcribe_audio_pipeline(str(audio), groq_api_key="fake")
    else:
        server.transcribe_audio_pipeline(str(audio), groq_api_key="fake")
    assert audio.read_bytes() == b"original stereo"
    assert audio.stat().st_mtime_ns == before
    assert seen and seen[0] != audio and not seen[0].exists()


def test_local_list_uses_recording_date_not_mtime(monkeypatch):
    audio = server.get_data_input_dir() / "session_20261012_203000.wav"
    audio.write_bytes(b"a" * 500)
    response = TestClient(server.app).get("/api/audio/local-recordings")
    item = response.json()["files"][0]
    assert item["created_at"] == "12/10/2026 20:30"
    assert item["recorded_at"] == "2026-10-12T20:30:00"


def test_ordered_parts_generate_one_session_with_original_date(monkeypatch):
    paths = []
    for i in (1, 2):
        p = server.get_data_input_dir() / f"session_20261012_20300{i}.wav"
        p.write_bytes(bytes([i]) * 500)
        paths.append(p)
    calls = []
    def transcribe(audio_path, **kwargs):
        calls.append(Path(audio_path).name)
        return {"text": f"Hecho {len(calls)}", "formatted_transcript": f"Hecho {len(calls)}", "segments": [{"start": 0, "end": 2, "text": f"Hecho {len(calls)}", "speaker": "DM"}], "duration": 3, "language": "es"}
    process = Mock(return_value={"session_number": 4, "campaign_state": {}, "session_chapter": {}})
    monkeypatch.setattr(server, "transcribe_audio_pipeline", transcribe)
    monkeypatch.setattr(server, "process_session_for_campaign", process)
    monkeypatch.setattr(server, "extract_client_api_keys", lambda _: ("fake", "fake"))
    monkeypatch.setattr(server, "validate_api_keys_or_raise", lambda *a, **k: None)
    response = TestClient(server.app).post("/api/transcribe/file", data={"existing_filenames_json": json.dumps([p.name for p in paths]), "campaign_name": "Mesa", "session_number": "4", "roster_json": "[]"})
    assert response.status_code == 200, response.text
    assert calls == [p.name for p in paths]
    assert process.call_count == 1
    kwargs = process.call_args.kwargs
    assert kwargs["session_number"] == 4
    assert kwargs["custom_date"].startswith("2026-10-12")
    assert [p["filename"] for p in kwargs["source_recordings"]] == [p.name for p in paths]
    assert kwargs["transcript_text"].index("Hecho 1") < kwargs["transcript_text"].index("Hecho 2")
    assert response.json()["duration"] == 6
    assert response.json()["segments"][1]["start"] == 3
    assert all(p.read_bytes() == bytes([i]) * 500 for i, p in enumerate(paths, 1))
    assert all((server.get_data_campaigns_dir() / "mesa" / "recordings" / p.name).exists() for p in paths)


@pytest.mark.parametrize("capture,expected", [("2026-10-12T20:30:00", "12/10/2026"), (None, "")])
def test_session_date_comes_from_capture_not_generated_or_current_date(monkeypatch, capture, expected):
    manager = server.CampaignManager()
    monkeypatch.setattr(server, "prepare_session_transcript", lambda text, **kw: text)
    monkeypatch.setattr(server, "GeminiTTRPGSummarizer", lambda **kw: Mock(model_name="offline-model", generate_campaign_session=Mock(return_value={"session_chapter": {"title": "Llave", "date": "03/11/2026", "chronicle_text": "Encuentran una llave."}})))
    monkeypatch.setattr(server, "export_living_journal_docx", lambda _: None)
    monkeypatch.setattr(server, "export_living_journal_md", lambda _: None)
    result = server.process_session_for_campaign("Mesa", "Encuentran una llave.", session_number=4, custom_date=capture, audio_source="file")
    from src.storage.session_review import load_review, apply_review
    rid = result["session_chapter"]["review_id"]
    draft = load_review(server.get_data_output_dir(), rid)
    apply_review(manager, server.get_data_output_dir(), rid, draft["revision"], [], {})
    saved = manager.load_campaign("Mesa")["sessions"][0]
    assert saved["date"] == expected
    assert saved["processed_at"]


def test_upload_with_existing_name_preserves_original(monkeypatch):
    original = server.get_data_input_dir() / "session_20261012_203000.wav"
    original.write_bytes(b"original" * 100)
    monkeypatch.setattr(server, "extract_client_api_keys", lambda _: ("fake", "fake"))
    monkeypatch.setattr(server, "validate_api_keys_or_raise", lambda *a, **k: None)
    monkeypatch.setattr(server, "transcribe_audio_pipeline", Mock(side_effect=RuntimeError("stop before generation")))
    TestClient(server.app).post("/api/transcribe/file", files={"file": (original.name, b"new audio" * 100, "audio/wav")})
    assert original.read_bytes() == b"original" * 100


def test_failed_second_part_does_not_generate_or_save_campaign(monkeypatch):
    paths = [server.get_data_input_dir() / f"part{i}.wav" for i in (1, 2)]
    for path in paths:
        path.write_bytes(b"synthetic original" * 100)
    monkeypatch.setattr(server, "extract_client_api_keys", lambda _: ("fake", "fake"))
    monkeypatch.setattr(server, "validate_api_keys_or_raise", lambda *a, **k: None)
    monkeypatch.setattr(server, "transcribe_audio_pipeline", Mock(side_effect=[{"text": "Llave", "segments": [], "duration": 3}, RuntimeError("part 2 failed")]))
    process = Mock()
    monkeypatch.setattr(server, "process_session_for_campaign", process)
    response = TestClient(server.app).post("/api/transcribe/file", data={"existing_filenames_json": json.dumps([p.name for p in paths]), "campaign_name": "Mesa"})
    assert response.status_code == 500
    process.assert_not_called()
    assert all(p.exists() for p in paths)


def test_timeline_from_different_audio_cannot_contaminate_current_part(tmp_path, monkeypatch):
    from src.transcription.audio_recorder import load_timeline_for_audio
    audio = tmp_path / "selected" / "same.wav"
    audio.parent.mkdir()
    audio.write_bytes(b"current")
    other = server.get_data_input_dir() / audio.name
    other.write_bytes(b"different recording")
    other.with_suffix(".timeline.json").write_text(json.dumps({"speaking_log": [{"name": "Wrong campaign"}]}))
    assert load_timeline_for_audio(audio) is None


def test_timeline_lookup_honors_configured_directories(tmp_path):
    from src.transcription.audio_recorder import load_timeline_for_audio
    audio = tmp_path / "selected" / "same.wav"
    audio.parent.mkdir()
    audio.write_bytes(b"current")
    mirror = server.get_data_input_dir() / audio.name
    mirror.write_bytes(audio.read_bytes())
    mirror.with_suffix(".timeline.json").write_text(json.dumps({"audio_file": audio.name, "speaking_log": [{"time": 1}]}))
    assert load_timeline_for_audio(audio) == [{"time": 1}]


def test_stop_does_not_process_audio_until_capture_thread_has_flushed(monkeypatch):
    from src.transcription.audio_recorder import DualChannelAudioRecorder
    recorder = DualChannelAudioRecorder()
    recorder._is_recording = True
    recorder._mode = "class"
    recorder._thread = Mock(is_alive=Mock(return_value=True))
    with pytest.raises(RuntimeError, match="guardando"):
        recorder.stop()
    assert recorder.is_recording


def test_failed_promotion_restores_audio_timeline_and_metadata(tmp_path):
    mod = recording_module()
    first = mod.create_recording_path(tmp_path, "Mesa", 4, dt.datetime(2026, 11, 3))
    first.write_bytes(b"first original")
    metadata = first.with_suffix(".recording.json").read_bytes()
    first.with_suffix(".timeline.json").write_bytes(b"invalid legacy json")
    with pytest.raises(ValueError):
        mod.create_recording_path(tmp_path, "Mesa", 4, dt.datetime(2026, 11, 3, 21))
    assert first.read_bytes() == b"first original"
    assert first.with_suffix(".timeline.json").read_bytes() == b"invalid legacy json"
    assert first.with_suffix(".recording.json").read_bytes() == metadata
    assert not list(tmp_path.glob("*_Parte_*.wav"))


def test_recorder_uses_campaign_session_name_without_starting_native_capture(tmp_path, monkeypatch):
    from src.transcription.audio_recorder import DualChannelAudioRecorder
    monkeypatch.setattr("src.transcription.audio_recorder.threading.Thread", Mock())
    monkeypatch.setattr("src.transcription.audio_recorder.discord_tracker.start_session", Mock())
    recorder = DualChannelAudioRecorder()
    audio = Path(recorder.start(campaign_name="Mesa", session_number=4))
    assert audio.parent == server.get_data_campaigns_dir() / "mesa" / "recordings"
    assert audio.name.startswith("Mesa_Sesion_04_")
    assert "Parte" not in audio.name
    assert recording_module().get_recorded_at(audio)


def test_browser_capture_uses_start_date_and_campaign_name(monkeypatch):
    monkeypatch.setattr(server, "extract_client_api_keys", lambda _: ("fake", "fake"))
    monkeypatch.setattr(server, "validate_api_keys_or_raise", lambda *a, **k: None)
    transcribe = Mock(side_effect=RuntimeError("stop before paid generation"))
    monkeypatch.setattr(server, "transcribe_audio_pipeline", transcribe)
    response = TestClient(server.app).post("/api/transcribe/file", data={"campaign_name": "Mesa", "session_number": 4, "processing_source": "recording", "recorded_at": "2026-10-12T20:30:00"}, files={"file": ("mobile_recording_123.webm", b"synthetic" * 100, "audio/webm")})
    assert response.status_code == 500
    audio = Path(transcribe.call_args.kwargs["audio_path"])
    assert audio.name == "Mesa_Sesion_04_12-10-26.webm"
    assert recording_module().get_recorded_at(audio) == "2026-10-12T20:30:00"


def test_large_mirror_copy_does_not_block_device_requests(monkeypatch):
    import asyncio
    import shutil
    audio = server.get_data_input_dir() / "part.wav"
    audio.write_bytes(b"synthetic" * 100)
    original_copy = shutil.copyfileobj
    def copy_off_loop(*args, **kwargs):
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        return original_copy(*args, **kwargs)
    monkeypatch.setattr(shutil, "copyfileobj", copy_off_loop)
    monkeypatch.setattr(server, "extract_client_api_keys", lambda _: ("fake", "fake"))
    monkeypatch.setattr(server, "validate_api_keys_or_raise", lambda *a, **k: None)
    transcribe = Mock(side_effect=RuntimeError("stop after copy"))
    monkeypatch.setattr(server, "transcribe_audio_pipeline", transcribe)
    TestClient(server.app).post("/api/transcribe/file", data={"existing_filename": audio.name, "campaign_name": "Mesa"})
    assert transcribe.called, "La copia debe terminar sin bloquear el bucle de peticiones"


@pytest.mark.parametrize("endpoint", ["/api/record/stop", "/api/record/stop-and-process"])
def test_stopping_and_flushing_capture_does_not_block_event_loop(monkeypatch, endpoint):
    import asyncio
    audio = server.get_data_input_dir() / "capture.wav"
    audio.write_bytes(b"synthetic" * 200)
    called = []
    def stop():
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        called.append(True)
        return str(audio)
    monkeypatch.setattr(server, "active_recorder", Mock(is_recording=True, _file_path=str(audio), stop=stop, speaking_log=[]))
    monkeypatch.setattr(server, "extract_client_api_keys", lambda _: ("fake", "fake"))
    monkeypatch.setattr(server, "validate_api_keys_or_raise", lambda *a, **k: None)
    monkeypatch.setattr(server, "transcribe_audio_pipeline", Mock(side_effect=RuntimeError("stop after flush")))
    TestClient(server.app).post(endpoint, json={"campaign_name": "Mesa"})
    assert called == [True]


def test_existing_timeline_upload_cannot_overwrite_history(monkeypatch):
    audio = server.get_data_input_dir() / "part.wav"
    audio.write_bytes(b"synthetic" * 100)
    timeline = audio.with_suffix(".timeline.json")
    before = json.dumps({"audio_file": audio.name, "speaking_log": [{"name": "Original"}]})
    timeline.write_text(before)
    monkeypatch.setattr(server, "extract_client_api_keys", lambda _: ("fake", "fake"))
    monkeypatch.setattr(server, "validate_api_keys_or_raise", lambda *a, **k: None)
    monkeypatch.setattr(server, "transcribe_audio_pipeline", Mock(side_effect=RuntimeError("stop")))
    response = TestClient(server.app).post("/api/transcribe/file", data={"existing_filename": audio.name}, files={"timeline_file": ("part.timeline.json", b'{"speaking_log": []}', "application/json")})
    assert response.status_code == 409
    assert timeline.read_text() == before


def test_consecutive_parts_complete_their_actual_progress_share(monkeypatch):
    paths=[server.get_data_input_dir()/f'part_{i}.wav' for i in (1,2)]
    for p in paths:p.write_bytes(b'a'*500)
    checkpoints=[]
    def transcribe(audio_path,**kwargs):
        kwargs['on_progress'](55,'Transcripción de la parte completada')
        checkpoints.append(server.get_task_progress('parts-progress')['percent'])
        return {'text':'Fuente','formatted_transcript':'Fuente','segments':[],'duration':3,'language':'es'}
    monkeypatch.setattr(server,'transcribe_audio_pipeline',transcribe)
    monkeypatch.setattr(server,'process_session_for_campaign',Mock(return_value={'session_number':4,'campaign_state':{},'session_chapter':{}}))
    monkeypatch.setattr(server,'extract_client_api_keys',lambda request:('offline','offline'))
    monkeypatch.setattr(server,'validate_api_keys_or_raise',lambda *a,**k:None)
    response=TestClient(server.app).post('/api/transcribe/file',data={'existing_filenames_json':json.dumps([p.name for p in paths]),'campaign_name':'Mesa','session_number':'4','roster_json':'[]','task_id':'parts-progress'})
    assert response.status_code==200,response.text
    assert checkpoints==[28.5,55.0]
