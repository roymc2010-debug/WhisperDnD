"""Prompt definitions and builders for Gemini TTRPG Summarizer."""

from typing import Any, Dict, List, Optional


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
    character_backstory: Optional[str] = None,
    last_session_recap: Optional[str] = None,
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
        if is_english:
            recap_guidance = f"""
CRITICAL CONTINUITY & RECAP DIRECTIVE (SESSION #{session_number}):
1. RECAP VS. TODAY'S ACTIONS SEPARATION: The recorded session may begin with players or DM recapping prior sessions. Acknowledge that initial recap purely as background context; DO NOT duplicate past events in the chronicle or active quests of session #{session_number}. The chronicle and quests must focus strictly on new events that occurred during session #{session_number}.
2. CONTEXTUAL LORE & MORAL INTENT (NEVER JUDGE ACTIONS BLINDLY OUT OF CONTEXT):
   - Ground all character actions in their declared intent and accumulated campaign lore.
   - For example: if the party exhumes a grave, opens a coffin, or recovers a corpse/relic to bury someone with dignity, return a sacred medallion, or lay a spirit to rest, DO NOT blindly judge this as malicious 'grave defilement'. Always evaluate actions against the party's actual quest goals and lore discoveries (e.g. returning relics, burying the baroness, or uncovering demons).
"""
        else:
            recap_guidance = f"""
REGLA CRUCIAL DE CONTINUIDAD Y RECAP (SESIÓN #{session_number}):
1. SEPARACIÓN ESTRICTA DE RECAP VS. SESIÓN DE HOY: La sesión grabada puede comenzar con los jugadores o el DM recordando o resumiendo sesiones anteriores. Reconoce ese resumen inicial ÚNICAMENTE como contexto previo; NO dupliques eventos pasados en la crónica ni en las misiones de esta sesión #{session_number}. La crónica y las misiones deben enfocarse exclusivamente en los hechos nuevos que ocurrieron en esta sesión #{session_number}.
2. CONTEXTO MORAL Y DE LORE (NO JUZGAR ACCIONES FUERA DE CONTEXTO):
   - Evalúa siempre las acciones de los personajes considerando su intención declarada y el lore acumulado de la campaña.
   - Por ejemplo: si el grupo desentierra un ataúd, exhuma una tumba o recupera un cuerpo/objeto para devolver un relicario, dar sepultura digna a una baronesa o consagrar un lugar, NO lo juzgues ciegamente como una 'profanación' o acto malvado. Considera SIEMPRE el objetivo de la misión del grupo y las revelaciones previas (como descubrir si una criatura era un demonio o la necesidad de liberar a un espíritu).
"""

    prior_lore_block = ""
    if prior_lore and str(prior_lore).strip():
        prior_lore_block = f"""
LORE PREVIO Y RESUMEN DE SESIONES ANTERIORES (CONTEXTO DE LA CAMPAÑA):
{str(prior_lore).strip()}
(Utiliza este lore previo para dar continuidad al mundo, misiones en curso y personajes clave preexistentes).
"""

    last_recap_block = ""
    if last_session_recap and str(last_session_recap).strip():
        if is_english:
            last_recap_block = f"""
PREVIOUS SESSION RECAP (WHERE THE PARTY LEFT OFF):
{str(last_session_recap).strip()}
(Use this recap strictly for narrative continuity so you know exactly what occurred at the climax of the previous session before new events unfolded).
"""
        else:
            last_recap_block = f"""
RESUMEN DE LA SESIÓN ANTERIOR (DÓNDE QUEDÓ LA COMPAÑÍA):
{str(last_session_recap).strip()}
(Utiliza este resumen estrictamente para continuidad narrativa, sabiendo con exactitud en qué punto quedó la historia al final de la sesión pasada).
"""

    backstory_block = ""
    if char_name and character_backstory and str(character_backstory).strip():
        if is_english:
            backstory_block = f"""
=== OFFICIAL CHARACTER BACKSTORY: {char_name} ===
{str(character_backstory).strip()}
=== END OF BACKSTORY ===
(Use this backstory as the authoritative reference for the Roleplay & Fellowship Reflection coaching section. Cross-reference character decisions, dialogue, and actions against this backstory to identify out-of-character moments and missed roleplay opportunities.)
"""
        else:
            backstory_block = f"""
=== TRASFONDO OFICIAL DEL PERSONAJE: {char_name} ===
{str(character_backstory).strip()}
=== FIN DEL TRASFONDO ===
(Usa este trasfondo como referencia autoritativa para la sección de Reflexión de Rol y Compañerismo. Cruza las decisiones, diálogos y acciones del personaje con este trasfondo para identificar momentos fuera de personaje y oportunidades de rol perdidas.)
"""

    if char_name:
        if is_english:
            coaching_instructions = f"""2. Accurately attribute every action, spell, roll, and decision to the characters and players in the Roster. Pay special attention to {char_name} ({char_desc}) for their "Roleplay & Fellowship Reflection: {char_name}".
STRICT ATTRIBUTION & PERSONAL EVALUATION RULE:
- Evaluate {char_name} EXCLUSIVELY based on words and declared actions spoken by {char_name} (or their player) in the verbal transcript.
- ABSOLUTELY FORBIDDEN to evaluate or attribute actions performed by other characters to {char_name} (e.g., if another party member kicked down a door, forced open a chest, or cast a spell, NEVER critique or judge that action as part of {char_name}'s review).
- NEVER assume an action was taken by {char_name} without direct verbal evidence in the transcript. If an action has no explicit named author, attribute it to 'the party' or 'the group'.
- MIN/MAXING OR ROBOTIC COACHING IS STRICTLY FORBIDDEN (zero lessons on maximizing damage per turn or mathematical action economy; focus is narrative, character depth, teamwork, and in-character dilemmas).
- ⚠️ STRICT PROHIBITION AGAINST ASSUMING UNSTATED RELIGIOUS DEVOTION:
  * ABSOLUTELY FORBIDDEN to assume devotion, religious piety, or worship of a deity unless explicitly stated in the character's official backstory as a cleric, devout paladin, or explicit believer.
  * E.g., carrying experimental arcane runes named after a deity (such as Markus Veyl carrying Helm runes crafted by scholar Edrin Vale) does NOT make the character a devotee or believer; they are a secular, civic protector, NOT a worshipper of Helm. NEVER call them a 'devotee of Helm' or judge their actions through a religious lens."""
            coaching_json_desc = f"""Roleplay & Fellowship Reflection for {char_name} ({char_desc}) WITHOUT min/maxing or combat optimization, divided into 4 areas:
1) Character Consistency & Development: Analyze fidelity to the character's known personality, backstory, and values. MANDATORY — detect and flag any moments where the player appeared to speak or act out-of-character (breaking immersion, making meta decisions, speaking as themselves rather than as {char_name}). Cite the exact scene. Then cross-reference with the character's known backstory and class identity to suggest 1-2 specific roleplay moments the player could have seized but didn't (e.g. 'In Scene 2 when the NPC mentioned X, {char_name}'s backstory with Y was a perfect opening that wasn't used').
2) Creativity & Rules vs. Environment: Constructive analysis of rule flexibility vs. cinematic narrative, and gentle warnings about overlooked dangers.
3) Group Dynamics & Teamwork: Support for party members, enabling others to shine, protecting vulnerabilities.
4) Next Session Dilemmas: 1-2 reflective in-character questions about worldview, loyalties, or relationships.
⚠️ HONESTY DIRECTIVE: Report things exactly as they happened — if the session was excellent, say so specifically and cite the exact scene. If there were real mistakes or missed opportunities, name them with the exact scene. STRICTLY FORBIDDEN: generic empty praise ('they did great', 'it was incredible') with no specific evidence, AND forced criticism invented just to 'balance' a genuinely good session. Every observation — positive or negative — MUST be grounded in a specific moment from the transcript."""
        else:
            coaching_instructions = f"""2. Atribuye con precisión cada acción, hechizo, tirada y decisión a los personajes y jugadores del Roster. Presta atención especial a {char_name} ({char_desc}) para su "Reflexión de Rol y Compañerismo: {char_name}".
REGLA DE ORO DE EVALUACIÓN PERSONAL ({char_name}):
- Evalúa a {char_name} EXCLUSIVAMENTE a partir de los diálogos, decisiones y acciones que {char_name} (o su jugador) verbalizó explícitamente en la transcripción.
- PROHIBIDO TERMINANTEMENTE evaluar o atribuir a {char_name} acciones de otros personajes (por ejemplo, si Atou o Selen derribaron una puerta, forzaron un cofre o lanzaron un conjuro, JAMÁS juzgues esa acción en la revisión de {char_name}).
- NUNCA asumir que una acción fue ejecutada por {char_name} sin evidencia verbal directa en la transcripción. Si una acción no tiene autor explícito, atribúyela a 'la compañía' o 'el grupo'.
- PROHIBIDO EL MIN/MAXING O COACHING ROBÓTICO (cero lecciones sobre maximizar daño por turno o economía matemática de acciones; el foco es narrativa, carácter de personaje, apoyo a compañeros y dilemas in-character).
- ⚠️ PROHIBICIÓN ESTRICTA DE ASUMIR DEVOCIÓN O RELIGIOSIDAD NO DECLARADA:
  * PROHIBIDO TERMINANTEMENTE asumir devoción, fervor religioso, fe o adoración a deidades a menos que esté expresamente declarado en el trasfondo oficial del personaje como clérigo, paladín devoto o creyente explícito.
  * Por ejemplo: portar marcas o runas arcanas vinculadas al nombre de una deidad (como las runas de Helm en Markus Veyl creadas por su amigo erudito Edrin Vale) NO convierte al personaje en devoto ni creyente religioso; es un protector cívico y pragmático secular, no un adorador de Helm. NUNCA lo llames 'devoto de Helm' ni juzgues sus acciones desde la fe o dogmas religiosos."""
            coaching_json_desc = f"""Reflexión de Rol y Compañerismo para {char_name} ({char_desc}) SIN min/maxing ni optimización robótica de combate, dividida en 4 áreas:
1) Coherencia y Desarrollo de Personaje: Analiza la fidelidad a la personalidad conocida, trasfondo y valores del personaje. OBLIGATORIO — detecta y señala cualquier momento donde el jugador pareció hablar o actuar fuera de personaje (rompiendo la inmersión, tomando decisiones meta, hablando como él mismo en lugar de como {char_name}). Cita la escena exacta. Luego cruza con el trasfondo conocido del personaje y su identidad de clase para sugerir 1-2 momentos de rol específicos que el jugador pudo aprovechar pero no aprovechó (ej. 'En la Escena 2 cuando el PNJ mencionó X, el trasfondo de {char_name} con Y era una apertura perfecta que no se utilizó').
2) Creatividad y Uso del Entorno vs. Reglas: Análisis constructivo si flexionó RAW en favor de la narrativa cinematográfica vs regla formal estricta, y advertencias amables sobre peligros pasados por alto.
3) Dinámica de Grupo y Trabajo en Equipo: Apoyo a sus compañeros de party, permitiéndoles brillar y protegiendo vulnerabilidades.
4) Dilemas para la Siguiente Sesión: 1 o 2 preguntas reflexivas in-character sobre su visión del mundo, lealtades o relaciones.
⚠️ DIRECTIVA DE HONESTIDAD: Di las cosas como fueron. Si la sesión fue excelente, dilo con evidencia concreta citando la escena exacta. Si hubo errores reales u oportunidades perdidas, nómbralos con la escena exacta. PROHIBIDO TERMINANTEMENTE: el elogio vacío sin evidencia ('lo hizo muy bien', 'fue increíble') Y la crítica inventada para 'equilibrar' artificialmente una sesión genuinamente buena o mala. Cada observación — positiva o negativa — DEBE estar anclada en un momento específico de la transcripción."""
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
        scene_instructions = """⚠️ MANDATORY DIRECTIVE: DEEP CHRONOLOGICAL SCENE BREAKDOWN (NO OVER-SUMMARIZATION / STORY-FIRST):
- STRICTLY FORBIDDEN to write a generic 3-paragraph summary for the session. This represents hours of real roleplay gameplay.
- Structure 'chronicle_text' into detailed chronological ACTS AND SCENES (e.g. '### Act I: Scene 1: ...', '### Scene 2: ...', '### Act II: Scene 3: ...').
- Dedicate 2 to 3 comprehensive, rich paragraphs per major scene:
  * STORY-FIRST NARRATIVE & CONTEXT: Recount what happened, context, cause-and-effect, discoveries, moral dilemmas, and how circumstances advanced. Anyone who missed the session must be able to read this and fully understand the entire story smoothly without gaps.
  * DO NOT OVER-SUMMARIZE: Narrate the progression from start to finish, but avoid word-for-word transcriptions of everyday banter or trivial details.
  * STRICT DICE ROLLS RULE (CRITICALS & FUMBLES ONLY - NO PHANTOM NAT 20s):
    - Highlight ONLY Natural 20s and Natural 1s if and only if they were explicitly verbalized as 'natural', 'nat 20', 'nat 1', or 'critical fumble/success' in the audio transcript.
    - CRITICAL: A roll of 20 (or total result of 20 with modifiers, like an Athletics check of 20) is NOT a Natural 20 unless the word 'natural' or 'nat 20' was explicitly spoken. NEVER label a total check of 20 as a Natural 20 without explicit spoken proof.
    - FORBIDDEN to clutter the chronicle with routine intermediate dice checks or technical DC logs.
  * LOOT & PARTY INVENTORY RULE:
    - All loot discovered in chests, rooms, or from enemies defaults strictly to the GROUP/PARTY INVENTORY.
    - STRICTLY FORBIDDEN to assume or narrate that a specific character equips armor, weapons, or items unless the player explicitly declares equipping it in spoken dialogue.
  * TACTICAL COMBATS & ENCOUNTERS: Chronicled with narrative drama and consequence (key spells, environmental hazards, heroes falling unconscious or saved in the nick of time, tactical resolution), NOT like robotic spreadsheet math.
- ⚠️ STRICT CHARACTER DISAMBIGUATION IN INTERLACED / PARALLEL ACTIONS:
  * When characters operate closely or alternate actions in the same front (e.g., Selen and Atou in the attic, or Markus and Minipeko in the courtyard), PRECISELY ATTRIBUTE EVERY ACTION TO ITS REAL ACTOR based strictly on dialogue, item transfers, and dice rolls:
    - NEVER rely on simplistic class stereotypes (e.g., do NOT assume the Rogue always succeeds in lockpicking or kicks doors, nor that the Monk always handles relics). If a lockpick fails and another character (e.g. Atou using a quarterstaff as a crowbar) smashes the lock with brute force, or if an item like a mirror is passed between characters and Selen delivers the verbal challenge, attribute each step strictly to the character who actually executed it.
    - Track physical custody of items and verbal cues (who kicks the door, who attempts the lock, who breaks it, and who utters the words holding the mirror).
  * STRICTLY FORBIDDEN to misattribute or swap actions between characters.
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
- ⚠️ PARALLEL SCENES & SIMULTANEOUS ACTION:
  * If the party splits or actions occur simultaneously in different locations (e.g. party members investigating the attic while others fight or investigate down in the courtyard/outside), explicitly chronicle both fronts as parallel simultaneous events. Maintain chronological coherence and detail the events, discoveries, and perils of each subgroup without omitting either perspective.
- ⚠️ MAGICAL OVERCHARGES & CRITICAL SPELL ANOMALIES:
  * Explicitly chronicle and highlight magical overcharge events, wild magic surges, scroll overcharges (e.g. a magical scroll firing 6 rays instead of 3), or critical magical anomalies as pivotal story and tactical moments. Detail who cast or triggered the magic, the overcharged effect, and its immediate tactical and narrative impact.
- ⚠️ REGISTER COMPANIONS & CHARACTER SWAPS:
  * Capture party animal companions, familiars, or mascots (e.g. Minipeko) and character switches/retirements.
- ⚠️ MINIMUM SCENE LENGTH: Each scene MUST contain at least 3 full paragraphs. A scene with fewer than 150 words is an INCOMPLETE scene — you MUST expand it with additional detail from the transcript before moving to the next scene."""
        chronicle_json_desc = "Deep narrative chronicle strictly organized into chronological Acts and Scenes (e.g. '### Act I: Scene 1: ...', '### Scene 2: ...'). Dedicate 2-3 detailed paragraphs per scene narrating the full story and context, highlighting causes and consequences, highlighting dice rolls ONLY when explicitly verbalized as natural 20s or natural 1s, keeping looted gear in party inventory unless explicitly equipped, and precisely attributing actions between interlaced characters without relying on class stereotypes."
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
        scene_instructions = """⚠️ DIRECTIVA OBLIGATORIA: CRÓNICA PROFUNDA POR ACTOS Y ESCENAS CRONOLÓGICAS (STORY-FIRST / INMERSIÓN TOTAL):
- PROHIBIDO TERMINANTEMENTE resumir toda la sesión en 3 o 4 párrafos genéricos. Esta sesión representa horas de juego real de rol.
- Estructura OBLIGATORIAMENTE 'chronicle_text' en ACTOS Y ESCENAS cronológicas detalladas (ej. '### Acto I: Escena 1: El Camino del Bosque', '### Escena 2: Negociación en la Posada', '### Acto II: Escena 3: Emboscada').
- Dedica entre 2 y 3 PÁRRAFOS COMPLETOS Y EXTENSOS a cada escena principal:
  * NARRATIVA Y CONTEXTO DE LA HISTORIA: Cuenta qué pasó, por qué pasó, qué descubrieron, qué dilemas enfrentaron y cómo cambiaron las circunstancias de la aventura. Si un lector que NO asistió a la partida lee el documento, debe entender la historia completa con claridad cinematográfica y fluida, sin lagunas argumentales.
  * PROHIBIDO EL RESUMEN SUPERFICIAL: Explica el desarrollo de la escena de principio a fin, pero NO te desgastes en transcripciones textuales palabra por palabra ni en registrar mecánicas mundanas irrelevantes.
  * REGLA ESTRICTA DE TIRADAS DE DADOS (SOLO CRÍTICOS Y PIFIAS VERBALIZADOS COMO TAL):
    - Menciona ÚNICAMENTE los 20 Naturales y los 1 Naturales SI Y SÓLO SI fueron verbalizados explícitamente en el audio o transcripción como 'natural', 'nat 20', 'nat 1', 'pifia' o 'crítico'.
    - DIRECTIVA CRÍTICA: Un resultado total de 20 (por ejemplo, tirada de Atletismo de 20 con modificadores) NO es un 20 natural a menos que en el audio se diga expresamente la palabra 'natural' o 'nat 20'. PROHIBIDO inventar o asumir que un 20 es 'natural' si no fue dicho con esas palabras exactas.
    - PROHIBIDO saturar el texto enumerando tiradas mundanas intermedias de dados o clases de dificultad (CD) técnicas.
  * GESTIÓN DE BOTÍN E INVENTARIO GRUPAL:
    - Todo botín encontrado en cofres, estancias o enemigos se destina por defecto al INVENTARIO GENERAL DEL GRUPO.
    - Queda terminantemente PROHIBIDO asumir o narrar que un personaje específico se equipa una armadura, arma o accesorio a menos que el jugador lo declare explícitamente en el diálogo de la transcripción.
  * COMBATES Y CONFLICTOS: Narra el combate desde una perspectiva narrativa y dramática (hechizos clave, peligros ambientales, héroes caídos o salvados al límite, desenlace táctico), no como un registro numérico de turnos de videojuego.
- ⚠️ DESAMBIGUACIÓN ESTRICTA DE PERSONAJES EN ACCIONES INTERCALADAS O EN PARALELO:
  * Cuando dos personajes actúan en el mismo frente o intercambian objetos y turnos rápidamente (por ejemplo, Selen y Atou en el ático, o Markus y Minipeko en el patio), ATRIBUYE CADA ACCIÓN ESTRICTAMENTE A QUIEN LA EJECUTÓ según el diálogo, el traspaso de objetos y las tiradas reales:
    - PROHIBIDO fiarse de estereotipos superficiales de clase (por ejemplo, NO asumas que por ser Pícaro forzó la cerradura con éxito o derribó la puerta, ni que por ser Monje usó la reliquia). Si una tirada de ganzúas falla (como Atou sacando un 2) y el mismo u otro personaje rompe el candado a la fuerza haciendo palanca con su bastón, o si un objeto (como el espejo) se pasa de mano en mano y al final Selen lo empuña diciendo la frase ('espejo, espejo...') para encarar al fantasma ganando inspiración, atribuye cada acción al personaje que efectivamente la realizó en la transcripción.
    - Sigue minuciosamente la posesión física de objetos y quién pronuncia las frases clave en voz alta.
  * PROHIBIDO TERMINANTEMENTE intercambiar, mezclar o atribuir por error las acciones entre personajes.
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
- ⚠️ ESCENAS PARALELAS Y ACCIÓN SIMULTÁNEA:
  * Si el grupo se divide o las acciones ocurren concurrentemente en diferentes lugares (ej. parte del grupo investigando en el ático mientras otros combaten o investigan en el patio/exterior), narra explícitamente ambos frentes como acciones simultáneas o sub-escenas paralelas. Mantén la coherencia temporal y detalla los sucesos y peligros de cada subgrupo sin omitir ningún frente.
- ⚠️ SOBRECARGAS MÁGICAS Y ANOMALÍAS DE CONJUROS:
  * Registra y resalta explícitamente eventos de sobrecarga mágica, magia salvaje, sobrecargas de pergaminos o anomalías mágicas críticas como puntos de inflexión tácticos y narrativos. Detalla quién activó o lanzó la magia, el efecto sobrecargado/anómalo y sus consecuencias directas.
- ⚠️ VOCABULARIO LITERAL DE MESA Y PROHIBICIÓN DE ARCAÍSMOS:
  * PROHIBIDO usar arcaísmos o sinónimos medievales rebuscados (ej. NUNCA uses 'sierpe' para dragón, 'pertrechos' para suministros o equipo, 'yacija', 'mengua').
  * Usa vocabulario directo de la mesa de D&D y spanglish natural: 'dragón', 'trol', 'suministros', 'equipo', 'pociones', 'trampa'.
- ⚠️ REGISTRO DE COMPAÑEROS, MASCOTAS Y RELEVOS DE PERSONAJE:
  * Registra adecuadamente acompañantes, familiares o mascotas de la party (ej. Minipeko) y cambios o relevos de personajes.
- ⚠️ PISO MÍNIMO DE EXTENSIÓN POR ESCENA: Cada escena DEBE contener al menos 3 párrafos completos. Una escena con menos de 150 palabras es una ESCENA INCOMPLETA — DEBES ampliarla con detalles adicionales de la transcripción antes de pasar a la siguiente escena."""
        chronicle_json_desc = "Crónica narrativa profunda estructurada OBLIGATORIAMENTE en Actos y Escenas cronológicas (ej. '### Acto I: Escena 1: El Camino del Bosque', '### Escena 2: Negociación en la Posada', '### Acto II: Escena 3: Emboscada'). PROHIBIDO resumir en 3 párrafos. Dedica 2 a 3 párrafos por escena narrando la historia y el contexto completo, destacando causas y consecuencias, destacando tiradas ÚNICAMENTE cuando sean 20s o 1s verbalizados explícitamente como naturales, guardando botín en inventario grupal a menos que se declare equipado, y desambiguando con precisión las acciones entre personajes sin sesgos de clase."

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
  * ⚠️ PROHIBICIÓN TOTAL DE MATEMÁTICAS DE DADOS O COMENTARIOS META EN HITOS:
    - Queda terminantemente PROHIBIDO incluir operaciones matemáticas de tiradas de dados, sumas de modificadores o comentarios meta en 'hitos_acumulados' o 'rol_en_sesion' (NUNCA escribas cosas como '(16+4)', 'sacó un 20 total', 'su mejor tirada del día' o 'tiró un dado').
    - Narra los hitos y roles siempre como hechos y logros heroicos in-world (ej. en vez de 'Obtuvo un 20 en Historia recordando los detalles de Nashkel', escribe 'Recordó con precisión táctica los peligros de Nashkel y los Picos Nubosos para negociar exitosamente la recompensa').
  * ⚠️ PROHIBICIÓN TOTAL DE INVENTAR PAPELES O HAZAÑAS A JUGADORES SILENCIOSOS O INACTIVOS:
    - NO fuerces ni inventes un papel activo, protagónico o hazañas heroicas para jugadores o personajes que no hablaron o no tuvieron participación activa en la sesión.
    - Si un jugador permaneció en silencio, habló poco, estuvo ausente o simplemente acompañó al grupo en segundo plano:
      * Narra con absoluta honestidad que permaneció en reserva, en segundo plano o acompañando a la compañía sin intervenir activamente.
      * PROHIBIDO TERMINANTEMENTE inventar justificaciones artificiosas o 'rellenos tácticos' falsos (NUNCA inventes cosas como 'mantuvo vigilancia táctica', 'facilitó el contacto para la partida', 'coordinó la logística' o 'custodió las espaldas' si no lo dijeron en el audio).
  * ⚠️ UNIFORMIDAD ESTRICTA DE IDIOMA EN MISIONES Y SUBOBJETIVOS (CERO MEZCLA INGLÉS/ESPAÑOL):
    - Todos los títulos, contextos, notas y subobjetivos de misiones ('text' dentro de 'subobjectives') DEBEN estar redactados al 100% en español fluido y natural.
    - PROHIBIDO TERMINANTEMENTE mezclar subobjetivos en inglés y en español dentro de una misma misión o campaña (ej. prohibido tener un subobjetivo en inglés como 'Deliver the dragon egg' y otro en español como 'Derrotar a la sierpe').
