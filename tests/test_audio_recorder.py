"""Unit tests for DualChannelAudioRecorder."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.transcription.audio_recorder import (
    DualChannelAudioRecorder,
    get_audio_devices,
    get_audio_levels,
)


class TestDualChannelAudioRecorder(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_recorder_initial_state(self):
        recorder = DualChannelAudioRecorder()
        self.assertFalse(recorder.is_recording)
        status = recorder.get_status()
        self.assertFalse(status["is_recording"])
        self.assertEqual(status["duration_seconds"], 0.0)
        self.assertEqual(status["mic_rms"], 0.0)
        self.assertEqual(status["speaker_rms"], 0.0)

    @patch("threading.Thread")
    def test_start_and_stop_lifecycle(self, mock_thread_class):
        mock_thread_instance = MagicMock()
        mock_thread_class.return_value = mock_thread_instance

        recorder = DualChannelAudioRecorder()
        custom_wav = str(Path(self.temp_dir) / "test_session_dummy.wav")

        # Start recording
        started_path = recorder.start(custom_wav)
        self.assertTrue(recorder.is_recording)
        self.assertTrue(started_path.endswith("test_session_dummy.wav"))

        status = recorder.get_status()
        self.assertTrue(status["is_recording"])

        # Cannot start twice
        with self.assertRaises(RuntimeError):
            recorder.start(custom_wav)

        # Stop recording
        stopped_path = recorder.stop()
        self.assertFalse(recorder.is_recording)
        self.assertEqual(stopped_path, started_path)

        # Cannot stop when not recording
        with self.assertRaises(RuntimeError):
            recorder.stop()

    @patch("threading.Thread")
    def test_start_with_class_mode(self, mock_thread_class):
        mock_thread_instance = MagicMock()
        mock_thread_class.return_value = mock_thread_instance

        recorder = DualChannelAudioRecorder()
        custom_wav = str(Path(self.temp_dir) / "lecture_test.wav")

        started_path = recorder.start(custom_wav, mode="class")
        self.assertTrue(recorder.is_recording)
        self.assertEqual(recorder.mode, "class")

        status = recorder.get_status()
        self.assertTrue(status["is_recording"])
        self.assertEqual(status["mode"], "class")

        stopped = recorder.stop()
        self.assertFalse(recorder.is_recording)
        self.assertEqual(stopped, started_path)

    @patch("threading.Thread")
    def test_start_with_custom_device_ids(self, mock_thread_class):
        mock_thread_instance = MagicMock()
        mock_thread_class.return_value = mock_thread_instance

        recorder = DualChannelAudioRecorder()
        custom_wav = str(Path(self.temp_dir) / "devices_test.wav")

        started_path = recorder.start(
            custom_wav,
            mode="roleplay",
            mic_id="{mic-guid-123}",
            speaker_id="{spk-guid-456}",
        )
        self.assertTrue(recorder.is_recording)
        self.assertEqual(recorder.mic_id, "{mic-guid-123}")
        self.assertEqual(recorder.speaker_id, "{spk-guid-456}")

        status = recorder.get_status()
        self.assertEqual(status["mic_id"], "{mic-guid-123}")
        self.assertEqual(status["speaker_id"], "{spk-guid-456}")

        args, kwargs = mock_thread_class.call_args
        self.assertEqual(kwargs.get("args"), (custom_wav, "roleplay", "{mic-guid-123}", "{spk-guid-456}"))

        recorder.stop()
        self.assertFalse(recorder.is_recording)

    def test_get_audio_devices(self):
        devices = get_audio_devices()
        self.assertIn("microphones", devices)
        self.assertIn("speakers", devices)
        self.assertIsInstance(devices["microphones"], list)
        self.assertIsInstance(devices["speakers"], list)
        self.assertIn("default_mic_id", devices)
        self.assertIn("default_speaker_id", devices)

    def test_get_audio_levels(self):
        levels = get_audio_levels()
        self.assertIn("mic_rms", levels)
        self.assertIn("speaker_rms", levels)
        self.assertIn("is_recording", levels)
        self.assertIsInstance(levels["mic_rms"], float)
        self.assertIsInstance(levels["speaker_rms"], float)
        self.assertIsInstance(levels["is_recording"], bool)


if __name__ == "__main__":
    unittest.main()
