"""Prompt definitions and builders for Gemini TTRPG Summarizer."""

from typing import Any, Dict, List, Optional


def build_dnd_session_prompt(
    roster_formatted: str,
    transcript_text: str,
    has_markus: Optional[bool] = None,
    user_character: Optional[Dict[str, Any]] = None,
    session_number: int = 1,
    target_language: str = "es",
    is_youtube: bool = False,
) -> str:
    """
    Build a forward-looking structured prompt for generating the comprehensive D&D session report:
    1. SECCIÓN 1: CRÓNICA DETALLADA DE LA AVENTURA Y COMBATES
       - Narrative recounting with dialogue highlights & story context.
       - Combat breakdown (dice rolls, spell names, tactical decisions).
       - NPCs encountered, locations discovered, and loot/gold acquired.
    2. SECCIÓN 2: CIERRE DE MESA, DECISIONES Y EXPECTATIVAS
       - Notable highlights chosen by the players at the end of the game.
       - Immediate plans, intentions, and loot/gold acquired.
    3. SECCIÓN 3: REFLEXIÓN DE ROL Y COMPAÑERISMO (CONDICIONAL)
       - ONLY generated if user_character is specified. OMITTED completely if none.
    4. SECCIÓN 4: 🎙️ GUION PARA ABRIR LA PRÓXIMA SESIÓN (PARA LEER EN VOZ ALTA)
       - Casual, conversational first-person plural recap ("A ver gente...") to open the next session.
    """
    is_english = str(target_language).lower().startswith("en")
    next_session = session_number + 1
    # Determine user character
    char_name = ""
    char_class_desc = ""
    if not is_youtube:
        if user_character is not None and isinstance(user_character, dict):
            char_name = (user_character.get("character_name") or user_character.get("name") or "").strip()
            if char_name in ("-", "(DM)", "Dungeon Master", ""):
                char_name = ""
            else:
                p_name = (user_character.get("player_name") or user_character.get("player") or "").strip()
                c_role = (user_character.get("role") or user_character.get("class") or "").strip()
                c_sub = (user_character.get("subclass") or "").strip()
                c_spec = (user_character.get("species") or "").strip()
                parts = [p for p in [p_name, c_spec, c_role, c_sub] if p and p not in ("-", "N/A", "(N/A)")]
                char_class_desc = " ".join(parts)
        elif has_markus and user_character is None:
            char_name = "Markus Veyl"
            char_class_desc = "Guerrero (Fighter) Battle Master"

    if is_english:
        lang_instruction = """⚠️ CRITICAL LANGUAGE DIRECTIVE (100% ENGLISH MANDATORY):
Generate all content (Executive Briefing, Detailed Notes, Action Items, Key Points, Chronicle) strictly in English (e.g., English if 'en', Spanish if 'es'). Match the language requested by the user.
- Target language is ENGLISH.
- 100% of the generated output (act and scene titles, headings, tables, combat breakdown, quotes, and synopsis) MUST be in English.
- STRICTLY FORBIDDEN to output text in any other language.
- ⚠️ CRITICAL DIAGRAMMING DIRECTIVE: Do NOT generate fragile ASCII text diagrams (boxes made of '+---+' or '|'). To represent comparisons, workflows, decision matrices, or state transitions, ALWAYS use native Markdown tables or structured step-by-step lists.
- When outputting mathematical or probabilistic formulas involving money, escape currency dollar signs inside math blocks (e.g., use '\\$1,000' or write 'USD 1,000') so they do not collide with LaTeX delimiters. Ensure equations are cleanly structured for KaTeX rendering."""
        header_title = "# 📜 D&D SESSION COMPREHENSIVE REPORT"
        sec0_title = "# 🎭 ADVENTURING COMPANY (DETECTED PROTAGONISTS)"
        sec0_body = """Generate a Markdown table of the detected protagonist characters in this session:
| Character | Player / Role | Class / Species | Session Role |
|---|---|---|---|
(Include Character name, Player, Class and Species, and a 1-sentence summary of their in-world fictional actions or achievements in this episode).
⚠️ STRICT DIRECTIVE: ONLY Player Characters (PCs) belong in this table. A player who acts as a core protagonist in the narrative (e.g. Liam O'Brien playing Halendiel Fang) is a Player Character (PC); DO NOT omit, discard, or drop them from this table. Distinguish the true Dungeon Master (who sets DCs, describes monster attacks, and runs the world) from the players. Liam O'Brien is a PLAYER playing the Bard Halendiel Fang. The Dungeon Master (DM) is strictly the referee/narrator and NEVER has a character row. Characters can NEVER have the class or role 'Dungeon Master'."""
        sec1_title = "# SECTION 1: DETAILED ADVENTURE CHRONICLE & COMBAT BREAKDOWN"
        sec1_guidelines = """⚠️ MANDATORY DIRECTIVE: DEEP CHRONOLOGICAL SCENE BREAKDOWN (NO OVER-SUMMARIZATION):
- STRICTLY FORBIDDEN to write a generic 3-paragraph summary. This audio represents hours of roleplay gameplay.
- Structure the chronicle into detailed chronological ACTS AND SCENES (e.g. '### Act I: Scene 1: The Mountain Trail', '### Scene 2: Negotiation in the Keep', '### Act II: Scene 3: Ambush in the Caverns').
- Dedicate 2 to 3 comprehensive, rich paragraphs per major scene or encounter:
  * Specific verbal dialogues and quotes between characters, NPCs, and the DM.
  * Strategic discussions and party plans debated prior to action.
  * Skill checks and dice rolls (Athletics, Perception, Stealth, saving throws, natural 20s, natural 1s).
  * Tactical combat maneuvers described step-by-step (specific spells cast, environmental interactions, tactical positioning), NOT just the final outcome.
- ⚠️ STRICT GROUNDING & ZERO TACTICAL HALLUCINATIONS:
  * FORBIDDEN to invent grid distances or precise foot movements not verbalized in the audio (e.g. NEVER invent 'retreated 25 feet' or 'moved 15 feet to the left').
  * FORBIDDEN to invent phantom terrain or structures not described by the DM (e.g. phantom shacks, huts, pits).
  * Ground all scene descriptions, spells, checks, and interactions strictly in the verbal transcript.
- ⚠️ STRICT PHYSICAL CAUSALITY & BAN ON PASSIVE/LAZY TRANSITION SUMMARIES:
  * STRICTLY FORBIDDEN to use passive abstractions or lazy transition summaries (e.g. NEVER write 'the party was transported', 'a trap absorbed them', 'they ended up at', or 'they suddenly appeared').
  * You MUST document the EXPLICIT PHYSICAL CAUSALITY spoken in the transcript: detail who or what executed the physical trigger (who pulled a lever, who pushed, who triggered the mechanism, who ambushed from behind, or what creature/entity intervened).
  * AUTOMATIC MYSTERY EXTRACTION: If a physical action, ambush, trap, or intervention is caused by an unseen, unidentified, masked, or concealed entity whose identity was not revealed in the audio, you MUST register it as an open mystery entry (e.g. 'Investigate the identity of the unknown entity that intervened/attacked during [Scene]').
- ⚠️ MANDATORY FULL COVERAGE OF ALL COMBATS & ENCOUNTERS:
  * If multiple major combats occurred (e.g. a Troll fight AND a Dragon fight), EACH MUST be chronicled in distinct chronological scenes. DO NOT merge, omit, or skip major battles.
- ⚠️ REGISTER COMPANIONS & CHARACTER SWAPS:
  * Capture party animal companions, familiars, or mascots (e.g. Minipeko) and character switches/retirements.
- ⚠️ UNIVERSAL MID-SESSION PLAYER CHARACTER TRANSITIONS:
  * If operational table discussion indicates a player is retiring/benching a character and introducing a new one mid-session:
    - Reflect the departure of the former character in their session milestone/role (e.g. separated, departed on their own path, or staying in reserve).
    - Register the new character starting from this session with their debut.
    - DO NOT attribute subsequent battles or actions to the retired character once the new character enters play."""
        sec1_sub1 = "## 1.1 Narrative Summary & Dialogue Highlights (Organized by Acts & Scenes)"
        sec1_sub2 = "## 1.2 Combat Breakdown & Tactical Decisions (Maneuvers, Spells & Critical Rolls)"
        sec1_sub3 = "## 1.3 NPCs Encountered & Key Clues (Include both direct interactions and NPCs tagged with '[Mentioned in story]')"
        sec1_sub4 = "## 1.4 Locations, Traps & Points of Interest"
        sec2_title = "# SECTION 2: TABLE CLOSING, DECISIONS & IMMEDIATE PLANS"
        sec2_body = "- Key takeaways, party decisions at session end, loot and gold acquired, and immediate plans."

        if char_name:
            sec3_title = f"# SECTION 3: ROLEPLAY & COMRADERY REFLECTION: {char_name} ({char_class_desc})"
            sec3_body = f"""Reflection for **{char_name}** ({char_class_desc}):
> ⚠️ **CRITICAL DIRECTIVE: NO MIN/MAXING OR ROBOTIC COMBAT DPS COACHING**
> - DO NOT lecture the player on damage optimization or action economy.
> - Help the player be a better teammate and roleplayer true to their character.
Analyze 4 areas:
## 3.1 Character Coherence & Roleplay Development
## 3.2 Creativity & Environment Usage vs. Rules (Rule of Cool vs RAW)
## 3.3 Party Dynamics & Teamwork
## 3.4 In-Character Dilemmas for Next Session"""
            sec3_block = f"{sec3_title}\n{sec3_body}\n\n---\n"
            sec4_num = 4
        else:
            sec3_block = ""
            sec4_num = 3

        if is_youtube:
            sec4_title = f"# SECTION {sec4_num}: 📌 EXECUTIVE EPISODE SYNOPSIS"
            sec4_body = """Write a crisp, objective executive synopsis of exactly **3 to 4 paragraphs** summarizing the episode's major plot developments, key revelations, dramatic twists, and the ending status of characters and factions for viewers and analysts."""
        else:
            sec4_title = f'# SECTION {sec4_num}: 🎙️ SCRIPT TO OPEN SESSION #{next_session} (READ ALOUD)'
            sec4_body = f"""Write a crisp, fast-paced read-aloud script of exactly **3 to 4 paragraphs** to be read at the start of Session #{next_session} before rolling dice.
> ⚠️ **STRICT DIRECTIVE: DO NOT USE AN EPIC HIGH-FANTASY NOVEL NARRATOR.**
> - **MANDATORY VOICE: Casual, conversational FIRST-PERSON PLURAL tone ("Alright folks, quick recap of where we left off last time: we went to... talked to... got ambushed at... and the session ended right when...")**, exactly as a player talking to friends over Discord.
> - Direct, practical, ends in the immediate cliffhanger."""

        return f"""PARTY ROSTER:
{roster_formatted}

GENERAL INSTRUCTIONS:
You are an expert Dungeons & Dragons (5e / 5.5e) chronicler and tactical roleplay analyst.
Analyze the following session audio transcript.
{lang_instruction}

{header_title}

---

{sec0_title}
{sec0_body}

---

{sec1_title}
{sec1_guidelines}

{sec1_sub1}
{sec1_sub2}
{sec1_sub3}
{sec1_sub4}

---

{sec2_title}
{sec2_body}

---

{sec3_block}{sec4_title}
{sec4_body}

---

{lang_instruction}

FULL SESSION AUDIO TRANSCRIPT:
{transcript_text}
"""

    # Spanish (Default)
    lang_instruction = """⚠️ DIRECTIVA CRÍTICA DE IDIOMA Y JERGA NATURAL DE D&D:
Generate all content (Executive Briefing, Detailed Notes, Action Items, Key Points, Chronicle) strictly in Spanish (e.g., English if 'en', Spanish if 'es'). Match the language requested by the user.
- Redacta la crónica, el informe y la narrativa en ESPAÑOL FLUIDO Y NATURAL.
- NO fuerces traducciones artificiales u ortopédicas de la terminología oficial de D&D.
- PRESERVA INTACTOS los términos oficiales de D&D, nombres de conjuros, clases, dotes, maniobras, tiradas de salvación y mecánicas en inglés o spanglish tal como se hablan en la mesa de juego (ej. Action Surge, Sneak Attack, Divine Smite, Battle Master, Insight check, Death saving throw, Saving throw, Short rest, Long rest, nat 20, nat 1).
- Usa títulos y encabezados de actos y escenas en español (ej. 'Acto I: Escena 1', 'Crónica Narrativa').
- Al generar fórmulas matemáticas o probabilísticas que involucren cantidades monetarias, escapa los signos de dólar dentro de los bloques matemáticos (ej. usa '\\$1,000' o escribe 'USD 1,000') para que no colisionen con los delimitadores de LaTeX."""
    header_title = "# 📜 INFORME COMPLETO DE SESIÓN DE D&D"
    sec0_title = "# 🎭 COMPAÑÍA DE AVENTUREROS (PROTAGONISTAS DETECTADOS)"
    sec0_body = """Genera una tabla Markdown con los personajes protagonistas de esta sesión:
| Personaje | Jugador / Rol | Clase / Especie | Rol en la Sesión |
|---|---|---|---|
(Incluye Nombre del personaje, Jugador, Clase y Especie, y un resumen de exactamente 1 oración sobre sus acciones ficticias in-character o logros dentro del mundo en este episodio).
⚠️ DIRECTIVA ESTRICTA: Esta tabla es EXCLUSIVA para Personajes Jugadores (PCs). Un jugador que actúe como protagonista clave en la narrativa (por ejemplo, Liam O'Brien interpretando al bardo Halendiel Fang) es un Personaje Jugador (PC); PROHIBIDO omitirlo, descartarlo o borrarlo de esta tabla. Distingue con precisión al verdadero Dungeon Master (quien establece dificultades de tirada/DC, describe ataques de monstruos, narra el entorno y arbitra el mundo) de los jugadores. Liam O'Brien es un JUGADOR que interpreta al bardo Halendiel Fang, NO el Dungeon Master. El DM es el narrador/árbitro fuera de personaje y NUNCA tiene fila en esta tabla. Ningún personaje puede tener la clase o rol 'Dungeon Master'."""
    sec1_title = "# SECCIÓN 1: CRÓNICA DETALLADA DE LA AVENTURA Y COMBATES"
    sec1_guidelines = """⚠️ DIRECTIVA OBLIGATORIA: CRÓNICA PROFUNDA POR ACTOS Y ESCENAS CRONOLÓGICAS (PROHIBIDO EL RESUMEN SUPERFICIAL):
- PROHIBIDO TERMINANTEMENTE escribir un resumen genérico o superficial de 3 o 4 párrafos para toda la sesión. Esta transcripción representa horas de partida real de rol.
- Estructura OBLIGATORIAMENTE la crónica narrativa en ACTOS Y ESCENAS cronológicas detalladas (ej. '### Acto I: Escena 1: El Camino del Bosque', '### Escena 2: Negociación en la Posada', '### Acto II: Escena 3: Emboscada en las Cavernas', etc.).
- Dedica entre 2 y 3 PÁRRAFOS COMPLETOS Y EXTENSOS a cada escena principal o combate:
  * Diálogos verbales y citas directas: cita frases, discusiones o intercambios emocionales entre personajes, PNJs o el DM.
  * Planes y debates estratégicos: describe las discusiones tácticas y dilemas que la mesa debatió antes de actuar.
  * Pruebas de habilidad y dados: menciona explícitamente tiradas destacadas (pruebas de Atletismo, Percepción, Sigilo, Engaño, salvaciones críticas '20 natural' y pifias '1 natural').
  * Combates y maniobras turno a turno: describe la coreografía táctica detallada (conjuros específicos lanzados, posiciones, uso del entorno, daño recibido), NO solo el desenlace.
- ⚠️ GROUNDING ESTRICTO Y CERO ALUCINACIONES TÁCTICAS:
  * PROHIBIDO inventar movimientos de cuadrícula o distancias precisas no verbalizadas en el audio (ej. NUNCA inventar 'se replegó 25 pies', 'se colocó a 15 pies').
  * PROHIBIDO inventar elementos topográficos, estructuras o terreno fantasma (ej. chozas, cabañas o fosos no descritos por el DM).
  * La crónica debe ceñirse al 100% a lo efectivamente verbalizado por los jugadores y el DM.
- ⚠️ CAUSALIDAD FÍSICA ESTRICTA Y PROHIBICIÓN DE RESÚMENES PASIVOS/PEREZOSOS:
  * PROHIBIDO TERMINANTEMENTE usar abstracciones pasivas o resúmenes perezosos de transición (ej. NUNCA escribas "el grupo fue transportado", "una trampa los absorbió", "terminaron en" o "aparecieron de repente").
  * Registra OBLIGATORIAMENTE la CAUSALIDAD FÍSICA EXPLÍCITA verbalizada en la transcripción: detalla quién o qué ejecutó el detonante físico (quién tiró de una palanca, quién empujó, quién activó el mecanismo, quién atacó por la espalda o qué criatura/entidad los emboscó).
  * EXTRACCIÓN AUTOMÁTICA DE MISTERIOS: Si una acción física, trampa, emboscada o intervención es provocada por una entidad oculta, enmascarada, invisible o cuya identidad no fue revelada en el audio, debes registrarla OBLIGATORIAMENTE como una entrada de misterio abierto (ej. "Investigar la identidad de la entidad desconocida que intervino/atacó durante [Escena]").
- ⚠️ COBERTURA OBLIGATORIA DE TODOS LOS COMBATES Y ENCUENTROS:
  * Si en la sesión ocurren múltiples combates o encuentros mayores (por ejemplo, combate con un Trol Y combate con un Dragón), AMBOS deben ser narrados exhaustivamente en escenas separadas.
  * PROHIBIDO omitir, fusionar apresuradamente o saltarse combates mayores.
- ⚠️ VOCABULARIO LITERAL DE MESA Y PROHIBICIÓN DE ARCAÍSMOS:
  * PROHIBIDO usar arcaísmos o sinónimos medievales rebuscados (ej. NUNCA uses 'sierpe' para dragón, 'pertrechos' para suministros o equipo, 'yacija', 'mengua').
  * Usa vocabulario directo de la mesa de D&D y spanglish natural: 'dragón', 'trol', 'suministros', 'equipo', 'pociones', 'trampa'.
- ⚠️ DIRECTIVA CRÍTICA DE DIAGRAMAS Y TABLAS: Queda estrictamente PROHIBIDO generar diagramas frágiles en texto ASCII (cajas compuestas por '+---+' o '|'). Para representar comparaciones, flujos de trabajo, matrices de decisión o transiciones de estado, utiliza SIEMPRE tablas nativas en Markdown o listas estructuradas paso a paso.
- ⚠️ REGISTRO DE COMPAÑEROS, MASCOTAS Y RELEVOS DE PERSONAJE:
  * Registra adecuadamente acompañantes, familiares o mascotas de la party (ej. Minipeko) y cambios o relevos de personajes.
- ⚠️ REGLA UNIVERSAL DE TRANSICIÓN Y RELEVO DE PERSONAJES A MITAD DE SESIÓN:
  * Si las conversaciones operativas de la mesa indican que un jugador retira, deja en reserva o sustituye a su personaje e introduce uno nuevo a mitad de la partida:
    - Refleja la salida o retiro del personaje saliente en su resumen/hito de sesión (ej. se separó del grupo, marchó por un camino propio o quedó en reserva).
    - Registra el nuevo personaje en la compañía de aventureros comenzando desde esta sesión con su debut.
    - PROHIBIDO TERMINANTEMENTE atribuir combates, diálogos o acciones posteriores al personaje retirado una vez que el nuevo entra en juego."""
    sec1_sub1 = "## 1.1 Resumen Narrativo y Diálogos Memorables (Estructurado por Actos y Escenas)"
    sec1_sub2 = "## 1.2 Desglose Pormenorizado de Combates y Táctica (Maniobras, Conjuros y Críticos/Pifias)"
    sec1_sub3 = "## 1.3 Personajes No Jugadores (PNJs) e Interacciones Clave (Taxonomía de 3 niveles: Importantes, Interacción/Contexto incluyendo regla de personajes sin nombre, y Mencionados en la historia)"
    sec1_sub4 = "## 1.4 Lugares Explorados, Trampas y Tesoros"
    sec2_title = "# SECCIÓN 2: CIERRE DE MESA, DECISIONES Y PLANES INMEDIATOS"
    sec2_body = "- Momentos destacados elegidos por la mesa, decisiones al culminar la partida y planes inmediatos para la siguiente sesión."

    if char_name:
        sec3_title = f"# SECCIÓN 3: REFLEXIÓN DE ROL Y COMPAÑERISMO: {char_name} ({char_class_desc})"
        sec3_body = f"""Reflexión de interpretación y trabajo en equipo para **{char_name}** ({char_class_desc}):
> ⚠️ **DIRECTIVA CRÍTICA: PROHIBIDO EL MIN/MAXING O COACHING ROBÓTICO DE COMBATE**
> - NO sermonees al jugador sobre maximizar daño por turno ni optimización matemática.
> - El objetivo es enriquecer el rol dramático y el compañerismo con la mesa.
Analiza 4 áreas:
## 3.1 Coherencia y Desarrollo de Personaje (fidelidad a personalidad y trasfondo, decisiones potentes y oportunidades desaprovechadas)
## 3.2 Creatividad y Uso del Entorno vs. Reglas (Rule of Cool vs RAW y advertencias amables)
## 3.3 Dinámica de Grupo y Trabajo en Equipo (apoyo a los compañeros para permitirles brillar)
## 3.4 Dilemas para la Próxima Sesión (1 o 2 preguntas reflexivas in-character)"""
        sec3_block = f"{sec3_title}\n{sec3_body}\n\n---\n"
        sec4_num = 4
    else:
        sec3_block = ""
        sec4_num = 3

    if is_youtube:
        sec4_title = f"# SECCIÓN {sec4_num}: 📌 SINOPSIS EJECUTIVA DEL EPISODIO"
        sec4_body = """Redacta un resumen ejecutivo y objetivo de exactamente **3 a 4 párrafos** que sintetice los acontecimientos dramáticos más importantes del episodio, revelaciones clave, giros de trama y el estado en el que quedan los personajes y facciones al concluir la sesión para espectadores y analistas."""
    else:
        sec4_title = f'# SECCIÓN {sec4_num}: 🎙️ GUION PARA ABRIR LA SESIÓN #{next_session} (PARA LEER EN VOZ ALTA)'
        sec4_body = f"""Redacta un guion electrizante de exactamente **3 a 4 párrafos** para leer en voz alta al inicio de la Sesión #{next_session} en 45-60 segundos antes de tirar dados.
> ⚠️ **DIRECTIVA CRÍTICA: PROHIBIDO USAR NARRADOR ÉPICO SOLEMNE DE NOVELA O EN TERCERA PERSONA.**
> - **VOZ Y TONO OBLIGATORIO: Conversacional, relajado y directo en PRIMERA PERSONA DEL PLURAL ("A ver gente, la sesión pasada fuimos a... hablamos con... nos emboscaron en... y la partida se cortó justo cuando...")**, como hablarle a compas por Discord.
> - Culmina en el cliffhanger o situación inmediata en la que arranca la Sesión #{next_session}."""

    return f"""ROSTER DE LA MESA:
{roster_formatted}

INSTRUCCIONES GENERALES:
Eres un cronista profesional de Dungeons & Dragons (5e / 5.5e) y analista táctico-narrativo.
Analiza la siguiente transcripción de audio. Divide el informe en las siguientes secciones secuenciales:
{lang_instruction}

{header_title}

---

{sec0_title}
{sec0_body}

---

{sec1_title}
{sec1_guidelines}

{sec1_sub1}
{sec1_sub2}
{sec1_sub3}
{sec1_sub4}

---

{sec2_title}
{sec2_body}

---

{sec3_block}{sec4_title}
{sec4_body}

---

{lang_instruction}

TRANSCRIPCIÓN COMPLETA DEL AUDIO DE LA SESIÓN:
{transcript_text}
"""


