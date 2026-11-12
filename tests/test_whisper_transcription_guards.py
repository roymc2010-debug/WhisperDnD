"""Offline guards against Whisper artifacts without rejecting real short speech."""
from types import SimpleNamespace

import pytest

from src.transcription.groq_whisper import GroqWhisperTranscriber, clean_whisper_hallucinations


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    for key in ("INPUT", "OUTPUT", "CAMPAIGNS", "QUOTA"):
        monkeypatch.setenv(f"WHISPER_{key}_DIR", str(tmp_path / key.lower()))


@pytest.mark.parametrize("text", [
    "Subtitles by the",
    "Subtitles by the Amara.org community.",
    "Captions by the Amara.org community.",
    "[00:00:00 -> 00:00:08] [Discord]: Subtitles by the",
])
def test_known_standalone_credit_artifacts_do_not_become_dialogue(text):
    assert clean_whisper_hallucinations(text) == ""


@pytest.mark.parametrize("text", [
    "Hasta luego.",
    "See ya. Bye.",
    "Abro la puerta y recojo una llave.",
    "Hay subtítulos sobre la puerta.",
    "El guardia lee 'Subtitles by the' en la pared.",
    "Amara abrió el cofre y nos entregó una llave.",
    "Visitamos el laboratorio de Bundru y encontramos una carta.",
])
def test_short_real_dialogue_and_mentions_of_subtitles_are_preserved(text):
    assert clean_whisper_hallucinations(text) == text


def test_repetition_cleanup_cannot_reverse_a_negated_action():
    cleaned = clean_whisper_hallucinations("No no no no no abro el cofre.")
    assert cleaned.casefold().startswith("no ")
    assert "abro el cofre" in cleaned


@pytest.mark.parametrize("metrics", [
    {"no_speech_prob": 0.99},
    {"no_speech_prob": 0.5, "avg_logprob": -2.0},
    {"compression_ratio": 3.0},
])
def test_text_from_rejected_segments_is_not_resurrected(metrics):
    text = "Texto que el propio filtro rechaza."
    response = SimpleNamespace(text=text, segments=[{"start": 0, "end": 2, "text": text, **metrics}],
                               language="es", duration=2)
    result = GroqWhisperTranscriber(api_key="unused-offline")._parse_groq_response(response)
    assert result["text"] == ""
    assert result["segments"] == []


def test_missing_segment_metadata_keeps_clean_real_text():
    response = SimpleNamespace(text="Abro la puerta.", segments=None, language="es", duration=2)
    result = GroqWhisperTranscriber(api_key="unused-offline")._parse_groq_response(response)
    assert result["text"] == "Abro la puerta."


def test_mixed_farewell_and_subtitle_artifact_keeps_only_the_farewell():
    response = SimpleNamespace(text="See ya. Bye. Subtitles by the", language="en", duration=8,
        segments=[{"start": 0, "end": 2, "text": "See ya. Bye."},
                  {"start": 2, "end": 8, "text": "Subtitles by the"}])
    result = GroqWhisperTranscriber(api_key="unused-offline")._parse_groq_response(response)
    assert result["text"] == "See ya. Bye."
    assert len(result["segments"]) == 1


def test_existing_consecutive_repetition_guard_keeps_one_real_utterance():
    response = SimpleNamespace(text="Abre la puerta. Abre la puerta.", language="es", duration=4,
        segments=[{"start": 0, "end": 2, "text": "Abre la puerta."},
                  {"start": 2, "end": 4, "text": "Abre la puerta."}])
    result = GroqWhisperTranscriber(api_key="unused-offline")._parse_groq_response(response)
    assert result["text"] == "Abre la puerta."


@pytest.mark.parametrize("metrics", [
    {"avg_logprob": -4.1239414, "no_speech_prob": 0.24890137, "compression_ratio": 1.5698925},
    {"avg_logprob": -3.0172617, "no_speech_prob": 0.13061523, "compression_ratio": 0.8},
    {"avg_logprob": -2.0577247, "no_speech_prob": 0.11828613, "compression_ratio": 0.6},
])
def test_extremely_low_confidence_is_quarantined_even_when_not_classed_as_silence(metrics):
    text = "Reconocimiento sin evidencia suficiente."
    response = SimpleNamespace(text=text, language="es", duration=30,
        segments=[{"start": 0, "end": 30, "text": text, **metrics}])
    result = GroqWhisperTranscriber(api_key="unused-offline")._parse_groq_response(response)
    assert result["text"] == ""
    assert result["segments"] == []
    assert result["uncertain_segments"][0]["text"] == text
    assert result["uncertain_segments"][0]["reason"] == "extremely_low_recognition_confidence"
    assert result["uncertain_segments"][0]["avg_logprob"] == metrics["avg_logprob"]


def test_moderately_uncertain_real_dialogue_is_not_removed_by_the_extreme_confidence_guard():
    text = "Abro la puerta."
    response = SimpleNamespace(text=text, language="es", duration=2,
        segments=[{"start": 0, "end": 2, "text": text,
                   "avg_logprob": -1.2, "no_speech_prob": 0.1}])
    result = GroqWhisperTranscriber(api_key="unused-offline")._parse_groq_response(response)
    assert result["text"] == text
