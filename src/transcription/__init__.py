"""Transcription module using faster-whisper, YouTube downloader, and dual audio recorder."""

from .local_whisper import LocalWhisperTranscriber
from .groq_whisper import GroqWhisperTranscriber, tag_dual_channel_speakers
from .engine import WhisperEngine
from .youtube_downloader import download_youtube_audio, is_valid_youtube_url
from .audio_recorder import (
    DualChannelAudioRecorder,
    active_recorder,
    get_audio_devices,
    get_audio_levels,
)

__all__ = [
    "LocalWhisperTranscriber",
    "GroqWhisperTranscriber",
    "tag_dual_channel_speakers",
    "WhisperEngine",
    "download_youtube_audio",
    "is_valid_youtube_url",
    "DualChannelAudioRecorder",
    "active_recorder",
    "get_audio_devices",
    "get_audio_levels",
]