# -----------------------------------------------------------------
# Multi-Session Continuity Prompt for Living Campaign Journal
# -----------------------------------------------------------------


def build_continuity_session_prompt(
    roster_formatted: str,
    existing_quests: List[Dict[str, Any]],
    known_npcs: List[Dict[str, Any]],
    transcript_text: str,
    session_number: int,
    has_markus: Optional[bool] = None,
    target_language: str = "es",
    user_character: Optional[Dict[str, Any]] = None,
    is_youtube: bool = False,
    prior_lore: Optional[str] = None,
) -> str:
    """
    Build a multi-session continuity prompt for Gemini.
    Extracts session chapter, updates active quests with sub-objectives, and tracks universal NPCs.
    Outputs structured JSON.
    """
    is_english = str(target_language).lower().startswith("en")

    # Determine user character for coaching (strictly disabled for YouTube)
    char_name = ""
    char_desc = ""
    if not is_youtube:
        if user_character is not None and isinstance(user_character, dict):
            char_name = (user_character.get("character_name") or user_character.get("name") or "").strip()
            if char_name in ("-", "(DM)", "Dungeon Master", ""):
                char_name = ""
            else:
                char_player = (user_character.get("player_name") or user_character.get("player") or "").strip()
                char_class = (user_character.get("role") or user_character.get("class") or "").strip()
                char_subclass = (user_character.get("subclass") or "").strip()
                char_species = (user_character.get("species") or "").strip()
                parts = []
                if char_player and char_player not in ("-", "N/A"):
                    parts.append(f"jugador {char_player}")
                if char_species and char_species not in ("-", "N/A", "(N/A - DM)"):
                    parts.append(char_species)
                if char_class and char_class not in ("-", "N/A"):
                    parts.append(char_class)
                if char_subclass and char_subclass not in ("-", "N/A", "(N/A)"):
                    parts.append(f"subclase {char_subclass}")
                char_desc = ", ".join(parts)
        elif has_markus is True and user_character is None:
            char_name = "Markus Veyl"
            char_desc = "Roymc89 - Battle Master Lvl 4"

    # Format existing quests
    if existing_quests:
        quests_lines = []
        for q in existing_quests:
            subs = ", ".join(
                [f"{s.get('text', '')} [{'x' if s.get('completed') else ' '}]" for s in q.get("subobjectives", [])]
            )
            subs_str = f" | Sub-objetivos: {subs}" if subs else ""
            quests_lines.append(
                f"- [ID: {q.get('id', '-')}] {q.get('title', '')} (Estado: {q.get('status', 'in_progress')}{subs_str})"
            )
        quests_formatted = "\n".join(quests_lines)
    else:
        quests_formatted = "Ninguna misión registrada aún (esta es la primera sesión o no hay misiones previas)."

    # Format known NPCs
    if known_npcs:
        npcs_lines = []
        for n in known_npcs:
            last_note = n.get("notes", [""])[-1] if n.get("notes") else ""
            note_str = f" | Última nota: {last_note}" if last_note else ""
            npcs_lines.append(
                f"- {n.get('name', '')} ({n.get('role', 'PNJ')} | Visto en Sesión {n.get('first_seen_session', 1)}{note_str})"
            )
        npcs_formatted = "\n".join(npcs_lines)
    else:
        npcs_formatted = "Ningún PNJ registrado aún (esta es la primera sesión o no hay PNJs previos)."

    recap_guidance = ""
    if session_number > 1:
        recap_guidance = f"""
REGLA CRUCIAL DE CONTINUIDAD (SESIÓN #{session_number}):
La sesión grabada puede comenzar con los jugadores o el DM haciendo un resumen o recordando lo que pasó en sesiones anteriores.
RECONOCE ese resumen inicial y utilízalo ÚNICAMENTE como contexto previo; NO dupliques eventos pasados en la crónica de esta sesión #{session_number}. La crónica y el combate deben enfocarse exclusivamente en los hechos nuevos que ocurrieron en esta sesión #{session_number}.
"""

    prior_lore_block = ""
    if prior_lore and str(prior_lore).strip():
        prior_lore_block = f"""
LORE PREVIO Y RESUMEN DE SESIONES ANTERIORES (CONTEXTO DE LA CAMPAÑA):
{str(prior_lore).strip()}
(Utiliza este lore previo para dar continuidad al mundo, misiones en curso y personajes clave preexistentes).
"""

    if char_name:
        if is_english:
            coaching_instructions = f"""2. Accurately attribute every action, spell, roll, and decision to the characters and players in the Roster. Pay special attention to {char_name} ({char_desc}) for their "Roleplay & Fellowship Reflection: {char_name}". IMPORTANT: MIN/MAXING OR ROBOTIC COACHING IS STRICTLY FORBIDDEN (zero lessons on maximizing damage per turn or mathematical action economy; focus is narrative, character depth, teamwork, and in-character dilemmas)."""
            coaching_json_desc = f"Roleplay & Fellowship Reflection for {char_name} ({char_desc}) WITHOUT min/maxing or combat optimization, divided into 4 areas: 1) Character Consistency & Development, 2) Creativity & Rules vs. Environment, 3) Group Dynamics & Teamwork, 4) Next Session Dilemmas."
        else:
            coaching_instructions = f"""2. Atribuye con precisión cada acción, hechizo, tirada y decisión a los personajes y jugadores del Roster. Presta atención especial a {char_name} ({char_desc}) para su "Reflexión de Rol y Compañerismo: {char_name}". IMPORTANTE: PROHIBIDO EL MIN/MAXING O COACHING ROBÓTICO (cero lecciones sobre maximizar daño por turno o economía matemática de acciones; el foco es narrativa, carácter de personaje, apoyo a compañeros y dilemas in-character)."""
            coaching_json_desc = f"Reflexión de Rol y Compañerismo para {char_name} ({char_desc}) SIN min/maxing ni optimización robótica de combate, dividida en 4 áreas: 1) Coherencia y Desarrollo de Personaje (fidelidad a personalidad/trasfondo, decisiones narrativas potentes y oportunidades de voz desaprovechadas), 2) Creatividad y Uso del Entorno vs. Reglas (análisis constructivo si flexionó RAW en favor de la narrativa cinematográfica vs regla formal estricta, y advertencias amables sobre peligros pasados por alto), 3) Dinámica de Grupo y Trabajo en Equipo (apoyo a sus compañeros de party, permitiéndoles brillar y protegiendo vulnerabilidades), 4) Dilemas para la Siguiente Sesión (1 o 2 preguntas reflexivas in-character sobre su visión del mundo, lealtades o relaciones)."
    else:
        if is_english:
            coaching_instructions = """2. Accurately attribute every action, spell, roll, and decision to the characters and players in the Roster. STRICT DIRECTIVE: There is no designated user character for personal reflection in this session (or this is an external YouTube video). Leave 'user_coaching' (and 'markus_coaching') strictly as an empty string ""."""
            coaching_json_desc = ""
        else:
            coaching_instructions = """2. Atribuye con precisión cada acción, hechizo, tirada y decisión a los personajes y jugadores del Roster. DIRECTIVA ESTRICTA: No hay un personaje del usuario designado para reflexión personal en esta sesión (o es un video externo de YouTube). Deja el campo 'user_coaching' (y 'markus_coaching') estrictamente como cadena vacía ""."""
            coaching_json_desc = ""

    if is_english:
        lang_banner = """⚠️ CRITICAL LANGUAGE DIRECTIVE (100% ENGLISH MANDATORY):
Generate all content (Executive Briefing, Detailed Notes, Action Items, Key Points, Chronicle) strictly in English (e.g., English if 'en', Spanish if 'es'). Match the language requested by the user.
- Target language is ENGLISH.
- 100% of all generated JSON text values ('title', 'chronicle_text', 'closing_expectations', 'episode_synopsis', 'updated_quests', 'subobjectives', 'rol_en_sesion', 'notes', 'clase', 'especie') MUST be written in natural, fluent English.
- STRICTLY FORBIDDEN to leave text in any other language.
- When outputting mathematical or probabilistic formulas involving money, escape currency dollar signs inside math blocks (e.g., use '\\$1,000' or write 'USD 1,000') so they do not collide with LaTeX delimiters. Ensure equations are cleanly structured for KaTeX rendering."""
        json_quotes_rule = """⚠️ CRITICAL JSON SYNTAX RULE (STRICTLY NO DOUBLE QUOTES INSIDE STRINGS):
- NEVER use raw double quotes (") inside JSON string values (for nicknames, character aliases, titles, or dialogue quotes).
- STRICTLY USE single quotes (') for any nicknames, titles, or dialogue quotes (e.g. 'Hal', 'Wiki', 'The Undying', 'He shouted: Attack!').
- Raw double quotes inside string values corrupt JSON parsing and will crash the application."""
        scene_instructions = """⚠️ MANDATORY DIRECTIVE: DEEP CHRONOLOGICAL SCENE BREAKDOWN (NO OVER-SUMMARIZATION):
- STRICTLY FORBIDDEN to write a generic 3-paragraph summary for the session. This represents hours of roleplay gameplay.
- Structure 'chronicle_text' into detailed chronological ACTS AND SCENES (e.g. '### Act I: Scene 1: ...', '### Scene 2: ...', '### Act II: Scene 3: ...').
- Dedicate 2 to 3 comprehensive, rich paragraphs per major scene:
  * Specific verbal dialogues and quotes between characters, NPCs, and DM.
  * Strategic discussions and party plans debated prior to action.
  * Skill checks and dice rolls (Athletics, Perception, Stealth, saving throws, natural 20s, natural 1s).
  * Tactical combat maneuvers described step-by-step (specific spells cast, positioning, environmental usage, damage taken), NOT just the final outcome.
- ⚠️ STRICT GROUNDING & ZERO TACTICAL HALLUCINATIONS:
  * FORBIDDEN to invent grid distances or precise foot movements not verbalized in the audio (e.g. NEVER invent 'retreated 25 feet' or 'moved 15 feet to the left').
  * FORBIDDEN to invent phantom terrain or structures not described by the DM (e.g. phantom shacks, huts, pits).
  * Ground all scene descriptions, spells, checks, and interactions strictly in the verbal transcript.
- ⚠️ STRICT PHYSICAL CAUSALITY & BAN ON PASSIVE/LAZY TRANSITION SUMMARIES:
  * STRICTLY FORBIDDEN to use passive abstractions or lazy transition summaries (e.g. NEVER write 'the party was transported', 'a trap absorbed them', 'they ended up at', or 'they suddenly appeared').
  * You MUST document the EXPLICIT PHYSICAL CAUSALITY spoken in the transcript: detail who or what executed the physical trigger (who pulled a lever, who pushed, who triggered the mechanism, who ambushed from behind, or what creature/entity intervened).
  * AUTOMATIC MYSTERY EXTRACTION: If a physical action, ambush, trap, or intervention is caused by an unseen, unidentified, masked, or concealed entity whose identity was not revealed in the audio, you MUST register it as an entry in 'updated_quests' with 'tipo': 'misterios_abiertos' (e.g. 'Investigate the identity of the unknown entity that intervened/attacked during [Scene]').
- ⚠️ MANDATORY FULL COVERAGE OF ALL COMBATS & ENCOUNTERS:
  * If multiple major combats occurred (e.g. a Troll fight AND a Dragon fight), EACH MUST be chronicled in distinct chronological scenes. DO NOT merge, omit, or skip major battles.
- ⚠️ REGISTER COMPANIONS & CHARACTER SWAPS:
  * Capture party animal companions, familiars, or mascots (e.g. Minipeko) and character switches/retirements."""
        chronicle_json_desc = "Deep chronicle strictly organized into chronological Acts and Scenes (e.g. '### Act I: Scene 1: ...', '### Scene 2: ...'). Dedicate 2-3 detailed paragraphs per scene with verbatim dialogue quotes, player strategic discussions, explicit dice rolls (Athletics, Perception, nat 20s, nat 1s), and step-by-step tactical combat maneuvers (spells, maneuvers, damage taken). STRICTLY FORBIDDEN to compress into a generic 3-paragraph summary."
    else:
        lang_banner = """⚠️ DIRECTIVA CRÍTICA DE IDIOMA Y JERGA NATURAL DE D&D:
Generate all content (Executive Briefing, Detailed Notes, Action Items, Key Points, Chronicle) strictly in Spanish (e.g., English if 'en', Spanish if 'es'). Match the language requested by the user.
- Redacta la crónica, la narrativa, las misiones y las notas en ESPAÑOL FLUIDO Y NATURAL.
- NO fuerces traducciones artificiales u ortopédicas de la terminología oficial de D&D.
- PRESERVA INTACTOS los términos oficiales de D&D, nombres de conjuros, clases, dotes, maniobras, habilidades, tiradas de salvación y mecánicas en inglés o spanglish tal como se hablan en la mesa de juego (ej. Action Surge, Sneak Attack, Divine Smite, Battle Master, Insight check, Death saving throw, Saving throw, Short rest, Long rest, nat 20, nat 1).
- Usa títulos y encabezados de actos y escenas en español (ej. 'Acto I: Escena 1: El Camino del Bosque', 'Acto II: Escena 2: Emboscada').
- Todos los textos explicativos, descripciones de contexto y diálogos deben fluir con naturalidad en español.
- Al generar fórmulas matemáticas o probabilísticas que involucren cantidades monetarias, escapa los signos de dólar dentro de los bloques matemáticos (ej. usa '\\$1,000' o escribe 'USD 1,000') para que no colisionen con los delimitadores de LaTeX.
- Queda estrictamente PROHIBIDO generar diagramas frágiles en texto ASCII (cajas compuestas por '+---+' o '|'). Para representar comparaciones, flujos de trabajo, matrices de decisión o transiciones de estado, utiliza SIEMPRE tablas nativas en Markdown o listas estructuradas paso a paso."""
        json_quotes_rule = """⚠️ REGLA CRÍTICA DE SINTAXIS JSON (PROHIBIDO EL USO DE COMILLAS DOBLES DENTRO DE STRINGS):
- NUNCA uses comillas dobles (") dentro de los valores de texto del JSON (por ejemplo para apodos, alias, títulos, nombres entre comillas o citas textuales de diálogos).
- Usa OBLIGATORIAMENTE comillas simples (') para cualquier apodo, alias, título o diálogo textual (ejemplo: 'Hal', 'Wiki', 'Escudo de Roble', 'Dijo: Adelante').
- Las comillas dobles (") se reservan EXCLUSIVAMENTE para delimitar las claves y los valores del objeto JSON. El uso de comillas dobles sin escapar dentro de un string corrompe el JSON y rompe el sistema."""
        scene_instructions = """⚠️ DIRECTIVA OBLIGATORIA: CRÓNICA PROFUNDA POR ACTOS Y ESCENAS CRONOLÓGICAS (PROHIBIDO EL RESUMEN SUPERFICIAL):
- PROHIBIDO TERMINANTEMENTE resumir toda la sesión en 3 o 4 párrafos genéricos. Esta sesión representa horas de partida real de rol.
- Estructura OBLIGATORIAMENTE 'chronicle_text' en ACTOS Y ESCENAS cronológicas detalladas (ej. '### Acto I: Escena 1: El Camino del Bosque', '### Escena 2: Negociación en la Posada', '### Acto II: Escena 3: Emboscada').
- Dedica entre 2 y 3 PÁRRAFOS COMPLETOS Y EXTENSOS a cada escena principal o combate:
  * Diálogos verbales y citas directas: cita frases, discusiones o intercambios emocionales entre personajes, PNJs o el DM.
  * Planes y debates estratégicos: describe las discusiones tácticas y dilemas que la mesa debatió antes de actuar.
  * Pruebas de habilidad y dados: menciona explícitamente tiradas destacadas (pruebas de Atletismo, Percepción, Sigilo, Engaño, salvaciones, críticos '20 natural' y pifias '1 natural').
  * Combates y maniobras turno a turno: describe la coreografía táctica detallada (conjuros específicos lanzados, posiciones, uso del entorno, daño recibido), NO solo el desenlace.
- ⚠️ GROUNDING ESTRICTO Y CERO ALUCINACIONES TÁCTICAS:
  * PROHIBIDO inventar movimientos de cuadrícula o distancias precisas no verbalizadas en el audio (ej. NUNCA inventar 'se replegó 25 pies', 'se colocó a 15 pies').
  * PROHIBIDO inventar elementos topográficos, estructuras o terreno fantasma (ej. chozas, cabañas o fosos no descritos por el DM).
  * La crónica debe ceñirse al 100% a lo efectivamente verbalizado por los jugadores y el DM.
- ⚠️ CAUSALIDAD FÍSICA ESTRICTA Y PROHIBICIÓN DE RESÚMENES PASIVOS/PEREZOSOS:
  * PROHIBIDO TERMINANTEMENTE usar abstracciones pasivas o resúmenes perezosos de transición (ej. NUNCA escribas "el grupo fue transportado", "una trampa los absorbió", "terminaron en" o "aparecieron de repente").
  * Registra OBLIGATORIAMENTE la CAUSALIDAD FÍSICA EXPLÍCITA verbalizada en la transcripción: detalla quién o qué ejecutó el detonante físico (quién tiró de una palanca, quién empujó, quién activó el mecanismo, quién atacó por la espalda o qué criatura/entidad los emboscó).
  * EXTRACCIÓN AUTOMÁTICA DE MISTERIOS: Si una acción física, trampa, emboscada o intervención es provocada por una entidad oculta, enmascarada, invisible o cuya identidad no fue revelada en el audio, debes registrarla OBLIGATORIAMENTE como una entrada en 'updated_quests' con 'tipo': 'misterios_abiertos' (ej. "Investigar la identidad de la entidad desconocida que intervino/atacó durante [Escena]").
- ⚠️ COBERTURA OBLIGATORIA DE TODOS LOS COMBATES Y ENCUENTROS:
  * Si en la sesión ocurren múltiples combates o encuentros mayores (por ejemplo, combate con un Trol Y combate con un Dragón), AMBOS deben ser narrados exhaustivamente en escenas separadas.
  * PROHIBIDO omitir, fusionar apresuradamente o saltarse combates mayores.
- ⚠️ VOCABULARIO LITERAL DE MESA Y PROHIBICIÓN DE ARCAÍSMOS:
  * PROHIBIDO usar arcaísmos o sinónimos medievales rebuscados (ej. NUNCA uses 'sierpe' para dragón, 'pertrechos' para suministros o equipo, 'yacija', 'mengua').
  * Usa vocabulario directo de la mesa de D&D y spanglish natural: 'dragón', 'trol', 'suministros', 'equipo', 'pociones', 'trampa'.
- ⚠️ REGISTRO DE COMPAÑEROS, MASCOTAS Y RELEVOS DE PERSONAJE:
  * Registra adecuadamente acompañantes, familiares o mascotas de la party (ej. Minipeko) y cambios o relevos de personajes."""
        chronicle_json_desc = "Crónica profunda estructurada OBLIGATORIAMENTE en Actos y Escenas cronológicas (ej. '### Acto I: Escena 1: El Camino del Bosque', '### Escena 2: Negociación en la Posada', '### Acto II: Escena 3: Emboscada'). PROHIBIDO resumir en 3 párrafos. Dedica 2 a 3 párrafos por escena describiendo diálogos textuales entre personajes, debates estratégicos de la mesa, tiradas de dados notables (Percepción, Atletismo, 20s y 1s naturales) y el desarrollo táctico turno a turno de los combates (conjuros, maniobras, daño)."

    lang_rule = "GENERA TODOS LOS CAMPOS DE TEXTO DEL JSON EN INGLÉS (English)." if is_english else "GENERA EN ESPAÑOL NATURAL CON JERGA OFICIAL DE D&D (SPANGILSH DE MESA PERMITIDO)."

    next_session_num = session_number + 1
    if is_youtube:
        if is_english:
            closing_section_desc = (
                '"episode_synopsis": "Crisp, objective executive synopsis of exactly 3 to 4 paragraphs summarizing the major dramatic developments of the episode, key plot revelations, twists, and the final state of characters and factions for viewers and analysts.\\n\\nSTRICT DIRECTIVE: DO NOT generate a read-aloud script for opening the next session for YouTube videos.",\n'
                '    "next_session_script": ""'
            )
        else:
            closing_section_desc = (
                '"episode_synopsis": "Resumen ejecutivo y objetivo de exactamente 3 a 4 párrafos que sintetice los acontecimientos dramáticos más importantes del episodio, revelaciones clave, giros de trama y el estado en el que quedan los personajes y facciones al concluir la sesión para espectadores y analistas.\\n\\nDIRECTIVA ESTRICTA: NO generes guion para leer en voz alta de apertura de siguiente sesión para videos de YouTube.",\n'
                '    "next_session_script": ""'
            )
    else:
        if is_english:
            next_session_script_desc = (
                f"Crisp, fast-paced read-aloud script of exactly 3 to 4 paragraphs to be read at the start of Session #{next_session_num} "
                f"in 45-60 seconds before rolling dice. Tone MUST be casual, conversational FIRST-PERSON PLURAL ('Alright folks, quick recap of where we left off: "
                f"last session we went to... talked to... got ambushed at... and the session cut right when...'), exactly as a player talking to friends over Discord. "
                f"NO epic novel narrator or solemn third-person prose. Ends in immediate cliffhanger for Session #{next_session_num}."
            )
        else:
            next_session_script_desc = (
                f"Guion electrizante de exactamente 3 a 4 párrafos para leer en voz alta al inicio de la Sesión #{next_session_num} "
                f"en 45-60 segundos antes de tirar dados. DIRECTIVA CRÍTICA: PROHIBIDO USAR NARRADOR ÉPICO SOLEMNE DE NOVELA O EN TERCERA PERSONA. "
                f"Voz obligatoria: conversacional, relajada y directa en PRIMERA PERSONA DEL PLURAL ('A ver gente, para acordarnos: la sesión pasada fuimos a... "
                f"hablamos con... nos emboscaron en... y la partida se cortó justo cuando...'), como hablarle a compas por Discord. "
                f"Culmina en el cliffhanger o encrucijada inmediata en la que arranca la Sesión #{next_session_num}."
            )
        closing_section_desc = (
            f'"user_coaching": "{coaching_json_desc}",\n'
            f'    "next_session_script": "{next_session_script_desc}"'
        )

    auto_detect_instruction = (
        """AUTO-DETECTION OF CHARACTERS (EXTERNAL VIDEOS / YOUTUBE / UNKNOWN ROSTER):
If you are analyzing an external video/YouTube and no specific roster was provided for this campaign (or the roster is empty):
- Automatically detect and identify characters and players from their introductions, dialogues, and interactions in the audio.
- Generate the 'detected_pcs' and 'detected_party' blocks with all actual characters from the video (Player/Jugador, Character/Personaje, Class/Clase, Species/Especie, and Session Role/Rol en la Sesión).
- CRITICAL DIRECTIVE: A player who acts as a core protagonist in the narrative (e.g. Liam O'Brien playing Halendiel Fang) is a Player Character (PC). DO NOT omit, discard, or drop them from 'detected_pcs'. Distinguish the true Dungeon Master (who sets DCs, describes monster attacks, and runs the world) from the players. Liam O'Brien is a PLAYER playing the Bard Halendiel Fang.
- Attribute all combat, rolls, dialogue, and decisions strictly to these detected characters.
- STRICT DIRECTIVE: DO NOT include, attribute, or hallucinate Markus Veyl or any outside party members if they do not appear in this session.
- If an explicit roster was already provided for this campaign, follow it faithfully and mirror it in 'detected_pcs'."""
        if is_english
        else """AUTO-DETECCIÓN DE PERSONAJES (VIDEOS EXTERNOS / YOUTUBE / ROSTER NO ESPECIFICADO):
Si estás analizando un video externo/YouTube y no se proporcionó un roster específico para esta campaña (o el roster está vacío o no especificado):
- Detecta e identifica automáticamente a los personajes y jugadores a partir de sus presentaciones y diálogos en el audio.
- Genera los bloques 'detected_pcs' y 'detected_party' con todos los personajes reales del video (Jugador, Personaje, Clase, Especie y Rol en la Sesión).
- DIRECTIVA CRÍTICA: Un jugador que actúe como protagonista clave en la narrativa (ej. Liam O'Brien interpretando a Halendiel Fang) es un Personaje Jugador (PC). PROHIBIDO omitirlos, descartarlos o borrarlos de 'detected_pcs'. Distingue claramente al verdadero Dungeon Master (quien establece dificultades de tiradas/DC, describe ataques de monstruos, narra el entorno y arbitra el mundo) de los jugadores. Liam O'Brien es un JUGADOR que interpreta al bardo Halendiel Fang, NO el Dungeon Master.
- Atribuye todos los combates, tiradas, diálogos y decisiones estrictamente a estos personajes reales detectados.
- DIRECTIVA ESTRICTA: PROHIBIDO incluir, atribuir o alucinar a Markus Veyl ni a ningún personaje ajeno si no aparecen explícitamente en el audio de esta sesión.
- Si ya se proporcionó un roster explícito con personajes de esta campaña, respétalo fielmente y refléjalo en 'detected_pcs'."""
    )

    group_dynamics_instruction = (
        """DINÁMICA DE GRUPO Y CANAL DE AUDIO (DISCORD / MESA):
Cuando los jugadores hablen genéricamente en el audio sin decir sus nombres de personaje, narra las decisiones y acciones como acuerdos colectivos de la compañía ("La compañía acordó...", "El grupo decidió avanzar...") en lugar de inventar o adivinar quién habló individualmente."""
        if not is_english
        else """GROUP DYNAMICS & AUDIO CHANNEL:
When players speak generically on the audio channel without saying character names, narrate actions as collective party decisions ("The company agreed...", "The party decided to advance...") instead of guessing names."""
    )

    quests_instruction = (
        """3. CRITERIOS ESTRICTOS DE EXTRACCIÓN DE MISIONES (TAXONOMÍA DE 4 NIVELES Y DESCOMPOSICIÓN NO MONOLÍTICA):
   - Extrae objetivos claramente delimitados y clasifica cada misión en su campo 'tipo':
     * 'principal': Trama principal o arco central de la campaña (macro-objetivo de largo plazo, amenazas mayores, destino del reino, artefactos clave). Reserva 'principal' EXCLUSIVAMENTE para estos grandes arcos abarcadores.
     * 'secundaria': Encargos importantes de facciones, favores a PNJs o metas que benefician sustancialmente a la compañía con recompensas reales.
     * 'opcional': Tareas totalmente prescindibles (cacerías menores de recompensas, favores tabernarios, apuestas) con cero impacto en la trama si se ignoran.
     * 'misterios_abiertos': Preguntas sin resolver, pistas intrigantes, enigmas o conspiraciones descubiertas por la party en la sesión (incluyendo intervenciones o emboscadas de entidades desconocidas o enmascaradas).
   - ⚠️ DESCOMPOSICIÓN NO MONOLÍTICA DE MISIONES (PROHIBIDO COLAPSAR LA SESIÓN EN UNA SOLA MISIÓN GIGANTE):
     * PROHIBIDO TERMINANTEMENTE agrupar todos los objetivos o acontecimientos de la sesión en una única misión monolítica.
     * OBJETIVOS INMEDIATOS -> MISIONES SECUNDARIAS COMPLETADAS: Si el grupo persiguió un objetivo concreto e inmediato que quedó plenamente resuelto durante la sesión (ej. rastrear a un aliado perdido, efectuar un rescate inmediato, resolver un enigma localizado o despejar un obstáculo puntual):
       - Créalo como una misión independiente con 'tipo': 'secundaria'.
       - Márcala como 'status': 'completed' con 'completed_session': {session_number}.
     * ARCOS PRINCIPALES: Reserva 'tipo': 'principal' estrictamente para el macro-objetivo abarcador de la campaña o arco en curso.
     * NUEVOS OBJETIVOS EMERGENTES: Las metas secundarias que surjan a raíz de las consecuencias de la sesión (ej. regresar a la base o punto de partida, transportar recursos o aliados recién adquiridos, orientarse en territorio desconocido, descifrar un artefacto hallado) deben inicializarse como NUEVAS MISIONES INDEPENDIENTES en progreso ('status': 'in_progress').
   - ⚠️ REGLA DE ORO DE MISIONES: Un paso intermedio dentro de un objetivo mayor (ej. encontrar una llave, forzar una reja, interrogar a un guardia) es SIEMPRE un sub-objetivo ('subobjectives': [{'id': 's1', 'text': '...', 'completed': true/false}]), NUNCA una misión separada.
   - ⚠️ REGLA DE COHERENCIA DE ESTADO Y SUBOBJETIVOS:
     * Si una misión tiene estado 'in_progress', OBLIGATORIAMENTE debes incluir al menos un sub-objetivo pendiente ('completed': false) para la siguiente sesión. NUNCA marques todos los sub-objetivos como 'completed': true si la misión principal sigue en progreso.
     * Si todos los sub-objetivos de una misión se han cumplido con éxito en la sesión, marca la misión principal OBLIGATORIAMENTE como 'completed'.
   - ⚠️ ESTADO EXPLÍCITO DE FRACASO ('status': 'failed'):
     * Si el objetivo principal de una misión se vuelve permanentemente imposible (ej. la persona a rescatar muere, el artefacto a proteger es destruido, o la defensa de la fortaleza fracasa):
       - Marca la misión OBLIGATORIAMENTE con 'status': 'failed' en esa sesión.
       - Establece 'completed_session': {session_number} y documenta en 'lifecycle_notes': 'Iniciada en Sesión X | Fracasada en Sesión {session_number} (Motivo del fallo)'.
   - ⚠️ REGLA ESTRICTA ANTI-MUTACIÓN (PROHIBIDO RECICLAR O MUTAR MISIONES):
     * PROHIBIDO añadir objetivos posteriores o tramas no relacionadas a una misión fallida o completada.
     * Una misión que comenzó como "Rescatar a Thiazi" JAMÁS debe mutar en "Investigar la traición" o "Escapar de la fortaleza".
     * Una vez que una misión alcanza un desenlace definitivo (completada o fallida), queda CERRADA para siempre. Cualquier consecuencia, represalia o nuevo plan de los héroes debe crearse como una NUEVA MISIÓN INDEPENDIENTE con un nuevo id (ej. 'q7').
   - ⚠️ IDs ÚNICOS Y CORRELATIVOS PARA SUBOBJETIVOS:
     * Asegura que todos los subobjetivos tengan IDs estrictamente correlativos y únicos ('s1', 's2', 's3', 's4', 's5', 's6'...). Jamás reutilices IDs existentes ni reinicies la numeración desde 's1' dentro de la misma misión a lo largo de las sesiones."""
        if not is_english
        else """3. STRICT QUEST EXTRACTION CRITERIA (4-TIER TAXONOMY & NON-MONOLITHIC DECOMPOSITION):
   - Extract clearly bounded objectives and classify each quest under 'tipo':
     * 'principal': Overarching campaign/arc macro-objective (major long-term threats, fate of the realm, key artifacts). Reserve 'principal' EXCLUSIVELY for these overarching macro-arcs.
     * 'secundaria': Important faction contracts, NPC favors, or goals with real consequences and rewards.
     * 'opcional': Completely dispensable tasks (bounties, small favors, tavern bets); zero plot impact if ignored.
     * 'misterios_abiertos': Unsolved questions, mysterious clues, or conspiracies discovered by the party (including interventions or ambushes by unknown or masked entities).
   - ⚠️ NON-MONOLITHIC QUEST DECOMPOSITION (NEVER COLLAPSE SESSION INTO ONE GIANT QUEST):
     * STRICTLY FORBIDDEN to bundle all session goals or events into a single monolithic quest.
     * IMMEDIATE OBJECTIVES -> COMPLETED SIDE QUESTS: If the party pursued a concrete, immediate objective that was fully resolved during the session (e.g. tracking a lost ally, securing an immediate rescue, solving a localized puzzle, or clearing a specific barrier):
       - Create it as a distinct 'tipo': 'secundaria' quest.
       - Mark it as 'status': 'completed' with 'completed_session': {session_number}.
     * MAIN ARCS: Reserve 'tipo': 'principal' strictly for the overarching macro-objective of the campaign or arc.
     * NEW EMERGENT OBJECTIVES: Secondary goals emerging from the session's aftermath (e.g. returning to base, transporting newly acquired resources or allies, navigating unfamiliar territory, decoding a retrieved relic) MUST be initialized as brand new, independent quests in progress ('status': 'in_progress').
   - ⚠️ GOLDEN RULE OF QUESTS: An intermediate step within a larger objective (e.g. finding a key, forcing a grate, questioning a guard) is ALWAYS a sub-objective ('subobjectives': [{'id': 's1', 'text': '...', 'completed': true/false}]), NEVER a separate quest.
   - ⚠️ QUEST STATUS & SUBOBJECTIVE CONSISTENCY RULE:
     * If a quest has status 'in_progress', you are OBLIGATED to include at least one pending sub-objective ('completed': false) for the next session. NEVER mark all sub-objectives as 'completed': true while leaving the quest in progress.
     * If all sub-objectives of a quest were fulfilled in the session, you MUST mark the quest status as 'completed'.
   - ⚠️ EXPLICIT FAILURE STATE ('status': 'failed'):
     * If a quest's primary objective becomes permanently impossible (e.g. the person to rescue dies, the protected artifact is destroyed, or defense fails):
       - You MUST immediately mark the quest as 'status': 'failed' in that session.
       - Set 'completed_session': {session_number} and record in 'lifecycle_notes': 'Iniciada en Sesión X | Fracasada en Sesión {session_number} (Failure reason)'.
   - ⚠️ STRICT ANTI-MUTATION RULE (NEVER RECYCLE OR MUTATE CLOSED QUESTS):
     * DO NOT append unrelated subsequent objectives to a failed or completed quest.
     * A quest that started as "Rescue Thiazi" MUST NEVER mutate into "Investigate the betrayal" or "Escape the fortress".
     * Once a quest reaches a definitive outcome (either completed or failed), it is CLOSED forever. Any subsequent aftermath, vengeance, or new goals MUST be created as a BRAND NEW INDEPENDENT QUEST with a new ID (e.g. 'q7').
   - ⚠️ SEQUENTIAL & UNIQUE SUBOBJECTIVE IDs:
     * Ensure all subobjectives have strictly sequential, unique IDs ('s1', 's2', 's3', 's4', 's5', 's6'...). Never reuse existing IDs or restart numbering from 's1' across sessions."""
    )

    pc_in_character_instruction = (
        """⚠️ REGLA ESTRICTA DE ACCIONES IN-CHARACTER Y EXCLUSIÓN DEL DUNGEON MASTER (DM):
- PRESERVACIÓN OBLIGATORIA DE PERSONAJES JUGADORES (PROHIBIDO DESCARTAR PCs LEGÍTIMOS):
  * Un jugador que actúe como protagonista clave en la narrativa (por ejemplo, Liam O'Brien interpretando al bardo Halendiel Fang) es un **Personaje Jugador (PC)**.
  * PROHIBIDO TERMINANTEMENTE omitir, descartar o excluir a estos jugadores de 'detected_pcs' o 'detected_party'.
  * Distingue con precisión quirúrgica al verdadero Dungeon Master (quien establece las dificultades de tirada/DC, describe los ataques de los monstruos, narra el entorno y arbitra el mundo) de los jugadores. Liam O'Brien es un JUGADOR que interpreta al bardo Halendiel Fang, NO el Dungeon Master.
- REGLA IN-CHARACTER ESTRICTA PARA PCs:
  * Los campos 'rol_en_sesion' e 'hitos_acumulados' de cada personaje (PC) deben describir EXCLUSIVAMENTE acciones ficticias dentro del mundo (in-world / in-character): combates librados, conjuros lanzados, decisiones tácticas, diálogos con PNJs, heridas sufridas o descubrimientos.
  * PROHIBIDO TERMINANTEMENTE escribir roles meta fuera de personaje, moderación de la mesa o acciones de la vida real (NUNCA escribas cosas como 'Actuó como Dungeon Master', 'Controló los PNJs', 'Dirigió la partida' o 'Tiró dados').
- ⚠️ REGLA UNIVERSAL DE TRANSICIÓN Y RELEVO DE PERSONAJES A MITAD DE SESIÓN:
  * Si las conversaciones operativas de la mesa indican que un jugador retira, deja en reserva o sustituye a su personaje e introduce uno nuevo a mitad de la partida:
    - Refleja la salida o retiro del personaje saliente en sus 'hitos_acumulados' y 'rol_en_sesion' (ej. se separó del grupo, marchó por un camino propio o quedó en reserva).
    - Registra el nuevo personaje en 'detected_pcs' / 'detected_party' comenzando desde esta sesión con su debut ('debut_sesion': {session_number}).
    - PROHIBIDO TERMINANTEMENTE atribuir combates, diálogos o acciones posteriores al personaje retirado una vez que el nuevo entra en juego.
- EXCLUSIÓN DEL DUNGEON MASTER (DM):
  * El Dungeon Master (DM) es estrictamente el narrador y árbitro fuera de personaje (out-of-character).
  * El DM NUNCA tiene tarjeta de personaje ni ficha en 'detected_pcs' o 'detected_party'.
  * Un personaje con nombre de fantasía jamás puede tener como clase o rol 'Dungeon Master' o 'DM'."""
        if not is_english
        else """⚠️ STRICT IN-CHARACTER RULE AND HARD DUNGEON MASTER (DM) EXCLUSION:
- MANDATORY PRESERVATION OF PLAYER CHARACTERS (DO NOT DISCARD LEGITIMATE PCs):
  * A player who acts as a core protagonist in the narrative (e.g. Liam O'Brien playing the Bard Halendiel Fang) is a **Player Character (PC)**.
  * ABSOLUTELY FORBIDDEN to omit, discard, or drop legitimate players from 'detected_pcs' or 'detected_party'.
  * Distinguish the true Dungeon Master (who sets DCs, describes monster attacks, adjudicates rules, and runs the world) from the players. Liam O'Brien is a PLAYER playing the Bard Halendiel Fang, NOT the Dungeon Master.
- STRICT IN-CHARACTER RULE FOR PCs:
  * 'rol_en_sesion' and 'hitos_acumulados' of each Player Character (PC) must describe EXCLUSIVELY in-world fictional actions (battles fought, spells cast, tactical decisions, conversations with NPCs, wounds taken, or discoveries).
  * ABSOLUTELY FORBIDDEN to write out-of-game meta roles, tabletop moderation, or real-life actions (NEVER write 'Acted as Dungeon Master', 'Controlled NPCs', 'Chaired session', or 'Rolled dice').
- ⚠️ UNIVERSAL MID-SESSION PLAYER CHARACTER TRANSITIONS:
  * If operational table discussion indicates a player is retiring, benching, or swapping a character and introducing a new one mid-session:
    - Reflect the departure of the former character in their session milestone and role ('hitos_acumulados' / 'rol_en_sesion') (e.g. separated, departed on their own path, or staying in reserve).
    - Register the new character in 'detected_pcs' / 'detected_party' starting from this session with their debut ('debut_sesion': {session_number}).
    - STRICTLY FORBIDDEN to attribute subsequent battles, dialogues, or actions to the retired character once the new character enters play.
- MUTUAL EXCLUSIVITY OF THE DM:
  * The Dungeon Master (DM) is strictly the out-of-character narrator and referee.
  * The DM NEVER has a character card or row in 'detected_pcs' or 'detected_party'.
  * A character with a fictional name can NEVER have the class or role 'Dungeon Master' or 'DM'."""
    )

    npc_instruction = (
        """4. CRITERIOS ESTRICTOS DE EXTRACCIÓN DE PNJs (TAXONOMÍA DE 3 NIVELES Y PERSONAJES SIN NOMBRE):
   - Clasifica CADA personaje no jugador (PNJ) en su campo 'tipo':
     * 'importantes': Villanos principales, patrones, líderes de facción, figuras clave recurrentes de la historia.
     * 'interaccion_contexto': Diálogo directo o interacción directa (interaccion_directa), comercio, combate o testigos presenciales cara a cara con la party.
     * 'mencionados': Personajes referenciados en cartas, rumores, trasfondo o menciones indirectas.
   - ⚠️ REGLA DE PERSONAJES SIN NOMBRE: Si un PNJ no tiene nombre propio pero aportó información útil, pistas o interactuó, regístralo por su rol/descriptor (ej. '[Sin nombre] Guardia de la puerta norte', '[Sin nombre] Posadero enano') registrando su pista o contribución específica en 'notes'.
   - REGLA TAXATIVA: PROHIBIDO omitir PNJs con nombre propio. Identifícalos a todos exhaustivamente.
   - Documenta pistas clave, secretos o revelaciones en el array de 'notes'."""
        if not is_english
        else """4. STRICT NPC EXTRACTION CRITERIA (3-TIER TAXONOMY & UNNAMED CHARACTERS):
   - Classify EVERY non-player character (NPC) under 'tipo':
     * 'importantes': Main villains, patrons, faction leaders, key recurring figures.
     * 'interaccion_contexto': Direct dialogue, direct interaction (interaccion_directa), trade, combat, or eyewitnesses face-to-face with the party.
     * 'mencionados': Characters referenced in letters, rumors, background lore, or mentioned indirectly.
   - ⚠️ UNNAMED CHARACTERS RULE: If an NPC lacks a proper name but provided useful information or clues, register them by their role/descriptor (e.g. '[Sin nombre] Guardia de la puerta norte') with their specific clue or contribution in 'notes'.
   - STRICT DIRECTIVE: DO NOT skip named characters. Identify all of them exhaustively.
   - Document key clues, secrets, or revelations in the 'notes' array."""
    )

    table_talk_filter_instruction = (
        """1. CRITERIO DE FILTRADO DE AUDIO: CHARLA OPERATIVA DE MESA VS. RUIDO DE LA VIDA REAL:
   - CHARLA OPERATIVA DE MESA (PRESERVAR OBLIGATORIAMENTE): Conversaciones y acuerdos de los jugadores que impactan directamente el estado de juego y la ficción compartida:
     * Cambios, relevos o retiros de personaje (ej. si un jugador retira a un héroe y presenta a otro nuevo).
     * Explicaciones operativas del DM sobre el entorno, mecanismos, acertijos o trampas (ej. sarcófagos o ataúdes de teletransporte, interruptores secretos).
     * Acuerdos tácticos y debates de la party sobre rutas, exploración, planes de combate o descansos.
     * Incorporación y acciones de compañeros, mascotas, familiares o aliados (ej. Minipeko).
   - RUIDO DE LA VIDA REAL (DESCARTAR ESTRICTAMENTE):
     * Pausas para ir al baño, comida, pedidos de pizza, charlas cotidianas de la vida real.
     * Glitches de Discord, problemas de micrófono o conexión, preguntas técnicas ('¿me escuchas?'), mascotas reales ladrando.
     * Bromas y comentarios 100% desconectados de la partida que no afecten a los personajes."""
        if not is_english
        else """1. AUDIO FILTERING CRITERIA: OPERATIVE TABLE TALK VS. REAL-WORLD NOISE:
   - OPERATIVE TABLE TALK (MANDATORY TO PRESERVE): Player discussions and agreements that alter game state or shared fiction:
     * Character swaps, substitutions, and retirements agreed upon by players (e.g. retiring a character and introducing a replacement).
     * DM operational explanations of environment, mechanisms, traps, and puzzles (e.g. teleportation coffins/sarcophagi, secret switches).
     * Party tactical debates, marching order, route choices, and long/short rest agreements.
     * Introduction and presence of animal companions, familiars, or mascots (e.g. Minipeko).
   - REAL-WORLD CHATTER (STRICTLY DISCARDED):
     * Breaks for food/drinks, pizza deliveries, out-of-game chores.
     * Discord/mic audio glitches, connectivity checks ('can you hear me?'), real-life barking pets.
     * Out-of-game jokes and unrelated conversation having zero bearing on the adventure."""
    )

    creative_title_instruction = (
        """⚠️ DIRECTIVA DE TÍTULO CREATIVO DE SESIÓN:
Genera un título creativo, épico o divertido para la sesión basado en los eventos clave (ej. 'Cucharas, runas y sangre en las alturas'). Devuélvelo en el campo JSON 'session_title' y dentro de 'session_chapter.title'."""
        if not is_english
        else """⚠️ CREATIVE SESSION TITLE DIRECTIVE:
Generate a creative, epic, or fun title for the session based on key events (e.g. 'Spoons, runes, and blood at high altitudes'). Return it in the JSON field 'session_title' and inside 'session_chapter.title'."""
    )

    return f"""ROSTER DE LA MESA (D&D 5e / 5.5e):
{roster_formatted}

NÚMERO DE SESIÓN ACTUAL: Sesión #{session_number}
IDIOMA DE SALIDA: {lang_rule}

{lang_banner}

{json_quotes_rule}

MISIONES EXISTENTES DE LA CAMPAÑA:
{quests_formatted}

DIRECTORIO DE PNJS CONOCIDOS DE LA CAMPAÑA:
{npcs_formatted}
{recap_guidance}{prior_lore_block}
{auto_detect_instruction}
{group_dynamics_instruction}

INSTRUCCIONES DE ANÁLISIS:
{lang_banner}

{json_quotes_rule}

{creative_title_instruction}
{scene_instructions}
{table_talk_filter_instruction}
{coaching_instructions}
{pc_in_character_instruction}
{quests_instruction}
{npc_instruction}
5. Devuelve la respuesta OBLIGATORIAMENTE como un objeto JSON válido con la siguiente estructura exacta (sin texto introductorio, solo el JSON puro o dentro de un bloque ```json):

{{
  "session_title": "Título creativo, épico o divertido para la sesión basado en los eventos clave (ej. 'Cucharas, runas y sangre en las alturas')",
  "session_chapter": {{
    "title": "Título creativo, épico o divertido para la sesión basado en los eventos clave",
    "session_title": "Título creativo, épico o divertido para la sesión basado en los eventos clave",
    "chronicle_text": "{chronicle_json_desc}",
    "closing_expectations": "Momentos culminantes de la sesión, botín u oro obtenido, y los planes inmediatos o expectativas de los jugadores para la próxima partida.",
    {closing_section_desc}
  }},
  "detected_pcs": [
    {{
      "jugador": "Nombre del jugador (o '-' si se desconoce)",
      "personaje": "Nombre del personaje",
      "especie": "Especie / Raza (ej. Elfo, Humano, etc.)",
      "clase": "Clase (ej. Paladín, Pícaro, Mago, Guerrero, etc. - NUNCA 'Dungeon Master')",
      "subclase": "Subclase (o '-' si aún no se menciona)",
      "debut_sesion": {session_number},
      "hitos_acumulados": ["Sesión #{session_number}: Logro o acción ficticia in-world principal"],
      "rol_en_sesion": "Resumen de exactamente 1 oración sobre sus acciones ficticias in-character, decisiones o logros dentro del mundo en este episodio."
    }}
  ],
  "detected_party": [
    {{
      "player_name": "Nombre del jugador (o '-' si se desconoce)",
      "character_name": "Nombre del personaje",
      "species": "Especie / Raza (ej. Elfo, Humano, etc.)",
      "role": "Clase (ej. Paladín, Pícaro, Mago, Guerrero, etc. - NUNCA 'Dungeon Master')",
      "subclass": "Subclase (o '-' si no se menciona)",
      "session_role": "Resumen de 1 oración sobre sus acciones ficticias in-character en la sesión"
    }}
  ],
  "updated_quests": [
    {{
      "id": "q1",
      "title": "Título claro y delimitado de la misión",
      "tipo": "principal",
      "context": "Breve contexto del objetivo y por qué la party lo realiza",
      "status": "in_progress",
      "completed_session": null,
      "lifecycle_notes": "Iniciada en Sesión #{session_number}",
      "subobjectives": [
        {{"id": "s1", "text": "Objetivo o paso concreto 1", "completed": true}},
        {{"id": "s2", "text": "Objetivo o paso concreto 2", "completed": false}}
      ]
    }}
  ],
  "updated_npcs": [
    {{
      "name": "Nombre exacto o descriptor del PNJ (ej. 'Eldrin', '[Sin nombre] Guardia de la puerta norte')",
      "role": "Ocupación o rol en la historia (ej. 'Mago de la Torre', 'Noble conspirador [Mencionado en la historia]')",
      "tipo": "interaccion_contexto",
      "notes": ["Sesión #{session_number}: Notas concretas de interacción, actitud y pistas clave aportadas"]
    }}
  ],
  "detected_npc_names": ["Lista", "De", "Nombres", "De", "PNJs", "Nuevos"]
}}

---
{lang_banner}

{json_quotes_rule}

TRANSCRIPCIÓN COMPLETA DEL AUDIO DE LA SESIÓN #{session_number}:
{transcript_text}
"""