- ⚠️ REGLA UNIVERSAL DE TRANSICIÓN Y RELEVO DE PERSONAJES A MITAD DE SESIÓN:
  * Si las conversaciones operativas de la mesa indican que un jugador retira, deja en reserva o sustituye a su personaje e introduce uno nuevo a mitad de la partida:
    - Refleja la salida o retiro del personaje saliente en sus 'hitos_acumulados' y 'rol_en_sesion' (ej. se separó del grupo, marchó por un camino propio o quedó en reserva).
    - Registra el nuevo personaje en 'detected_pcs' / 'detected_party' comenzando desde esta sesión con su debut ('debut_sesion': {session_number}).
    - PROHIBIDO TERMINANTEMENTE atribuir combates, diálogos o acciones posteriores al personaje retirado una vez que el nuevo entra en juego.
- EXCLUSIÓN DEL DUNGEON MASTER (DM):
  * El Dungeon Master (DM) es estrictamente el narrador y árbitro fuera de personaje (out-of-character).
  * El DM NUNCA tiene tarjeta de personaje ni ficha en 'detected_pcs' o 'detected_party'.
  * Un personaje con nombre de fantasía jamás puede tener como clase o rol 'Dungeon Master' o 'DM'.
- ⚠️ PARTICIPANTES INVITADOS / EXTERNOS (NO CONTAR EN LA CAMPAÑA PERMANENTE):
  * Si en la transcripción aparecen intervenciones de personas no registradas en el Roster de la campaña o etiquetadas como [Invitado] o [Invitado / Nombre]:
    - Trátalas estrictamente como **Invitados** temporales en la narración.
    - PROHIBIDO TERMINANTEMENTE incorporarlos como protagonistas a 'universal_pcs', inventarles fichas permanentes o subirlos de nivel en la campaña.
    - NO se cuentan en la composición fija de la compañía de aventureros ni en la reflexión personal."""
        if not is_english
        else """⚠️ STRICT IN-CHARACTER RULE AND HARD DUNGEON MASTER (DM) EXCLUSION:
- MANDATORY PRESERVATION OF PLAYER CHARACTERS (DO NOT DISCARD LEGITIMATE PCs):
  * A player who acts as a core protagonist in the narrative (e.g. Liam O'Brien playing the Bard Halendiel Fang) is a **Player Character (PC)**.
  * ABSOLUTELY FORBIDDEN to omit, discard, or drop legitimate players from 'detected_pcs' or 'detected_party'.
  * Distinguish the true Dungeon Master (who sets DCs, describes monster attacks, adjudicates rules, and runs the world) from the players. Liam O'Brien is a PLAYER playing the Bard Halendiel Fang, NOT the Dungeon Master.
- STRICT IN-CHARACTER RULE FOR PCs:
  * 'rol_en_sesion' and 'hitos_acumulados' of each Player Character (PC) must describe EXCLUSIVELY in-world fictional actions (battles fought, spells cast, tactical decisions, conversations with NPCs, wounds taken, or discoveries).
  * ABSOLUTELY FORBIDDEN to write out-of-game meta roles, tabletop moderation, or real-life actions (NEVER write 'Acted as Dungeon Master', 'Controlled NPCs', 'Chaired session', or 'Rolled dice').
  * ⚠️ STRICT PROHIBITION OF DICE MATH OR TABLETOP META COMMENTARY IN MILESTONES:
    - STRICTLY FORBIDDEN to include dice arithmetic, modifier sums, or tabletop comments in 'hitos_acumulados' or 'rol_en_sesion' (NEVER write '(16+4)', 'best roll of the day', 'rolled a 20 total', or 'rolled dice').
    - Always narrate character milestones as in-world heroic deeds and dramatic accomplishments (e.g. instead of 'Rolled a 20 on History recalling Nashkel', write 'Accurately recalled the strategic hazards of Nashkel and Cloud Peaks to successfully negotiate the bounty').
    - If a player makes a casual joke about their dice roll during Discord audio, NEVER turn that casual meta joke into their character's narrative milestone.
  * ⚠️ STRICT PROHIBITION OF INVENTING FAKE ROLES OR DEEDS FOR SILENT OR PASSIVE PLAYERS:
    - DO NOT force an active role or invent fictional accomplishments for players who did not speak or participate actively.
    - If a player or character was quiet, remained in the background, or did not actively intervene in a scene, negotiation, or battle:
      * Honestly state that they remained in the background, in reserve, or accompanying the party without active involvement.
      * ABSOLUTELY FORBIDDEN to invent artificial filler deeds such as 'maintained tactical watch', 'coordinated logistics', 'facilitated contact', or similar embellished excuses.
  * ⚠️ STRICT LANGUAGE UNIFORMITY IN QUESTS AND SUBOBJECTIVES (NO MIXED LANGUAGES):
    - 100% of quest titles, contexts, notes, and subobjectives ('text' in 'subobjectives') MUST match the target output language.
    - STRICTLY FORBIDDEN to mix English and Spanish subobjectives within the same quest or campaign.
- ⚠️ UNIVERSAL MID-SESSION PLAYER CHARACTER TRANSITIONS:
  * If operational table discussion indicates a player is retiring, benching, or swapping a character and introducing a new one mid-session:
    - Reflect the departure of the former character in their session milestone and role ('hitos_acumulados' / 'rol_en_sesion') (e.g. separated, departed on their own path, or staying in reserve).
    - Register the new character in 'detected_pcs' / 'detected_party' starting from this session with their debut ('debut_sesion': {session_number}).
    - STRICTLY FORBIDDEN to attribute subsequent battles, dialogues, or actions to the retired character once the new character enters play.
- MUTUAL EXCLUSIVITY OF THE DM:
  * The Dungeon Master (DM) is strictly the out-of-character narrator and referee.
  * The DM NEVER has a character card or row in 'detected_pcs' or 'detected_party'.
  * A character with a fictional name can NEVER have the class or role 'Dungeon Master' or 'DM'.
- ⚠️ GUEST / OUTSIDE PARTICIPANTS (DO NOT COUNT IN PERMANENT PARTY):
  * If the transcript contains participants not listed in the campaign Roster or tagged as [Invitado] or [Invitado / Name]:
    - Treat them strictly as temporary **Guests** in the narrative.
    - ABSOLUTELY FORBIDDEN to incorporate them as permanent protagonists in 'universal_pcs', create permanent character sheets, or level them up in the campaign.
    - Guests DO NOT count towards the permanent adventuring company composition or personal reflection."""
    )

    npc_instruction = (
        """4. CRITERIOS ESTRICTOS DE EXTRACCIÓN DE PNJs, ALIADOS E INVOCACIONES:
   - ⚠️ REGLA DE EXCLUSIÓN DE PERSONAJES JUGADORES (LISTA CERRADA DE PCs):
     * Los ÚNICOS Personajes Jugadores (PCs) son:
       - Sir Yato (Scailer)
       - Johngalli A. III / John / Ion (GuzMan_)
       - Aquilus Bunker (Drowser45)
       - Zafkiel (lDarkLink)
       - Raul-Hell / Raúl (Raulhell)
     * CRÍTICO: Cualquier otro personaje aliado que tenga turno en la iniciativa, tire dados, ataque, cure o acompañe al grupo (por ejemplo, Halsey o la Hermana Lenure / Garael) NO es un jugador. Debe ser extraído obligatoriamente en el directorio de PNJs como 'Compañero / Aliado' ('category': 'aliado').
   - ⚠️ RECONSTRUCCIÓN FONÉTICA DE D&D 5e / 5.5e (UNIFICAR VARIANTES DE WHISPER):
     * Whisper genera distorsiones fonéticas por ruido o acentos. Agrupa todas las variantes bajo un solo nombre canónico con sus variantes en 'aliases':
       - 'Halsey', 'Harsin', 'Hellsie', 'Hetzi', 'Hellsye', 'Hellsing', 'Halcy', 'Halcyon', 'Hasi', 'Jalsi', 'Calcis' → 'Halsey' (Guerrera/Bárbara aliada que combate con Glaive y arco).
       - 'Hermana Garael', 'Hermana Oscura', 'Lennard', 'Nubre', 'Permanele Nure', 'hermana Lenure', 'hermana del lune' → 'Hermana Lenure / Garael' (Bruja/Guía aliada en la Infraoscuridad que lanza Eldritch Blast e invoca un Celestial).
       - 'Kira', 'Kirrel', 'Kirreloy', 'Kyrrle', 'Kirill', 'Kyrrell', 'Kyrel', 'Kirin' → 'Quirrel' (Corcel convocado de Sir Yato mediante Find Steed, terrestre, cura 2d8 con lengüetazos; alias fonéticos: Kira, Kirrel, Kyrrel, Kirreloy).
       - 'Valgo', 'Balbura', 'valvura', 'Vargula' → 'Barlgura' (Demonio simio enemigo).
       - 'Bundru', 'El Gal', 'El GreciaNiko', 'El Grell' → 'Bundru (El Grell)' (Custodio mutante del laboratorio).
     * El DM o los jugadores pueden introducir, nombrar o interactuar con múltiples personajes no jugadores (PNJs) a lo largo de la sesión: eruditos, bibliotecarios, monjes, sabios, guardias, posaderos, comerciantes, heraldos, prisioneros, enviados de facciones o figuras misteriosas.
     * PROHIBIDO TERMINANTEMENTE ignorar o filtrar PNJs que hablen poco o solo sean introducidos/mencionados por el DM. Si se nombra o introduce a un PNJ, REGÍSTRALO OBLIGATORIAMENTE tanto en 'updated_npcs' como en 'detected_npc_names' para su posterior revisión ortográfica.
     * PRECISIÓN FONÉTICA Y DE ORTOGRAFÍA: En el audio en español, los nombres de fantasía de D&D a menudo son transcritos fonéticamente por Whisper (ej. nombres de Forgotten Realms / Candlekeep Mysteries como Miirym, Sylvira Savikas, Matreous, Bookwyrm, Fistandia, etc.). Utiliza el contexto del mundo de D&D para deducir y corregir la ortografía canónica más verosímil del nombre de fantasía, evitando sustituirlo por palabras comunes del español.
      * DESAMBIGUACIÓN FONÉTICA ESTRICTA (JUGADORES vs PNJs):
        - PROHIBIDO confundir a un Personaje Jugador con un PNJ debido a distorsiones fonéticas de Whisper:
          * "Viri", "Belly", "Belith", "Belita", "Veli", "Vel" se refieren a la barda tiefling Velith. NUNCA crees un PNJ llamado 'Viri'.
          * "Atou", "Ato", "A-tú", "Toad" se refieren al monje elfo Atou Shadowgrace.
          * "Markus", "Marco", "Matthew" se refieren al guerrero humano Markus Veyl.
          * "Minipeko", "Peko", "Mipe", "Mi pez", "Mi pepe", "Nipe" se refieren al mago kenku Minipeko.
          * "Selen", "Selle", "Seren" se refieren a la pícaro Selen.
        - Para PNJs de aventuras oficiales (ej. Candlekeep Mysteries - Book of the Raven / Chalet Brantifax):
          * Usa siempre los nombres canónicos: Madrina Natterask, Taspar Hatchhill, Vinique, Rennick Groka, Barón Brantifax, Baronesa Ariadne, Sylphene, Heluthe, Brorn.
         - Para PNJs de aventuras oficiales de Phandalin (Lost Mine of Phandelver / Dragon of Icespire Peak):
          * Usa siempre los nombres canónicos: Sildar Hallwinter, Gundren Rockseeker, Sister Garaele, Linene Graywind, Halia Thornton, Harbin Wester, Toblen Stonehill, Elmar Barthen, Daran Edermath, Qelline Alderleaf, Carp Alderleaf.
          * Los PCs de Phandalin: \"Aquilus\", \"Aquilo\", \"Aquila\" → Aquilus Bunker (Dragonborn Ranger). \"Johngalli\", \"Juan Gali\", \"John\" → Johngalli A. III (Human Pugilist). \"Raul\", \"Raúl Hell\" → Raul-Hell (Gnome Monk). \"Sir Yato\", \"Yato\" → Sir Yato (Human Paladin). \"Zafkiel\", \"Safkiel\", \"Zafquiel\" → Zafkiel (Tiefling Wizard).
   - ⚠️ SEPARACIÓN ESTRICTA DE INVOCACIONES, FAMILIARES Y MASCOTAS (PROHIBIDO FUSIONAR):
     * NO fusiones diferentes mascotas o convocaciones en una sola entidad. Extrae cada una como una entrada independiente con 'category': 'invocacion', indicando en 'role' de quién proviene:
       - Corceles convocados: ej. 'Quirrel' (Corcel terrestre convocado por Sir Yato mediante Find Steed; NO es aliado aéreo; variantes de Whisper: Kira, Kirrel).
       - Familiares: ej. 'Búho de Zafkiel' (Familiar aéreo con Flyby que asiste con la acción Help y puede perecer ante daño en área).
       - Espíritus / Conjuros de Invocación: ej. 'Espíritu Celestial' (Invocado por la Hermana Lenure con conjuro de nivel 5, ataca con arco/rayo radiante a 600 pies y habla en Celestial).
       - Criaturas de Objetos Mágicos: ej. animales extraídos del 'Bolsito de Trucos' (Bag of Tricks) de Zafkiel: 'Tigre', 'Comadreja Gigante (Giant Weasel)' y 'Simio (Ape)'.
   - ⚠️ DETECCIÓN DE AMENAZAS Y JEFES RELEVANTES SIN NOMBRE PROPIO:
     * Si en la sesión aparecen monstruos importantes o jefes de encuentro sin nombre propio (ej. 'Demonio Barlgura', 'Aberración Colosal de Cuerpos Cosidos', 'Aberración Voladora de Cuatro Colas', 'Dragón/Monstruosidad de Truenos'), extráelos obligatoriamente con 'category': 'amenaza'.
   - ⚠️ EXCLUSIÓN DE CHARLA FUERA DE ROL (OOC / META-JUEGO Y ESTRELLAS Y DESEOS):
     * Prohibido extraer personajes mencionados únicamente en bromas de campañas pasadas, memes o en la sección post-partida de 'Estrellas y Deseos' (ej. omitir a Zendo, Markus, Velith, Meglax, Ocelen, Van). Solo registra entidades que interactúan o existen activamente en la narrativa in-world de la sesión actual.
   - CATEGORIZACIÓN SEMÁNTICA ('category') Y ESTADO VITAL ('status'):
     * 'category':
       - 'clave': Villanos principales, patrones, líderes de facción, figuras clave recurrentes.
       - 'aliado': Compañeros de armas, guías o aliados que viajan o combaten con la party (ej. Halsey, Hermana Lenure).
       - 'invocacion': Corceles convocados, familiares, espíritus de conjuros o criaturas de objetos mágicos.
       - 'amenaza': Monstruos relevantes, jefes de encuentro, demonios, aberraciones.
       - 'interaccion_contexto': Diálogo directo, comercio, testigos presenciales cara a cara.
     * 'status':
       - 'activo': Vivo, operativo o en combate al final de la sesión.
       - 'herido': Malherido, derribado, revivido o estabilizado.
       - 'abatido': Muerto, destruido o abatido en combate.
       - 'desvanecido': Invocación disipada, tiempo de conjuro expirado o desconvocado.
     * 'tipo' (retrocompatibilidad):
       - 'importantes' para clave; 'mencionados' para menciones indirectas [Mencionado en la historia]; 'interaccion_contexto' para los demás.
    - ⚠️ REGLA DE PERSONAJES SIN NOMBRE: Si un PNJ no tiene nombre propio pero aportó información útil, pistas o interactuó, regístralo por su rol/descriptor (ej. '[Sin nombre] Guardia de la puerta norte') registrando su pista o contribución específica en 'notes'.
    - REGLA TAXATIVA: PROHIBIDO omitir PNJs con nombre propio. Identifícalos a todos exhaustivamente.
    - Documenta pistas clave, secretos o revelaciones en el array de 'notes'."""
        if not is_english
        else """4. STRICT NPC EXTRACTION CRITERIA (3-TIER TAXONOMY & HIGH RECALL):
   - ⚠️ HIGH SENSITIVITY AND EXHAUSTIVE COVERAGE OF INTRODUCED NPCS:
     * The DM or players may introduce, name, or interact with multiple non-player characters (NPCs) throughout the session: scholars, monks, librarians, guards, innkeepers, merchants, faction emissaries, prisoners, or mysterious figures.
     * STRICTLY FORBIDDEN to ignore or drop NPCs who speak briefly or are only introduced/described by the DM. If an NPC is named or introduced, MANDATORILY register them in both 'updated_npcs' and 'detected_npc_names' for spelling review.
     * PHONETIC & FANTASY ACCURACY: In audio transcripts, D&D fantasy names may be phonetically transcribed. Deduce the most accurate fantasy name from D&D context (e.g. Candlekeep Mysteries / Forgotten Realms lore) rather than Spanish common words.
   - Classify EVERY non-player character (NPC) under 'tipo':
     * 'importantes': Main villains, patrons, faction leaders, key recurring figures.
     * 'interaccion_contexto': Direct dialogue, direct interaction (interaccion_directa), trade, combat, or eyewitnesses face-to-face with the party.
     * 'mencionados': Characters referenced in letters, rumors, background lore, or mentioned indirectly.
   - ⚠️ UNNAMED CHARACTERS RULE: If an NPC lacks a proper name but provided useful information or clues, register them by their role/descriptor (e.g. '[Sin nombre] Guardia de la puerta norte') with their specific clue or contribution in 'notes'.
   - STRICT DIRECTIVE: DO NOT skip named characters. Identify all of them exhaustively.
   - Document key clues, secrets, or revelations in the 'notes' array."""
    )

    entity_resolution_instruction = (
        """⚠️ RESOLUCIÓN DE ENTIDADES Y PREVENCIÓN DE DUPLICADOS (CASO OCTUS):
- Si a lo largo de la sesión un personaje o PNJ es mencionado por diferentes nombres, alias, títulos o formas abreviadas (ej. 'Octus', 'Octus Taconis', 'Lord Octus'):
  * NO generes múltiples entradas duplicadas en 'detected_pcs' o 'updated_npcs'.
  * Resuelve la entidad bajo su nombre canónico más completo (ej. 'Octus Taconis').
  * Incluye en el campo 'aliases' una lista con todas las formas alternas o abreviadas utilizadas (ej. 'aliases': ['Octus', 'Lord Octus'])."""
        if not is_english
        else """⚠️ ENTITY RESOLUTION & DEDUPLICATION (OCTUS CASE):
- If throughout the session a character or NPC is called by different names, aliases, titles, or nicknames (e.g. 'Octus', 'Octus Taconis', 'Lord Octus'):
  * DO NOT output separate duplicated entries in 'detected_pcs' or 'updated_npcs'.
  * Resolve the entity to its most complete canonical name (e.g. 'Octus Taconis').
  * Provide the 'aliases' array containing all alternative forms or titles used (e.g. 'aliases': ['Octus', 'Lord Octus'])."""
    )

    locations_instruction = (
        """6. EXTRACCIÓN DE LUGARES Y PUNTOS DE INTERÉS:
- Extrae todas las ciudades, regiones, mazmorras, fortalezas o puntos de interés explorados o descubiertos en la sesión.
- Asigna 'status': 'explorado' (si la party lo recorrió activamente), 'en_progreso' (si la sesión concluyó allí), 'destruido' o 'no_visitado' (si solo fue mencionado como destino futuro).
- REGLA ESTRICTA DE HABITANTES / RESIDENCIA EN 'associated_characters':
  * NUNCA incluyas a Personajes Jugadores (PCs) ni aventureros visitantes en 'associated_characters' solo porque combatieron, descansaron o pasaron por allí.
  * Solo incluye en 'associated_characters' a aquellos PNJs, custodios o monstruos residentes para quienes ese lugar es su HOGAR, RESIDENCIA PERMANENTE, PUESTO DE CUSTODIO, DOMINIO/GOBIERNO o GUARIDA/CREACIÓN RESIDENTE (ej. 'Bundru' como custodio; aberraciones o creaciones que habitan en el laboratorio; un rey en su corte). Los aventureros itinerantes, PCs y enemigos de paso están PROHIBIDOS en este campo."""
        if not is_english
        else """6. LOCATIONS & POINTS OF INTEREST EXTRACTION:
- Extract all cities, dungeons, regions, strongholds, or points of interest explored or discovered in the session.
- Set 'status': 'explorado' (actively explored), 'en_progreso' (current location), 'destruido' (destroyed), or 'no_visitado' (mentioned for the future).
- STRICT RESIDENCY / INHABITANT RULE FOR 'associated_characters':
  * NEVER include Player Characters (PCs) or visiting adventurers in 'associated_characters' merely because they explored, fought, or rested there.
  * Only include in 'associated_characters' NPCs, custodians, or resident monsters for whom this location is their HOME, PERMANENT RESIDENCE, CUSTODIAL POST, SEAT OF RULERSHIP, or RESIDENT LAIR/CREATION (e.g. 'Bundru' guarding his lab; laboratory aberrational creations dwelling there; a monarch in their throne room). Transient travelers, adventurers, and roaming enemies are STRICTLY PROHIBITED in this field."""
    )

    items_instruction = (
        """7. EXTRACCIÓN DE OBJETOS, ARTEFACTOS Y BOTÍN:
- Extrae armas, armaduras, artefactos mágicos, reliquias o tesoros clave obtenidos, equipados, transferidos o utilizados en la sesión.
- Asigna 'type': 'arma', 'armadura', 'artefacto', 'consumible', 'reliquia' o 'mision'.
- Asigna 'status': 'equipado', 'en_posesion', 'perdido', 'consumido' o 'entregado'.
- En 'holder', indica el nombre del personaje o PNJ que lo porta o custodia."""
        if not is_english
        else """7. ITEMS, ARTIFACTS & LOOT EXTRACTION:
- Extract weapons, armor, magical artifacts, relics, or key quest items obtained, equipped, transferred, or used in the session.
- Set 'type': 'arma', 'armadura', 'artefacto', 'consumible', 'reliquia', or 'mision'.
- Set 'status': 'equipado', 'en_posesion', 'perdido', 'consumido', or 'entregado'.
- In 'holder', specify the character or NPC holding or guarding it."""
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
{recap_guidance}{prior_lore_block}{last_recap_block}{backstory_block}
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
{entity_resolution_instruction}
{locations_instruction}
{items_instruction}
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
      "aliases": ["Alias1", "Apodo"],
      "especie": "Especie / Raza (ej. Elfo, Humano, etc.)",
      "clase": "Clase (ej. Paladín, Pícaro, Mago, Guerrero, etc. - NUNCA 'Dungeon Master')",
      "subclase": "Subclase (o '-' si aún no se menciona)",
      "debut_sesion": {session_number},
      "hitos_acumulados": ["Sesión #{session_number}: Logro o acción ficticia in-world principal"],
      "rol_en_sesion": "Resumen de exactamente 1 oración sobre sus acciones ficticias in-character, decisiones o logros dentro del mundo en este episodio."
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
      "name": "Nombre canónico del PNJ, Aliado, Invocación o Monstruo (ej. 'Halsey', 'Hermana Lenure / Garael', 'Kira / Kirrel', 'Búho de Zafkiel', 'Espíritu Celestial', 'Barlgura')",
      "aliases": ["Variante Fonética 1", "Apodo"],
      "role": "Rol, ocupación o procedencia exacta (ej. 'Guerrera/Bárbara aliada', 'Corcel terrestre convocado por Sir Yato (Find Steed)', 'Familiar aéreo de Zafkiel', 'Espíritu convocado por Hermana Lenure (Nivel 5)', 'Animal extraído del bolsito de trucos por Zafkiel', 'Demonio simio enemigo')",
      "category": "clave | aliado | invocacion | amenaza | interaccion_contexto",
      "tipo": "importantes | interaccion_contexto | mencionados",
      "status": "activo | herido | abatido | desvanecido",
      "notes": ["Sesión #{session_number}: Notas concretas de combate, conjuros, interacción, heridas o muerte"]
    }}
  ],
  "detected_npc_names": ["Lista", "De", "Nombres", "De", "PNJs", "Nuevos"],
  "locations": [
    {{
      "name": "Nombre de la ubicación o punto de interés",
      "type": "ciudad | mazmorra | punto_de_interes | region",
      "description": "Descripción concisa del lugar y lo acontecido allí en la sesión",
      "status": "explorado | en_progreso | destruido | no_visitado",
      "associated_characters": ["Nombre del personaje o PNJ"]
    }}
  ],
  "items": [
    {{
      "name": "Nombre del arma, artefacto o reliquia",
      "type": "arma | armadura | artefacto | consumible | reliquia | mision",
      "description": "Propiedades, efecto o importancia del objeto",
      "holder": "Nombre del personaje o PNJ que lo porta o custodia",
      "status": "equipado | en_posesion | perdido | consumido | entregado"
    }}
  ]
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
GENERAL DIRECTIVE ON PHONETICS, LOANWORDS & ZERO HALLUCINATIONS:
- The primary audio was spoken in its detected language, but speakers frequently introduce technical terms, author names, programming libraries, methodologies, or acronyms in English or foreign languages with regional accents or non-native pronunciation.
- Whisper transcribes sounds phonetically. Recognize the true canonical technical/academic meaning of these spoken terms instead of inventing phantom words or misattributing sounds.
- Preserve standard technical nomenclature in its original canonical form (e.g., 'Random Forest', 'Trade-off', 'Pipeline', 'Backpropagation', 'REST API', 'Deadlock') without awkward literal translations.
- ⚠️ STRICT ZERO-HALLUCINATION, SPEAKER ATTRIBUTION & TIMESTAMP DIRECTIVE:
  * Ground 100% of the content strictly in what is explicitly spoken in the transcript.
  * STRICTLY FORBIDDEN to invent philosophical doctrines, religious texts (e.g. Bhagavad Gita, Karma), external business examples, fictitious timelines, or quotes not present in the transcript.
  * If a concept, equation, or assignment is NOT mentioned in the audio, DO NOT invent it.
  * SPEAKER ATTRIBUTION: Accurately distinguish who says what (e.g., host/interviewer introducing metrics in the opening vs. guest/speaker). Never attribute background or introductory facts to the main speaker or vice-versa.
  * TIMESTAMPS: Whenever timestamps (e.g. [mm:ss] or [hh:mm:ss]) appear in the transcript lines, include the exact timestamp [mm:ss] next to key claims, quantitative metrics, or major case studies so that every important assertion can be independently verified.
================================================================================
CRITICAL MATHEMATICAL & FORMULA FORMATTING DIRECTIVE:
- Use LaTeX delimiters ($...$ for inline or $$...$$ for display blocks) EXCLUSIVELY for genuine mathematical, physical, or chemical equations (e.g., $E = mc^2$, $\\Delta H = Q_p$, $\\sum_{{i=1}}^n x_i$, $\\int f(x)\\,dx$).
- STRICTLY FORBIDDEN: NEVER wrap optical magnifications, zoom levels, multipliers, scales, or camera settings in dollar signs (e.g. write '40x', '10x', '100x', '5x' directly as plain text, NEVER '$40x$' nor '$10x$').
- NEVER wrap plain numbers, percentages, physical dimensions, or single units in dollar signs (e.g. write '10 mm', '50%', '30 fps', NEVER '$10 mm$' nor '$50%$').
- When outputting formulas involving money, escape currency dollar signs inside math blocks (e.g., use '\\$1,000' or write 'USD 1,000') so they do not collide with LaTeX delimiters. Ensure equations are cleanly structured for KaTeX rendering.
================================================================================
CRITICAL DIAGRAMMING & TABLE DIRECTIVE:
Do NOT generate fragile ASCII text diagrams (boxes made of '+---+' or '|'). To represent comparisons, workflows, decision matrices, or state transitions, ALWAYS use native Markdown tables or structured step-by-step lists.
================================================================================
CRITICAL EXPLANATORY DIRECTIVE (WORK & STUDY):
Do NOT output lazy, shallow summaries or disconnected bullet points. Write a comprehensive, deeply explanatory narrative breakdown of the talk/lecture.
1. Introduction & Context: Outline the speaker's main thesis, context, and core argument.
2. Thematic Walkthrough: Explain each topic covered in logical progression. You MUST retain and fully explain all real-world examples, case studies, technical analogies, and edge cases shared by the speaker.
3. Key Takeaways & Data Points (In Section 5): Reserve concise bullet points strictly for Section 5: specific dates, metrics, tools mentioned, and review questions.
================================================================================

Structure the guide into the following sections:

# 🎓 EXECUTIVE BRIEFING & DEEP STUDY GUIDE: {subj}
## 📌 Topic: {top}

---

# 1. Introduction & Context
- Comprehensive narrative outlining the speaker's main thesis, background context, core problem being addressed, and primary thesis.

# 2. Fundamental Theoretical Concepts & Glossary
### 📖 Conceptual Glossary
- **[Term / Concept]**: Concise, clear, and precise technical definition explaining what it means in this context.
(Define ONLY terms that were actually discussed or introduced in the lecture. There is NO minimum or maximum: include all and only the terms mentioned, whether 0 or many. If no distinct technical terms were introduced, write: "No new specialized terms introduced in this session.")

### 🛠️ Key Techniques, Procedures & Methods
- **[Technique or Method]**: When to use it, how to apply it step-by-step, and expected outcome or diagnostic criteria.
(Document only techniques and methods actually discussed by the speaker).

# 3. Thematic Walkthrough & Deep Explanations
- Detailed walkthrough of each topic in logical progression.
- Retain and fully explain every real-world example, case study, technical analogy, equation, physical law, or algorithm shared.
- Explicitly document edge cases, limitations, and nuances emphasized by the speaker.

# 4. Solved Examples & Practical Applications
- Detailed breakdown of practical exercises, case studies, code patterns, or real-world dilemmas discussed, including problem statement, methodology, steps, and resolution.
- If no practical exercises or solved examples were conducted, write: "No practical exercises or numerical examples were covered in this session."

# 5. Key Takeaways, Metrics & Concluding Actions
- Reserve concise bullet points strictly for this section:
  * Key numerical metrics, benchmarks, and quantitative data points.
  * Tools, libraries, and frameworks mentioned.
  * 3 to 5 key conceptual review questions for exam or meeting retention.
- Note: This section must always be included. Do not append '(MANDATORY SECTION)' to the section heading.

# 6. Announcements, Deadlines & Deliverables
- If the lecture/meeting explicitly mentioned homework, problem sets, project deliverables, or exam dates, list them with clear requirements and deadlines.
- If NO formal assignments, homework, or exam dates were mentioned in the audio, OMIT this Section 6 entirely so the document concludes cleanly at Section 5. Do not append '(STRICTLY CONDITIONAL)' to the section heading.

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
DIRECTIVA GENERAL DE FONÉTICA, PRÉSTAMOS LINGÜÍSTICOS Y CERO ALUCINACIONES:
- El audio se desarrolla en el idioma detectado, pero los expositores frecuentemente mencionan términos técnicos, nombres de autores, librerías, metodologías, herramientas o acrónimos en inglés u otros idiomas con acentos locales o pronunciación no nativa.
- Whisper transcribe interpretando sonidos fonéticamente. Reconoce e interpreta el significado canónico y técnico real de dichos términos en lugar de transcribir errores fonéticos o inventar términos inexistentes.
- Preserva la terminología técnica estándar en su grafía canónica original (ej. 'Random Forest', 'Gradient Descent', 'Trade-off', 'Pipeline', 'Backpropagation', 'REST API', 'Deadlock', 'Overfitting') sin forzar traducciones ortopédicas.
- ⚠️ REGLA ESTRICTA DE CERO ALUCINACIONES, ATRIBUCIÓN Y MARCAS DE TIEMPO:
  * Fundamenta el 100% del contenido estrictamente en lo verbalizado en la transcripción.
  * QUEDA ESTRICTAMENTE PROHIBIDO inventar doctrinas filosóficas o religiosas (ej. Karma-Phala, Bhagavad Gita), citas externas, anécdotas ajenas, o ejemplos no mencionados en el audio.
  * Si un concepto, fórmula, tarea o fecha NO fue mencionado por el expositor, PROHIBIDO inventarlo para rellenar secciones.
  * ATRIBUCIÓN DE HABLANTES: Distingue con rigor quién dice cada dato (ej. presentadora o anfitriona en la introducción vs. expositor o invitado). No atribuyas cifras de la apertura al invitado ni viceversa.
  * MARCAS DE TIEMPO: Siempre que la transcripción contenga marcas de tiempo (ej. [mm:ss] o [hh:mm:ss]), incluye la marca de tiempo exacta [mm:ss] junto a las afirmaciones centrales, métricas cuantitativas y casos de estudio para permitir su verificación inmediata.
================================================================================
DIRECTIVA CRÍTICA DE FORMATEO MATEMÁTICO Y FÓRMULAS:
- Utiliza delimitadores de LaTeX ($...$ para fórmulas en línea o $$...$$ para bloques destacados) EXCLUSIVAMENTE para ecuaciones matemáticas, físicas, químicas o algebraicas reales (ej. $E = mc^2$, $\\Delta H = Q_p$, $\\sum_{{i=1}}^n x_i$, $\\int f(x)\\,dx$).
- QUEDA ESTRICTAMENTE PROHIBIDO encerrar aumentos ópticos, niveles de zoom, escalas o multiplicadores entre signos de dólar (por ejemplo, escribe '40x', '10x', '100x', '5x' directamente como texto simple, NUNCA '$40x$' ni '$10x$').
- NUNCA coloques signos de dólar alrededor de números simples, porcentajes, dimensiones físicas o unidades (por ejemplo, escribe '10 mm', '50%', '30 fps', '40 aumentos', NUNCA '$10 mm$' ni '$50%$').
- Al generar fórmulas que involucren dinero, escapa los símbolos de moneda para no romper KaTeX (usa '\\$1,000' o escribe 'USD 1,000').
================================================================================
DIRECTIVA CRÍTICA DE DIAGRAMAS Y TABLAS:
Queda estrictamente PROHIBIDO generar diagramas frágiles en texto ASCII (cajas compuestas por '+---+' o '|'). Para representar comparaciones, flujos de trabajo, matrices de decisión o transiciones de estado, utiliza SIEMPRE tablas nativas en Markdown (| Columna 1 | Columna 2 |) o listas estructuradas paso a paso.
================================================================================
DIRECTIVA CRÍTICA DE PROFUNDIDAD EXPLICATIVA (WORK & STUDY):
NO generes resúmenes superficiales, perezosos ni listas de viñetas desconectadas. Escribe un desglose narrativo exhaustivo, profundo y detallado de la exposición/clase/reunión.
1. Introducción y Contexto: Sintetiza la tesis central del expositor, el contexto de fondo y su argumento rector.
2. Recorrido Temático Detallado: Explica cada tema tratado en rigurosa progresión lógica. DEBES conservar y explicar a fondo todos los ejemplos del mundo real, casos de estudio, analogías técnicas y casos extremos (edge cases) mencionados por el expositor.
3. Conclusiones Clave, Datos y Acciones (En la Sección 5): Reserva las viñetas concisas para la Sección 5: fechas exactas, métricas, herramientas mencionadas y preguntas de repaso.
================================================================================

Estructura la respuesta en las siguientes secciones:

# 🎓 BRIEFING EJECUTIVO Y GUÍA DE ESTUDIO PROFUNDA: {subj}
## 📌 Tema: {top}

---

# 1. Introducción y Contexto
- Desglose narrativo profundo que sintetiza la tesis central del expositor, el contexto de fondo, la problemática analizada y los objetivos pedagógicos o estratégicos.

# 2. Conceptos Teóricos Fundamentales y Glosario
### 📖 Glosario Conceptual
- **[Término o Concepto]**: Definición técnica concisa, clara y precisa de su significado exacto en este contexto.
(Define ÚNICAMENTE los términos que hayan sido efectivamente tratados o explicados en la clase. La cantidad es totalmente flexible: incluye todos y solo los que se hayan mencionado, sean 0 o muchos, SIN mínimos ni máximos forzados. Si no se introdujeron términos técnicos especializados, escribe: "No se introdujeron términos especializados nuevos en esta sesión").

### 🛠️ Técnicas, Métodos y Cuándo se Usan
- **[Técnica o Método]**: Cuándo se utiliza, cómo se aplica paso a paso y qué criterio o resultado produce.
(Documenta únicamente las técnicas o métodos realmente explicados por el expositor).

# 3. Recorrido Temático Detallado y Explicaciones Profundas
- Explicación estructurada de cada tema en progresión lógica.
- Conserva y explica a fondo todos los ejemplos reales, casos de estudio, analogías técnicas, leyes, algoritmos o métodos paso a paso presentados.
- Documenta detalladamente los casos extremos (edge cases), limitaciones y advertencias enfatizadas por el expositor.

# 4. Ejemplos Resueltos y Casos Prácticos
- Desglose exhaustivo de los problemas prácticos, ejercicios o casos de negocio discutidos durante la sesión, detallando su planteamiento, desarrollo analítico paso a paso y conclusión.
- Si en la sesión no se realizaron ejercicios prácticos o casos numéricos, indica: "No se desarrollaron ejercicios prácticos ni problemas resueltos en esta sesión."

# 5. Conclusiones Clave, Métricas y Acciones
- Reserva las viñetas concisas para esta sección:
  * Métricas numéricas clave, benchmarks y datos cuantitativos específicos.
  * Herramientas, software, librerías o normativas citadas.
  * 3 a 5 preguntas de repaso conceptual o práctico para autoevaluación o preparación de exámenes.
- Nota: Esta sección debe incluirse siempre. No agregues '(SECCIÓN OBLIGATORIA)' al título del encabezado.

# 6. Avisos Relevantes, Tareas y Entregables
- Si en la clase o reunión se mencionaron tareas obligatorias, lecturas asignadas, proyectos o fechas de exámenes, detállalos aquí con claridad, requisitos y plazos.
- Si NO se anunciaron tareas, compromisos formales ni fechas límite en el audio, OMITE la Sección 6 por completo para que el documento concluya limpiamente en la Sección 5. No agregues '(ESTRICTAMENTE CONDICIONAL)' al título del encabezado.

---

TRANSCRIPCIÓN DE LA CLASE / REUNIÓN:
{transcript_text}
"""
