"""Unit tests for CampaignManager persistence and multi-session continuity."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.storage.campaign_manager import CampaignManager, purge_session_data


class TestCampaignManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.env_patcher = patch.dict(
            "os.environ",
            {
                "WHISPER_CAMPAIGNS_DIR": self.temp_dir,
                "WHISPER_OUTPUT_DIR": self.temp_dir,
            },
        )
        self.env_patcher.start()
        self.manager = CampaignManager(campaigns_dir=self.temp_dir)

    def tearDown(self):
        self.env_patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_nonexistent_creates_default(self):
        state = self.manager.load_campaign("Campaña de Prueba")
        self.assertEqual(state["campaign_name"], "Campaña de Prueba")
        self.assertEqual(state["last_session"], 0)
        self.assertEqual(len(state["quests"]), 0)
        self.assertEqual(len(state["npcs"]), 0)
        self.assertEqual(len(state["sessions"]), 0)

    def test_multi_session_continuity_and_merging(self):
        # Session 1
        roster = [
            {"player_name": "Rodrigo", "character_name": "Markus Veyl", "species": "Humano", "role": "Guerrero", "subclass": "Battle Master"}
        ]
        s1_chapter = {
            "title": "El Inicio del Viaje",
            "recap_text": "Recap de la primera sesión.",
            "chronicle_text": "Markus y el grupo combatieron a los goblins en el camino.",
            "closing_expectations": "Llegar a la villa de Oakhaven.",
            "markus_coaching": "Buen uso de Riposte. Olvidó Second Wind.",
        }
        s1_quests = [
            {
                "id": "q1",
                "title": "Investigar la caravana perdida",
                "context": "El comerciante prometió 100 po.",
                "status": "in_progress",
                "subobjectives": [
                    {"text": "Seguir el rastro", "completed": True},
                    {"text": "Encontrar el escondite", "completed": False},
                ],
            }
        ]
        s1_npcs = [
            {"name": "Barkeep Tomas", "role": "Tabernero", "notes": ["Sesión 1: Informó sobre los bandidos"]}
        ]

        state1 = self.manager.record_session(
            name="Campaña de Prueba",
            session_chapter=s1_chapter,
            updated_quests=s1_quests,
            updated_npcs=s1_npcs,
            detected_npc_names=["Barkeep Tomas"],
            roster=roster,
            session_number=1,
        )

        self.assertEqual(state1["last_session"], 1)
        self.assertEqual(len(state1["sessions"]), 1)
        self.assertEqual(len(state1["quests"]), 1)
        self.assertEqual(state1["quests"][0]["id"], "q1")
        self.assertEqual(state1["quests"][0]["subobjectives"][0]["completed"], True)
        self.assertEqual(state1["quests"][0]["subobjectives"][1]["completed"], False)
        self.assertIn("Iniciada en Sesión 1", state1["quests"][0]["lifecycle_notes"])
        self.assertEqual(len(state1["npcs"]), 1)
        self.assertEqual(state1["npcs"][0]["name"], "Barkeep Tomas")

        # Session 2 - Advances quest q1, completes it, adds a new NPC and notes to Tomas
        s2_chapter = {
            "title": "La Cueva de los Bandidos",
            "recap_text": "Recap de la segunda sesión.",
            "chronicle_text": "El grupo derrotó al líder de los bandidos.",
            "closing_expectations": "Cobrar la recompensa.",
            "markus_coaching": "Excelente Action Surge en el turno 2.",
        }
        s2_quests = [
            {
                "id": "q1",
                "title": "Investigar la caravana perdida",
                "status": "completed",
                "subobjectives": [
                    {"text": "Encontrar el escondite", "completed": True},
                    {"text": "Rescatar supervivientes", "completed": True},
                ],
            },
            {
                "id": "q2",
                "title": "El Amuleto del Culto",
                "context": "Encontrado en el cadáver del líder bandido.",
                "status": "in_progress",
                "subobjectives": [
                    {"text": "Llevar el amuleto al sabio", "completed": False}
                ],
            },
        ]
        s2_npcs = [
            {"name": "Barkeep Tomas", "role": "Tabernero de Oakhaven", "notes": ["Sesión 2: Agradeció la recuperación de la cerveza"]},
            {"name": "Alcalde Roderick", "role": "Líder de Oakhaven", "notes": ["Sesión 2: Pagó la recompensa"]},
        ]

        state2 = self.manager.record_session(
            name="Campaña de Prueba",
            session_chapter=s2_chapter,
            updated_quests=s2_quests,
            updated_npcs=s2_npcs,
            detected_npc_names=["Alcalde Roderick"],
            session_number=2,
        )

        self.assertEqual(state2["last_session"], 2)
        self.assertEqual(len(state2["sessions"]), 2)
        # Quests: q1 updated, q2 added -> total 2
        self.assertEqual(len(state2["quests"]), 2)
        q1 = next(q for q in state2["quests"] if q["id"] == "q1")
        self.assertEqual(q1["status"], "completed")
        self.assertIn("Iniciada en Sesión 1", q1["lifecycle_notes"])
        self.assertIn("Completada en Sesión 2", q1["lifecycle_notes"])
        self.assertEqual(len(q1["subobjectives"]), 3)  # Seguir rastro + Encontrar escondite + Rescatar supervivientes

        # NPCs: Tomas updated with new note, Roderick added -> total 2
        self.assertEqual(len(state2["npcs"]), 2)
        tomas = next(n for n in state2["npcs"] if n["name"] == "Barkeep Tomas")
        self.assertEqual(len(tomas["notes"]), 2)
        self.assertIn("Sesión 1: Informó sobre los bandidos", tomas["notes"])
        self.assertIn("Sesión 2: Agradeció la recuperación de la cerveza", tomas["notes"])

    def test_update_quest_subobjective(self):
        state = self.manager.load_campaign("Test Subobj")
        s_quests = [
            {
                "id": "q1",
                "title": "Misión de Rescate",
                "status": "in_progress",
                "subobjectives": [
                    {"text": "Paso 1", "completed": False},
                    {"text": "Paso 2", "completed": False},
                ],
            }
        ]
        self.manager.record_session("Test Subobj", session_chapter={"title": "S1"}, updated_quests=s_quests)

        updated_state = self.manager.update_quest_subobjective("Test Subobj", "q1", 0, True)
        self.assertTrue(updated_state["quests"][0]["subobjectives"][0]["completed"])
        self.assertFalse(updated_state["quests"][0]["subobjectives"][1]["completed"])
        self.assertEqual(updated_state["quests"][0]["status"], "in_progress")

        # Complete second subobjective -> entire quest should auto-complete
        final_state = self.manager.update_quest_subobjective("Test Subobj", "q1", 1, True)
        self.assertTrue(final_state["quests"][0]["subobjectives"][1]["completed"])
        self.assertEqual(final_state["quests"][0]["status"], "completed")

    def test_update_npc_name_spellcheck(self):
        state = self.manager.load_campaign("Test Spellcheck")
        s_npcs = [
            {"name": "Gorgok el Ogro", "role": "Jefe Bandido", "notes": ["Sesión 1: Amenazó al grupo"]}
        ]
        self.manager.record_session("Test Spellcheck", session_chapter={"title": "S1"}, updated_npcs=s_npcs)

        updated_state = self.manager.update_npc_name("Test Spellcheck", "Gorgok el Ogro", "Gor'gok el Devorador")
        self.assertEqual(updated_state["npcs"][0]["name"], "Gor'gok el Devorador")

    def test_external_campaign_detected_party_and_purges_markus(self):
        # When an external campaign session is recorded with detected_party
        detected = [
            {"player_name": "StreamerA", "character_name": "Thorin", "species": "Enano", "role": "Guerrero", "subclass": "Campeón"}
        ]
        # Even if legacy roster mistakenly had Markus
        bad_roster = [
            {"player_name": "Roymc89", "character_name": "Markus Veyl", "species": "Humano", "role": "Guerrero", "subclass": "Battle Master"}
        ]
        state = self.manager.record_session(
            "Caoz con todo",
            session_chapter={"title": "S1"},
            roster=bad_roster,
            detected_party=detected,
        )
        self.assertEqual(state["detected_party"], detected)
        self.assertEqual(state["roster"], detected)
        self.assertFalse(any("markus" in str(p.get("character_name", "")).lower() for p in state["roster"]))

    def test_record_session_user_character_and_next_script(self):
        roster = [
            {"player_name": "Roymc89", "character_name": "Markus Veyl", "role": "Guerrero", "is_user_character": True},
            {"player_name": "Carlos", "character_name": "Selen", "role": "Mago", "is_user_character": False},
        ]
        session_chapter = {
            "title": "Apertura en el Bosque",
            "chronicle_text": "Los héroes lucharon con bravura.",
            "closing_expectations": "Descansar en la posada.",
            "user_coaching": "Excelente uso de Tactical Maneuvers.",
            "next_session_script": "A ver gente, para acordarnos: fuimos al bosque...",
        }
        user_char = {"character_name": "Markus Veyl", "player_name": "Roymc89", "role": "Guerrero", "is_user_character": True}
        state = self.manager.record_session(
            "Campaña Personal",
            session_chapter=session_chapter,
            roster=roster,
            user_character=user_char,
        )

        # Verify roster preserved is_user_character
        self.assertTrue(state["roster"][0]["is_user_character"])
        self.assertFalse(state["roster"][1]["is_user_character"])

        # Verify session chapter stored next_session_script and user_coaching
        session_rec = state["sessions"][0]
        self.assertEqual(session_rec["next_session_script"], "A ver gente, para acordarnos: fuimos al bosque...")
        self.assertEqual(session_rec["recap_text"], "A ver gente, para acordarnos: fuimos al bosque...")
        self.assertEqual(session_rec["user_coaching"], "Excelente uso de Tactical Maneuvers.")
        self.assertEqual(session_rec["user_character"]["character_name"], "Markus Veyl")


    def test_universal_pcs_accumulation_across_sessions(self):
        # Session 1: Party introduces themselves
        pcs_s1 = [
            {
                "personaje": "Kaelen",
                "jugador": "Laura",
                "especie": "Elfo",
                "clase": "Paladín",
                "subclase": "Voto de Devoción",
                "rol_en_sesion": "Salvó al rehén en el puente colapsado.",
            },
            {
                "personaje": "Boran",
                "jugador": "Carlos",
                "especie": "Enano",
                "clase": "Clérigo",
                "subclase": "-",
                "rol_en_sesion": "Curó a la party tras la emboscada.",
            }
        ]
        state1 = self.manager.record_session(
            "Campaña Épica",
            session_chapter={"title": "Sesión 1"},
            detected_pcs=pcs_s1,
            session_number=1,
        )

        self.assertIn("universal_pcs", state1)
        self.assertEqual(len(state1["universal_pcs"]), 2)
        kaelen = next(p for p in state1["universal_pcs"] if p["personaje"] == "Kaelen")
        self.assertEqual(kaelen["jugador"], "Laura")
        self.assertEqual(kaelen["clase"], "Paladín")
        self.assertEqual(kaelen["debut_sesion"], 1)
        self.assertEqual(len(kaelen["hitos_acumulados"]), 1)
        self.assertIn("Sesión #1: Salvó al rehén", kaelen["hitos_acumulados"][0])

        # Session 2: Boran reveals subclass, both achieve new milestones
        pcs_s2 = [
            {
                "personaje": "Kaelen",
                "jugador": "Laura",
                "especie": "Elfo",
                "clase": "Paladín",
                "subclase": "Voto de Devoción",
                "rol_en_sesion": "Desafió al comandante orco a combate singular.",
            },
            {
                "personaje": "Boran",
                "jugador": "Carlos",
                "especie": "Enano",
                "clase": "Clérigo",
                "subclase": "Dominio de la Guerra",
                "rol_en_sesion": "Invocó Guardianes Espirituales para repeler la horda.",
            },
            {
                "personaje": "Lyra",
                "jugador": "Sofía",
                "especie": "Tiefling",
                "clase": "Bardo",
                "subclase": "Colegio del Lore",
                "rol_en_sesion": "Descifró el acertijo de la puerta rúnica.",
            }
        ]
        state2 = self.manager.record_session(
            "Campaña Épica",
            session_chapter={"title": "Sesión 2"},
            detected_pcs=pcs_s2,
            session_number=2,
        )

        self.assertEqual(len(state2["universal_pcs"]), 3)
        boran = next(p for p in state2["universal_pcs"] if p["personaje"] == "Boran")
        self.assertEqual(boran["subclase"], "Dominio de la Guerra")
        self.assertEqual(boran["debut_sesion"], 1)
        self.assertEqual(len(boran["hitos_acumulados"]), 2)
        self.assertIn("Guardianes Espirituales", boran["hitos_acumulados"][1])

        lyra = next(p for p in state2["universal_pcs"] if p["personaje"] == "Lyra")
        self.assertEqual(lyra["debut_sesion"], 2)
        self.assertEqual(len(lyra["hitos_acumulados"]), 1)

    def test_delete_campaign_and_list_campaigns(self):
        self.manager.record_session(
            "Campaña Para Borrar",
            session_chapter={"title": "S1"},
            session_number=1,
        )
        camps = self.manager.list_campaigns()
        self.assertTrue(any(c["name"] == "Campaña Para Borrar" for c in camps))
        target_c = next(c for c in camps if c["name"] == "Campaña Para Borrar")
        self.assertEqual(target_c["sessions_count"], 1)
        self.assertTrue(bool(target_c["last_updated"]))

        # Delete campaign
        deleted = self.manager.delete_campaign("Campaña Para Borrar", delete_exports=True)
        self.assertTrue(deleted)
        camps_after = self.manager.list_campaigns()
        self.assertFalse(any(c["name"] == "Campaña Para Borrar" for c in camps_after))

    def test_prior_lore_persistence_and_context(self):
        # Initial state has empty prior_lore
        state = self.manager.load_campaign("Campaña Lore")
        self.assertEqual(state["prior_lore"], "")

        ctx = self.manager.get_active_context("Campaña Lore")
        self.assertEqual(ctx["prior_lore"], "")

        # Set prior lore
        updated_state = self.manager.set_prior_lore("Campaña Lore", "La party ya derrotó al dragón en la sesión 4 y rescató al archimago.")
        self.assertEqual(updated_state["prior_lore"], "La party ya derrotó al dragón en la sesión 4 y rescató al archimago.")

        # Reload and check active context
        reloaded = self.manager.load_campaign("Campaña Lore")
        self.assertEqual(reloaded["prior_lore"], "La party ya derrotó al dragón en la sesión 4 y rescató al archimago.")

        ctx2 = self.manager.get_active_context("Campaña Lore")
        self.assertEqual(ctx2["prior_lore"], "La party ya derrotó al dragón en la sesión 4 y rescató al archimago.")

        # Also listed in list_campaigns
        camps = self.manager.list_campaigns()
        lore_camp = next((c for c in camps if c["name"] == "Campaña Lore"), None)
        self.assertIsNotNone(lore_camp)
        self.assertEqual(lore_camp["prior_lore"], "La party ya derrotó al dragón en la sesión 4 y rescató al archimago.")

    def test_quest_auto_completion_on_session_record(self):
        """Test that record_session automatically promotes quest to completed if all subobjectives are completed."""
        state = self.manager.load_campaign("Test AutoComplete")
        quests = [
            {
                "id": "q_test",
                "title": "Investigar Cripta",
                "status": "in_progress",
                "subobjectives": [
                    {"id": "s1", "text": "Entrar a la cripta", "completed": True},
                    {"id": "s2", "text": "Derrotar al espectro", "completed": True},
                ],
            }
        ]
        rec = self.manager.record_session("Test AutoComplete", session_chapter={"title": "S1"}, updated_quests=quests)
        q = next(q for q in rec["quests"] if q["id"] == "q_test")
        self.assertEqual(q["status"], "completed")
        self.assertEqual(q["completed_session"], 1)

    def test_toggle_quest_status(self):
        """Test toggle_quest_status manual switching between completed and in_progress."""
        state = self.manager.load_campaign("Test Toggle")
        quests = [
            {
                "id": "q_tog",
                "title": "Misión Secreta",
                "status": "in_progress",
                "subobjectives": [{"id": "s1", "text": "Paso 1", "completed": False}],
            }
        ]
        self.manager.record_session("Test Toggle", session_chapter={"title": "S1"}, updated_quests=quests)
        
        # Toggle to completed
        s1 = self.manager.toggle_quest_status("Test Toggle", "q_tog")
        q1 = next(q for q in s1["quests"] if q["id"] == "q_tog")
        self.assertEqual(q1["status"], "completed")
        self.assertEqual(q1["completed_session"], 1)

        # Toggle back to in_progress
        s2 = self.manager.toggle_quest_status("Test Toggle", "q_tog")
        q2 = next(q for q in s2["quests"] if q["id"] == "q_tog")
        self.assertEqual(q2["status"], "in_progress")
        self.assertIsNone(q2["completed_session"])

        # Explicitly set status
        s3 = self.manager.toggle_quest_status("Test Toggle", "q_tog", status="completed")
        q3 = next(q for q in s3["quests"] if q["id"] == "q_tog")
        self.assertEqual(q3["status"], "completed")

    def test_dm_hard_exclusion_and_class_sanitization(self):
        """Test that Dungeon Master is never recorded as a PC and characters cannot have class DM."""
        pcs = [
            {
                "personaje": "Dungeon Master",
                "jugador": "Carlos",
                "especie": "Humano",
                "clase": "Dungeon Master",
                "rol_en_sesion": "Actuó como Dungeon Master y controló los PNJs",
            },
            {
                "personaje": "Halendiel",
                "jugador": "Ana",
                "especie": "Elfo",
                "clase": "Dungeon Master",
                "rol_en_sesion": "Disparó flechas certeras y curó a un aliado",
            }
        ]
        rec = self.manager.record_session("Test DM Exclusion", session_chapter={"title": "S1"}, detected_pcs=pcs)
        universal_names = [p["personaje"] for p in rec.get("universal_pcs", [])]
        self.assertNotIn("Dungeon Master", universal_names)
        self.assertIn("Halendiel", universal_names)

        halendiel = next(p for p in rec["universal_pcs"] if p["personaje"] == "Halendiel")
        self.assertEqual(halendiel["clase"], "-")
        self.assertIn("Disparó flechas", halendiel["hitos_acumulados"][0])

    def test_re_record_true_overwrite_sessions_and_milestones(self):
        """Test true overwrite on re-record: no duplicate sessions and no duplicate milestones."""
        camp_name = "Test True Overwrite"
        # First recording of Session 1
        s1_v1 = {
            "title": "Asalto Inicial",
            "chronicle_text": "Lucharon contra goblins.",
            "recap_text": "Goblins atacaron.",
        }
        pcs_v1 = [
            {
                "personaje": "Markus Veyl",
                "jugador": "Roymc89",
                "especie": "Humano",
                "clase": "Guerrero",
                "subclase": "Battle Master",
                "rol_en_sesion": "Luchó fieramente contra la vanguardia goblin.",
            }
        ]
        rec1 = self.manager.record_session(camp_name, session_chapter=s1_v1, session_number=1, detected_pcs=pcs_v1)
        self.assertEqual(len(rec1["sessions"]), 1)
        markus = next(p for p in rec1["universal_pcs"] if p["personaje"] == "Markus Veyl")
        self.assertEqual(len(markus["hitos_acumulados"]), 1)
        self.assertIn("Luchó fieramente", markus["hitos_acumulados"][0])

        # Record Session 2
        s2 = {
            "title": "La Cripta",
            "chronicle_text": "Exploraron la cripta.",
            "recap_text": "Entraron a la cripta.",
        }
        pcs_v2 = [
            {
                "personaje": "Markus Veyl",
                "jugador": "Roymc89",
                "especie": "Humano",
                "clase": "Guerrero",
                "subclase": "Battle Master",
                "rol_en_sesion": "Destruyó al nigromante con su mandoble.",
            }
        ]
        rec2 = self.manager.record_session(camp_name, session_chapter=s2, session_number=2, detected_pcs=pcs_v2)
        self.assertEqual(len(rec2["sessions"]), 2)
        markus = next(p for p in rec2["universal_pcs"] if p["personaje"] == "Markus Veyl")
        self.assertEqual(len(markus["hitos_acumulados"]), 2)

        # Re-record Session 1 with new narrative (e.g. diplomacy instead of combat)
        s1_v2 = {
            "title": "Diplomacia en el Camino",
            "chronicle_text": "Negociaron una tregua pacífica con los goblins.",
            "recap_text": "Tregua acordada.",
        }
        pcs_v1_new = [
            {
                "personaje": "Markus Veyl",
                "jugador": "Roymc89",
                "especie": "Humano",
                "clase": "Guerrero",
                "subclase": "Battle Master",
                "rol_en_sesion": "Negoció una tregua pacífica evitando el derramamiento de sangre.",
            }
        ]
        rec3 = self.manager.record_session(camp_name, session_chapter=s1_v2, session_number=1, detected_pcs=pcs_v1_new)
        
        # Sessions list must contain exactly 2 sessions, NOT 3 (no duplicate Session 1)
        self.assertEqual(len(rec3["sessions"]), 2)
        session_numbers = [s["session_number"] for s in rec3["sessions"]]
        self.assertEqual(session_numbers, [1, 2])
        self.assertEqual(rec3["sessions"][0]["title"], "Diplomacia en el Camino")

        # Markus must have exactly 2 milestones, NOT 3 (the old Session 1 milestone was removed)
        markus = next(p for p in rec3["universal_pcs"] if p["personaje"] == "Markus Veyl")
        self.assertEqual(len(markus["hitos_acumulados"]), 2)
        # Verify Session 1 milestone was overwritten
        s1_milestones = [h for h in markus["hitos_acumulados"] if h.startswith("Sesión #1:")]
        self.assertEqual(len(s1_milestones), 1)
        self.assertIn("Negoció una tregua", s1_milestones[0])
        self.assertNotIn("Luchó fieramente", markus["hitos_acumulados"][0])
        # Verify Session 2 milestone was preserved
        s2_milestones = [h for h in markus["hitos_acumulados"] if h.startswith("Sesión #2:")]
        self.assertEqual(len(s2_milestones), 1)
        self.assertIn("Destruyó al nigromante", s2_milestones[0])

    def test_legitimate_pc_preservation_liam_halendiel(self):
        """Test that legitimate PCs like Liam O'Brien (Halendiel Fang) are preserved in universal_pcs."""
        pcs = [
            {
                "personaje": "Halendiel Fang",
                "jugador": "Liam O'Brien",
                "especie": "Medio Elfo (Half-Elf)",
                "clase": "Bardo (Bard)",
                "subclase": "Colegio de la Elocuencia",
                "rol_en_sesion": "Inspiró a sus compañeros con canciones arcanas e interrogó al prisionero.",
            }
        ]
        rec = self.manager.record_session("Test Liam Preservation", session_chapter={"title": "S1"}, session_number=1, detected_pcs=pcs)
        universal_names = [p["personaje"] for p in rec.get("universal_pcs", [])]
        self.assertIn("Halendiel Fang", universal_names)

        pc = next(p for p in rec["universal_pcs"] if p["personaje"] == "Halendiel Fang")
        self.assertEqual(pc["jugador"], "Liam O'Brien")
        self.assertEqual(pc["clase"], "Bardo (Bard)")
        self.assertEqual(pc["subclase"], "Colegio de la Elocuencia")
        self.assertEqual(len(pc["hitos_acumulados"]), 1)
        self.assertIn("Inspiró a sus compañeros", pc["hitos_acumulados"][0])

    def test_purge_session_data_explicit(self):
        """Test that purge_session_data cleanly strips session entries, milestones, and resets quests."""
        campaign_state = {
            "campaign_name": "Test Purge",
            "last_session": 2,
            "sessions": [
                {"session_number": 1, "title": "Sesión 1"},
                {"session_number": 2, "title": "Sesión 2 (a purgar)"},
            ],
            "universal_pcs": [
                {
                    "personaje": "Markus Veyl",
                    "hitos_acumulados": [
                        "Sesión #1: Luchó valientemente",
                        "Sesión #2: Cayó en una trampa",
                        "Sesión 2: Curó sus heridas",
                    ],
                },
                {
                    "personaje": "Selen",
                    "hitos_acumulados": [
                        "Sesión #1: Lanzó bola de fuego",
                        "Sesión #2: Aprendió un conjuro",
                    ],
                },
            ],
            "quests": [
                {
                    "id": "q1",
                    "title": "Misión Completada en Sesión 2",
                    "status": "completed",
                    "completed_session": 2,
                },
                {
                    "id": "q2",
                    "title": "Misión Antigua de Sesión 1",
                    "status": "completed",
                    "completed_session": 1,
                },
            ],
        }

        # Purge session 2
        purged = self.manager.purge_session_data(campaign_state, 2)

        # 1. Sessions: only session 1 remains
        self.assertEqual(len(purged["sessions"]), 1)
        self.assertEqual(purged["sessions"][0]["session_number"], 1)

        # 2. Universal PCs milestones: session 2 milestones removed
        markus = next(p for p in purged["universal_pcs"] if p["personaje"] == "Markus Veyl")
        self.assertEqual(len(markus["hitos_acumulados"]), 1)
        self.assertEqual(markus["hitos_acumulados"][0], "Sesión #1: Luchó valientemente")

        selen = next(p for p in purged["universal_pcs"] if p["personaje"] == "Selen")
        self.assertEqual(len(selen["hitos_acumulados"]), 1)
        self.assertEqual(selen["hitos_acumulados"][0], "Sesión #1: Lanzó bola de fuego")

        # 3. Quests: q1 reset to in_progress with completed_session = None; q2 untouched
        q1 = next(q for q in purged["quests"] if q["id"] == "q1")
        self.assertEqual(q1["status"], "in_progress")
        self.assertIsNone(q1.get("completed_session"))

        q2 = next(q for q in purged["quests"] if q["id"] == "q2")
        self.assertEqual(q2["status"], "completed")
        self.assertEqual(q2.get("completed_session"), 1)

    def test_bilingual_milestone_purge_on_rerecord(self):
        """Test that purge_session_data handles both Spanish and English milestones case-insensitively."""
        campaign_state = {
            "sessions": [{"session_number": 1}, {"session_number": 2}],
            "universal_pcs": [
                {
                    "personaje": "Kaelen",
                    "hitos_acumulados": [
                        "Session #1: Defended the gate",
                        "Session #2: Cast daylight",
                        "session 2: Found secret door",
                        "Sesión #2: Descansó en la taberna",
                    ],
                }
            ],
            "quests": [],
        }

        purged = self.manager.purge_session_data(campaign_state, 2)
        kaelen = purged["universal_pcs"][0]
        # Only session 1 milestone should remain
        self.assertEqual(len(kaelen["hitos_acumulados"]), 1)
        self.assertEqual(kaelen["hitos_acumulados"][0], "Session #1: Defended the gate")

    def test_smart_npc_deduplication_with_surnames(self):
        """Test that surname expansions and core names are deduplicated rather than creating duplicate cards."""
        # Session 1 introduces Vanessa Fothark and Thiazi
        s1_npcs = [
            {"name": "Fothark Vanessa", "role": "Noble diplomática", "notes": ["Sesión 1: Conoció a la party en el banquete."]},
            {"name": "Thiazi", "role": "Prisionero", "notes": ["Sesión 1: Encerrado en las mazmorras."]},
            {"name": "[Sin nombre] Guardia norte", "role": "Guardia", "notes": ["Sesión 1: Dejó pasar al grupo."]},
        ]
        state1 = self.manager.record_session(
            "Campaña Deduplicacion",
            session_chapter={"title": "Sesión 1"},
            updated_npcs=s1_npcs,
            session_number=1,
        )
        self.assertEqual(len(state1["npcs"]), 3)

        # Session 2 introduces full surnames: Fothark Vanessa Halovar and Thiazi Coldbreaker
        s2_npcs = [
            {"name": "Fothark Vanessa Halovar", "role": "Consejera del Duque", "notes": ["Sesión 2: Reveló su verdadero linaje."]},
            {"name": "Thiazi Coldbreaker", "role": "Guerrero liberado", "notes": ["Sesión 2: Se unió como aliado temporal."]},
            {"name": "[Sin nombre] Guardia sur", "role": "Guardia", "notes": ["Sesión 2: Montaba guardia en el sur."]},
        ]
        state2 = self.manager.record_session(
            "Campaña Deduplicacion",
            session_chapter={"title": "Sesión 2"},
            updated_npcs=s2_npcs,
            session_number=2,
        )

        # Vanessa and Thiazi should be merged into their existing cards; Guardia sur should be separate
        # Total NPCs = 4 (Vanessa, Thiazi, Guardia norte, Guardia sur)
        self.assertEqual(len(state2["npcs"]), 4)

        vanessa = next(n for n in state2["npcs"] if "vanessa" in n["name"].lower())
        self.assertEqual(vanessa["name"], "Fothark Vanessa Halovar")
        self.assertEqual(len(vanessa["notes"]), 2)
        self.assertEqual(vanessa["first_seen_session"], 1)

        thiazi = next(n for n in state2["npcs"] if "thiazi" in n["name"].lower())
        self.assertEqual(thiazi["name"], "Thiazi Coldbreaker")
        self.assertEqual(len(thiazi["notes"]), 2)
        self.assertEqual(thiazi["first_seen_session"], 1)

    def test_quest_failure_state_and_anti_mutation(self):
        """Test quest failure status persistence, no auto-promotion, and unique subobjective IDs."""
        # Session 1: Quest in progress
        s1_quests = [
            {
                "id": "q1",
                "title": "Rescatar a Thiazi",
                "tipo": "principal",
                "status": "in_progress",
                "subobjectives": [
                    {"id": "s1", "text": "Infiltrarse en la prisión", "completed": True},
                    {"id": "s2", "text": "Abrir la celda de Thiazi", "completed": False},
                ],
            }
        ]
        state1 = self.manager.record_session(
            "Campaña Quests",
            session_chapter={"title": "Sesión 1"},
            updated_quests=s1_quests,
            session_number=1,
        )
        self.assertEqual(state1["quests"][0]["status"], "in_progress")

        # Session 2: Thiazi dies, quest fails
        s2_quests = [
            {
                "id": "q1",
                "title": "Rescatar a Thiazi",
                "status": "failed",
                "subobjectives": [
                    {"id": "s1", "text": "Infiltrarse en la prisión", "completed": True},
                    {"id": "s2", "text": "Abrir la celda de Thiazi", "completed": False},
                    {"id": "s3", "text": "Encontrar a Thiazi muerto", "completed": True},
                ],
            },
            {
                "id": "q2",
                "title": "Vengar a Thiazi",
                "tipo": "secundaria",
                "status": "in_progress",
                "subobjectives": [
                    {"id": "s1", "text": "Interrogar al carcelero", "completed": False},
                ],
            }
        ]
        state2 = self.manager.record_session(
            "Campaña Quests",
            session_chapter={"title": "Sesión 2"},
            updated_quests=s2_quests,
            session_number=2,
        )

        q1 = next(q for q in state2["quests"] if q["id"] == "q1")
        self.assertEqual(q1["status"], "failed")
        self.assertEqual(q1["completed_session"], 2)
        self.assertIn("Fracasada en Sesión 2", q1.get("lifecycle_notes", ""))

        # Even if all subobjectives were completed, failed quest must NEVER auto-promote to completed
        state2 = self.manager.update_quest_subobjective("Campaña Quests", "q1", 1, True)
        q1_updated = next(q for q in state2["quests"] if q["id"] == "q1")
        self.assertEqual(q1_updated["status"], "failed")

        # Subobjective IDs in q1 must be sequential and unique
        q1_sub_ids = [s["id"] for s in q1["subobjectives"]]
        self.assertEqual(len(q1_sub_ids), len(set(q1_sub_ids)))

    def test_youtube_roster_sync_brennan_and_liam(self):
        """Test that YouTube sessions sync Brennan as DM, Liam as Halendiel PC, and purge mock DMs."""
        detected_pcs = [
            {
                "jugador": "Liam O'Brien",
                "personaje": "Halendiel 'Hal' Fang",
                "especie": "Orc",
                "clase": "Bard",
                "subclase": "College of Lore",
                "rol_en_sesion": "Inspiró al grupo con su balada épica.",
            },
            {
                "jugador": "Laura Bailey",
                "personaje": "Vex",
                "especie": "Half-Elf",
                "clase": "Ranger",
                "subclase": "Hunter",
                "rol_en_sesion": "Disparó certeramente contra el monstruo.",
            }
        ]
        updated_npcs = [
            {"name": "Brennan Lee Mulligan", "role": "Dungeon Master (DM)", "notes": ["Sesión 1: Narró el mundo."]}
        ]
        mock_roster = [
            {"player_name": "Rodrigo", "character_name": "(DM)", "role": "Dungeon Master", "species": "-"},
            {"player_name": "Liam O'Brien", "character_name": "(DM)", "role": "Dungeon Master", "species": "-"},
        ]

        state = self.manager.record_session(
            "Critical Role Daggerheart",
            session_chapter={"title": "Apertura con Brennan Lee Mulligan"},
            updated_npcs=updated_npcs,
            detected_pcs=detected_pcs,
            roster=mock_roster,
            session_number=1,
            is_youtube=True,
        )

        # 1. Roster must have Brennan Lee Mulligan as DM
        roster = state["roster"]
        dm_entry = next((p for p in roster if p.get("role") == "Dungeon Master (DM)"), None)
        self.assertIsNotNone(dm_entry)
        self.assertEqual(dm_entry["player_name"], "Brennan Lee Mulligan")
        self.assertEqual(dm_entry["character_name"], "(DM)")

        # 2. Mock DM Rodrigo must be purged
        self.assertFalse(any(p.get("player_name") == "Rodrigo" for p in roster))

        # 3. Liam O'Brien must strictly be a Player Character
        liam_roster = next((p for p in roster if p.get("player_name") == "Liam O'Brien"), None)
        self.assertIsNotNone(liam_roster)
        self.assertEqual(liam_roster["character_name"], "Halendiel 'Hal' Fang")
        self.assertEqual(liam_roster["species"], "Orc")
        self.assertEqual(liam_roster["role"], "Bard")

        # 4. Brennan Lee Mulligan must NEVER be in universal_pcs
        self.assertFalse(any("brennan" in p.get("personaje", "").lower() or "brennan" in p.get("jugador", "").lower() for p in state["universal_pcs"]))

        # 5. Liam O'Brien must be in universal_pcs as Halendiel 'Hal' Fang
        liam_universal = next((p for p in state["universal_pcs"] if "liam" in p.get("jugador", "").lower()), None)
        self.assertIsNotNone(liam_universal)
        self.assertEqual(liam_universal["personaje"], "Halendiel 'Hal' Fang")
        self.assertEqual(liam_universal["clase"], "Bard")

    def test_pc_fuzzy_surname_deduplication(self):
        """Test that universal_pcs uses fuzzy/surname deduplication (e.g. 'Octus' -> 'Octus Taconis')."""
        # Session 1: Character identified simply as 'Octus'
        detected_s1 = [
            {
                "jugador": "Player1",
                "personaje": "Octus",
                "especie": "Humano",
                "clase": "Guerrero",
                "subclase": "Campeón",
                "rol_en_sesion": "Defendió la entrada del templo.",
            }
        ]
        state = self.manager.record_session(
            "Test Fuzzy PC Campaign",
            session_chapter={"title": "Sesión 1"},
            detected_pcs=detected_s1,
            session_number=1,
        )

        octus = next((p for p in state["universal_pcs"] if "octus" in p["personaje"].lower()), None)
        self.assertIsNotNone(octus)
        self.assertEqual(octus["personaje"], "Octus")
        self.assertEqual(octus["debut_sesion"], 1)
        self.assertEqual(len(octus.get("hitos_acumulados", [])), 1)

        # Session 2: Character identified by full name 'Octus Taconis'
        detected_s2 = [
            {
                "jugador": "Player1",
                "personaje": "Octus Taconis",
                "especie": "Humano",
                "clase": "Guerrero",
                "subclase": "Campeón",
                "rol_en_sesion": "Derrotó al dragón en la cima de la montaña.",
            }
        ]
        state = self.manager.record_session(
            "Test Fuzzy PC Campaign",
            session_chapter={"title": "Sesión 2"},
            detected_pcs=detected_s2,
            session_number=2,
        )

        # Should NOT have 2 separate PCs (Octus and Octus Taconis); should merge into 1!
        pcs = [p for p in state["universal_pcs"] if "octus" in p["personaje"].lower()]
        self.assertEqual(len(pcs), 1, "Octus and Octus Taconis should have merged into a single PC card")
        merged_pc = pcs[0]
        # Should upgrade to longer name 'Octus Taconis'
        self.assertEqual(merged_pc["personaje"], "Octus Taconis")
        # Should preserve debut_sesion = 1
        self.assertEqual(merged_pc["debut_sesion"], 1)
        # Should accumulate milestones chronologically
        hitos = merged_pc.get("hitos_acumulados", [])
        self.assertEqual(len(hitos), 2)
        self.assertTrue(hitos[0].startswith("Sesión #1:"))
        self.assertTrue(hitos[1].startswith("Sesión #2:"))

        # Roster should also be updated with 'Octus Taconis'
        roster_octus = next((r for r in state["roster"] if "octus" in r.get("character_name", "").lower()), None)
        self.assertIsNotNone(roster_octus)
        self.assertEqual(roster_octus["character_name"], "Octus Taconis")

    def test_is_entity_substring_duplicate(self):
        from src.storage.campaign_manager import is_entity_substring_duplicate

        # Substring cases
        self.assertTrue(is_entity_substring_duplicate("Octus", "Octus Taconis"))
        self.assertTrue(is_entity_substring_duplicate("Thiazi", "Thiazi Coldbreaker"))
        self.assertTrue(is_entity_substring_duplicate("Fothark Vanessa", "Fothark Vanessa Halovar"))

        # Exact match
        self.assertTrue(is_entity_substring_duplicate("Octus", "octus"))

        # Reversed length (longer cannot be duplicate of shorter)
        self.assertFalse(is_entity_substring_duplicate("Octus Taconis", "Octus"))

        # Distinct people with shared surname or words
        self.assertFalse(is_entity_substring_duplicate("Hiro Fang", "Thjazi Fang"))

        # Generic titles
        self.assertFalse(is_entity_substring_duplicate("Lord", "Lord Primus Taconis"))
        self.assertFalse(is_entity_substring_duplicate("Guardia", "Guardia de la Puerta"))

        # Unnamed descriptors
        self.assertFalse(is_entity_substring_duplicate("[Sin nombre] Guardia norte", "[Sin nombre] Guardia sur"))

    def test_retroactive_deduplicate_campaign_entities_octus(self):
        import json
        camp_name = "Retroactive Deduplication Test"
        state = self.manager.load_campaign(camp_name)

        # Pre-populate state with duplicate Octus and Octus Taconis entries
        state["universal_pcs"] = [
            {
                "personaje": "Octus",
                "jugador": "Alex Ward",
                "especie": "Human",
                "clase": "Rogue",
                "subclase": "Arcane Trickster",
                "debut_sesion": 1,
                "hitos_acumulados": [
                    "Sesión #1: Bypassed magical lock at flophouse.",
                    "Sesión #2: Used Pin to spy on Vaelis.",
                ]
            },
            {
                "personaje": "Octus Taconis",
                "jugador": "Alex Ward",
                "especie": "Human",
                "clase": "Rogue",
                "subclase": "Arcane Trickster",
                "debut_sesion": 3,
                "hitos_acumulados": [
                    "Sesión #3: Escorted to Palazzo DeVino.",
                    "Sesión #4: Resurrected without heartbeat.",
                    "Sesión #5: Returned from limbo.",
                ]
            }
        ]
        state["roster"] = [
            {"player_name": "Alex Ward", "character_name": "Octus", "role": "Rogue"},
            {"player_name": "Alex Ward", "character_name": "Octus Taconis", "role": "Rogue"}
        ]
        self.manager.save_campaign(state)

        # Also create a dummy orphaned disk file for Octus
        orphan_file = self.manager.campaigns_dir / "octus.json"
        orphan_file.write_text("{}", encoding="utf-8")
        self.assertTrue(orphan_file.is_file())

        # Execute retroactive deduplication
        result = self.manager.deduplicate_campaign_entities(camp_name)
        self.assertEqual(result["merged_count"], 1)
        self.assertEqual(result["merged"][0]["source"], "Octus")
        self.assertEqual(result["merged"][0]["target"], "Octus Taconis")

        # Reload campaign state
        cleaned_state = self.manager.load_campaign(camp_name)
        self.assertEqual(len(cleaned_state["universal_pcs"]), 1)
        merged_pc = cleaned_state["universal_pcs"][0]
        self.assertEqual(merged_pc["personaje"], "Octus Taconis")
        self.assertEqual(merged_pc["debut_sesion"], 1)
        self.assertIn("Octus", merged_pc.get("aliases", []))

        # Check all 5 hitos are merged in order
        hitos = merged_pc.get("hitos_acumulados", [])
        self.assertEqual(len(hitos), 5)
        self.assertTrue(hitos[0].startswith("Sesión #1:"))
        self.assertTrue(hitos[1].startswith("Sesión #2:"))
        self.assertTrue(hitos[2].startswith("Sesión #3:"))
        self.assertTrue(hitos[3].startswith("Sesión #4:"))
        self.assertTrue(hitos[4].startswith("Sesión #5:"))

        # Check roster deduplication
        self.assertEqual(len(cleaned_state["roster"]), 1)
        self.assertEqual(cleaned_state["roster"][0]["character_name"], "Octus Taconis")

        # Check orphaned file was deleted
        self.assertFalse(orphan_file.is_file())

    def test_manual_merge_entities(self):
        camp_name = "Manual Merge Test"
        state = self.manager.load_campaign(camp_name)
        state["universal_pcs"] = [
            {
                "personaje": "Arthur",
                "jugador": "Invitado",
                "especie": "Humano",
                "clase": "Guerrero",
                "subclase": "-",
                "debut_sesion": 2,
                "hitos_acumulados": ["Sesión #2: Luchó en la taberna."]
            },
            {
                "personaje": "Gareth",
                "jugador": "Invitado Especial",
                "especie": "Humano",
                "clase": "Paladín",
                "subclase": "Devotion",
                "debut_sesion": 1,
                "hitos_acumulados": ["Sesión #1: Llegó a la ciudad."]
            }
        ]
        self.manager.save_campaign(state)

        # Merge Arthur into Gareth manually
        result = self.manager.merge_entities(
            campaign_name=camp_name,
            source_name="Arthur",
            target_name="Gareth",
            entity_type="pc"
        )
        self.assertEqual(result["source"], "Arthur")
        self.assertEqual(result["target"], "Gareth")

        cleaned = self.manager.load_campaign(camp_name)
        self.assertEqual(len(cleaned["universal_pcs"]), 1)
        target = cleaned["universal_pcs"][0]
        self.assertEqual(target["personaje"], "Gareth")
        self.assertIn("Arthur", target.get("aliases", []))
        self.assertEqual(len(target["hitos_acumulados"]), 2)
        self.assertTrue(target["hitos_acumulados"][0].startswith("Sesión #1:"))
        self.assertTrue(target["hitos_acumulados"][1].startswith("Sesión #2:"))


if __name__ == "__main__":
    unittest.main()