# -----------------------------------------------------------------
# University Lecture / Academic Study Guide Prompt
# -----------------------------------------------------------------


def build_academic_lecture_prompt(
    subject: str,
    topic: str,
    transcript_text: str,
    date_str: Optional[str] = None,
    target_language: str = "es",
) -> str:
    """
    Build a prompt for university lecture transcription, creating an Academic Study Guide:
    1. Resumen de la Clase: Síntesis del objetivo pedagógico de la sesión.
    2. Conceptos Teóricos Fundamentales: Glosario y explicaciones claras.
    3. Fórmulas, Ecuaciones y Procedimientos: Fórmulas matemáticas mencionadas y su aplicación.
    4. Ejemplos Resueltos en Clase: Casos de estudio y ejercicios guiados por el profesor.
    5. Avisos Relevantes y Fechas Clave: Tareas encargadas, lecturas obligatorias o fechas de exámenes anunciadas.
    6. Guía de Estudio Rápida: 3 a 5 preguntas de repaso para preparar el examen.
    """
    is_english = str(target_language).lower().startswith("en")
    subj = subject.strip() if subject and subject.strip() else ("Academic Course" if is_english else "Materia Universitaria")
    top = topic.strip() if topic and topic.strip() else ("Lecture Topic" if is_english else "Tema de Clase")
    date_line = f"DATE: {date_str}\n" if (date_str and is_english) else (f"FECHA: {date_str}\n" if date_str else "")

    lang_name = "English" if is_english else "Spanish"

    if is_english:
        return f"""COURSE / SUBJECT: {subj}
LECTURE / MEETING TOPIC: {top}
{date_line}
GENERAL INSTRUCTIONS:
You are an expert academic and technical intelligence assistant for university lectures, conferences, and executive meetings.
Analyze the following transcript recorded via microphone.
Filter background noise, coughs, audio pauses, or irrelevant off-topic side comments.
Organize and synthesize the speaker's presentation into a rigorous, deeply explanatory, and structured Markdown document IN ENGLISH.

================================================================================
CRITICAL LANGUAGE ENFORCEMENT DIRECTIVE:
Generate all content (Executive Briefing, Detailed Notes, Action Items, Key Points) strictly in English (e.g., English if 'en', Spanish if 'es'). Match the language requested by the user.
100% of all headings, narrative notes, terms, action items, and review questions MUST be written in English.
================================================================================
CRITICAL MATHEMATICAL & FORMULA FORMATTING DIRECTIVE:
When outputting mathematical or probabilistic formulas involving money, escape currency dollar signs inside math blocks (e.g., use '\\$1,000' or write 'USD 1,000') so they do not collide with LaTeX delimiters. Ensure equations are cleanly structured for KaTeX rendering.
================================================================================
CRITICAL DIAGRAMMING & TABLE DIRECTIVE:
Do NOT generate fragile ASCII text diagrams (boxes made of '+---+' or '|'). To represent comparisons, workflows, decision matrices, or state transitions, ALWAYS use native Markdown tables or structured step-by-step lists.
================================================================================
CRITICAL EXPLANATORY DIRECTIVE (WORK & STUDY):
Do NOT output lazy, shallow summaries or disconnected bullet points. Write a comprehensive, deeply explanatory narrative breakdown of the talk/lecture.
1. Introduction & Context: Outline the speaker's main thesis, context, and core argument.
2. Thematic Walkthrough: Explain each topic covered in logical progression. You MUST retain and fully explain all real-world examples, case studies, technical analogies, and edge cases shared by the speaker.
3. Key Takeaways & Data Points (At the end only): Reserve concise bullet points strictly for the final section: specific dates, metrics, tools mentioned, action items, and concluding answers.
================================================================================

Structure the guide into the following 6 sections:

# 🎓 EXECUTIVE BRIEFING & DEEP STUDY GUIDE: {subj}
## 📌 Topic: {top}

---

# 1. Introduction & Context
- Comprehensive narrative outlining the speaker's main thesis, background context, core problem being addressed, and primary thesis.

# 2. Fundamental Theoretical Concepts & Terminology
- Deep explanatory glossary, technical definitions, mathematical foundations, and thorough conceptual explanations taught by the speaker.

# 3. Thematic Walkthrough & Deep Explanations
- Detailed walkthrough of each topic in logical progression.
- Retain and fully explain every real-world example, case study, technical analogy, equation, physical law, or algorithm shared.
- Explicitly document edge cases, limitations, and nuances emphasized by the speaker.

# 4. Solved Examples & Practical Applications
- Detailed breakdown of practical exercises, case studies, code patterns, or real-world dilemmas discussed, including problem statement, methodology, steps, and resolution.

# 5. Announcements, Deadlines & Next Steps (STRICTLY CONDITIONAL)
- Deadlines & Action Items Section: Include this section ONLY IF concrete homework assignments, project deadlines, or explicit organizational announcements were stated in the audio. If NO actionable tasks or deadlines exist (e.g. YouTube educational videos, general keynotes), OMIT this section entirely. Do NOT output placeholder text such as 'No assignments were mentioned'.

# 6. Key Takeaways, Metrics & Action Items
- Reserve concise bullet points strictly for this final section:
  * Key numerical metrics, benchmarks, and quantitative data points.
  * Tools, libraries, and frameworks mentioned.
  * Direct action items and concluding answers.
  * 3 to 5 key conceptual review questions for exam or meeting retention.

---

LECTURE / MEETING TRANSCRIPT:
{transcript_text}
"""

    return f"""MATERIA / ASIGNATURA: {subj}
TEMA DE LA CLASE / REUNIÓN: {top}
{date_line}
INSTRUCCIONES GENERALES:
Eres un asistente pedagógico y de inteligencia técnica de alto nivel para clases universitarias, conferencias y reuniones ejecutivas.
Analiza la siguiente transcripción grabada mediante micrófono.
Filtra ruidos de fondo, carraspeos, pausas de audio o comentarios irrelevantes fuera de tema.
Organiza y sintetiza el contenido impartido en una Guía de Estudio y Síntesis Ejecutiva rigurosa, profunda y estructurada en Markdown en español.

================================================================================
DIRECTIVA CRÍTICA DE IDIOMA OBLIGATORIO:
Generate all content (Executive Briefing, Detailed Notes, Action Items, Key Points) strictly in Spanish (e.g., English if 'en', Spanish if 'es'). Match the language requested by the user.
El 100% de los encabezados, textos narrativos, glosarios, tareas y preguntas DEBEN generarse estrictamente en español.
================================================================================
DIRECTIVA CRÍTICA DE FORMATEO MATEMÁTICO Y FÓRMULAS:
When outputting mathematical or probabilistic formulas involving money, escape currency dollar signs inside math blocks (e.g., use '\\$1,000' or write 'USD 1,000') so they do not collide with LaTeX delimiters. Ensure equations are cleanly structured for KaTeX rendering.
================================================================================
DIRECTIVA CRÍTICA DE DIAGRAMAS Y TABLAS:
Queda estrictamente PROHIBIDO generar diagramas frágiles en texto ASCII (cajas compuestas por '+---+' o '|'). Para representar comparaciones, flujos de trabajo, matrices de decisión o transiciones de estado, utiliza SIEMPRE tablas nativas en Markdown (| Columna 1 | Columna 2 |) o listas estructuradas paso a paso.
================================================================================
DIRECTIVA CRÍTICA DE PROFUNDIDAD EXPLICATIVA (WORK & STUDY):
NO generes resúmenes superficiales, perezosos ni listas de viñetas desconectadas. Escribe un desglose narrativo exhaustivo, profundo y detallado de la exposición/clase/reunión.
1. Introducción y Contexto: Sintetiza la tesis central del expositor, el contexto de fondo y su argumento rector.
2. Recorrido Temático Detallado: Explica cada tema tratado en rigurosa progresión lógica. DEBES conservar y explicar a fondo todos los ejemplos del mundo real, casos de estudio, analogías técnicas y casos extremos (edge cases) mencionados por el expositor.
3. Conclusiones Clave, Datos y Acciones (Exclusivamente al final): Reserva las viñetas concisas ÚNICAMENTE para la sección final: fechas exactas, métricas, herramientas mencionadas, tareas/acuerdos pendientes y respuestas de cierre.
================================================================================

Estructura obligatoriamente la respuesta en las siguientes 6 secciones:

# 🎓 BRIEFING EJECUTIVO Y GUÍA DE ESTUDIO PROFUNDA: {subj}
## 📌 Tema: {top}

---

# 1. Introducción y Contexto
- Desglose narrativo profundo que sintetiza la tesis central del expositor, el contexto de fondo, la problemática analizada y los objetivos pedagógicos o estratégicos.

# 2. Conceptos Teóricos Fundamentales y Terminología
- Glosario riguroso, definiciones técnicas precisas, formulaciones y explicaciones teóricas detalladas de los conceptos abordados.

# 3. Recorrido Temático Detallado y Explicaciones Profundas
- Explicación estructurada de cada tema en progresión lógica.
- Conserva y explica a fondo todos los ejemplos reales, casos de estudio, analogías técnicas, leyes, algoritmos o métodos paso a paso presentados.
- Documenta detalladamente los casos extremos (edge cases), limitaciones y advertencias enfatizadas por el expositor.

# 4. Ejemplos Resueltos y Casos Prácticos
- Desglose exhaustivo de los problemas prácticos, ejercicios o casos de negocio discutidos durante la sesión, detallando su planteamiento, desarrollo analítico y conclusión.

# 5. Avisos Relevantes, Tareas y Próximos Pasos (ESTRICTAMENTE CONDICIONAL)
- Sección de Avisos, Tareas y Próximos Pasos: Incluye esta sección ÚNICAMENTE SI en el audio se mencionaron explícitamente tareas concretas, fechas de examen, entregas de proyectos o avisos organizativos formales. Si NO existen tareas ni fechas límite accionables (por ejemplo, videos educativos de YouTube, charlas magistrales o ponencias generales), OMITE esta sección por completo. Queda estrictamente PROHIBIDO emitir texto de relleno como 'No se anunciaron exámenes ni tareas pendientes'.

# 6. Conclusiones Clave, Métricas y Acciones
- Reserva las viñetas concisas EXCLUSIVAMENTE para esta sección de cierre:
  * Métricas numéricas clave, benchmarks y datos cuantitativos específicos.
  * Herramientas, software, librerías o normativas citadas.
  * Tareas y acuerdos de acción concretos.
  * 3 a 5 preguntas de repaso conceptual o práctico para autoevaluación o preparación de exámenes.

---

TRANSCRIPCIÓN DE LA CLASE / REUNIÓN:
{transcript_text}
"""
