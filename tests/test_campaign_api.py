"""Unit tests for Living Campaign Journal API endpoints."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.api.server import app


class TestCampaignApi(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_out_dir = tempfile.mkdtemp()
        self.env_patch = patch.dict("os.environ", {
            "WHISPER_CAMPAIGNS_DIR": self.temp_dir,
            "WHISPER_OUTPUT_DIR": self.temp_out_dir,
        })
        self.env_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.env_patch.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.temp_out_dir, ignore_errors=True)

    def test_list_and_create_campaign(self):
        # Create or init campaign
        create_payload = {
            "campaign_name": "API Test Campaign",
            "roster": [
                {
                    "player_name": "Rodrigo",
                    "character_name": "Markus Veyl",
                    "species": "Humano",
                    "role": "Guerrero",
                    "subclass": "Battle Master",
                }
            ],
        }
        res = self.client.post("/api/campaigns", json=create_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["campaign_name"], "API Test Campaign")
        self.assertEqual(len(data["roster"]), 1)

        # Get campaign
        get_res = self.client.get("/api/campaigns/API Test Campaign")
        self.assertEqual(get_res.status_code, 200)
        get_data = get_res.json()
        self.assertIn("campaign_state", get_data)
        self.assertIn("active_context", get_data)
        self.assertEqual(get_data["active_context"]["session_number"], 1)

        # List campaigns
        list_res = self.client.get("/api/campaigns")
        self.assertEqual(list_res.status_code, 200)
        camps = list_res.json()
        self.assertTrue(any(c["campaign_name"] == "API Test Campaign" for c in camps))

    def test_subobjective_and_spellcheck_endpoints(self):
        # First create campaign with a quest and NPC
        from src.storage.campaign_manager import CampaignManager
        mgr = CampaignManager()
        mgr.record_session(
            name="API Interactive Test",
            session_chapter={"title": "Capítulo 1"},
            updated_quests=[
                {
                    "id": "q1",
                    "title": "Cazar trasgos",
                    "status": "in_progress",
                    "subobjectives": [{"text": "Buscar cueva", "completed": False}],
                }
            ],
            updated_npcs=[{"name": "Thork", "role": "Herrero"}],
            session_number=1,
        )

        # Update subobjective
        sub_res = self.client.put(
            "/api/campaigns/API Interactive Test/quests/q1/subobjective",
            json={"subobjective_idx": 0, "completed": True},
        )
        self.assertEqual(sub_res.status_code, 200)
        sub_data = sub_res.json()
        self.assertEqual(sub_data["status"], "success")
        self.assertTrue(sub_data["campaign_state"]["quests"][0]["subobjectives"][0]["completed"])

        # Finalize NPCs spellcheck
        npc_res = self.client.post(
            "/api/campaigns/API Interactive Test/finalize-npcs",
            json={"name_corrections": {"Thork": "Thor'kall el Firbolg"}},
        )
        self.assertEqual(npc_res.status_code, 200)
        npc_data = npc_res.json()
        self.assertEqual(npc_data["status"], "success")
        self.assertEqual(npc_data["campaign_state"]["npcs"][0]["name"], "Thor'kall el Firbolg")

    def test_download_docx_and_md_endpoints(self):
        # Create campaign state first
        from src.storage.campaign_manager import CampaignManager
        mgr = CampaignManager()
        mgr.load_campaign("Download Test Campaign")

        docx_res = self.client.get("/api/campaigns/Download Test Campaign/download-docx")
        self.assertEqual(docx_res.status_code, 200)
        self.assertEqual(
            docx_res.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        md_res = self.client.get("/api/campaigns/Download Test Campaign/download-md")
        self.assertEqual(md_res.status_code, 200)
        self.assertEqual(md_res.headers["content-type"], "text/markdown; charset=utf-8")

    def test_delete_campaign_endpoint(self):
        from src.storage.campaign_manager import CampaignManager
        mgr = CampaignManager()
        state = mgr.load_campaign("Delete Test Campaign")
        mgr.save_campaign(state)

        # Verify it exists in listing
        list_res = self.client.get("/api/campaigns")
        self.assertEqual(list_res.status_code, 200)
        camps = list_res.json()
        self.assertTrue(any(c["campaign_name"] == "Delete Test Campaign" for c in camps))

        # Delete via API
        del_res = self.client.delete("/api/campaigns/Delete Test Campaign")
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(del_res.json()["status"], "deleted")
        self.assertEqual(del_res.json()["campaign"], "Delete Test Campaign")

        # Verify it is gone
        list_res_after = self.client.get("/api/campaigns")
        camps_after = list_res_after.json()
        self.assertFalse(any(c["campaign_name"] == "Delete Test Campaign" for c in camps_after))

    def test_put_prior_lore_and_create_with_lore(self):
        # 1. Create with prior_lore
        create_payload = {
            "campaign_name": "Lore Test Campaign",
            "prior_lore": "El grupo ya derrotó al dragón en la sesión 4.",
        }
        res = self.client.post("/api/campaigns", json=create_payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["prior_lore"], "El grupo ya derrotó al dragón en la sesión 4.")

        # 2. Get campaign and check prior_lore in active_context
        get_res = self.client.get("/api/campaigns/Lore Test Campaign")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["campaign_state"]["prior_lore"], "El grupo ya derrotó al dragón en la sesión 4.")
        self.assertEqual(get_res.json()["active_context"]["prior_lore"], "El grupo ya derrotó al dragón en la sesión 4.")

        # 3. Update prior_lore via PUT endpoint
        put_res = self.client.put(
            "/api/campaigns/Lore Test Campaign/prior-lore",
            json={"prior_lore": "Lore ampliado: descubrieron un templo subterráneo en la sesión 5."},
        )
        self.assertEqual(put_res.status_code, 200)
        put_data = put_res.json()
        self.assertEqual(put_data["status"], "success")
        self.assertEqual(put_data["prior_lore"], "Lore ampliado: descubrieron un templo subterráneo en la sesión 5.")

        # 4. Verify persisted state
        get_res2 = self.client.get("/api/campaigns/Lore Test Campaign")
        self.assertEqual(get_res2.json()["campaign_state"]["prior_lore"], "Lore ampliado: descubrieron un templo subterráneo en la sesión 5.")

    def test_put_quest_status_toggle(self):
        # 1. Create a campaign with a quest
        self.client.post("/api/campaigns", json={"campaign_name": "Quest Toggle Campaign"})
        from src.storage.campaign_manager import CampaignManager
        manager = CampaignManager()
        quests = [
            {
                "id": "q_api_tog",
                "title": "Misión de Prueba API",
                "status": "in_progress",
                "subobjectives": [{"id": "s1", "text": "Paso 1", "completed": False}],
            }
        ]
        manager.record_session("Quest Toggle Campaign", session_chapter={"title": "S1"}, updated_quests=quests)

        # 2. Toggle status via PUT /status
        put_res = self.client.put("/api/campaigns/Quest Toggle Campaign/quests/q_api_tog/status")
        self.assertEqual(put_res.status_code, 200)
        state1 = put_res.json()["campaign_state"]
        q1 = next(q for q in state1["quests"] if q["id"] == "q_api_tog")
        self.assertEqual(q1["status"], "completed")

        # 3. Toggle back
        put_res2 = self.client.put("/api/campaigns/Quest Toggle Campaign/quests/q_api_tog/status")
        self.assertEqual(put_res2.status_code, 200)
        state2 = put_res2.json()["campaign_state"]
        q2 = next(q for q in state2["quests"] if q["id"] == "q_api_tog")
        self.assertEqual(q2["status"], "in_progress")

    def test_get_campaign_session_endpoint_success(self):
        """Test retrieving full historical session data including chronicle_markdown and raw_transcript."""
        from src.storage.campaign_manager import CampaignManager
        manager = CampaignManager()
        camp_name = "Session Fetch Test Camp"

        manager.record_session(
            name=camp_name,
            session_chapter={
                "title": "La Cripta Olvidada",
                "chronicle_text": "El grupo entró a la cripta.",
                "closing_expectations": "Subir a nivel 3.",
                "recap_text": "Resumen para la próxima sesión.",
            },
            updated_quests=[{"id": "q_crypt", "title": "Limpiar la cripta", "status": "in_progress"}],
            updated_npcs=[{"name": "Sacerdote Elian", "role": "Clérigo"}],
            detected_pcs=[{"character_name": "Valeros", "player_name": "Carlos", "role": "Guerrero"}],
            session_number=1,
            chronicle_markdown="# Crónica Completa de la Sesión 1\n\nTodo salió bien.",
            raw_transcript="[00:00:01 -> 00:00:05] 🎙️ [TÚ / Valeros]: Abro la puerta.",
        )

        res = self.client.get(f"/api/campaigns/{camp_name}/session/1")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["campaign_name"], camp_name)
        self.assertEqual(data["session_number"], 1)
        self.assertEqual(data["title"], "La Cripta Olvidada")
        self.assertEqual(data["chronicle_markdown"], "# Crónica Completa de la Sesión 1\n\nTodo salió bien.")
        self.assertEqual(data["raw_transcript"], "[00:00:01 -> 00:00:05] 🎙️ [TÚ / Valeros]: Abro la puerta.")
        self.assertEqual(len(data["quests"]), 1)
        self.assertEqual(len(data["npcs"]), 1)
        self.assertEqual(len(data["pcs"]), 1)
        self.assertIn("Resumen", data["recap"])

    def test_get_campaign_session_endpoint_synthesis_fallback(self):
        """When chronicle_markdown or raw_transcript were not stored, the endpoint synthesizes fallbacks cleanly."""
        from src.storage.campaign_manager import CampaignManager
        manager = CampaignManager()
        camp_name = "Session Synthesis Camp"

        manager.record_session(
            name=camp_name,
            session_chapter={
                "title": "El Pantano Sombrío",
                "chronicle_text": "Combate en el pantano.",
                "closing_expectations": "Descansar en la posada.",
            },
            session_number=1,
        )

        res = self.client.get(f"/api/campaigns/{camp_name}/session/1")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("## 1. Crónica Narrativa y Combates\nCombate en el pantano.", data["chronicle_markdown"])
        self.assertIn("## 2. Cierre de Mesa, Decisiones y Expectativas\nDescansar en la posada.", data["chronicle_markdown"])
        self.assertIn("Transcripción no guardada", data["raw_transcript"])

    def test_get_campaign_session_endpoint_not_found(self):
        """404 should be returned if campaign or session number does not exist."""
        res = self.client.get("/api/campaigns/Inexistente/session/99")
        self.assertEqual(res.status_code, 404)

    def test_merge_entities_endpoint(self):
        from src.storage.campaign_manager import CampaignManager
        manager = CampaignManager()
        camp_name = "API Merge Entities Camp"

        state = manager.load_campaign(camp_name)
        state["universal_pcs"] = [
            {"personaje": "Lancelot", "jugador": "Player1", "clase": "Paladín", "debut_sesion": 2, "hitos_acumulados": ["Sesión #2: Rescató aldeanos."]},
            {"personaje": "Sir Lancelot Du Lac", "jugador": "Player1", "clase": "Paladín", "debut_sesion": 1, "hitos_acumulados": ["Sesión #1: Juró lealtad."]}
        ]
        manager.save_campaign(state)

        # Call merge-entities endpoint
        merge_payload = {
            "source_name": "Lancelot",
            "target_name": "Sir Lancelot Du Lac",
            "entity_type": "pc"
        }
        res = self.client.post(f"/api/campaigns/{camp_name}/merge-entities", json=merge_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("Sir Lancelot Du Lac", data["message"])
        self.assertEqual(len(data["campaign_state"]["universal_pcs"]), 1)
        merged = data["campaign_state"]["universal_pcs"][0]
        self.assertEqual(merged["personaje"], "Sir Lancelot Du Lac")
        self.assertIn("Lancelot", merged.get("aliases", []))
        self.assertEqual(len(merged["hitos_acumulados"]), 2)

    def test_deduplicate_campaign_endpoint(self):
        from src.storage.campaign_manager import CampaignManager
        manager = CampaignManager()
        camp_name = "API Deduplicate Camp"

        state = manager.load_campaign(camp_name)
        state["universal_pcs"] = [
            {"personaje": "Octus", "jugador": "Alex", "clase": "Rogue", "debut_sesion": 1, "hitos_acumulados": ["Sesión #1: Flophouse."]},
            {"personaje": "Octus Taconis", "jugador": "Alex", "clase": "Rogue", "debut_sesion": 3, "hitos_acumulados": ["Sesión #3: Palazzo."]}
        ]
        manager.save_campaign(state)

        res = self.client.post(f"/api/campaigns/{camp_name}/deduplicate")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["merged_count"], 1)
        self.assertEqual(len(data["campaign_state"]["universal_pcs"]), 1)
        self.assertEqual(data["campaign_state"]["universal_pcs"][0]["personaje"], "Octus Taconis")
        self.assertIn("Octus", data["campaign_state"]["universal_pcs"][0].get("aliases", []))

    def test_dm_and_discord_persistence_save_endpoint(self):
        camp_name = "DM Persistence Campaign"
        payload = {
            "campaign_name": camp_name,
            "dm_name": "Dungeon Master Roy",
            "dm_discord_id": "9876543210",
            "roster": [
                {
                    "player_name": "Dungeon Master Roy",
                    "character_name": "(DM)",
                    "species": "(N/A - DM)",
                    "role": "Dungeon Master (DM)",
                    "subclass": "N/A",
                    "discord_user_id": "9876543210",
                },
                {
                    "player_name": "Alice",
                    "character_name": "Valeros",
                    "species": "Humano",
                    "role": "Guerrero",
                    "subclass": "Champion",
                    "discord_user_id": "111222333",
                }
            ]
        }
        # Test /api/campaigns/save route alias
        res = self.client.post("/api/campaigns/save", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["dm_name"], "Dungeon Master Roy")
        self.assertEqual(data["dm"], "Dungeon Master Roy")
        self.assertEqual(data["dm_discord_id"], "9876543210")
        self.assertEqual(data["dm_discord"], "9876543210")
        self.assertEqual(data["roster"][0]["player_name"], "Dungeon Master Roy")
        self.assertEqual(data["roster"][0]["character_name"], "(DM)")
        self.assertEqual(data["roster"][0]["discord_user_id"], "9876543210")

        # Test GET /api/campaigns/{campaign_name}
        get_res = self.client.get(f"/api/campaigns/{camp_name}")
        self.assertEqual(get_res.status_code, 200)
        get_data = get_res.json()
        state = get_data["campaign_state"]
        self.assertEqual(state["dm_name"], "Dungeon Master Roy")
        self.assertEqual(state["dm_discord_id"], "9876543210")
        self.assertEqual(state["roster"][0]["player_name"], "Dungeon Master Roy")
        self.assertEqual(state["roster"][0]["discord_user_id"], "9876543210")


if __name__ == "__main__":
    unittest.main()


