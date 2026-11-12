"""
Regression tests for campaign selection, session 4 persistence in Candlekeep 2.0,
and re-recording idempotency without data duplication.
"""

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from src.storage.campaign_manager import CampaignManager


class TestCampaignSessionsRegression(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = CampaignManager(campaigns_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_candlekeep_session_4_is_not_wiped_on_record_and_reload(self):
        """
        REGRESSION TEST:
        Previously, _clean_candlekeep_taint had a hardcoded filter:
        sessions = [s for s in data.get("sessions", []) if s.get("session_number") != 4]
        which deleted session 4 every time Candlekeep was loaded or saved!
        """
        camp_name = "Candlekeep 2.0"

        # 1. Record sessions 1, 2, 3
        for s_num in [1, 2, 3]:
            self.manager.record_session(
                name=camp_name,
                session_chapter={
                    "session_number": s_num,
                    "title": f"Capítulo {s_num}",
                    "chronicle_text": f"Texto de la crónica de la sesión {s_num}",
                },
                session_number=s_num,
            )

        state_after_3 = self.manager.load_campaign(camp_name)
        self.assertEqual(len(state_after_3["sessions"]), 3)
        self.assertEqual(state_after_3["last_session"], 3)

        # 2. Record session 4
        self.manager.record_session(
            name=camp_name,
            session_chapter={
                "session_number": 4,
                "title": "La Noche en las Ruinas",
                "chronicle_text": "Crónica épica de la sesión 4 en Candlekeep 2.0",
            },
            session_number=4,
        )

        # 3. Reload campaign state from disk
        reloaded = self.manager.load_campaign(camp_name)
        session_numbers = [s["session_number"] for s in reloaded.get("sessions", [])]

        # Session 4 MUST persist!
        self.assertIn(4, session_numbers, f"Session 4 was wiped! Existing sessions: {session_numbers}")
        self.assertEqual(reloaded["last_session"], 4)
        self.assertEqual(len(reloaded["sessions"]), 4)

    def test_reprocessing_session_replaces_without_duplication(self):
        """
        Verify that re-processing an existing session number (e.g. Session 4)
        replaces the record with updated content without creating duplicates.
        """
        camp_name = "Candlekeep 2.0"

        # First pass for session 4
        self.manager.record_session(
            name=camp_name,
            session_chapter={
                "session_number": 4,
                "title": "Título Borrador",
                "chronicle_text": "Texto inicial",
            },
            session_number=4,
        )

        # Second pass for session 4 (re-processing)
        self.manager.record_session(
            name=camp_name,
            session_chapter={
                "session_number": 4,
                "title": "Título Definitivo",
                "chronicle_text": "Texto definitivo y corregido",
            },
            session_number=4,
        )

        state = self.manager.load_campaign(camp_name)
        s4_list = [s for s in state.get("sessions", []) if s.get("session_number") == 4]
        self.assertEqual(len(s4_list), 1, "Duplicate session 4 records found!")
        self.assertEqual(s4_list[0]["title"], "Título Definitivo")
        self.assertEqual(s4_list[0]["chronicle_text"], "Texto definitivo y corregido")

    def test_list_campaigns_includes_modular_campaigns(self):
        """
        Verify that list_campaigns detects campaigns whether stored as monolithic JSON
        or modular directory structures (with campaign.json).
        """
        # Create a modular campaign directory without root .json
        mod_dir = Path(self.temp_dir) / "modular_adventure"
        mod_dir.mkdir(parents=True)
        (mod_dir / "campaign.json").write_text(
            json.dumps({"campaign_name": "Aventura Modular", "storage_version": 2, "last_session": 1, "sessions": [{"session_number": 1}]}),
            encoding="utf-8"
        )

        # Monolithic campaign
        (Path(self.temp_dir) / "campana_clasica.json").write_text(
            json.dumps({"campaign_name": "Campaña Clásica", "last_session": 2, "sessions": [{"session_number": 1}, {"session_number": 2}]}),
            encoding="utf-8"
        )

        camps = self.manager.list_campaigns()
        camp_names = [c["name"] for c in camps]
        self.assertIn("Campaña Clásica", camp_names)
        self.assertIn("Aventura Modular", camp_names)

        # Test deduplication: if both monolithic and modular directory exist for same campaign
        mod_camp_path = Path(self.temp_dir) / "campana_clasica"
        mod_camp_path.mkdir(parents=True, exist_ok=True)
        (mod_camp_path / "campaign.json").write_text(
            json.dumps({"campaign_name": "Campaña Clásica", "storage_version": 2, "last_session": 2, "sessions": [{"session_number": 1}, {"session_number": 2}]}),
            encoding="utf-8"
        )
        camps_dedup = self.manager.list_campaigns()
        clasica_entries = [c for c in camps_dedup if c["name"] == "Campaña Clásica"]
        self.assertEqual(len(clasica_entries), 1, "Duplicate campaign entry when both monolithic and modular exist!")

    def test_new_session_appears_in_wiki_after_saving(self):
        """
        Verify that after record_session completes, load_campaign and list_campaigns
        immediately reflect the updated session count and session records so the Wiki
        and session selectors get fresh data without caching stale sessions.
        """
        camp_name = "Candlekeep 2.0"

        # Initial 3 sessions
        for s in [1, 2, 3]:
            self.manager.record_session(
                name=camp_name,
                session_chapter={"session_number": s, "title": f"S{s}"},
                session_number=s,
            )

        camps_before = self.manager.list_campaigns()
        c_before = next(c for c in camps_before if c["name"] == camp_name)
        self.assertEqual(c_before["sessions_count"], 3)
        self.assertEqual(c_before["last_session"], 3)

        # Record session 4
        self.manager.record_session(
            name=camp_name,
            session_chapter={"session_number": 4, "title": "Capítulo 4"},
            session_number=4,
        )

        # Check list_campaigns for Wiki selector
        camps_after = self.manager.list_campaigns()
        c_after = next(c for c in camps_after if c["name"] == camp_name)
        self.assertEqual(c_after["sessions_count"], 4)
        self.assertEqual(c_after["last_session"], 4)

        # Check loaded state for Wiki sessions view
        state = self.manager.load_campaign(camp_name)
        session_nums = [s["session_number"] for s in state.get("sessions", [])]
        self.assertIn(4, session_nums)


if __name__ == "__main__":
    unittest.main()
