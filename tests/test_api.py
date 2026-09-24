"""Unit tests for FastAPI backend endpoints."""

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

try:
    import fastapi
    from src.api.server import (
        app,
        serve_index,
        transcribe_youtube,
        YouTubeTranscribeRequest,
        start_recording,
        StartRecordingRequest,
        get_audio_devices_endpoint,
        test_audio_level,
        get_recording_status,
        stop_and_process,
        StopAndProcessRequest,
        PlayerMetadata,
        export_to_drive,
        DriveExportRequest,
        get_drive_status,
        connect_drive,
        get_task_status_endpoint,
        update_task_progress,
        check_api_keys,
        drive_login,
        drive_callback,
        delete_recording_audio,
        DeleteAudioRequest,
        set_task_error,
        format_human_error,
        switch_summary_language,
        SwitchLanguageRequest,
        reprocess_campaign,
        ReprocessCampaignRequest,
        download_transcript_txt,
        download_audio_file,
        get_campaign_session_endpoint,
    )
    from fastapi import HTTPException
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


@unittest.skipUnless(FASTAPI_AVAILABLE, "FastAPI is not installed yet")
class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.temp_in_dir = tempfile.mkdtemp()
        self.temp_out_dir = tempfile.mkdtemp()
        self.temp_camp_dir = tempfile.mkdtemp()
        self.env_patcher = patch.dict(
            "os.environ",
            {
                "WHISPER_INPUT_DIR": self.temp_in_dir,
                "WHISPER_OUTPUT_DIR": self.temp_out_dir,
                "WHISPER_CAMPAIGNS_DIR": self.temp_camp_dir,
            },
        )
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()
        shutil.rmtree(self.temp_in_dir, ignore_errors=True)
        shutil.rmtree(self.temp_out_dir, ignore_errors=True)
        shutil.rmtree(self.temp_camp_dir, ignore_errors=True)

    def test_serve_index(self):
        response = asyncio.run(serve_index())
        self.assertEqual(response.status_code, 200)
        self.assertIn("WhisperDnD", response.body.decode("utf-8"))

    @patch("src.api.server.download_youtube_audio")
    @patch("src.api.server.LocalWhisperTranscriber")
    def test_transcribe_youtube_endpoint(self, mock_transcriber_class, mock_download):
        mock_download.return_value = "/path/to/downloaded.mp3"
        mock_instance = MagicMock()
        mock_instance.transcribe.return_value = {
            "text": "Hello world from YouTube",
            "segments": [{"start": 0.0, "end": 2.0, "text": "Hello world"}],
            "language": {"code": "en", "probability": 0.99},
            "language_code": "en",
            "duration": 15.0,
        }
        mock_transcriber_class.return_value = mock_instance

        request_payload = YouTubeTranscribeRequest(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            model_size="base",
        )

        response = asyncio.run(transcribe_youtube(request_payload))
        self.assertEqual(response.text, "Hello world from YouTube")
        self.assertEqual(response.language, "en")
        self.assertEqual(response.duration, 15.0)
        self.assertEqual(len(response.segments), 1)
        self.assertTrue(response.file_path)

    @patch("src.api.server.GoogleDriveStorage")
    def test_export_to_drive_endpoint(self, mock_storage_class):
        # Create a dummy file in temp output
        test_file = Path(self.temp_out_dir) / "test_api_drive_doc.docx"
        test_file.write_text("dummy docx content")

        try:
            mock_storage_instance = MagicMock()
            mock_storage_instance.upload_file.return_value = {
                "file_id": "api_file_123",
                "file_name": "test_api_drive_doc.docx",
                "web_view_link": "https://drive.google.com/file/d/api_file_123/view",
            }
            mock_storage_class.return_value = mock_storage_instance

            req = DriveExportRequest(file_path=str(test_file))
            res = asyncio.run(export_to_drive(req))

            self.assertEqual(res.status, "success")
            self.assertEqual(res.file_id, "api_file_123")
            self.assertEqual(res.file_name, "test_api_drive_doc.docx")
            self.assertIn("drive.google.com", res.web_view_link)
            mock_storage_instance.upload_file.assert_called_once_with(str(test_file.resolve()))
        finally:
            if test_file.is_file():
                test_file.unlink()

    @patch("src.api.server.active_recorder")
    def test_recording_lifecycle_endpoints(self, mock_recorder):
        mock_recorder.start.return_value = "session_test.wav"
        mock_recorder.get_status.return_value = {
            "is_recording": True,
            "duration_seconds": 12.5,
            "file_path": "session_test.wav",
        }

        # Start recording endpoint
        start_res = asyncio.run(start_recording())
        self.assertEqual(start_res["status"], "recording")

        # Status endpoint
        status_res = asyncio.run(get_recording_status())
        self.assertTrue(status_res["is_recording"])
        self.assertEqual(status_res["duration_seconds"], 12.5)

    @patch("src.api.server.export_chronicle_docx")
    @patch("src.api.server.GeminiTTRPGSummarizer")
    @patch("src.api.server.LocalWhisperTranscriber")
    @patch("src.api.server.active_recorder")
    def test_stop_and_process_endpoint(
        self, mock_recorder, mock_transcriber_class, mock_summarizer_class, mock_docx_export
    ):
        mock_recorder.is_recording = True
        dummy_wav = Path(__file__).resolve()  # pass is_file check
        mock_recorder.stop.return_value = str(dummy_wav)

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe.return_value = {
            "text": "El grupo entró a la mazmorra.",
            "segments": [{"start": 0.0, "end": 3.0, "text": "El grupo entró a la mazmorra."}],
            "language": {"code": "es", "probability": 0.98},
            "language_code": "es",
            "duration": 3.0,
        }
        mock_transcriber_class.return_value = mock_transcriber

        mock_summarizer = MagicMock()
        mock_summarizer.generate_chronicle.return_value = "# Crónica de Sesión\n\nLos héroes triunfaron."
        mock_summarizer_class.return_value = mock_summarizer

        payload = StopAndProcessRequest(
            roster=[
                PlayerMetadata(
                    player_name="Roymc89",
                    role="Guerrero (Fighter)",
                    character_name="Markus Veyl",
                    species="Humano",
                    subclass="Battle Master",
                )
            ],
            model_size="base",
            task_id="test_task_123",
        )

        response = asyncio.run(stop_and_process(payload))
        self.assertEqual(response["status"], "completed")
        self.assertIn("Los héroes triunfaron", response["chronicle"])
        self.assertEqual(response["transcript"], "El grupo entró a la mazmorra.")
        self.assertTrue(response["docx_filename"].startswith("cronica_sesion_"))

        # Verify task progress was tracked
        task_st = asyncio.run(get_task_status_endpoint(task_id="test_task_123"))
        self.assertEqual(task_st["percent"], 100)
        self.assertEqual(task_st["status"], "completed")

    @patch("src.api.server.GoogleDriveStorage")
    def test_drive_status_endpoint(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.credentials_path.is_file.return_value = True
        mock_storage.is_connected.return_value = True
        mock_storage_cls.return_value = mock_storage

        res = asyncio.run(get_drive_status())
        self.assertTrue(res["connected"])
        self.assertTrue(res["has_credentials"])
        self.assertEqual(res["message"], "Google Drive conectado")

    @patch("src.api.server.GoogleDriveStorage")
    def test_drive_connect_endpoint(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.credentials_path.is_file.return_value = True
        mock_storage.authenticate.return_value = MagicMock()
        mock_storage_cls.return_value = mock_storage

        res = asyncio.run(connect_drive())
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["connected"])

    def test_task_status_endpoint_returns_data(self):
        update_task_progress("task_abc", 50, "Descargando audio de YouTube...")
        res = asyncio.run(get_task_status_endpoint("task_abc"))
        self.assertEqual(res["percent"], 50)
        self.assertEqual(res["step"], "Descargando audio de YouTube...")

    @patch("src.api.server.export_academic_notes_docx")
    @patch("src.api.server.GeminiTTRPGSummarizer")
    @patch("src.api.server.LocalWhisperTranscriber")
    @patch("src.api.server.active_recorder")
    def test_stop_and_process_class_mode(
        self, mock_recorder, mock_transcriber_class, mock_summarizer_class, mock_docx_export
    ):
        mock_recorder.is_recording = True
        dummy_wav = Path(__file__).resolve()
        mock_recorder.stop.return_value = str(dummy_wav)

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe.return_value = {
            "text": "La estabilidad de Nyquist se evalúa en el plano complejo.",
            "segments": [{"start": 0.0, "end": 4.0, "text": "La estabilidad de Nyquist."}],
            "language": {"code": "es", "probability": 0.99},
            "language_code": "es",
            "duration": 4.0,
        }
        mock_transcriber_class.return_value = mock_transcriber

        mock_summarizer = MagicMock()
        mock_summarizer.generate_academic_notes.return_value = "# 🎓 Guía de Estudio\n\n## 1. Resumen\nCriterio de Nyquist."
        mock_summarizer_class.return_value = mock_summarizer

        payload = StopAndProcessRequest(
            recording_mode="class",
            subject="Sistemas de Control",
            topic="Criterio de Nyquist",
            model_size="base",
            task_id="test_task_class_1",
        )

        response = asyncio.run(stop_and_process(payload))
        self.assertEqual(response["status"], "completed")
        self.assertEqual(response["recording_mode"], "class")
        self.assertEqual(response["subject"], "Sistemas de Control")
        self.assertEqual(response["topic"], "Criterio de Nyquist")
        self.assertIn("Guía de Estudio", response["chronicle"])
        self.assertTrue(response["docx_filename"].startswith("apuntes_"))

        # Verify task progress
        task_st = asyncio.run(get_task_status_endpoint(task_id="test_task_class_1"))
        self.assertEqual(task_st["percent"], 100)
        self.assertEqual(task_st["status"], "completed")

    @patch.dict("os.environ", {"GROQ_API_KEY": "gsk_test123", "GEMINI_API_KEY": "AIzaSyTest123"})
    @patch("src.api.server.GoogleDriveStorage")
    def test_check_api_keys_success(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.is_connected.return_value = True
        mock_storage_cls.return_value = mock_storage

        with patch("groq.Client") as mock_groq_cls, patch("google.genai.Client") as mock_gemini_cls:
            mock_groq = MagicMock()
            mock_groq_cls.return_value = mock_groq
            mock_gemini = MagicMock()
            mock_gemini.models.list.return_value = [MagicMock()]
            mock_gemini_cls.return_value = mock_gemini

            res = asyncio.run(check_api_keys())
            self.assertTrue(res["groq"])
            self.assertTrue(res["gemini"])
            self.assertTrue(res["drive"])
            self.assertIn("operativa", res["groq_message"])
            self.assertIn("operativa", res["gemini_message"])
            self.assertEqual(res["drive_message"], "Google Drive conectado.")

    @patch.dict("os.environ", {"GROQ_API_KEY": "", "GEMINI_API_KEY": ""}, clear=True)
    @patch("src.api.server.GoogleDriveStorage")
    def test_check_api_keys_missing(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.is_connected.return_value = False
        mock_storage.credentials_path.is_file.return_value = False
        mock_storage_cls.return_value = mock_storage

        res = asyncio.run(check_api_keys())
        self.assertFalse(res["groq"])
        self.assertFalse(res["gemini"])
        self.assertFalse(res["drive"])
        self.assertIn("no configurada", res["groq_message"])
        self.assertIn("no configurada", res["gemini_message"])
        self.assertIn("Falta credentials.json", res["drive_message"])

    @patch("src.api.server.GoogleDriveStorage")
    def test_drive_login_endpoint(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.get_authorization_url.return_value = "https://accounts.google.com/o/oauth2/auth?test=1"
        mock_storage_cls.return_value = mock_storage

        res = asyncio.run(drive_login())
        self.assertEqual(res["auth_url"], "https://accounts.google.com/o/oauth2/auth?test=1")

    @patch("src.api.server.GoogleDriveStorage")
    def test_drive_callback_success(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.exchange_code_for_token.return_value = MagicMock()
        mock_storage_cls.return_value = mock_storage

        res = asyncio.run(drive_callback(code="test_auth_code"))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers["location"], "/?drive_connected=true")

    def test_drive_callback_errors(self):
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(drive_callback(error="access_denied"))
        self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(drive_callback(code=None))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_delete_recording_audio_success(self):
        test_audio = Path(self.temp_in_dir) / "test_recording_to_delete.wav"
        test_audio.write_bytes(b"RIFF dummy wav data")

        try:
            req = DeleteAudioRequest(filename=test_audio.name)
            res = asyncio.run(delete_recording_audio(req))
            self.assertEqual(res["status"], "success")
            self.assertIn("eliminado correctamente", res["message"])
            self.assertFalse(test_audio.is_file())
        finally:
            if test_audio.is_file():
                test_audio.unlink()

    def test_delete_recording_audio_not_found(self):
        req = DeleteAudioRequest(filename="non_existent_audio_file.wav")
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(delete_recording_audio(req))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_task_error_tracking(self):
        test_task_id = "test_err_task_123"
        err_msg = "Error 429: Límite de tasa de Groq superado."
        set_task_error(test_task_id, err_msg)

        res = asyncio.run(get_task_status_endpoint(test_task_id))
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_message"], err_msg)

    def test_format_human_error(self):
        self.assertIn("Rate Limit", format_human_error(Exception("groq rate_limit_exceeded 429")))
        self.assertIn("Cuota", format_human_error(Exception("gemini RESOURCE_EXHAUSTED quota exceeded")))
        self.assertIn("FFmpeg", format_human_error(Exception("ffmpeg executable not found")))
        self.assertIn("Fallo genérico", format_human_error(Exception("Fallo genérico")))

    @patch("src.api.server.export_academic_notes_docx")
    @patch("src.api.server.GeminiTTRPGSummarizer")
    def test_switch_summary_language_class_mode(self, mock_summarizer_class, mock_export_docx):
        mock_summarizer = MagicMock()
        mock_summarizer.generate_academic_notes.return_value = "# 🎓 Study Guide: Control Systems\n\n## 1. Summary\nNyquist stability."
        mock_summarizer_class.return_value = mock_summarizer

        req = SwitchLanguageRequest(
            transcript_text="La estabilidad de Nyquist en el plano complejo.",
            target_language="en",
            recording_mode="class",
            subject="Control Systems",
            topic="Nyquist Stability",
        )
        res = asyncio.run(switch_summary_language(req))
        self.assertEqual(res.target_language, "en")
        self.assertIn("Study Guide", res.chronicle)
        mock_summarizer.generate_academic_notes.assert_called_once()
        self.assertEqual(mock_summarizer.generate_academic_notes.call_args.kwargs["target_language"], "en")

    @patch("src.api.server.process_session_for_campaign")
    def test_switch_summary_language_roleplay_mode(self, mock_process_camp):
        mock_process_camp.return_value = {
            "chronicle": "# 📜 Comprehensive Report\n\n## 1. Adventure Chronicle",
            "campaign_state": {"campaign_name": "Test Camp", "last_session": 1},
            "docx_filename": "Grimorio_Test_en.docx",
            "md_filename": "Grimorio_Test_en.md",
            "file_path": str(Path(self.temp_out_dir) / "Grimorio_Test_en.docx"),
        }

        req = SwitchLanguageRequest(
            transcript_text="Hicimos una tirada de iniciativa contra los orcos.",
            target_language="en",
            recording_mode="roleplay",
            campaign_name="Test Camp",
            session_number=1,
            roster=[PlayerMetadata(player_name="Rodrigo", character_name="Markus Veyl", role="Guerrero")],
        )
        res = asyncio.run(switch_summary_language(req))
        self.assertEqual(res.target_language, "en")
        self.assertIn("Comprehensive Report", res.chronicle)
        mock_process_camp.assert_called_once()
        self.assertEqual(mock_process_camp.call_args.kwargs["target_language"], "en")

    @patch("src.api.server.process_session_for_campaign")
    def test_reprocess_campaign_roleplay(self, mock_process_camp):
        mock_process_camp.return_value = {
            "chronicle": "## 1. Crónica Narrativa y Combates\nLuchamos contra goblins.\n\n## 2. Cierre\nDescanso.\n\n## 3. 🎙️ Guion para abrir la Sesión #3\nA ver gente...",
            "campaign_state": {"campaign_name": "Campaña Principal", "last_session": 2},
            "session_chapter": {"title": "Sesión #2"},
            "updated_quests": [{"id": "q1", "title": "Salvar al herrero"}],
            "updated_npcs": [{"name": "Toblen", "role": "Posadero"}],
            "detected_npc_names": ["Toblen"],
            "docx_filename": "Grimorio_Campaña_Principal.docx",
            "md_filename": "Grimorio_Campaña_Principal.md",
            "file_path": str(Path(self.temp_out_dir) / "Grimorio_Campaña_Principal.docx"),
        }

        req = ReprocessCampaignRequest(
            transcript_text="Encontramos a Toblen en la posada.",
            campaign_name="Campaña Principal",
            session_number=2,
            target_language="es",
            recording_mode="roleplay",
        )
        res = asyncio.run(reprocess_campaign(req))
        self.assertEqual(res.engine_used, "gemini-reprocess")
        self.assertEqual(res.session_chapter["title"], "Sesión #2")
        self.assertEqual(len(res.updated_quests), 1)
        self.assertEqual(len(res.updated_npcs), 1)
        self.assertEqual(res.detected_npc_names, ["Toblen"])
        self.assertIn("Crónica Narrativa", res.chronicle)
        mock_process_camp.assert_called_once()

    def test_reprocess_campaign_empty_transcript_raises(self):
        req = ReprocessCampaignRequest(
            transcript_text="   ",
            campaign_name="Campaña Principal",
        )
        with self.assertRaises(HTTPException):
            asyncio.run(reprocess_campaign(req))

    @patch("src.api.server.process_session_for_campaign")
    def test_reprocess_campaign_returns_detected_party(self, mock_process_camp):
        detected = [
            {"player_name": "StreamerA", "character_name": "Gorg", "species": "Goliath", "role": "Bárbaro", "subclass": "Berserker"}
        ]
        mock_process_camp.return_value = {
            "chronicle": "Crónica de la sesión.",
            "campaign_state": {"campaign_name": "Caoz con todo", "last_session": 1},
            "session_chapter": {"title": "Sesión #1"},
            "updated_quests": [],
            "updated_npcs": [],
            "detected_npc_names": [],
            "detected_party": detected,
            "docx_filename": "Caoz_con_todo_Grimorio.docx",
            "md_filename": "Caoz_con_todo_Grimorio.md",
            "file_path": str(Path(self.temp_out_dir) / "Caoz_con_todo_Grimorio.docx"),
        }

        req = ReprocessCampaignRequest(
            transcript_text="Gorg atacó al jefe con su hacha.",
            campaign_name="Caoz con todo",
            session_number=1,
            target_language="es",
            recording_mode="roleplay",
        )
        res = asyncio.run(reprocess_campaign(req))
        self.assertEqual(res.detected_party, detected)
        self.assertEqual(res.detected_party[0]["character_name"], "Gorg")

    @patch("src.api.server.GeminiTTRPGSummarizer")
    @patch("src.api.server.CampaignManager")
    @patch("src.api.server.export_living_journal_docx")
    @patch("src.api.server.export_living_journal_md")
    def test_process_session_for_campaign_youtube_omits_reflection(
        self, mock_md, mock_docx, mock_mgr_cls, mock_sum_cls
    ):
        from src.api.server import process_session_for_campaign

        mock_mgr = MagicMock()
        mock_mgr.get_active_context.return_value = {
            "session_number": 1,
            "all_quests": [],
            "known_npcs": [],
            "roster": [],
        }
        mock_mgr.record_session.return_value = {"campaign_name": "YouTube Camp"}
        mock_mgr_cls.return_value = mock_mgr

        mock_sum = MagicMock()
        mock_sum.generate_campaign_session.return_value = {
            "session_chapter": {
                "title": "Sesión #1",
                "chronicle_text": "Vencieron al dragón.",
                "closing_expectations": "Repartir el tesoro.",
                "user_coaching": "",
                "next_session_script": "",
                "episode_synopsis": "Los héroes derrotaron al dragón tras una intensa batalla y aseguraron la reliquia.",
            },
            "detected_pcs": [{"jugador": "Player1", "personaje": "Hero1", "especie": "Elfo", "clase": "Mago"}],
            "detected_party": [{"player_name": "Player1", "character_name": "Hero1", "species": "Elfo", "role": "Mago", "subclass": "-"}],
            "updated_quests": [],
            "updated_npcs": [],
            "detected_npc_names": [],
        }
        mock_sum_cls.return_value = mock_sum
        mock_docx.return_value = str(Path(self.temp_out_dir) / "dummy.docx")
        mock_md.return_value = str(Path(self.temp_out_dir) / "dummy.md")

        # Call with is_youtube=True
        res = process_session_for_campaign(
            campaign_name="YouTube Camp",
            transcript_text="Texto del video de youtube.",
            roster_dicts=[{"player_name": "Roy", "character_name": "Markus", "is_user_character": True}],
            is_youtube=True,
        )

        # Confirm user_character was forced to None for Gemini
        sum_call_kwargs = mock_sum.generate_campaign_session.call_args.kwargs
        self.assertIsNone(sum_call_kwargs.get("user_character"))
        self.assertTrue(sum_call_kwargs.get("is_youtube"))

        # Confirm chronicle does NOT contain reflection
        self.assertNotIn("Reflexión de Rol y Compañerismo", res["chronicle"])
        # Confirm chronicle does NOT contain read-aloud script for YouTube
        self.assertNotIn("🎙️ Guion para abrir la Sesión", res["chronicle"])
        # Confirm chronicle contains executive episode synopsis
        self.assertIn("📌 Sinopsis Ejecutiva del Episodio", res["chronicle"])
        self.assertIn("Los héroes derrotaron al dragón", res["chronicle"])
        # Confirm detected_pcs is returned
        self.assertEqual(len(res["detected_pcs"]), 1)
        self.assertEqual(res["detected_pcs"][0]["personaje"], "Hero1")

    def test_get_audio_devices_endpoint(self):
        with patch("src.api.server.get_audio_devices") as mock_get_devs:
            mock_get_devs.return_value = {
                "microphones": [{"id": "mic1", "name": "Test Mic"}],
                "speakers": [{"id": "spk1", "name": "Test Speaker"}],
                "default_mic_id": "mic1",
                "default_speaker_id": "spk1",
            }
            res = asyncio.run(get_audio_devices_endpoint())
            self.assertEqual(len(res["microphones"]), 1)
            self.assertEqual(res["microphones"][0]["name"], "Test Mic")
            self.assertEqual(res["default_speaker_id"], "spk1")

    def test_test_audio_level_endpoint(self):
        with patch("src.api.server.get_audio_levels") as mock_get_levels:
            mock_get_levels.return_value = {
                "mic_rms": 0.042,
                "speaker_rms": 0.018,
                "is_recording": False,
            }
            res = asyncio.run(test_audio_level(mic_id="mic1", speaker_id="spk1"))
            self.assertEqual(res["mic_rms"], 0.042)
            self.assertEqual(res["speaker_rms"], 0.018)
            mock_get_levels.assert_called_once_with(mic_id="mic1", speaker_id="spk1")

    def test_start_recording_with_devices(self):
        with patch("src.api.server.active_recorder.start") as mock_start:
            mock_start.return_value = str(Path(self.temp_in_dir) / "session_test.wav")
            payload = StartRecordingRequest(
                mode="roleplay",
                mic_id="custom-mic-id",
                speaker_id="custom-spk-id",
            )
            res = asyncio.run(start_recording(payload))
            self.assertEqual(res["status"], "recording")
            self.assertEqual(res["mode"], "roleplay")
            self.assertEqual(res["mic_id"], "custom-mic-id")
            self.assertEqual(res["speaker_id"], "custom-spk-id")
            mock_start.assert_called_once_with(
                mode="roleplay",
                mic_id="custom-mic-id",
                speaker_id="custom-spk-id",
            )

    def test_download_transcript_txt(self):
        # Create a transcript file in output dir
        txt_path = Path(self.temp_out_dir) / "test_campaign_sesion_1_transcripcion.txt"
        txt_path.write_text("[00:00:00 -> 00:00:05] [Tu / Markus]: Hola mundo.\n", encoding="utf-8")

        response = asyncio.run(download_transcript_txt("test_campaign_sesion_1_transcripcion.txt"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.media_type, "text/plain; charset=utf-8")
        self.assertIn("attachment", response.headers.get("content-disposition", ""))

    def test_download_audio_file(self):
        # Create audio file in input dir
        audio_path = Path(self.temp_in_dir) / "session_recording.wav"
        audio_path.write_bytes(b"RIFFdummywavdata")

        response = asyncio.run(download_audio_file("session_recording.wav"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.media_type, "audio/wav")
        self.assertIn("attachment", response.headers.get("content-disposition", ""))

    @patch("src.api.server.CampaignManager")
    def test_get_campaign_session_txt_handling(self, mock_mgr_cls):
        mock_mgr = MagicMock()
        mock_mgr.sanitize_name.return_value = "Camp1"
        mock_mgr.load_campaign.return_value = {
            "name": "Camp1",
            "sessions": [
                {
                    "session_number": 1,
                    "title": "Sesión 1",
                    "chronicle_markdown": "# Cronica",
                    "raw_transcript": "[00:00:01 -> 00:00:05] [Tu]: Accion",
                }
            ],
            "quests": [],
            "npcs": [],
            "roster": [],
        }
        mock_mgr_cls.return_value = mock_mgr

        res = asyncio.run(get_campaign_session_endpoint("Camp1", 1))
        self.assertEqual(res["txt_filename"], "Camp1_sesion_1_transcripcion.txt")
        self.assertEqual(res["raw_transcript"], "[00:00:01 -> 00:00:05] [Tu]: Accion")
        # Ensure file was created in output dir
        out_txt = Path(self.temp_out_dir) / "Camp1_sesion_1_transcripcion.txt"
        self.assertTrue(out_txt.is_file())
        self.assertEqual(out_txt.read_text(encoding="utf-8"), "[00:00:01 -> 00:00:05] [Tu]: Accion")

    @patch("src.transcription.discord_rpc.discord_tracker")
    def test_get_discord_participants(self, mock_tracker):
        from src.api.server import get_discord_participants_endpoint
        mock_tracker.get_active_participants.return_value = {
            "connected": True,
            "channel_id": "123456789",
            "channel_name": "Partida D&D",
            "participants": [
                {"user_id": "111", "username": "Beta", "display_name": "BetaDM"},
                {"user_id": "222", "username": "Acher08", "display_name": "Selen"},
            ],
        }

        res = asyncio.run(get_discord_participants_endpoint())
        self.assertTrue(res["connected"])
        self.assertEqual(res["channel_name"], "Partida D&D")
        self.assertEqual(len(res["participants"]), 2)
        self.assertEqual(res["participants"][1]["user_id"], "222")
        mock_tracker.ensure_running.assert_called_once()


if __name__ == "__main__":
    unittest.main()

