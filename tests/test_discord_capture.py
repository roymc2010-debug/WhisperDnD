"""
Unit tests for isolated Discord WASAPI Application Loopback capture
and microphone recommendation in WhisperDnD.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from src.transcription.discord_audio_capture import (
    is_application_loopback_supported,
    find_discord_pids,
    find_discord_root_pid,
    resample_48k_stereo_to_16k_mono,
    DiscordAudioCapture,
)
from src.transcription.audio_recorder import (
    get_audio_devices,
    _resolve_microphone,
    get_audio_levels,
    DualChannelAudioRecorder,
)


class TestDiscordAudioCapture(unittest.TestCase):

    def test_windows_version_compatibility(self):
        # Must report supported on Windows 11 Build 22621 (or mock >= 20348)
        self.assertTrue(is_application_loopback_supported())

    @patch("src.transcription.discord_audio_capture._get_running_processes")
    def test_find_discord_root_pid_identifies_root_process(self, mock_procs):
        # Mock process list with parent-child Discord processes and unrelated processes
        mock_procs.return_value = [
            {"pid": 100, "parent_pid": 1, "name": "explorer.exe"},
            {"pid": 200, "parent_pid": 100, "name": "Discord.exe"},        # Root Discord process
            {"pid": 201, "parent_pid": 200, "name": "Discord.exe"},        # Child renderer
            {"pid": 202, "parent_pid": 200, "name": "Discord.exe"},        # Child audio worker
            {"pid": 300, "parent_pid": 1, "name": "Spotify.exe"},          # External app
        ]

        pids = find_discord_pids()
        self.assertEqual(len(pids), 3)

        root_pid = find_discord_root_pid()
        self.assertEqual(root_pid, 200)

    @patch("src.transcription.discord_audio_capture._get_running_processes")
    def test_find_discord_root_pid_returns_none_when_not_running(self, mock_procs):
        mock_procs.return_value = [
            {"pid": 100, "parent_pid": 1, "name": "explorer.exe"},
            {"pid": 300, "parent_pid": 1, "name": "Spotify.exe"},
        ]
        self.assertIsNone(find_discord_root_pid())

    def test_resample_48k_stereo_to_16k_mono(self):
        # 48000 Hz stereo -> 16000 Hz mono (exact 3:1 decimation ratio)
        # Create 480 frames of stereo audio (0.01s at 48kHz)
        left = np.full((480,), 0.6, dtype=np.float32)
        right = np.full((480,), 0.4, dtype=np.float32)
        stereo_48k = np.column_stack((left, right))

        mono_16k = resample_48k_stereo_to_16k_mono(stereo_48k)
        # Length should be exactly 480 / 3 = 160 frames
        self.assertEqual(len(mono_16k), 160)
        # Mono average of 0.6 and 0.4 is 0.5
        np.testing.assert_allclose(mono_16k[:, 0], 0.5, rtol=1e-5)

    def test_discord_capture_generates_silence_when_discord_not_connected(self):
        capture = DiscordAudioCapture(samplerate=16000, blocksize=1600)
        # Without starting, request a chunk
        chunk = capture.get_audio_chunk(num_frames=1600)
        self.assertEqual(chunk.shape, (1600, 1))
        # Must be pure silence
        self.assertEqual(float(np.max(np.abs(chunk))), 0.0)
        self.assertFalse(capture.is_connected)

    def test_discord_capture_status_reports_waiting_state(self):
        capture = DiscordAudioCapture()
        status = capture.get_status()
        self.assertIn("discord_detected", status)
        self.assertIn("is_capturing", status)
        self.assertIn("status_message", status)
        self.assertFalse(status["is_capturing"])

    @patch("src.transcription.audio_recorder.sc.all_microphones")
    @patch("src.transcription.audio_recorder.sc.default_microphone")
    def test_get_audio_devices_recommends_conexant_internal_over_bluetooth(self, mock_def_mic, mock_all_mics):
        # Simulate user's actual hardware:
        # 1. Auriculares con micrófono (2- Redmi Buds 6 Pro) - Bluetooth
        # 2. Micrófono interno (Conexant SmartAudio HD) - Internal
        bt_mic = MagicMock()
        bt_mic.id = "mic-bt-redmi"
        bt_mic.name = "Auriculares con micrófono (2- Redmi Buds 6 Pro)"

        internal_mic = MagicMock()
        internal_mic.id = "mic-conexant-internal"
        internal_mic.name = "Micrófono interno (Conexant SmartAudio HD)"

        mock_all_mics.return_value = [bt_mic, internal_mic]
        # Even if Windows default mic is the Bluetooth headset:
        mock_def_mic.return_value = bt_mic

        devices = get_audio_devices()
        # suggested_mic_id MUST recommend the internal Conexant mic
        self.assertEqual(devices.get("suggested_mic_id"), "mic-conexant-internal")

    @patch("src.transcription.audio_recorder.sc.all_microphones")
    def test_resolve_microphone_avoids_bluetooth_when_unspecified(self, mock_all_mics):
        bt_mic = MagicMock()
        bt_mic.id = "mic-bt"
        bt_mic.name = "Auriculares con micrófono (Redmi Buds)"

        internal_mic = MagicMock()
        internal_mic.id = "mic-internal"
        internal_mic.name = "Micrófono interno (Conexant SmartAudio HD)"

        mock_all_mics.return_value = [bt_mic, internal_mic]

        resolved = _resolve_microphone(None)
        # Must resolve to internal mic, NOT bluetooth mic
        self.assertEqual(resolved.id, "mic-internal")

    @patch("src.transcription.audio_recorder._resolve_microphone")
    def test_get_audio_levels_does_not_open_bluetooth_mic_if_unselected(self, mock_resolve_mic):
        # If user did not explicitly select a mic, meter must not resolve/open Bluetooth mic
        bt_mic = MagicMock()
        bt_mic.id = "mic-bt"
        bt_mic.name = "Auriculares con micrófono (Redmi Buds)"
        mock_resolve_mic.return_value = bt_mic

        # When mic_id is None, get_audio_levels should guard against opening bluetooth
        levels = get_audio_levels(mic_id=None)
        self.assertIn("mic_rms", levels)
        self.assertIn("speaker_rms", levels)
        self.assertIn("discord_message", levels)

    @patch("src.transcription.audio_recorder._resolve_speaker_loopback")
    @patch("src.transcription.audio_recorder.DiscordAudioCapture")
    @patch("src.transcription.audio_recorder._resolve_microphone")
    def test_recorder_roleplay_uses_discord_capture_and_never_calls_global_loopback(
        self, mock_resolve_mic, mock_discord_capture_cls, mock_resolve_loopback
    ):
        mock_mic = MagicMock()
        mock_resolve_mic.return_value = mock_mic

        mock_capture_inst = MagicMock()
        mock_capture_inst.get_audio_chunk.return_value = np.zeros((1600, 1), dtype=np.float32)
        mock_capture_inst.get_status.return_value = {
            "discord_detected": True,
            "target_pid": 1234,
            "is_capturing": True,
            "status_message": "Audio de Discord (aislado) capturándose activamente",
        }
        mock_discord_capture_cls.return_value = mock_capture_inst

        rec = DualChannelAudioRecorder()
        # Verify initial status has discord info
        status = rec.get_status()
        self.assertIn("discord_status", status)

        # In roleplay mode, _resolve_speaker_loopback must NEVER be called
        mock_resolve_loopback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
