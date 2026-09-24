"""Unit tests for LocalWhisperTranscriber."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.transcription.local_whisper import LocalWhisperTranscriber


class TestLocalWhisperTranscriber(unittest.TestCase):
    def test_init_defaults(self):
        transcriber = LocalWhisperTranscriber()
        self.assertEqual(transcriber.model_size, "base")
        self.assertEqual(transcriber.device, "auto")
        self.assertEqual(transcriber.compute_type, "int8")

    def test_init_custom(self):
        transcriber = LocalWhisperTranscriber(
            model_size="tiny",
            device="cpu",
            compute_type="float32",
        )
        self.assertEqual(transcriber.model_size, "tiny")
        self.assertEqual(transcriber.device, "cpu")
        self.assertEqual(transcriber.compute_type, "float32")

    def test_missing_audio_file_raises_error(self):
        transcriber = LocalWhisperTranscriber()
        with self.assertRaises(FileNotFoundError):
            transcriber.transcribe("non_existent_audio_file.wav")

    def test_transcribe_mocked(self):
        transcriber = LocalWhisperTranscriber()

        # Create mock segments and info
        mock_seg1 = MagicMock()
        mock_seg1.start = 0.0
        mock_seg1.end = 2.5
        mock_seg1.text = "Hello world"

        mock_seg2 = MagicMock()
        mock_seg2.start = 2.5
        mock_seg2.end = 5.0
        mock_seg2.text = "This is a test"

        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.985
        mock_info.duration = 5.0

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_seg1, mock_seg2], mock_info)
        transcriber._model = mock_model

        # Use an existing file (like this test file itself) to pass the path.is_file() check
        current_file = str(Path(__file__).resolve())
        result = transcriber.transcribe(current_file)

        mock_model.transcribe.assert_called_once_with(current_file, vad_filter=True)
        self.assertEqual(result["text"], "Hello world This is a test")
        self.assertEqual(result["duration"], 5.0)
        self.assertEqual(result["language"]["code"], "en")
        self.assertEqual(result["language"]["probability"], 0.985)
        self.assertEqual(len(result["segments"]), 2)
        self.assertEqual(result["segments"][0]["start"], 0.0)
        self.assertEqual(result["segments"][0]["end"], 2.5)
        self.assertEqual(result["segments"][0]["text"], "Hello world")

    def test_transcribe_with_callbacks(self):
        transcriber = LocalWhisperTranscriber()

        mock_seg = MagicMock()
        mock_seg.start = 1.0
        mock_seg.end = 3.0
        mock_seg.text = "Testing callbacks"

        mock_info = MagicMock()
        mock_info.language = "es"
        mock_info.language_probability = 0.99
        mock_info.duration = 4.0

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_seg], mock_info)
        transcriber._model = mock_model

        info_received = []
        segments_received = []

        current_file = str(Path(__file__).resolve())
        result = transcriber.transcribe(
            current_file,
            on_info=lambda info: info_received.append(info),
            on_segment=lambda seg: segments_received.append(seg),
        )

        self.assertEqual(len(info_received), 1)
        self.assertEqual(info_received[0].language, "es")
        self.assertEqual(len(segments_received), 1)
        self.assertEqual(segments_received[0]["text"], "Testing callbacks")
        self.assertEqual(result["text"], "Testing callbacks")


if __name__ == "__main__":
    unittest.main()
