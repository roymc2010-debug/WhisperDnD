"""
Tests for transcription engine selection (Groq vs faster-whisper local)
and model size selection (base vs small) across live recording, YouTube, and file upload flows.
"""

import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.server import app, validate_api_keys_or_raise, transcribe_audio_pipeline


class TestTranscriptionEngineSelection(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_validate_api_keys_local_does_not_require_groq(self):
        # When require_groq=False, missing groq_key should succeed as long as gemini_key exists
        mock_request = MagicMock()
        mock_request.headers = {}
        try:
            validate_api_keys_or_raise(
                mock_request,
                groq_key=None,
                gemini_key="test-gemini-key",
                require_gemini=True,
                require_groq=False,
            )
        except Exception as e:
            self.fail(f"validate_api_keys_or_raise raised unexpectedly for local mode: {e}")

    def test_validate_api_keys_groq_requires_groq_key(self):
        # When require_groq=True, missing groq_key should raise HTTPException (401)
        mock_request = MagicMock()
        mock_request.headers = {}
        with self.assertRaises(HTTPException) as ctx:
            validate_api_keys_or_raise(
                mock_request,
                groq_key=None,
                gemini_key="test-gemini-key",
                require_gemini=True,
                require_groq=True,
            )
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Groq", str(ctx.exception.detail))

    @patch("src.api.server.LocalWhisperTranscriber")
    @patch("src.api.server.GroqWhisperTranscriber")
    def test_transcribe_audio_pipeline_local_uses_cpu_int8_and_never_calls_groq(
        self, mock_groq_cls, mock_local_cls
    ):
        mock_local_inst = MagicMock()
        mock_local_inst.transcribe.return_value = {
            "text": "Transcripcion local de prueba",
            "segments": [{"start": 0.0, "end": 2.0, "text": "Transcripcion local de prueba"}],
            "language": {"code": "es", "probability": 0.99},
            "duration": 2.0,
        }
        mock_local_cls.return_value = mock_local_inst

        dummy_audio = Path(self.temp_dir) / "dummy_audio.wav"
        dummy_audio.write_bytes(b"RIFFdummywavdata")

        res = transcribe_audio_pipeline(
            audio_path=str(dummy_audio),
            engine="local",
            model_size="small",
            language="es",
            source="file",
            groq_api_key=None,
        )

        mock_local_cls.assert_called_once_with(model_size="small", device="cpu", compute_type="int8")
        mock_local_inst.transcribe.assert_called_once()
        mock_groq_cls.assert_not_called()
        self.assertEqual(res["engine_used"], "local-small")
        self.assertEqual(res["text"], "Transcripcion local de prueba")

    @patch("src.api.server.LocalWhisperTranscriber")
    @patch("src.api.server.GroqWhisperTranscriber")
    def test_transcribe_audio_pipeline_local_failure_does_not_silently_fallback_to_groq(
        self, mock_groq_cls, mock_local_cls
    ):
        mock_local_inst = MagicMock()
        mock_local_inst.transcribe.side_effect = RuntimeError("CTranslate2 OOM or processing error")
        mock_local_cls.return_value = mock_local_inst

        dummy_audio = Path(self.temp_dir) / "dummy_audio.wav"
        dummy_audio.write_bytes(b"RIFFdummywavdata")

        with self.assertRaises(RuntimeError):
            transcribe_audio_pipeline(
                audio_path=str(dummy_audio),
                engine="local",
                model_size="base",
                language="es",
                source="file",
                groq_api_key=None,
            )

        mock_groq_cls.assert_not_called()

    @patch("src.api.routers.audio.server.validate_api_keys_or_raise")
    @patch("src.api.routers.audio.server.active_recorder")
    @patch("src.api.routers.audio.server.transcribe_audio_pipeline")
    @patch("src.api.routers.audio.server.GeminiTTRPGSummarizer")
    def test_stop_and_process_endpoint_passes_engine_and_model_size(
        self, mock_summarizer_cls, mock_pipeline, mock_recorder, mock_validate
    ):
        dummy_wav = Path(self.temp_dir) / "session_rec.wav"
        dummy_wav.write_bytes(b"RIFFdummywavdata" * 100)
        mock_recorder.is_recording = True
        mock_recorder.stop.return_value = str(dummy_wav)
        mock_recorder._file_path = str(dummy_wav)
        mock_recorder.mode = "class"

        mock_pipeline.return_value = {
            "text": "Texto grabado",
            "segments": [],
            "language": {"code": "es"},
            "duration": 5.0,
            "engine_used": "local-small",
        }

        mock_summarizer_inst = MagicMock()
        mock_summarizer_inst.generate_academic_notes.return_value = "# Resumen académico"
        mock_summarizer_cls.return_value = mock_summarizer_inst

        resp = self.client.post(
            "/api/record/stop-and-process",
            json={
                "task_id": "test-task-1",
                "engine": "local",
                "model_size": "small",
                "recording_mode": "class",
                "subject": "Historia",
                "topic": "Imperio Romano",
            },
            headers={"X-Gemini-Key": "gemini-test-key"},
        )

        self.assertEqual(resp.status_code, 200, resp.text)
        mock_validate.assert_called_once()
        _, kwargs_val = mock_validate.call_args
        self.assertEqual(kwargs_val.get("require_groq"), False)

        mock_pipeline.assert_called_once()
        _, kwargs_pipe = mock_pipeline.call_args
        self.assertEqual(kwargs_pipe.get("engine"), "local")
        self.assertEqual(kwargs_pipe.get("model_size"), "small")

    @patch("src.api.routers.transcription.server.validate_api_keys_or_raise")
    @patch("src.api.routers.transcription.server.download_youtube_audio")
    @patch("src.api.routers.transcription.server.transcribe_audio_pipeline")
    @patch("src.api.routers.transcription.server.GeminiTTRPGSummarizer")
    def test_youtube_endpoint_passes_engine_and_model_size(
        self, mock_summarizer_cls, mock_pipeline, mock_download, mock_validate
    ):
        dummy_audio = Path(self.temp_dir) / "yt_audio.mp3"
        dummy_audio.write_bytes(b"dummy_mp3_data")
        mock_download.return_value = str(dummy_audio)

        mock_pipeline.return_value = {
            "text": "Transcripcion de youtube",
            "segments": [],
            "language": {"code": "es"},
            "duration": 10.0,
            "engine_used": "local-base",
        }

        mock_summarizer_inst = MagicMock()
        mock_summarizer_inst.generate_academic_notes.return_value = "# Resumen YouTube"
        mock_summarizer_cls.return_value = mock_summarizer_inst

        resp = self.client.post(
            "/api/transcribe/youtube",
            json={
                "task_id": "test-task-yt",
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "engine": "local",
                "model_size": "base",
                "recording_mode": "class",
                "subject": "Musica",
                "topic": "80s",
            },
            headers={"X-Gemini-Key": "gemini-test-key"},
        )

        self.assertEqual(resp.status_code, 200, resp.text)
        mock_validate.assert_called_once()
        _, kwargs_val = mock_validate.call_args
        self.assertEqual(kwargs_val.get("require_groq"), False)

        mock_pipeline.assert_called_once()
        _, kwargs_pipe = mock_pipeline.call_args
        self.assertEqual(kwargs_pipe.get("engine"), "local")
        self.assertEqual(kwargs_pipe.get("model_size"), "base")

    @patch("src.api.routers.transcription.server.validate_api_keys_or_raise")
    @patch("src.api.routers.transcription.server.transcribe_audio_pipeline")
    @patch("src.api.routers.transcription.server.GeminiTTRPGSummarizer")
    def test_file_upload_endpoint_passes_engine_and_model_size(
        self, mock_summarizer_cls, mock_pipeline, mock_validate
    ):
        mock_pipeline.return_value = {
            "text": "Transcripcion de archivo",
            "segments": [],
            "language": {"code": "es"},
            "duration": 8.0,
            "engine_used": "local-small",
        }

        mock_summarizer_inst = MagicMock()
        mock_summarizer_inst.generate_academic_notes.return_value = "# Resumen Archivo"
        mock_summarizer_cls.return_value = mock_summarizer_inst

        fake_audio_bytes = io.BytesIO(b"RIFFfakeaudiobytes")

        resp = self.client.post(
            "/api/transcribe/file",
            data={
                "task_id": "test-task-file",
                "engine": "local",
                "model_size": "small",
                "recording_mode": "class",
                "subject": "Fisica",
                "topic": "Termodinamica",
            },
            files={"file": ("test.wav", fake_audio_bytes, "audio/wav")},
            headers={"X-Gemini-Key": "gemini-test-key"},
        )

        self.assertEqual(resp.status_code, 200, resp.text)
        mock_validate.assert_called_once()
        _, kwargs_val = mock_validate.call_args
        self.assertEqual(kwargs_val.get("require_groq"), False)

        mock_pipeline.assert_called_once()
        _, kwargs_pipe = mock_pipeline.call_args
        self.assertEqual(kwargs_pipe.get("engine"), "local")
        self.assertEqual(kwargs_pipe.get("model_size"), "small")


    def test_transcription_test_report_creation_and_privacy(self):
        from src.transcription.test_reporter import create_transcription_test_report
        temp_out = Path(self.temp_dir) / "test_reports"

        rep = create_transcription_test_report(
            engine="local",
            model_size="base",
            source="file",
            audio_duration_seconds=125.4,
            transcription_time_seconds=12.3,
            total_time_seconds=13.1,
            language="es",
            device="cpu",
            compute_type="int8",
            vad_enabled=True,
            condition_on_previous_text=False,
            success=True,
            hypothesis_text="Esta es la transcripcion que no debe aparecer por defecto",
            output_dir=temp_out,
        )

        self.assertTrue(rep.is_file())
        content = rep.read_text(encoding="utf-8")

        # Verify essential benchmarking metadata
        self.assertIn("faster-whisper", content)
        self.assertIn("base", content)
        self.assertIn("cpu", content.lower())
        self.assertIn("int8", content)
        self.assertIn("silero_vad", content)
        self.assertIn("02:05", content)
        self.assertIn("12.30 s", content)
        self.assertIn("COMPLETADO", content)

        # Verify strict privacy constraints:
        # 1. No full transcript
        self.assertNotIn("Esta es la transcripcion que no debe aparecer por defecto", content)
        # 2. No API keys or tokens
        self.assertNotIn("gsk_", content)
        self.assertNotIn("AIza", content)
        # 3. No campaign or player data
        self.assertNotIn("Campaña Principal", content)
        self.assertNotIn("Dungeon Master", content)

    def test_transcription_test_report_failure_logging(self):
        from src.transcription.test_reporter import create_transcription_test_report
        temp_out = Path(self.temp_dir) / "test_reports"

        rep = create_transcription_test_report(
            engine="groq",
            model_size="whisper-large-v3",
            source="youtube",
            audio_duration_seconds=60.0,
            total_time_seconds=2.5,
            success=False,
            error_summary="GROQ_API_KEY gsk_1234567890abcdef invalid authentication",
            output_dir=temp_out,
        )

        self.assertTrue(rep.is_file())
        content = rep.read_text(encoding="utf-8")
        self.assertIn("FALLIDO", content)
        self.assertIn("Groq Cloud Whisper API", content)
        self.assertIn("YouTube (Audio de video)", content)
        # Key must be redacted
        self.assertNotIn("gsk_1234567890abcdef", content)
        self.assertIn("[GROQ_KEY_REDACTED]", content)

    def test_wer_and_cer_calculation_and_normalization(self):
        from src.transcription.test_reporter import calculate_wer_and_cer, normalize_text_for_evaluation

        # Normalization test
        norm = normalize_text_for_evaluation("¡Hola, Mundo! ¿Cómo estás? (Test: 1, 2, 3...)")
        self.assertEqual(norm, "hola mundo cómo estás test 1 2 3")

        # Exact match = 0% WER and CER
        metrics_exact = calculate_wer_and_cer("El veloz murciélago hindú", "El veloz murciélago hindú")
        self.assertEqual(metrics_exact["wer"], 0.0)
        self.assertEqual(metrics_exact["cer"], 0.0)

        # 1 substitution out of 4 words = 25% WER
        metrics_diff = calculate_wer_and_cer("uno dos tres cuatro", "uno dos diez cuatro")
        self.assertEqual(metrics_diff["wer"], 25.0)
        self.assertGreater(metrics_diff["cer"], 0.0)

    def test_drive_upload_blocks_transcription_test_reports(self):
        from src.storage.drive_client import GoogleDriveStorage
        drive = GoogleDriveStorage()

        fake_report = Path(self.temp_dir) / "transcription-tests" / "test_report_20261031_sample.txt"
        fake_report.parent.mkdir(parents=True, exist_ok=True)
        fake_report.write_text("Report content", encoding="utf-8")

        with self.assertRaises(ValueError) as ctx:
            drive.upload_file(str(fake_report))
        self.assertIn("confidenciales", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
