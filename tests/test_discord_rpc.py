import asyncio
import unittest
from unittest.mock import MagicMock
from src.transcription.discord_rpc import (
    match_user_id_in_interval,
    match_speaker_in_interval,
    DiscordRpcTracker,
)


class TestDiscordRPC(unittest.TestCase):
    """Test suite for Discord RPC speaking log matcher and participant tracking."""

    def test_match_user_id_in_interval(self):
        speaking_log = [
            {"start": 10.0, "end": 15.0, "user_id": "111", "username": "Alice"},
            {"start": 16.0, "end": 20.0, "user_id": "222", "username": "Bob"},
        ]

        # Exact match inside interval
        self.assertEqual(match_user_id_in_interval(10.5, 14.5, speaking_log), "111")
        # Overlapping boundary
        self.assertEqual(match_user_id_in_interval(15.5, 18.0, speaking_log), "222")
        # No overlap
        self.assertIsNone(match_user_id_in_interval(0.0, 5.0, speaking_log))
        # Insufficient overlap (< 0.15s default min_overlap)
        self.assertIsNone(match_user_id_in_interval(14.95, 16.0, speaking_log))

    def test_match_speaker_in_interval(self):
        speaking_log = [
            {"start": 5.0, "end": 10.0, "user_id": "333", "username": "Charlie"},
        ]
        self.assertEqual(match_speaker_in_interval(6.0, 8.0, speaking_log), "Charlie")
        self.assertIsNone(match_speaker_in_interval(0.0, 4.0, speaking_log))

    def test_tracker_participants_lifecycle(self):
        tracker = DiscordRpcTracker()
        tracker._connected = True

        # Before connecting to channel
        status = tracker.get_active_participants()
        self.assertFalse(status["connected"])
        self.assertEqual(len(status["participants"]), 0)

        # Connect to voice channel with participants
        select_event = {
            "channel_id": "987654321",
            "name": "Sala de Aventuras",
            "voice_states": [
                {
                    "user": {"id": "101", "username": "player1", "global_name": "Player One"},
                    "nick": "Kaelen",
                },
                {
                    "user": {"id": "102", "username": "dm_host", "global_name": "The DM"},
                    "nick": None,
                },
            ],
        }
        asyncio.run(tracker._handle_voice_channel_select(select_event))

        status = tracker.get_active_participants()
        self.assertTrue(status["connected"])
        self.assertEqual(status["channel_id"], "987654321")
        self.assertEqual(status["channel_name"], "Sala de Aventuras")
        self.assertEqual(len(status["participants"]), 2)

        p1 = next(p for p in status["participants"] if p["user_id"] == "101")
        self.assertEqual(p1["display_name"], "Kaelen")
        self.assertEqual(p1["username"], "player1")

        p2 = next(p for p in status["participants"] if p["user_id"] == "102")
        self.assertEqual(p2["display_name"], "The DM")
        self.assertEqual(p2["username"], "dm_host")

        # Disconnect event (channel_id = None)
        asyncio.run(tracker._handle_voice_channel_select({"channel_id": None}))
        disconnected_status = tracker.get_active_participants()
        self.assertFalse(disconnected_status["connected"])
        self.assertEqual(len(disconnected_status["participants"]), 0)


if __name__ == "__main__":
    unittest.main()
