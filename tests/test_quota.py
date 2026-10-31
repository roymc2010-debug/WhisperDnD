"""Unit tests for API Token and Audio Quota Tracker."""

import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from starlette.testclient import TestClient

from src.api.server import app
from src.storage import quota_tracker


class TestQuotaTracker(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        ledger_patch = patch.object(quota_tracker, "_get_ledger_path", return_value=Path(temporary.name) / "quota.json")
        ledger_patch.start()
        self.addCleanup(ledger_patch.stop)
        self.client = TestClient(app)

    def test_quota_tracker_recording(self):
        # Record tokens and audio
        quota_tracker.record_gemini_tokens(50000)
        quota_tracker.record_groq_audio_seconds(120.0)

        status = quota_tracker.get_quota_status()
        self.assertIn("percent_remaining", status)
        self.assertIn("gemini", status)
        self.assertIn("groq", status)
        self.assertGreaterEqual(status["gemini"]["tokens_used"], 50000)
        self.assertGreaterEqual(status["groq"]["seconds_used"], 120.0)
        self.assertIsInstance(status["can_process_safe"], bool)

    def test_quota_endpoint(self):
        response = self.client.get("/api/system/quota")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("percent_remaining", data)
        self.assertIn("gemini", data)
        self.assertIn("groq", data)
        self.assertIn("can_process_safe", data)



    def _low_quota_with_samples(self):
        quota_tracker.record_gemini_tokens(899200)
        for tokens in (6000, 7200, 4800):
            quota_tracker.record_audio_sample(600, tokens)

    def test_audio_capacity_uses_highest_rate_and_then_removes_five_percent(self):
        self._low_quota_with_samples()
        capacity = quota_tracker.get_quota_status()["audio_capacity"]
        self.assertEqual(capacity["seconds"], 7980)  # 2 h 13 min, after 5% margin
        self.assertEqual(capacity["safety_margin_percent"], 5)
        self.assertEqual(capacity["samples"], 3)

    def test_audio_capacity_is_limited_by_remaining_transcription_audio(self):
        self._low_quota_with_samples()
        quota_tracker.record_groq_audio_seconds(85800)
        self.assertEqual(quota_tracker.get_quota_status()["audio_capacity"]["seconds"], 570)

    def test_audio_capacity_is_unknown_without_enough_samples(self):
        quota_tracker.record_gemini_tokens(899200)
        quota_tracker.record_audio_sample(600, 6000)
        self.assertIsNone(quota_tracker.get_quota_status()["audio_capacity"]["seconds"])

    def test_invalid_samples_are_not_used(self):
        for duration, tokens in ((0, 10), (float('nan'), 10), (600, 0), (600, float('inf')), (None, 5)):
            quota_tracker.record_audio_sample(duration, tokens)
        self.assertEqual(quota_tracker.get_quota_status()["audio_capacity"]["samples"], 0)

    def test_estimate_is_not_displayed_above_twenty_percent(self):
        for tokens in (6000, 7200, 4800):
            quota_tracker.record_audio_sample(600, tokens)
        self.assertIsNone(quota_tracker.get_quota_status()["audio_capacity"]["seconds"])

    def test_samples_survive_daily_rollover(self):
        self._low_quota_with_samples()
        with patch.object(quota_tracker, "_get_current_quota_date", return_value="2099-01-01"):
            self.assertEqual(quota_tracker.get_quota_status()["audio_capacity"]["samples"], 3)


    def test_samples_use_instance_consumption_and_do_not_charge_tokens_twice(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from src.summarizer.gemini_client import GeminiTTRPGSummarizer
        summarizer = GeminiTTRPGSummarizer(api_key="test-only")
        summarizer._client = MagicMock()
        summarizer._client.models.generate_content.side_effect = [
            SimpleNamespace(text="ok", usage_metadata=SimpleNamespace(total_token_count=200)),
            SimpleNamespace(text="ok", usage_metadata=SimpleNamespace(total_token_count=300)),
        ]
        with patch.object(quota_tracker, "record_gemini_tokens"):
            summarizer._generate_with_retry("primera llamada")
            summarizer._generate_with_retry("segunda llamada")
        self.assertEqual(summarizer._quota_tokens_used, 500)
        quota_tracker.record_audio_sample(600, summarizer._quota_tokens_used)
        status = quota_tracker.get_quota_status()
        self.assertEqual(status["audio_capacity"]["samples"], 1)
        self.assertEqual(status["gemini"]["tokens_used"], 0)


    def test_capacity_uses_only_the_selected_origin_workspace_and_format(self):
        self._low_quota_with_samples()  # Older unlabelled samples are not assigned a profile.
        for tokens in (6000, 7200, 4800):
            quota_tracker.record_audio_sample(600, tokens, source="youtube", workspace="dnd")
        for tokens in (600, 1200, 600):
            quota_tracker.record_audio_sample(600, tokens, source="file", workspace="work_and_study", document_format="executive")
        work = quota_tracker.get_quota_status(source="file", workspace="work_and_study", document_format="executive")["audio_capacity"]
        self.assertEqual(work["seconds"], 47880)
        self.assertEqual(work["samples"], 3)
        wrong_format = quota_tracker.get_quota_status(source="file", workspace="work_and_study", document_format="academic")["audio_capacity"]
        self.assertIsNone(wrong_format["seconds"])
        self.assertEqual(wrong_format["samples"], 0)

    def test_failed_and_estimated_generations_are_saved_but_do_not_calibrate(self):
        from types import SimpleNamespace
        summarizer = SimpleNamespace(_quota_tokens_used=0, _quota_usage_estimated=False)
        with self.assertRaisesRegex(RuntimeError, "private error"):
            with quota_tracker.track_audio_processing(summarizer, 600, source="recording", workspace="dnd"):
                summarizer._quota_tokens_used = 1200
                raise RuntimeError("private error")
        quota_tracker.record_audio_sample(600, 2000, source="recording", workspace="dnd", usage_estimated=True)
        history = quota_tracker.get_processing_usage()
        self.assertEqual(history["records"], 2)
        self.assertEqual(history["recent"][0]["status"], "failed")
        self.assertEqual(history["recent"][0]["tokens_used"], 1200)
        self.assertNotIn("private error", str(history))
        self.assertEqual(quota_tracker.get_quota_status(source="recording", workspace="dnd")["audio_capacity"]["samples"], 0)

    def test_generation_tracker_records_only_its_own_usage_and_numeric_metadata(self):
        from types import SimpleNamespace
        summarizer = SimpleNamespace(_quota_tokens_used=500, _quota_usage_estimated=False)
        with quota_tracker.track_audio_processing(summarizer, 120, source="recording", workspace="work_and_study", document_format="academic"):
            summarizer._quota_tokens_used += 1600
        row = quota_tracker.get_processing_usage()["recent"][0]
        self.assertEqual(row["tokens_used"], 1600)
        self.assertEqual(row["source"], "recording")
        self.assertEqual(row["workspace"], "work_and_study")
        self.assertEqual(row["document_format"], "academic")
        self.assertEqual(row["stage"], "generation")
        self.assertGreaterEqual(row["generation_seconds"], 0)
        self.assertTrue(row["timestamp"].endswith("+00:00"))
        self.assertEqual(set(row), {"duration_seconds", "tokens_used", "source", "workspace", "document_format", "status", "usage_estimated", "generation_seconds", "timestamp", "stage"})

    def test_profile_endpoint_validates_categories_and_exposes_local_usage(self):
        response = self.client.get('/api/system/quota?source=file&workspace=work_and_study&document_format=executive')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["audio_capacity"]["samples"], 0)
        self.assertEqual(self.client.get('/api/system/quota?source=anything').status_code, 422)
        self.assertEqual(self.client.get('/api/system/usage').json()["storage"], "local")


    def test_fallback_token_count_is_marked_estimated_and_not_used_for_calibration(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from src.summarizer.gemini_client import GeminiTTRPGSummarizer
        summarizer = GeminiTTRPGSummarizer(api_key="test-only")
        summarizer._client = MagicMock()
        summarizer._client.models.generate_content.return_value = SimpleNamespace(text="Respuesta", usage_metadata=None)
        with patch.object(quota_tracker, "record_gemini_tokens"):
            with quota_tracker.track_audio_processing(summarizer, 120, source="file", workspace="dnd"):
                summarizer._generate_with_retry("Transcripción de ejemplo")
        row = quota_tracker.get_processing_usage()["recent"][0]
        self.assertTrue(row["usage_estimated"])
        self.assertGreater(row["tokens_used"], 0)
        self.assertEqual(quota_tracker.get_quota_status(source="file", workspace="dnd")["audio_capacity"]["samples"], 0)


if __name__ == "__main__":
    unittest.main()
