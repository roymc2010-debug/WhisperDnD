"""Offline volume gating: synthetic audio only, no provider calls."""
import copy
import json

import numpy as np
import pytest
import soundfile as sf


def recording(tmp_path, mic):
    path = tmp_path / "source.wav"
    # Discord stays audible even when the microphone is silent.
    sf.write(path, np.column_stack([mic, np.full(len(mic), 0.15)]), 16000,
             subtype="FLOAT")
    return path


def recognition():
    return {"text": "Gracias por ver el video. Abro la puerta.",
            "raw_text": "Original recognition evidence",
            "formatted_transcript": "Original formatted text",
            "duration": 2,
            "segments": [
                {"start": 0, "end": 1, "speaker": "[Tu / Personaje]",
                 "text": "Gracias por ver el video."},
                {"start": 0, "end": 1, "speaker": "[Discord]",
                 "text": "Abro la puerta."}]}


def gate(path, result, **kwargs):
    from src.transcription.mic_volume_gate import apply_mic_volume_gate
    return apply_mic_volume_gate(str(path), result, **kwargs)


def test_low_mic_is_excluded_but_discord_and_raw_evidence_survive(tmp_path):
    path = recording(tmp_path, np.full(32000, 0.00003))
    before = path.read_bytes()
    source = recognition()
    untouched = copy.deepcopy(source)
    result = gate(path, source)
    assert result["text"] == "Abro la puerta."
    assert "Gracias" not in result["formatted_transcript"]
    assert result["segments"] == [source["segments"][1]]
    assert result["raw_text"] == source["raw_text"]
    assert result["excluded_segments"][0]["text"] == source["segments"][0]["text"]
    assert result["excluded_segments"][0]["reason"] == "mic_below_minimum_volume"
    assert source == untouched
    assert path.read_bytes() == before


def test_single_click_does_not_count_as_audible_speech(tmp_path):
    mic = np.zeros(32000)
    mic[4000] = 0.9
    result = gate(recording(tmp_path, mic), recognition())
    assert len(result["segments"]) == 1


def test_brief_audible_intervention_with_long_pauses_is_kept(tmp_path):
    mic = np.zeros(32000)
    mic[4000:7200] = 0.006 * np.sin(2 * np.pi * 200 * np.arange(3200) / 16000)
    source = recognition()
    result = gate(recording(tmp_path, mic), source)
    assert result["segments"] == source["segments"]
    assert not result.get("excluded_segments")


def test_volume_threshold_can_be_adjusted_without_touching_recording(tmp_path):
    path = recording(tmp_path, np.full(32000, 0.004))
    assert len(gate(path, recognition(), min_rms=0.003)["segments"]) == 2
    assert len(gate(path, recognition(), min_rms=0.005)["segments"]) == 1


def test_mono_is_not_assumed_to_be_a_separate_microphone(tmp_path):
    path = tmp_path / "mono.wav"
    sf.write(path, np.zeros(32000), 16000)
    assert gate(path, recognition()) == recognition()


def test_unreadable_audio_is_reported_not_treated_as_silence(tmp_path):
    path = tmp_path / "bad.wav"
    path.write_bytes(b"invalid")
    result = gate(path, recognition())
    assert result["segments"] == recognition()["segments"]
    assert result["mic_volume_gate"]["status"] == "unavailable"


@pytest.mark.parametrize("speech_detected", [False, True])
def test_long_sparse_segment_requires_voice_not_just_a_noise_burst(tmp_path, monkeypatch, speech_detected):
    import src.transcription.mic_volume_gate as module
    mic = np.zeros(30 * 16000)
    mic[16000:19200] = 0.01
    path = recording(tmp_path, mic)
    source = recognition()
    source["segments"][0]["end"] = 30
    monkeypatch.setattr(module, "_has_detected_speech", lambda *args: speech_detected, raising=False)
    result = gate(path, source)
    assert len(result["segments"]) == (2 if speech_detected else 1)
    if not speech_detected:
        assert result["excluded_segments"][0]["reason"] == "mic_no_detected_speech"


def test_unavailable_voice_detector_does_not_claim_a_sparse_segment_was_silent(tmp_path, monkeypatch):
    import src.transcription.mic_volume_gate as module
    mic = np.zeros(30 * 16000)
    mic[16000:19200] = 0.01
    source = recognition()
    source["segments"][0]["end"] = 30
    def unavailable(*args):
        raise RuntimeError("voice detector unavailable")
    monkeypatch.setattr(module, "_has_detected_speech", unavailable, raising=False)
    result = gate(recording(tmp_path, mic), source)
    assert result["segments"] == source["segments"]
    assert result["mic_volume_gate"]["status"] == "unavailable"


@pytest.mark.parametrize("engine", ["groq", "local"])
def test_app_pipeline_uses_original_levels_for_both_engines(tmp_path, monkeypatch, engine):
    from src.api import server
    path = recording(tmp_path, np.full(32000, 0.00003))
    before = path.read_bytes()

    def worker(working, *args, **kwargs):
        # Simulate preprocessing amplification on the temporary working copy.
        sf.write(working, np.full((32000, 2), 0.2), 16000)
        return recognition()

    monkeypatch.setattr(server, "_transcribe_audio_pipeline", worker)
    output = tmp_path / "outputs"
    output.mkdir()
    monkeypatch.setattr(server, "get_data_output_dir", lambda: output)
    result = server.transcribe_audio_pipeline(str(path), engine=engine,
                                              recording_mode="roleplay", speaking_log=[])
    assert result["text"] == "Abro la puerta."
    assert path.read_bytes() == before
    reports = list(output.glob("mic-volume-review-*.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report["excluded_segments"][0]["text"] == "Gracias por ver el video."
    assert report["source_filename"] == path.name


@pytest.mark.parametrize("source", ["local", "youtube"])
def test_app_preserves_quarantined_recognitions_even_without_a_stereo_mic(tmp_path, monkeypatch, source):
    from src.api import server
    path = tmp_path / "mono.wav"
    sf.write(path, np.zeros(16000), 16000)
    output = tmp_path / "reviews"
    output.mkdir()
    uncertain = {"start": 0, "end": 1, "text": "Reconocimiento dudoso",
                 "reason": "extremely_low_recognition_confidence", "avg_logprob": -3.0}
    monkeypatch.setattr(server, "get_data_output_dir", lambda: output)
    monkeypatch.setattr(server, "_transcribe_audio_pipeline", lambda *a, **k: {
        "segments": [], "text": "", "formatted_transcript": "", "uncertain_segments": [uncertain]})
    result = server.transcribe_audio_pipeline(str(path), source=source, speaking_log=[])
    assert result["text"] == ""
    report = json.loads(next(output.glob("recognition-review-*.json")).read_text(encoding="utf-8"))
    assert report["uncertain_segments"] == [uncertain]
