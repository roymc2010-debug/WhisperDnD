"""Unit tests for Groq Whisper Cloud Engine (GroqWhisperTranscriber and transcription pipeline)."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.transcription.groq_whisper import GroqWhisperTranscriber
from src.api.server import transcribe_audio_pipeline


class TestGroqWhisperTranscriber(unittest.TestCase):
    """Test suite for GroqWhisperTranscriber."""

    def test_missing_api_key_raises_value_error(self):
        """Should raise ValueError when api_key is missing on accessing client."""
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}, clear=False):
            transcriber = GroqWhisperTranscriber(api_key="")
            with self.assertRaises(ValueError) as ctx:
                _ = transcriber.client
            self.assertIn("GROQ_API_KEY no está configurada", str(ctx.exception))

    def test_client_initialization_with_key(self):
        """Should initialize client when api_key is provided."""
        with patch("groq.Client") as mock_client_cls:
            transcriber = GroqWhisperTranscriber(api_key="gsk_test123")
            client = transcriber.client
            mock_client_cls.assert_called_once_with(api_key="gsk_test123")
            self.assertIsNotNone(client)

    @patch("groq.Client")
    def test_transcribe_single_file(self, mock_client_cls):
        """Test transcription of a single audio file (<24MB)."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # Mock Groq API response
        mock_response = MagicMock()
        mock_response.text = "Bienvenidos a la taberna del Dragón Verde."
        mock_response.language = "spanish"
        mock_response.duration = 4.5
        mock_response.segments = [
            {"id": 0, "start": 0.0, "end": 4.5, "text": "Bienvenidos a la taberna del Dragón Verde."}
        ]
        mock_client.audio.transcriptions.create.return_value = mock_response

        transcriber = GroqWhisperTranscriber(api_key="gsk_dummy")
        # Use existing dummy file
        dummy_file = Path(__file__).resolve()
        result = transcriber.transcribe(str(dummy_file))

        self.assertEqual(result["text"], "Bienvenidos a la taberna del Dragón Verde.")
        self.assertEqual(len(result["segments"]), 1)
        self.assertEqual(result["segments"][0]["start"], 0.0)
        self.assertEqual(result["segments"][0]["end"], 4.5)
        self.assertEqual(result["language"]["code"], "es")
        self.assertEqual(result["duration"], 4.5)

    @patch("groq.Client")
    def test_transcribe_chunked_offsets_timestamps(self, mock_client_cls):
        """Test that chunked transcription calculates cumulative timestamp offsets correctly."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        transcriber = GroqWhisperTranscriber(api_key="gsk_dummy")

        # Mock _slice_audio to return 2 fake chunks
        fake_chunks = [
            ("chunk_0.mp3", 0.0, 1200.0),
            ("chunk_1.mp3", 1200.0, 600.0),
        ]

        # Mock responses for the 2 chunks
        chunk1_resp = MagicMock()
        chunk1_resp.text = "Parte 1 de la aventura."
        chunk1_resp.language = "es"
        chunk1_resp.duration = 1200.0
        chunk1_resp.segments = [
            {"start": 10.0, "end": 20.0, "text": "Parte 1 de la aventura."}
        ]

        chunk2_resp = MagicMock()
        chunk2_resp.text = "Parte 2 y final del combate."
        chunk2_resp.language = "es"
        chunk2_resp.duration = 600.0
        chunk2_resp.segments = [
            {"start": 5.0, "end": 15.0, "text": "Parte 2 y final del combate."}
        ]

        with patch.object(transcriber, "_slice_audio", return_value=fake_chunks):
            with patch.object(transcriber, "_transcribe_single_file", side_effect=[
                {
                    "segments": [{"start": 10.0, "end": 20.0, "text": "Parte 1 de la aventura."}],
                    "text": "Parte 1 de la aventura.",
                    "language": {"code": "es", "probability": 1.0},
                    "language_code": "es",
                    "duration": 1200.0,
                },
                {
                    "segments": [{"start": 1205.0, "end": 1215.0, "text": "Parte 2 y final del combate."}],
                    "text": "Parte 2 y final del combate.",
                    "language": {"code": "es", "probability": 1.0},
                    "language_code": "es",
                    "duration": 600.0,
                }
            ]):
                dummy_file = Path(__file__).resolve()
                result = transcriber._transcribe_chunked(str(dummy_file))

                self.assertIn("Parte 1 de la aventura.", result["text"])
                self.assertIn("Parte 2 y final del combate.", result["text"])
                self.assertEqual(len(result["segments"]), 2)
                # Second segment has cumulative offset
                self.assertEqual(result["segments"][1]["start"], 1205.0)
                self.assertEqual(result["duration"], 1800.0)

    @patch("groq.Client")
    def test_chunk_percentage_calibration(self, mock_client_cls):
        """Test that chunk progress math reaches exactly 75% on the final chunk for local/live sources."""
        transcriber = GroqWhisperTranscriber(api_key="gsk_dummy")
        num_chunks = 19
        fake_chunks = [("chunk_%d.mp3" % i, i * 60.0, 60.0) for i in range(num_chunks)]
        
        progress_calls = []
        def progress_cb(pct, msg):
            progress_calls.append(pct)

        with patch.object(transcriber, "_slice_audio", return_value=fake_chunks):
            with patch.object(transcriber, "_transcribe_single_file", return_value={
                "segments": [],
                "text": "test",
                "language_code": "es",
                "duration": 60.0,
            }):
                dummy_file = Path(__file__).resolve()
                transcriber._transcribe_chunked(str(dummy_file), on_progress=progress_cb, source="local")

        # For local/live sources, slicing is 25.0% and chunks range from 30.0% to 80.0%
        self.assertEqual(progress_calls[0], 25.0)
        self.assertEqual(progress_calls[-2], 77.4)
        self.assertEqual(progress_calls[-1], 80.0)

        # For youtube sources, slicing is 25.0% and chunks range from 30.0% to 80.0%
        progress_calls_yt = []
        with patch.object(transcriber, "_slice_audio", return_value=fake_chunks):
            with patch.object(transcriber, "_transcribe_single_file", return_value={
                "segments": [], "text": "test", "language_code": "es", "duration": 60.0,
            }):
                transcriber._transcribe_chunked(str(dummy_file), on_progress=lambda pct, msg: progress_calls_yt.append(pct), source="youtube")
        self.assertEqual(progress_calls_yt[0], 25.0)
        self.assertEqual(progress_calls_yt[-2], 77.4)
        self.assertEqual(progress_calls_yt[-1], 80.0)


class TestTranscriptionPipeline(unittest.TestCase):
    """Test suite for backend transcribe_audio_pipeline routing."""

    @patch("src.api.server.LocalWhisperTranscriber")
    def test_route_to_local_when_requested(self, mock_local_whisper_cls):
        """When engine='local', pipeline should call LocalWhisperTranscriber directly."""
        mock_local = MagicMock()
        mock_local.transcribe.return_value = {
            "text": "Sesión local privada.",
            "segments": [],
            "language": "es",
            "language_code": "es",
            "duration": 10.0,
        }
        mock_local_whisper_cls.return_value = mock_local

        dummy_file = Path(__file__).resolve()
        res = transcribe_audio_pipeline(str(dummy_file), engine="local", model_size="tiny")

        mock_local_whisper_cls.assert_called_once_with(model_size="tiny")
        self.assertEqual(res["engine_used"], "local")
        self.assertEqual(res["text"], "Sesión local privada.")

    @patch("src.api.server.GroqWhisperTranscriber")
    def test_route_to_groq_when_requested_and_key_present(self, mock_groq_cls):
        """When engine='groq' and key is present, pipeline should use GroqWhisperTranscriber."""
        mock_groq = MagicMock()
        mock_groq.transcribe.return_value = {
            "text": "Transcripción ultrarrápida en la nube.",
            "segments": [],
            "language": "es",
            "language_code": "es",
            "duration": 25.0,
        }
        mock_groq_cls.return_value = mock_groq

        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_valid_key"}):
            dummy_file = Path(__file__).resolve()
            res = transcribe_audio_pipeline(str(dummy_file), engine="groq")

            mock_groq_cls.assert_called_once()
            self.assertEqual(res["engine_used"], "groq")
            self.assertEqual(res["text"], "Transcripción ultrarrápida en la nube.")

    @patch("src.api.server.LocalWhisperTranscriber")
    def test_fallback_to_local_when_groq_key_missing(self, mock_local_whisper_cls):
        """When engine='groq' but GROQ_API_KEY is missing, should fall back to local whisper."""
        mock_local = MagicMock()
        mock_local.transcribe.return_value = {
            "text": "Fallback a local exitoso.",
            "segments": [],
            "language": "es",
            "language_code": "es",
            "duration": 15.0,
        }
        mock_local_whisper_cls.return_value = mock_local

        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            dummy_file = Path(__file__).resolve()
            res = transcribe_audio_pipeline(str(dummy_file), engine="groq", model_size="base")

            mock_local_whisper_cls.assert_called_once_with(model_size="base")
            self.assertEqual(res["engine_used"], "local")
            self.assertEqual(res["text"], "Fallback a local exitoso.")

    @patch("subprocess.run")
    def test_slice_audio_for_groq_ffmpeg_call(self, mock_subproc_run):
        """Test that slice_audio_for_groq invokes ffmpeg with correct segmentation arguments preserving native extensions."""
        from src.transcription.groq_whisper import slice_audio_for_groq, clean_groq_chunks

        with tempfile.TemporaryDirectory() as tmp_input:
            with patch.dict("os.environ", {"WHISPER_INPUT_DIR": tmp_input}):
                chunks_dir = Path(tmp_input) / "chunks"
                chunks_dir.mkdir(parents=True, exist_ok=True)
                dummy_chunk_m4a = chunks_dir / "chunk_000.m4a"
                dummy_chunk_webm = chunks_dir / "chunk_000.webm"
                dummy_chunk_mp3 = chunks_dir / "chunk_000.mp3"

                def fake_ffmpeg(cmd, *args, **kwargs):
                    out_pat = cmd[-1]
                    if out_pat.endswith(".m4a"):
                        dummy_chunk_m4a.write_text("dummy m4a")
                    elif out_pat.endswith(".webm"):
                        dummy_chunk_webm.write_text("dummy webm")
                    else:
                        dummy_chunk_mp3.write_text("dummy mp3")
                    return MagicMock(returncode=0)

                mock_subproc_run.side_effect = fake_ffmpeg

                try:
                    # 1. Native M4A audio: fast stream copy (-c copy) preserving .m4a extension
                    res_m4a = slice_audio_for_groq("dummy_input.m4a", chunk_minutes=15)
                    mock_subproc_run.assert_called_once()
                    cmd_m4a = mock_subproc_run.call_args[0][0]
                    self.assertEqual(cmd_m4a[0], "ffmpeg")
                    self.assertIn("-segment_time", cmd_m4a)
                    self.assertIn("900", cmd_m4a)
                    self.assertIn("copy", cmd_m4a)
                    self.assertTrue(cmd_m4a[-1].endswith("chunk_%03d.m4a"))
                    self.assertTrue(len(res_m4a) >= 1)
                    self.assertTrue(res_m4a[0].endswith(".m4a"))

                    # 2. Native WebM audio: fast stream copy (-c copy) preserving .webm extension
                    mock_subproc_run.reset_mock()
                    res_webm = slice_audio_for_groq("dummy_input.webm", chunk_minutes=15)
                    mock_subproc_run.assert_called_once()
                    cmd_webm = mock_subproc_run.call_args[0][0]
                    self.assertIn("copy", cmd_webm)
                    self.assertTrue(cmd_webm[-1].endswith("chunk_%03d.webm"))
                    self.assertTrue(len(res_webm) >= 1)
                    self.assertTrue(res_webm[0].endswith(".webm"))

                    # 3. For WAV or non-stream-copyable files, libmp3lame re-encoding is used
                    mock_subproc_run.reset_mock()
                    res_wav = slice_audio_for_groq("dummy_input.wav", chunk_minutes=15)
                    cmd_wav = mock_subproc_run.call_args[0][0]
                    self.assertIn("libmp3lame", cmd_wav)
                    self.assertIn("64k", cmd_wav)
                    self.assertTrue(cmd_wav[-1].endswith("chunk_%03d.mp3"))
                    self.assertTrue(len(res_wav) >= 1)
                finally:
                    clean_groq_chunks()
                    self.assertFalse(dummy_chunk_m4a.exists())
                    self.assertFalse(dummy_chunk_webm.exists())
                    self.assertFalse(dummy_chunk_mp3.exists())

    def test_tag_dual_channel_speakers_mono_audio(self):
        """Mono audio should not be altered by tag_dual_channel_speakers."""
        import numpy as np
        import soundfile as sf
        from src.transcription.groq_whisper import tag_dual_channel_speakers

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = tf.name

        try:
            samplerate = 16000
            data = np.zeros((samplerate, 1), dtype=np.float32)
            sf.write(wav_path, data, samplerate)

            segments = [{"start": 0.0, "end": 1.0, "text": "Hola mono"}]
            tagged = tag_dual_channel_speakers(wav_path, segments, user_char_name="Thor")
            self.assertEqual(len(tagged), 1)
            self.assertNotIn("speaker", tagged[0])
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_tag_dual_channel_speakers_stereo_audio(self):
        """Stereo audio should tag segments as [TÚ] when mic energy dominates, else [Discord / Mesa]."""
        import numpy as np
        import soundfile as sf
        from src.transcription.groq_whisper import tag_dual_channel_speakers

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = tf.name

        try:
            samplerate = 16000
            data = np.zeros((samplerate * 2, 2), dtype=np.float32)
            data[:samplerate, 0] = 0.5
            data[:samplerate, 1] = 0.01
            data[samplerate:, 0] = 0.01
            data[samplerate:, 1] = 0.5

            sf.write(wav_path, data, samplerate)

            segments = [
                {"start": 0.0, "end": 1.0, "text": "Ataco con mi espada."},
                {"start": 1.0, "end": 2.0, "text": "El dragón ruge ferozmente."},
            ]

            tagged = tag_dual_channel_speakers(wav_path, segments, user_char_name="Valeros")
            self.assertEqual(len(tagged), 2)
            self.assertEqual(tagged[0]["speaker"], "[Tu / Valeros]")
            self.assertEqual(tagged[1]["speaker"], "[Discord]")
            self.assertIn("[00:00:00 -> 00:00:01] [Tu / Valeros]: Ataco con mi espada.", tagged[0]["formatted_line"])
            self.assertIn("[00:00:01 -> 00:00:02] [Discord]: El dragón ruge ferozmente.", tagged[1]["formatted_line"])
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_tag_dual_channel_speakers_with_discord_rpc(self):
        """Stereo Channel 2 should use Discord RPC username when speaking_log matches."""
        import numpy as np
        import soundfile as sf
        from src.transcription.groq_whisper import tag_dual_channel_speakers

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = tf.name

        try:
            samplerate = 16000
            data = np.zeros((samplerate * 2, 2), dtype=np.float32)
            data[samplerate:, 0] = 0.01
            data[samplerate:, 1] = 0.5

            sf.write(wav_path, data, samplerate)

            segments = [
                {"start": 1.0, "end": 2.0, "text": "Lanzó bola de fuego."},
            ]
            speaking_log = [
                {"start": 0.9, "end": 2.1, "username": "Beta", "user_id": "123"},
            ]

            tagged = tag_dual_channel_speakers(wav_path, segments, speaking_log=speaking_log)
            self.assertEqual(len(tagged), 1)
            self.assertEqual(tagged[0]["speaker"], "[Beta]")
            self.assertIn("[00:00:01 -> 00:00:02] [Beta]: Lanzó bola de fuego.", tagged[0]["formatted_line"])
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_tag_dual_channel_speakers_with_discord_roster_mapping(self):
        """Stereo Channel 2 should resolve Discord user ID to Roster Character & Player name."""
        import numpy as np
        import soundfile as sf
        from src.transcription.groq_whisper import tag_dual_channel_speakers

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = tf.name

        try:
            samplerate = 16000
            data = np.zeros((samplerate * 4, 2), dtype=np.float32)
            data[samplerate:, 0] = 0.01
            data[samplerate:, 1] = 0.5

            sf.write(wav_path, data, samplerate)

            segments = [
                {"start": 1.0, "end": 2.0, "text": "Yo reviso la fosa con sigilo."},
                {"start": 2.0, "end": 3.0, "text": "Tirad iniciativa todos."},
            ]
            speaking_log = [
                {"start": 0.9, "end": 2.1, "username": "acher_nick", "user_id": "999888"},
                {"start": 1.9, "end": 3.1, "username": "beta_voice", "user_id": "777666"},
            ]
            roster = [
                {
                    "player_name": "Beta",
                    "character_name": "(DM)",
                    "role": "Dungeon Master (DM)",
                    "discord_user_id": "777666",
                },
                {
                    "player_name": "Acher08",
                    "character_name": "Selen",
                    "role": "Pícaro (Rogue)",
                    "discord_user_id": "999888",
                },
            ]

            tagged = tag_dual_channel_speakers(
                wav_path, segments, speaking_log=speaking_log, roster=roster
            )
            self.assertEqual(len(tagged), 2)
            self.assertEqual(tagged[0]["speaker"], "[Selen (Acher08)]")
            self.assertIn("[00:00:01 -> 00:00:02] [Selen (Acher08)]: Yo reviso la fosa con sigilo.", tagged[0]["formatted_line"])
            self.assertEqual(tagged[1]["speaker"], "[DM (Beta)]")
            self.assertIn("[00:00:02 -> 00:00:03] [DM (Beta)]: Tirad iniciativa todos.", tagged[1]["formatted_line"])
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)


if __name__ == "__main__":
    unittest.main()
