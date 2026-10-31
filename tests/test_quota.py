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


if __name__ == "__main__":
    unittest.main()
