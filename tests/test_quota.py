"""Unit tests for API Token and Audio Quota Tracker."""

import os
import unittest
from starlette.testclient import TestClient

from src.api.server import app
from src.storage import quota_tracker


class TestQuotaTracker(unittest.TestCase):
    def setUp(self):
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


if __name__ == "__main__":
    unittest.main()
