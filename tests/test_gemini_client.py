"""Unit tests for Gemini TTRPG Summarizer client."""

import unittest
from unittest.mock import MagicMock, patch

from src.summarizer.gemini_client import GeminiTTRPGSummarizer


class TestGeminiTTRPGSummarizer(unittest.TestCase):
    def test_format_roster(self):
        roster = [
            {"player_name": "Beta", "role": "Dungeon Master (DM)", "character_name": "(DM)", "species": "(N/A - DM)", "subclass": "N/A"},
            {"player_name": "Roymc89", "role": "Guerrero (Fighter)", "character_name": "Markus Veyl", "species": "Humano", "subclass": "Battle Master"},
        ]
        formatted = GeminiTTRPGSummarizer.format_roster(roster)
        self.assertIn("Beta", formatted)
        self.assertIn("Dungeon Master (DM)", formatted)
        self.assertIn("Roymc89", formatted)
        self.assertIn("Markus Veyl", formatted)
        self.assertIn("Especie: Humano", formatted)
        self.assertIn("Battle Master", formatted)

    def test_format_empty_roster(self):
        formatted = GeminiTTRPGSummarizer.format_roster([])
        self.assertIn("sin personajes especificados", formatted)

    @patch("google.genai.Client")
    def test_generate_chronicle_mocked(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "# 📜 Crónica de Sesión\n\n## 1. Resumen Narrativo\nLos héroes vencieron."
        mock_client.models.generate_content.return_value = mock_response

        summarizer = GeminiTTRPGSummarizer(api_key="dummy_api_key")
        roster = [{"player_name": "Sofía", "role": "Pícaro", "character_name": "Kaelen"}]
        chronicle = summarizer.generate_chronicle(
            transcript_text="Kaelen desactivó la trampa en la cripta.",
            roster=roster,
        )

        self.assertIn("Crónica de Sesión", chronicle)
        self.assertIn("Los héroes vencieron", chronicle)
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args
        prompt_passed = call_args.kwargs.get("contents", "")
        self.assertIn("SECCIÓN 1: CRÓNICA DETALLADA DE LA AVENTURA", prompt_passed)
        self.assertIn("SECCIÓN 2: CIERRE DE MESA, DECISIONES Y PLANES INMEDIATOS", prompt_passed)
        # Without Markus Veyl in the roster and no user character, section 3 should be read-aloud script for next session
        self.assertIn("SECCIÓN 3: 🎙️ GUION PARA ABRIR LA SESIÓN #2", prompt_passed)

        # When Markus Veyl is present in the roster
        mock_client.models.generate_content.reset_mock()
        roster_markus = [{"player_name": "Roymc89", "role": "Guerrero", "character_name": "Markus Veyl"}]
        summarizer.generate_chronicle(
            transcript_text="Markus ataca con su espada.",
            roster=roster_markus,
        )
        prompt_markus = mock_client.models.generate_content.call_args.kwargs.get("contents", "")
        self.assertIn("SECCIÓN 3: REFLEXIÓN DE ROL Y COMPAÑERISMO: Markus Veyl", prompt_markus)
        self.assertIn("SECCIÓN 4: 🎙️ GUION PARA ABRIR LA SESIÓN #2", prompt_markus)

    def test_build_dnd_session_prompt(self):
        from src.summarizer.prompts import build_dnd_session_prompt

        sample_roster = "- Jugador: Roymc89 | Personaje: Markus Veyl | Especie: Humano | Clase/Rol: Guerrero (Fighter) (Battle Master)"
        sample_transcript = "Rodrigo: Ataco al orco con mi espada larga."
        prompt = build_dnd_session_prompt(sample_roster, sample_transcript, has_markus=True)

        # Verify 4 sections in forward order
        self.assertIn("SECCIÓN 1: CRÓNICA DETALLADA DE LA AVENTURA", prompt)
        self.assertIn("SECCIÓN 2: CIERRE DE MESA, DECISIONES Y PLANES INMEDIATOS", prompt)
        self.assertIn("SECCIÓN 3: REFLEXIÓN DE ROL Y COMPAÑERISMO: Markus Veyl", prompt)
        self.assertIn("SECCIÓN 4: 🎙️ GUION PARA ABRIR LA SESIÓN #2 (PARA LEER EN VOZ ALTA)", prompt)

        # Verify Section 1 breakdown items
        self.assertIn("Resumen Narrativo y Diálogos Memorables", prompt)
        self.assertIn("Desglose Pormenorizado de Combates y Táctica", prompt)
        self.assertIn("Personajes No Jugadores (PNJs) e Interacciones Clave", prompt)
        self.assertIn("Lugares Explorados, Trampas y Tesoros", prompt)

        # Verify Section 4 conversational Discord requirements
        self.assertIn("3 a 4 párrafos", prompt)
        self.assertIn("PRIMERA PERSONA DEL PLURAL", prompt)
        self.assertIn("PROHIBIDO USAR NARRADOR ÉPICO", prompt)

        # Verify Section 3 requirements for Markus Veyl (Roleplay & Party Reflection, NO min/maxing)
        self.assertIn("Markus Veyl", prompt)
        self.assertIn("Coherencia y Desarrollo de Personaje", prompt)
        self.assertIn("Creatividad y Uso del Entorno vs. Reglas", prompt)
        self.assertIn("Dinámica de Grupo y Trabajo en Equipo", prompt)
        self.assertIn("Dilemas para la Próxima Sesión", prompt)
        self.assertIn("PROHIBIDO EL MIN/MAXING", prompt)

    def test_build_academic_lecture_prompt(self):
        from src.summarizer.prompts import build_academic_lecture_prompt

        subject = "Sistemas de Control"
        topic = "Funciones de Transferencia"
        transcript = "El profesor explicó la transformada de Laplace y los polos en el plano S."
        prompt = build_academic_lecture_prompt(subject, topic, transcript, date_str="19/09/2026")

        self.assertIn("Sistemas de Control", prompt)
        self.assertIn("Funciones de Transferencia", prompt)
        self.assertIn("DIRECTIVA CRÍTICA DE PROFUNDIDAD EXPLICATIVA (WORK & STUDY)", prompt)
        self.assertIn("1. Introducción y Contexto", prompt)
        self.assertIn("2. Conceptos Teóricos Fundamentales", prompt)
        self.assertIn("3. Recorrido Temático Detallado y Explicaciones Profundas", prompt)
        self.assertIn("4. Ejemplos Resueltos y Casos Prácticos", prompt)
        self.assertIn("5. Avisos Relevantes, Tareas y Próximos Pasos", prompt)
        self.assertIn("6. Conclusiones Clave, Métricas y Acciones", prompt)

    @patch("google.genai.Client")
    def test_generate_academic_notes_mocked(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "# 🎓 Guía de Estudio: Sistemas de Control\n\n## 1. Resumen de la Clase\nAnálisis de polos."
        mock_client.models.generate_content.return_value = mock_response

        summarizer = GeminiTTRPGSummarizer(api_key="dummy_api_key")
        notes = summarizer.generate_academic_notes(
            transcript_text="Explicación de polos y ceros.",
            subject="Sistemas de Control",
            topic="Funciones de Transferencia",
            date_str="19/09/2026",
        )

        self.assertIn("Guía de Estudio", notes)
        self.assertIn("Sistemas de Control", notes)
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args
        prompt_passed = call_args.kwargs.get("contents", "")
        self.assertIn("Sistemas de Control", prompt_passed)
        self.assertIn("Funciones de Transferencia", prompt_passed)

    def test_build_dnd_session_prompt_bilingual(self):
        from src.summarizer.prompts import build_dnd_session_prompt

        sample_roster = "- Player: John | Character: Thorin | Class: Fighter"
        sample_transcript = "John: I attack the goblin."
        prompt_en = build_dnd_session_prompt(sample_roster, sample_transcript, has_markus=False, target_language="en")
        self.assertIn("D&D SESSION COMPREHENSIVE REPORT", prompt_en)
        self.assertIn("SECTION 1: DETAILED ADVENTURE CHRONICLE", prompt_en)
        self.assertIn("SECTION 2: TABLE CLOSING, DECISIONS & IMMEDIATE PLANS", prompt_en)
        self.assertIn("SECTION 3: 🎙️ SCRIPT TO OPEN SESSION #2 (READ ALOUD)", prompt_en)

    def test_check_has_markus(self):
        from src.summarizer.gemini_client import check_has_markus

        self.assertFalse(check_has_markus([]))
        self.assertFalse(check_has_markus([{"character_name": "Thorin"}]))
        self.assertTrue(check_has_markus([{"character_name": "Markus Veyl"}]))
        self.assertTrue(check_has_markus([{"player_name": "Roymc89", "character_name": "markus"}]))

    @patch("google.genai.Client")
    def test_generate_campaign_session_json_config(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = '{"session_chapter": {"title": "Sesión #1", "recap_text": "Nos fuimos al bosque.", "chronicle_text": "Llegamos a la torre.", "closing_expectations": "Subir de nivel.", "markus_coaching": "Buen roleplay."}, "updated_quests": [{"id": "q1", "title": "Misión 1", "status": "in_progress"}], "updated_npcs": [{"name": "Eldrin", "role": "Mago"}], "detected_npc_names": ["Eldrin"]}'
        mock_client.models.generate_content.return_value = mock_response

        summarizer = GeminiTTRPGSummarizer(api_key="dummy_api_key")
        result = summarizer.generate_campaign_session(
            transcript_text="Encontramos a Eldrin en la torre.",
            roster=[{"player_name": "Roymc89", "role": "Guerrero", "character_name": "Markus Veyl"}],
            session_number=1,
            target_language="es",
        )

        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        self.assertEqual(call_kwargs.get("config"), {
            "temperature": 0.0,
            "top_p": 0.95,
            "response_mime_type": "application/json",
        })
        self.assertEqual(result["session_chapter"]["title"], "Sesión #1")
        self.assertEqual(len(result["updated_quests"]), 1)
        self.assertEqual(len(result["updated_npcs"]), 1)
        self.assertEqual(result["detected_npc_names"], ["Eldrin"])

    def test_parse_json_response_markdown_fences(self):
        raw_output_with_fences = """```json
{
  "session_chapter": {
    "title": "El Asedio de Phandalin",
    "recap_text": "Nos emboscaron unos goblins...",
    "chronicle_text": "La batalla fue intensa...",
    "closing_expectations": "Descansar en la posada.",
    "markus_coaching": "Gran uso de Second Wind."
  },
  "updated_quests": [{"id": "q1", "title": "Salvar al herrero", "status": "completed"}],
  "updated_npcs": [{"name": "Toblen", "role": "Posadero"}],
  "detected_npc_names": ["Toblen"]
}
```"""
        parsed = GeminiTTRPGSummarizer.parse_json_response(raw_output_with_fences, session_number=2)
        self.assertEqual(parsed["session_chapter"]["title"], "El Asedio de Phandalin")
        self.assertIn("Nos emboscaron", parsed["session_chapter"]["recap_text"])
        self.assertEqual(len(parsed["updated_quests"]), 1)
        self.assertEqual(parsed["updated_quests"][0]["title"], "Salvar al herrero")
        self.assertEqual(len(parsed["updated_npcs"]), 1)
        self.assertEqual(parsed["detected_npc_names"], ["Toblen"])

    def test_parse_json_response_flat_schema(self):
        # When Gemini returns chapter fields flat without nesting inside session_chapter
        raw_flat = """{
  "title": "Cripta Olvidada",
  "recap_text": "Llegamos a la cripta.",
  "chronicle_text": "Vencimos a los esqueletos.",
  "closing_expectations": "Recoger el botín.",
  "markus_coaching": "Buen liderazgo táctico.",
  "updated_quests": [],
  "updated_npcs": [],
  "detected_npc_names": []
}"""
        parsed = GeminiTTRPGSummarizer.parse_json_response(raw_flat, session_number=3)
        self.assertEqual(parsed["session_chapter"]["title"], "Cripta Olvidada")
        self.assertEqual(parsed["session_chapter"]["chronicle_text"], "Vencimos a los esqueletos.")

    def test_parse_json_response_fallback_on_malformed(self):
        raw_invalid = "Esto no es JSON pero es una crónica descriptiva de la batalla."
        parsed = GeminiTTRPGSummarizer.parse_json_response(raw_invalid, session_number=1)
        self.assertEqual(parsed["session_chapter"]["title"], "Sesión #1")
        self.assertEqual(parsed["session_chapter"]["chronicle_text"], raw_invalid)
        self.assertEqual(parsed["updated_quests"], [])
        self.assertEqual(parsed["updated_npcs"], [])


    def test_parse_json_response_detected_pcs_and_synopsis(self):
        raw_output = """{
  "session_chapter": {
    "title": "Episodio 12: El Despertar del Titán",
    "chronicle_text": "Los aventureros descienden al abismo...",
    "closing_expectations": "Explorar la tumba.",
    "episode_synopsis": "En este episodio dramático, el grupo descubrió la verdadera identidad del traidor y selló la cripta antes del colapso.",
    "next_session_script": ""
  },
  "detected_pcs": [
    {
      "jugador": "Carlos",
      "personaje": "Kaelen",
      "especie": "Tiefling",
      "clase": "Paladín"
    },
    {
      "jugador": "Laura",
      "personaje": "Lyra",
      "especie": "Elfo",
      "clase": "Pícaro"
    }
  ],
  "updated_quests": [{"id": "q1", "title": "Sellar la cripta", "status": "completed"}],
  "updated_npcs": [
    {"name": "Lord Brandon", "role": "Noble [Mencionado en la historia]", "notes": ["Sesión #1: Discutido por los guardias"]},
    {"name": "Gorg", "role": "Herrero", "notes": ["Sesión #1: Interacción directa en la forja"]}
  ],
  "detected_npc_names": ["Lord Brandon", "Gorg"]
}"""
        parsed = GeminiTTRPGSummarizer.parse_json_response(raw_output, session_number=12)
        self.assertEqual(parsed["session_chapter"]["title"], "Episodio 12: El Despertar del Titán")
        self.assertEqual(parsed["session_chapter"]["episode_synopsis"], "En este episodio dramático, el grupo descubrió la verdadera identidad del traidor y selló la cripta antes del colapso.")
        self.assertEqual(len(parsed["detected_pcs"]), 2)
        self.assertEqual(parsed["detected_pcs"][0]["personaje"], "Kaelen")
        self.assertEqual(parsed["detected_pcs"][0]["clase"], "Paladín")
        self.assertEqual(len(parsed["detected_party"]), 2)
        self.assertEqual(parsed["detected_party"][0]["character_name"], "Kaelen")
        self.assertEqual(parsed["detected_party"][0]["role"], "Paladín")
        self.assertEqual(len(parsed["updated_npcs"]), 2)
        self.assertIn("[Mencionado en la historia]", parsed["updated_npcs"][0]["role"])

    def test_continuity_prompt_youtube_and_npcs(self):
        from src.summarizer.prompts import build_continuity_session_prompt

        prompt = build_continuity_session_prompt(
            roster_formatted="Roster vacío",
            existing_quests=[],
            known_npcs=[],
            transcript_text="Carlos (Kaelen): Ataquemos al dragón!",
            session_number=1,
            is_youtube=True,
            user_character={"character_name": "Markus Veyl", "is_user_character": True},
        )
        # Verify user coaching is strictly omitted for YouTube
        self.assertNotIn("Reflexión de Rol y Compañerismo: Markus Veyl", prompt)
        self.assertIn("cadena vacía", prompt)
        # Verify episode_synopsis schema is requested
        self.assertIn("episode_synopsis", prompt)
        self.assertIn("detected_pcs", prompt)
        # Verify comprehensive NPC instruction (both direct and mentioned)
        self.assertIn("Mencionado en la historia", prompt)
        # Verify language directives and deep scene breakdown
        self.assertIn("JERGA NATURAL DE D&D", prompt)
        self.assertIn("Action Surge", prompt)
        self.assertIn("Sneak Attack", prompt)
        self.assertIn("CRÓNICA PROFUNDA POR ACTOS Y ESCENAS CRONOLÓGICAS", prompt)
        self.assertIn("PROHIBIDO EL RESUMEN SUPERFICIAL", prompt)
        self.assertIn("rol_en_sesion", prompt)
        # Verify strict NPC and Quest extraction criteria
        self.assertIn("CRITERIOS ESTRICTOS DE EXTRACCIÓN DE PNJs", prompt)
        self.assertIn("interaccion_contexto", prompt)
        self.assertIn("interaccion_directa", prompt)
        self.assertIn("CRITERIOS ESTRICTOS DE EXTRACCIÓN DE MISIONES", prompt)
        self.assertIn("subclase", prompt)

    def test_continuity_prompt_prior_lore_injection(self):
        from src.summarizer.prompts import build_continuity_session_prompt

        prior_lore_text = "En la sesión 3, el grupo firmó un pacto con los rebeldes de Oakhaven y descubrieron el culto del Ojo Rojo."
        prompt = build_continuity_session_prompt(
            roster_formatted="Roster",
            existing_quests=[],
            known_npcs=[],
            transcript_text="Continuamos la exploración.",
            session_number=4,
            prior_lore=prior_lore_text,
        )
        self.assertIn("LORE PREVIO Y RESUMEN DE SESIONES ANTERIORES", prompt)
        self.assertIn("pacto con los rebeldes de Oakhaven", prompt)
        self.assertIn("culto del Ojo Rojo", prompt)

    def test_parse_json_response_rol_en_sesion(self):
        raw_json = """{
  "session_chapter": {
    "title": "Acto I: La Emboscada",
    "chronicle_text": "### Acto I: Escena 1: Encuentro en el camino\\nLos héroes debatieron la ruta...",
    "closing_expectations": "Descansar en la posada.",
    "episode_synopsis": "Sinopsis de prueba de 3 párrafos.",
    "next_session_script": ""
  },
  "detected_pcs": [
    {
      "jugador": "Carlos",
      "personaje": "Kaelen",
      "especie": "Elfo",
      "clase": "Paladín",
      "rol_en_sesion": "Lideró la carga en el puente y salvó al prisionero."
    }
  ],
  "updated_quests": [],
  "updated_npcs": []
}"""
        parsed = GeminiTTRPGSummarizer.parse_json_response(raw_json, session_number=1)
        pcs = parsed["detected_pcs"]
        self.assertEqual(len(pcs), 1)
        self.assertEqual(pcs[0]["personaje"], "Kaelen")
        self.assertEqual(pcs[0]["rol_en_sesion"], "Lideró la carga en el puente y salvó al prisionero.")
        party = parsed["detected_party"]
        self.assertEqual(party[0]["session_role"], "Lideró la carga en el puente y salvó al prisionero.")


    def test_parse_json_response_unescaped_internal_quotes(self):
        # Raw JSON from Gemini where nicknames and dialogue have unescaped internal double quotes
        raw_output_with_internal_quotes = """{
  "session_chapter": {
    "title": "Episodio 5: La Furia de "El Martillo"",
    "chronicle_text": "El líder gritó: "¡Avanzad sin miedo!" mientras embestían la puerta.",
    "closing_expectations": "Planear el asalto.",
    "episode_synopsis": "Los aventureros se reunieron con "El Cuervo" para preparar la emboscada."
  },
  "detected_pcs": [
    {
      "jugador": "Rodrigo",
      "personaje": "Halendiel "Hal" Fang",
      "especie": "Semielfo",
      "clase": "Pícaro",
      "rol_en_sesion": "Apodado "El Sombras", se infiltró por los tejados."
    }
  ],
  "updated_quests": [
    {
      "id": "q1",
      "title": "Recuperar el amuleto de "La Dama Luna"",
      "status": "in_progress",
      "subobjectives": [
        {"id": "s1", "text": "Entrar a la cripta", "completed": true}
      ]
    }
  ],
  "updated_npcs": [
    {
      "name": "Boran "Pies Rápidos"",
      "role": "Informante [Mencionado en la historia]",
      "notes": ["Sesión #5: Conocido como "El Chismoso" en los bajos fondos"]
    }
  ],
  "detected_npc_names": ["Boran"]
}"""
        parsed = GeminiTTRPGSummarizer.parse_json_response(raw_output_with_internal_quotes, session_number=5)
        self.assertEqual(len(parsed["detected_pcs"]), 1)
        self.assertIn("Hal", parsed["detected_pcs"][0]["personaje"])
        self.assertEqual(parsed["detected_pcs"][0]["clase"], "Pícaro")
        self.assertEqual(len(parsed["updated_quests"]), 1)
        self.assertIn("La Dama Luna", parsed["updated_quests"][0]["title"])
        self.assertEqual(len(parsed["updated_npcs"]), 1)
        self.assertIn("Pies Rápidos", parsed["updated_npcs"][0]["name"])
        self.assertIn("Avanzad", parsed["session_chapter"]["chronicle_text"])

    def test_dm_filtered_from_parse_json_response(self):
        raw_json = """{
  "detected_pcs": [
    {
      "personaje": "Dungeon Master",
      "jugador": "Carlos",
      "especie": "Humano",
      "clase": "Dungeon Master",
      "rol_en_sesion": "Actuó como Dungeon Master y controló los PNJs",
      "hitos_acumulados": ["Dirigió la sesión"]
    },
    {
      "personaje": "Halendiel",
      "jugador": "Ana",
      "especie": "Elfo",
      "clase": "Dungeon Master",
      "rol_en_sesion": "Lanzó flechas certeras contra el ogro.",
      "hitos_acumulados": ["Sesión #1: Derrotó al ogro"]
    }
  ]
}"""
        parsed = GeminiTTRPGSummarizer.parse_json_response(raw_json, session_number=1)
        names = [p["personaje"] for p in parsed["detected_pcs"]]
        self.assertNotIn("Dungeon Master", names)
        self.assertIn("Halendiel", names)
        halendiel = next(p for p in parsed["detected_pcs"] if p["personaje"] == "Halendiel")
        self.assertEqual(halendiel["clase"], "-")

    def test_prompt_in_character_and_dm_rules(self):
        from src.summarizer.prompts import build_continuity_session_prompt
        prompt = build_continuity_session_prompt(
            roster_formatted="Roster",
            existing_quests=[],
            known_npcs=[],
            transcript_text="Texto",
            session_number=1,
            target_language="es",
        )
        self.assertIn("REGLA ESTRICTA DE ACCIONES IN-CHARACTER", prompt)
        self.assertIn("EXCLUSIÓN DEL DUNGEON MASTER", prompt)
        self.assertIn("REGLA DE COHERENCIA DE ESTADO Y SUBOBJETIVOS", prompt)
        self.assertIn("NUNCA 'Dungeon Master'", prompt)

    def test_prompt_table_talk_and_grounding_rules(self):
        from src.summarizer.prompts import build_continuity_session_prompt, build_dnd_session_prompt

        # 1. Spanish Continuity Prompt
        prompt_es = build_continuity_session_prompt(
            roster_formatted="Roster",
            existing_quests=[],
            known_npcs=[],
            transcript_text="Texto de prueba",
            session_number=2,
            target_language="es",
            user_character={},  # Explicitly empty
        )
        self.assertIn("CHARLA OPERATIVA DE MESA VS. RUIDO DE LA VIDA REAL", prompt_es)
        self.assertIn("GROUNDING ESTRICTO Y CERO ALUCINACIONES TÁCTICAS", prompt_es)
        self.assertIn("COBERTURA OBLIGATORIA DE TODOS LOS COMBATES Y ENCUENTROS", prompt_es)
        self.assertIn("VOCABULARIO LITERAL DE MESA", prompt_es)
        self.assertIn("No hay un personaje del usuario designado", prompt_es)
        self.assertNotIn("REFLEXIÓN Y COACHING ESTRATÉGICO PARA MARKUS", prompt_es)

        # 2. English Continuity Prompt
        prompt_en = build_continuity_session_prompt(
            roster_formatted="Roster",
            existing_quests=[],
            known_npcs=[],
            transcript_text="Test audio text",
            session_number=2,
            target_language="en",
            user_character={},
        )
        self.assertIn("OPERATIVE TABLE TALK VS. REAL-WORLD NOISE", prompt_en)
        self.assertIn("STRICT GROUNDING & ZERO TACTICAL HALLUCINATIONS", prompt_en)
        self.assertIn("MANDATORY FULL COVERAGE OF ALL COMBATS & ENCOUNTERS", prompt_en)
        self.assertIn("REGISTER COMPANIONS & CHARACTER SWAPS", prompt_en)
        self.assertIn("There is no designated user character for personal reflection", prompt_en)
        self.assertNotIn("STRATEGIC COACHING & REFLECTION FOR MARKUS", prompt_en)

        # 3. Base DnD Session Prompt Grounding
        prompt_dnd = build_dnd_session_prompt(
            roster_formatted="Roster",
            transcript_text="Audio text",
            target_language="es",
            user_character={},
        )
        self.assertIn("GROUNDING ESTRICTO Y CERO ALUCINACIONES TÁCTICAS", prompt_dnd)
        self.assertIn("COBERTURA OBLIGATORIA DE TODOS LOS COMBATES Y ENCUENTROS", prompt_dnd)
        self.assertNotIn("REFLEXIÓN Y COACHING ESTRATÉGICO PARA MARKUS", prompt_dnd)

    def test_universal_causality_and_mystery_extraction(self):
        """Test that prompts enforce physical causality and automatic mystery extraction for unseen entities."""
        from src.summarizer.prompts import build_continuity_session_prompt, build_dnd_session_prompt

        # Spanish Continuity Prompt
        p_es = build_continuity_session_prompt(
            roster_formatted="Roster",
            existing_quests=[],
            known_npcs=[],
            transcript_text="Texto",
            session_number=1,
            target_language="es",
        )
        self.assertIn("CAUSALIDAD FÍSICA ESTRICTA Y PROHIBICIÓN DE RESÚMENES PASIVOS/PEREZOSOS", p_es)
        self.assertIn("EXTRACCIÓN AUTOMÁTICA DE MISTERIOS", p_es)
        self.assertIn("misterios_abiertos", p_es)

        # English Continuity Prompt
        p_en = build_continuity_session_prompt(
            roster_formatted="Roster",
            existing_quests=[],
            known_npcs=[],
            transcript_text="Text",
            session_number=1,
            target_language="en",
        )
        self.assertIn("STRICT PHYSICAL CAUSALITY & BAN ON PASSIVE/LAZY TRANSITION SUMMARIES", p_en)
        self.assertIn("AUTOMATIC MYSTERY EXTRACTION", p_en)

        # Base DnD Session Prompt
        p_dnd_es = build_dnd_session_prompt(roster_formatted="Roster", transcript_text="Audio", target_language="es")
        self.assertIn("CAUSALIDAD FÍSICA ESTRICTA Y PROHIBICIÓN DE RESÚMENES PASIVOS/PEREZOSOS", p_dnd_es)
        self.assertIn("EXTRACCIÓN AUTOMÁTICA DE MISTERIOS", p_dnd_es)

        p_dnd_en = build_dnd_session_prompt(roster_formatted="Roster", transcript_text="Audio", target_language="en")
        self.assertIn("STRICT PHYSICAL CAUSALITY & BAN ON PASSIVE/LAZY TRANSITION SUMMARIES", p_dnd_en)
        self.assertIn("AUTOMATIC MYSTERY EXTRACTION", p_dnd_en)

    def test_non_monolithic_quest_decomposition(self):
        """Test that prompts enforce non-monolithic quest decomposition into side quests and emergent arcs."""
        from src.summarizer.prompts import build_continuity_session_prompt

        # Spanish
        p_es = build_continuity_session_prompt(
            roster_formatted="Roster",
            existing_quests=[],
            known_npcs=[],
            transcript_text="Texto",
            session_number=3,
            target_language="es",
        )
        self.assertIn("DESCOMPOSICIÓN NO MONOLÍTICA DE MISIONES", p_es)
        self.assertIn("OBJETIVOS INMEDIATOS -> MISIONES SECUNDARIAS COMPLETADAS", p_es)
        self.assertIn("NUEVOS OBJETIVOS EMERGENTES", p_es)

        # English
        p_en = build_continuity_session_prompt(
            roster_formatted="Roster",
            existing_quests=[],
            known_npcs=[],
            transcript_text="Text",
            session_number=3,
            target_language="en",
        )
        self.assertIn("NON-MONOLITHIC QUEST DECOMPOSITION", p_en)
        self.assertIn("IMMEDIATE OBJECTIVES -> COMPLETED SIDE QUESTS", p_en)
        self.assertIn("NEW EMERGENT OBJECTIVES", p_en)

    def test_universal_character_mid_session_transitions(self):
        """Test that prompts enforce mid-session character transition rules without phantom attribution."""
        from src.summarizer.prompts import build_continuity_session_prompt, build_dnd_session_prompt

        # Spanish continuity
        p_es = build_continuity_session_prompt(
            roster_formatted="Roster",
            existing_quests=[],
            known_npcs=[],
            transcript_text="Texto",
            session_number=2,
            target_language="es",
        )
        self.assertIn("REGLA UNIVERSAL DE TRANSICIÓN Y RELEVO DE PERSONAJES A MITAD DE SESIÓN", p_es)

        # English continuity
        p_en = build_continuity_session_prompt(
            roster_formatted="Roster",
            existing_quests=[],
            known_npcs=[],
            transcript_text="Text",
            session_number=2,
            target_language="en",
        )
        self.assertIn("UNIVERSAL MID-SESSION PLAYER CHARACTER TRANSITIONS", p_en)

        # Base DnD Prompts
        p_dnd_es = build_dnd_session_prompt(roster_formatted="Roster", transcript_text="Audio", target_language="es")
        self.assertIn("REGLA UNIVERSAL DE TRANSICIÓN Y RELEVO DE PERSONAJES A MITAD DE SESIÓN", p_dnd_es)

        p_dnd_en = build_dnd_session_prompt(roster_formatted="Roster", transcript_text="Audio", target_language="en")
        self.assertIn("UNIVERSAL MID-SESSION PLAYER CHARACTER TRANSITIONS", p_dnd_en)


if __name__ == "__main__":
    unittest.main()


