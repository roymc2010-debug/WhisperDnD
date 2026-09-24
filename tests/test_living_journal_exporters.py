"""Unit tests for Living Campaign Journal exporters (docx and md)."""

import tempfile
import unittest
from pathlib import Path

from src.exporters.docx_exporter import export_living_journal_docx
from src.exporters.md_exporter import export_living_journal_md


class TestLivingJournalExporters(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.out_dir = Path(self.temp_dir.name)

        self.sample_campaign_state = {
            "campaign_name": "Crónicas de Faerûn",
            "campaign_id": "cronicas_de_faerun",
            "created_at": "2026-09-19T12:00:00Z",
            "updated_at": "2026-09-19T14:00:00Z",
            "last_session": 2,
            "roster": [
                {
                    "player_name": "Rodrigo",
                    "character_name": "Markus Veyl",
                    "species": "Humano",
                    "role": "Guerrero",
                    "subclass": "Battle Master",
                },
                {
                    "player_name": "Carlos",
                    "character_name": "Selen",
                    "species": "Elfo",
                    "role": "Mago",
                    "subclass": "Evocación",
                },
            ],
            "quests": [
                {
                    "id": "q1",
                    "title": "La Caravana Asediada",
                    "context": "Rescatar la carga del comerciante.",
                    "status": "completed",
                    "lifecycle_notes": "Iniciada en Sesión 1 | Completada en Sesión 2",
                    "subobjectives": [
                        {"text": "Rastrear huellas", "completed": True},
                        {"text": "Derrotar al jefe bandido", "completed": True},
                    ],
                },
                {
                    "id": "q2",
                    "title": "Investigar el Culto Sombrío",
                    "context": "El sabio sospecha de nigromancia.",
                    "status": "in_progress",
                    "lifecycle_notes": "Iniciada en Sesión 2",
                    "subobjectives": [
                        {"text": "Visitar el cementerio", "completed": False},
                    ],
                },
            ],
            "npcs": [
                {
                    "name": "Alcalde Roderick",
                    "role": "Alcalde de Oakhaven",
                    "first_seen_session": 1,
                    "notes": ["Sesión 1: Contrató al grupo", "Sesión 2: Pagó la recompensa con 150 po"],
                }
            ],
            "sessions": [
                {
                    "session_number": 1,
                    "date": "10/09/2026",
                    "title": "Emboscada en el Bosque",
                    "recap_text": "El grupo comenzó su viaje escoltando una carreta.",
                    "chronicle_text": "Unos trasgos atacaron por sorpresa. Markus utilizó su escudo para proteger a Selen.",
                    "closing_expectations": "Descansar en la posada del Jabalí.",
                    "markus_coaching": "Excelente intercepción táctica. Considerar Action Surge.",
                },
                {
                    "session_number": 2,
                    "date": "17/09/2026",
                    "title": "El Bastión de los Bandidos",
                    "recap_text": "Los héroes asaltaron el escondite trasgo y encontraron pistas de un culto.",
                    "chronicle_text": "Un combate feroz se desató en la caverna central.",
                    "closing_expectations": "Hablar con el sacerdote local.",
                    "markus_coaching": "Gran uso de Menacing Attack para aterrorizar al jefe.",
                },
            ],
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_export_living_journal_docx(self):
        out_docx = self.out_dir / "test_grimorio.docx"
        res_path = export_living_journal_docx(self.sample_campaign_state, str(out_docx))

        self.assertTrue(Path(res_path).is_file())
        self.assertGreater(Path(res_path).stat().st_size, 1000)

    def test_export_living_journal_md(self):
        out_md = self.out_dir / "test_grimorio.md"
        res_path = export_living_journal_md(self.sample_campaign_state, str(out_md))

        self.assertTrue(Path(res_path).is_file())
        content = Path(res_path).read_text(encoding="utf-8")
        self.assertIn("# 📜 Grimorio de Campaña: Crónicas de Faerûn", content)
        self.assertIn("Markus Veyl", content)
        self.assertIn("La Caravana Asediada", content)
        self.assertIn("Alcalde Roderick", content)
        self.assertIn("Capítulo 1: Emboscada en el Bosque", content)
        self.assertIn("Capítulo 2: El Bastión de los Bandidos", content)
        self.assertIn("Reflexión de Rol y Compañerismo: Markus Veyl", content)

        # Verify chronological order: Chronicle -> Closing -> Reflection -> Next Session Script
        idx_chronicle = content.find("1. Crónica Narrativa y Desglose de Combates")
        idx_closing = content.find("2. Cierre de Sesión, Decisiones y Expectativas")
        idx_reflection = content.find("3. Reflexión de Rol y Compañerismo: Markus Veyl")
        idx_script = content.find("4. 🎙️ Guion para abrir la Sesión #2")
        self.assertTrue(0 < idx_chronicle < idx_closing < idx_reflection < idx_script)

    def test_export_living_journal_external_campaign_detected_party(self):
        state = {
            "campaign_name": "Caoz con todo",
            "campaign_id": "caoz_con_todo",
            "last_session": 1,
            "roster": [
                {"player_name": "Roymc89", "character_name": "Markus Veyl", "role": "Guerrero"}
            ],
            "detected_party": [
                {
                    "player_name": "Streamer1",
                    "character_name": "Valeros",
                    "species": "Humano",
                    "role": "Guerrero",
                    "subclass": "Campeón",
                }
            ],
            "quests": [],
            "npcs": [],
            "sessions": [],
        }

        # MD Test
        out_md = self.out_dir / "external_grimorio.md"
        res_md = export_living_journal_md(state, str(out_md))
        content_md = Path(res_md).read_text(encoding="utf-8")

        self.assertIn("## 👥 Compañía de Aventureros (Personajes Detectados en el Video)", content_md)
        self.assertIn("Valeros", content_md)
        self.assertNotIn("Markus Veyl", content_md)

        # DOCX Test
        out_docx = self.out_dir / "external_grimorio.docx"
        res_docx = export_living_journal_docx(state, str(out_docx))
        self.assertTrue(Path(res_docx).is_file())

    def test_youtube_detected_pcs_and_executive_synopsis(self):
        state = {
            "campaign_name": "Camp Caoz",
            "campaign_id": "camp_caoz",
            "last_session": 1,
            "detected_pcs": [
                {
                    "jugador": "Beto",
                    "personaje": "Kallista",
                    "especie": "Tiefling",
                    "clase": "Bruja",
                    "subclase": "Pact of the Blade",
                }
            ],
            "quests": [],
            "npcs": [
                {
                    "name": "Arzobispo Malakor",
                    "role": "Villano [Mencionado en la historia]",
                    "first_seen_session": 1,
                    "notes": ["Sesión 1: Nombrado como la mente maestra detrás del culto"],
                }
            ],
            "sessions": [
                {
                    "session_number": 1,
                    "title": "La Noche Carmesí",
                    "date": "19/09/2026",
                    "chronicle_text": "Kallista investigó las catacumbas.",
                    "closing_expectations": "Huir de la ciudad.",
                    "episode_synopsis": "En este episodio, Kallista descubrió la conspiración del Arzobispo Malakor y escapó por los tejados de la ciudadela.",
                    "next_session_script": "",
                }
            ],
        }

        # MD Test
        out_md = self.out_dir / "youtube_caoz.md"
        res_md = export_living_journal_md(state, str(out_md))
        content_md = Path(res_md).read_text(encoding="utf-8")

        self.assertIn("## 👥 Compañía de Aventureros (Personajes Detectados en el Video)", content_md)
        self.assertIn("Kallista", content_md)
        self.assertIn("Tiefling", content_md)
        self.assertIn("Bruja", content_md)
        self.assertIn("[Mencionado en la historia]", content_md)
        self.assertIn("📌 Sinopsis Ejecutiva del Episodio", content_md)
        self.assertIn("Kallista descubrió la conspiración", content_md)
        self.assertNotIn("🎙️ Guion para abrir la Sesión", content_md)

        # DOCX Test
        out_docx = self.out_dir / "youtube_caoz.docx"
        res_docx = export_living_journal_docx(state, str(out_docx))
        self.assertTrue(Path(res_docx).is_file())

    def test_export_living_journal_protagonists_in_chapters(self):
        state = {
            "campaign_name": "Caoz con todo",
            "campaign_id": "caoz_con_todo",
            "last_session": 1,
            "detected_pcs": [
                {
                    "personaje": "Kallista",
                    "jugador": "Elena",
                    "clase": "Bruja",
                    "especie": "Tiefling",
                    "rol_en_sesion": "Negoció el salvoconducto con la guardia.",
                }
            ],
            "quests": [],
            "npcs": [],
            "sessions": [
                {
                    "session_number": 1,
                    "title": "El Inicio del Caos",
                    "date": "20/09/2026",
                    "chronicle_text": "### Acto I: Escena 1: Encuentro en la plaza\\nEl grupo se conoció.",
                    "closing_expectations": "Continuar hacia el norte.",
                    "detected_pcs": [
                        {
                            "personaje": "Kallista",
                            "jugador": "Elena",
                            "clase": "Bruja",
                            "especie": "Tiefling",
                            "rol_en_sesion": "Negoció el salvoconducto con la guardia.",
                        }
                    ],
                }
            ],
        }

        # MD test
        out_md = self.out_dir / "protagonists_test.md"
        res_md = export_living_journal_md(state, str(out_md))
        md_text = Path(res_md).read_text(encoding="utf-8")
        self.assertIn("🎭 Compañía de Aventureros (Protagonistas Detectados)", md_text)
        self.assertIn("| Personaje | Jugador / Rol | Clase / Especie | Rol en la Sesión |", md_text)
        self.assertIn("| **Kallista** | Elena | Bruja / Tiefling | Negoció el salvoconducto con la guardia. |", md_text)

        # DOCX test
        out_docx = self.out_dir / "protagonists_test.docx"
        res_docx = export_living_journal_docx(state, str(out_docx))
        self.assertTrue(Path(res_docx).is_file())


if __name__ == "__main__":
    unittest.main()


