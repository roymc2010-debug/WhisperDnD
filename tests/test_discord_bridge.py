"""Unit tests for client_bridge.discord_bridge module."""

import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from client_bridge.discord_bridge import (
    DiscordBridge,
    DiscordIpcClient,
    WASAPIStereoRecorder,
    draw_vu_meter,
)


class TestDiscordBridge(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_draw_vu_meter(self):
        silent = draw_vu_meter(0.0, width=8)
        self.assertEqual(silent, "[░░░░░░░░]")

        loud = draw_vu_meter(0.2, width=8)
        self.assertEqual(loud, "[████████]")

    def test_discord_ipc_event_handling(self):
        client = DiscordIpcClient()
        client.session_start_time = 1000.0
        client.is_tracking = True

        # Test voice channel select
        import asyncio
        data = {
            "id": "123456789",
            "name": "General Voice",
            "voice_states": [
                {
                    "nick": "Gorg",
                    "user": {
                        "id": "user_111",
                        "username": "streamer_a",
                        "global_name": "Streamer A",
                    },
                }
            ],
        }
        asyncio.run(client._handle_channel_select(data, lambda *args: None))
        self.assertEqual(client.current_channel_id, "123456789")
        self.assertEqual(client.current_channel_name, "General Voice")
        self.assertIn("user_111", client.participants)
        self.assertEqual(client.participants["user_111"]["display_name"], "Gorg")

        # Test speaking start & stop
        with patch("time.time", side_effect=[1002.5, 1006.8]):
            client._handle_speaking_start({"user_id": "user_111"})
            self.assertIn("user_111", client.active_speaking)
            self.assertEqual(client.active_speaking["user_111"], 2.5)

            client._handle_speaking_stop({"user_id": "user_111"})
            self.assertNotIn("user_111", client.active_speaking)
            self.assertEqual(len(client.speaking_log), 1)
            event = client.speaking_log[0]
            self.assertEqual(event["user_id"], "user_111")
            self.assertEqual(event["speaker"], "Gorg")
            self.assertEqual(event["start"], 2.5)
            self.assertEqual(event["end"], 6.8)

    def test_discord_bridge_stop_recording_generates_telemetry_json(self):
        bridge = DiscordBridge(output_dir=self.temp_dir)
        bridge.session_start_time = time.time() - 10.0
        bridge.current_wav_path = str(Path(self.temp_dir) / "test.wav")
        Path(bridge.current_wav_path).write_bytes(b"dummy wav")
        bridge.current_json_path = str(Path(self.temp_dir) / "discord_events.json")

        bridge.ipc.current_channel_id = "channel_999"
        bridge.ipc.current_channel_name = "Sala D&D"
        bridge.ipc.participants = {
            "u1": {"user_id": "u1", "username": "alice", "display_name": "Alice"}
        }
        bridge.ipc.speaking_log = [
            {"start": 1.0, "end": 4.0, "speaker": "Alice", "user_id": "u1"}
        ]

        with patch.object(bridge.recorder, "stop", return_value=bridge.current_wav_path):
            result = bridge.stop_recording()

        self.assertEqual(result["wav_path"], bridge.current_wav_path)
        self.assertTrue(Path(bridge.current_json_path).is_file())

        saved_data = json.loads(Path(bridge.current_json_path).read_text(encoding="utf-8"))
        self.assertEqual(saved_data["channel_id"], "channel_999")
        self.assertEqual(saved_data["channel_name"], "Sala D&D")
        self.assertEqual(len(saved_data["participants"]), 1)
        self.assertEqual(len(saved_data["events"]), 1)
        self.assertEqual(saved_data["events"][0]["user_id"], "u1")

    @patch("urllib.request.urlopen")
    def test_upload_to_render_formats_multipart(self, mock_urlopen):
        bridge = DiscordBridge(server_url="https://whisperdnd.onrender.com", output_dir=self.temp_dir)

        wav_path = Path(self.temp_dir) / "session.wav"
        wav_path.write_bytes(b"RIFF dummy stereo wav data")
        json_path = Path(self.temp_dir) / "events.json"
        json_path.write_text(json.dumps({"events": []}), encoding="utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "status": "completed",
            "campaign_name": "Dragonlance",
            "session_number": 3,
            "session_title": "El Regreso",
            "telemetry_events_count": 5,
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        res = bridge.upload_to_render(
            wav_path=str(wav_path),
            events_json_path=str(json_path),
            campaign_name="Dragonlance",
            session_number=3,
            roster=[{"character_name": "Raistlin", "player_name": "Roy"}],
            target_language="es",
            recording_mode="roleplay",
            engine="groq",
            gemini_api_key="gem_123",
            groq_api_key="groq_456",
        )

        self.assertEqual(res["session_title"], "El Regreso")
        self.assertTrue(mock_urlopen.called)

        # Inspect request
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://whisperdnd.onrender.com/api/sessions/upload-with-telemetry")
        self.assertEqual(req.headers.get("X-gemini-key"), "gem_123")
        self.assertEqual(req.headers.get("X-groq-key"), "groq_456")

        body_str = req.data.decode("utf-8", errors="replace")
        self.assertIn("name=\"campaign_name\"\r\n\r\nDragonlance", body_str)
        self.assertIn("name=\"session_number\"\r\n\r\n3", body_str)
        self.assertIn("name=\"roster_json\"", body_str)
        self.assertIn("Raistlin", body_str)
        self.assertIn("name=\"audio_file\"; filename=\"session.wav\"", body_str)
        self.assertIn("name=\"events_file\"; filename=\"events.json\"", body_str)


if __name__ == "__main__":
    unittest.main()
