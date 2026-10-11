"""Gemini TTRPG Summarizer client for D&D session chronicles."""

import os
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


from src.summarizer.prompts import (
    build_continuity_session_prompt,
    build_academic_lecture_prompt,
)
import json
import re


def normalize_academic_sections(md: str) -> str:
    """
    Ensure correct ordering and numbering of Academic Study Guide sections:
    - Cleans non-formula dollar signs ($40x$, $10x$, $50%, etc.).
    - Section 5 MUST ALWAYS be 'Conclusiones Clave, Métricas y Acciones' (or Key Takeaways).
    - Section 6 is STRICTLY CONDITIONAL: 'Avisos Relevantes, Tareas y Entregables' (or Announcements).
    - If Section 5 is Tasks and Section 6 is Conclusions: swaps them.
    - If Section 6 is Conclusions and Section 5 was skipped (jumped from 4 to 6): renumbers Section 6 to Section 5.
    - If Tasks/Announcements section is empty or states no tasks exist: omits it cleanly.
    """
    if not md:
        return ""

    # 1. Clean non-formula dollar signs like $40x$, $10x$, $50%$
    cleaned = re.sub(r'\$\s*([0-9]+(?:\.[0-9]+)?\s*[xX])\s*\$', r'\1', md)
    cleaned = re.sub(r'\$\s*([0-9]+(?:\.[0-9]+)?\s*(?:%|mm|cm|m|km|g|kg|mg|ml|mL|L|fps|rpm|Hz|kHz|MHz|GHz))\s*\$', r'\1', cleaned)
    # Strip prompt template tags from headings (e.g. '(MANDATORY SECTION)', '(SECCIÓN OBLIGATORIA)', etc.)
    cleaned = re.sub(r'\s*\((?:MANDATORY SECTION|SECCIÓN OBLIGATORIA|STRICTLY CONDITIONAL|ESTRICTAMENTE CONDICIONAL|Correct|Obligatoria|Condicional)\)', '', cleaned, flags=re.IGNORECASE)

    concl_pat = r'(?:Conclusiones|Key Takeaways|Takeaways|Métricas|Metrics|Acciones y Conclusiones|Resumen Final)'
    tasks_pat = r'(?:Avisos|Tareas|Entregables|Compromisos|Próximos Pasos|Announcements|Deadlines|Deliverables|Action Items)'

    sec_blocks = list(re.finditer(r'(?m)^(#{1,2}\s*(\d)\.\s*([^\n]+))\n([\s\S]*?)(?=(?:^#{1,2}\s*\d\.|\Z))', cleaned))

    sec5_match = None
    sec6_match = None

    for m in sec_blocks:
        num = m.group(2)
        if num == '5':
            sec5_match = m
        elif num == '6':
            sec6_match = m

    def is_empty_tasks(body: str) -> bool:
        lines = [l.strip() for l in body.split('\n') if l.strip()]
        if not lines:
            return True
        first_few = ' '.join(lines[:3]).lower()
        return any(neg in first_few for neg in [
            'no se anunciaron', 'no se mencionaron', 'no hay tareas', 'no se asignaron',
            'ninguna tarea', 'ningún aviso', 'no formal assignments', 'none', 'no hay entregables',
            'no se establecieron'
        ])

    if sec5_match and sec6_match:
        sec5_title = sec5_match.group(3)
        sec5_body = sec5_match.group(4)
        sec6_title = sec6_match.group(3)
        sec6_body = sec6_match.group(4)

        sec5_is_tasks = bool(re.search(tasks_pat, sec5_title, re.I))
        sec5_is_concl = bool(re.search(concl_pat, sec5_title, re.I))
        sec6_is_tasks = bool(re.search(tasks_pat, sec6_title, re.I))
        sec6_is_concl = bool(re.search(concl_pat, sec6_title, re.I))

        if sec5_is_tasks and sec6_is_concl:
            clean_sec5_title = re.sub(r'^(?:5|6)\.\s*', '', sec6_title).strip()
            clean_sec6_title = re.sub(r'^(?:5|6)\.\s*', '', sec5_title).strip()
            new_sec5 = f"# 5. {clean_sec5_title}\n{sec6_body.strip()}\n\n"
            
            if is_empty_tasks(sec5_body):
                new_sec6 = ""
            else:
                new_sec6 = f"# 6. {clean_sec6_title}\n{sec5_body.strip()}\n\n"

            start_pos = sec5_match.start()
            end_pos = sec6_match.end()
            cleaned = cleaned[:start_pos] + new_sec5 + new_sec6 + cleaned[end_pos:]

        elif sec5_is_concl and sec6_is_tasks:
            if is_empty_tasks(sec6_body):
                cleaned = cleaned[:sec6_match.start()].rstrip() + '\n'

    elif not sec5_match and sec6_match:
        sec6_title = sec6_match.group(3)
        sec6_body = sec6_match.group(4)
        clean_title = re.sub(r'^(?:5|6)\.\s*', '', sec6_title).strip()
        start_pos = sec6_match.start()
        end_pos = sec6_match.end()
        new_sec5 = f"# 5. {clean_title}\n{sec6_body.strip()}\n\n"
        cleaned = cleaned[:start_pos] + new_sec5 + cleaned[end_pos:]

    return cleaned.strip() + '\n'


class GeminiTTRPGSummarizer:
    """Client for generating D&D session chronicles using Gemini API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "GEMINI_API_KEY no está configurada. "
                    "Por favor añade tu clave de API en el archivo .env o en el formulario."
                )
            try:
                from google import genai
            except ImportError as exc:
                raise ImportError(
                    "google-genai no está instalado. Ejecuta 'pip install google-genai'."
                ) from exc

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    @staticmethod
    def format_roster(roster: List[Dict[str, str]]) -> str:
        """Format the player roster list into a clean Markdown block."""
        if not roster:
            return "- (Mesa general sin personajes especificados)"
        lines = []
        for p in roster:
            player = p.get("player_name", "Desconocido").strip()
            role = p.get("role", "Aventurero").strip()
            character = p.get("character_name", "-").strip()
            species = p.get("species", "").strip()
            subclass = p.get("subclass", "").strip()
            species_str = f" | Especie: {species}" if species and species not in ("(N/A - DM)", "N/A", "N/A - DM") else ""
            subclass_str = f" ({subclass})" if subclass and subclass not in ("N/A", "(N/A)", "-") else ""
            is_absent = bool(p.get("is_absent"))
            absent_str = " | [ESTADO EN ESTA SESIÓN: AUSENTE / NO ASISTIÓ HOY - El jugador faltó a esta sesión. El personaje permanece con la compañía en segundo plano; NO lo elimines de la tabla de aventureros ni inventes que murió o abandonó la campaña, simplemente no participó activamente en los combates ni diálogos de este episodio]" if is_absent else ""
            lines.append(f"- Jugador: {player} | Personaje: {character}{species_str} | Clase/Rol: {role}{subclass_str}{absent_str}")
        return "\n".join(lines)

    @staticmethod
    def check_has_user_character(roster: Optional[List[Dict[str, Any]]]) -> bool:
        """Check if the roster has a character marked as the user's character (is_user_character: true)."""
        if not roster:
            return False
        for p in roster:
            if p.get("is_user_character"):
                return True
        return False

    @staticmethod
    def check_has_markus(roster: Optional[List[Dict[str, Any]]]) -> bool:
        """Check if roster has Markus Veyl or any character marked as user character."""
        if not roster:
            return False
        if GeminiTTRPGSummarizer.check_has_user_character(roster):
            return True
        return any(
            "markus" in str(p.get("character_name", "")).lower()
            or "markus" in str(p.get("player_name", "")).lower()
            for p in roster
        )

    def _generate_with_retry(self, contents: Any, config: Any = None) -> str:
        """
        Executes generate_content with automatic retries on 503 UNAVAILABLE / 429 RESOURCE_EXHAUSTED
        and seamless fallback to next available active models:
        [self.model_name, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        """
        candidate_models = [
            self.model_name,
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash",
        ]
        models_to_try = []
        for m in candidate_models:
            if m and m not in models_to_try:
                models_to_try.append(m)

        last_error = None
        for model in models_to_try:
            for attempt in range(3):
                try:
                    kwargs = {"model": model, "contents": contents}
                    if config is not None:
                        kwargs["config"] = config
                    response = self.client.models.generate_content(**kwargs)
                    if response and response.text:
                        return response.text
                except Exception as exc:
                    last_error = exc
                    err_msg = str(exc)
                    if "API_KEY_INVALID" in err_msg or "PERMISSION_DENIED" in err_msg:
                        raise ValueError(f"Error de autenticación con Gemini API: {err_msg}") from exc
                    if "503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    break

        raise RuntimeError(f"Error al generar con Gemini tras reintentos y modelos alternativos: {last_error}") from last_error


    def generate_academic_notes(
        self,
        transcript_text: str,
        subject: str = "Materia Universitaria",
        topic: str = "Tema de Clase",
        date_str: Optional[str] = None,
        target_language: str = "es",
    ) -> str:
        """
        Generate a structured Academic Study Guide from a university lecture transcript:
        1. Resumen de la Clase
        2. Conceptos Teóricos Fundamentales y Glosario
        3. Recorrido Temático Detallado y Explicaciones Profundas
        4. Ejemplos Resueltos en Clase y Casos Prácticos
        5. Conclusiones Clave, Métricas y Acciones
        6. Avisos Relevantes y Fechas Clave (Estrictamente condicional)

        :param transcript_text: Full speech-to-text transcript of the lecture.
        :param subject: Course / Subject title (e.g. 'Sistemas de Control').
        :param topic: Class topic (e.g. 'Funciones de Transferencia').
        :param date_str: Optional lecture date string.
        :param target_language: Target output language ('es' or 'en').
        :return: Formatted Markdown Academic Study Guide.
        """
        if not transcript_text or not transcript_text.strip():
            return "No hay transcripción de audio disponible para generar la guía de estudio."

        prompt = build_academic_lecture_prompt(
            subject=subject,
            topic=topic,
            transcript_text=transcript_text,
            date_str=date_str,
            target_language=target_language,
        )

        generation_config = {
            "temperature": 0.0,
            "top_p": 0.95,
        }
        raw_notes = self._generate_with_retry(prompt, config=generation_config)
        notes_md = normalize_academic_sections(raw_notes)
        if transcript_text and transcript_text.strip() and "# 📝" not in notes_md and "Transcripción" not in notes_md:
            is_en = str(target_language).lower().startswith("en")
            transcript_header = (
                "\n\n---\n\n# 📝 Complete Audio Transcript\n\n"
                if is_en
                else "\n\n---\n\n# 📝 Transcripción Completa del Audio\n\n"
            )
            notes_md = f"{notes_md.rstrip()}{transcript_header}{transcript_text.strip()}\n"
        return notes_md

    def generate_campaign_session(
        self,
        transcript_text: str,
        roster: List[Dict[str, str]],
        existing_quests: Optional[List[Dict[str, Any]]] = None,
        known_npcs: Optional[List[Dict[str, Any]]] = None,
        session_number: int = 1,
        target_language: str = "es",
        user_character: Optional[Dict[str, Any]] = None,
        is_youtube: bool = False,
        prior_lore: Optional[str] = None,
        character_backstory: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured session chapter and cumulative updates for Living Campaign Journal.
        Returns parsed dictionary with keys: session_chapter, detected_pcs, detected_party, updated_quests, updated_npcs, detected_npc_names.
        """
        if not transcript_text or not transcript_text.strip():
            return {
                "session_chapter": {
                    "title": f"Sesión #{session_number}",
                    "recap_text": "",
                    "next_session_script": "",
                    "episode_synopsis": "",
                    "chronicle_text": "No hay transcripción disponible.",
                    "closing_expectations": "",
                    "user_coaching": "",
                    "markus_coaching": "",
                },
                "detected_pcs": [],
                "detected_party": [],
                "updated_quests": [],
                "updated_npcs": [],
                "detected_npc_names": [],
            }

        roster_formatted = self.format_roster(roster)
        has_markus = self.check_has_user_character(roster)
        prompt = build_continuity_session_prompt(
            roster_formatted=roster_formatted,
            existing_quests=existing_quests or [],
            known_npcs=known_npcs or [],
            transcript_text=transcript_text,
            session_number=session_number,
            has_markus=has_markus,
            target_language=target_language,
            user_character=user_character,
            is_youtube=is_youtube,
            prior_lore=prior_lore,
            character_backstory=character_backstory,
        )

        campaign_temperature = 0.1 if is_youtube else 0.2
        generation_config = {
            "temperature": campaign_temperature,
            "top_p": 0.95,
            "response_mime_type": "application/json",
        }

        raw_text = self._generate_with_retry(prompt, config=generation_config)
        return self.parse_json_response(raw_text, session_number)

    @staticmethod
    def sanitize_raw_json(raw_text: str) -> str:
        """
        Sanitize raw JSON string from LLMs:
        - Strip markdown fences
        - Trim whitespace and backticks
        """
        clean_text = raw_text.strip()
        clean_text = re.sub(r"^```json\s*", "", clean_text, flags=re.MULTILINE)
        clean_text = re.sub(r"^```\s*", "", clean_text, flags=re.MULTILINE)
        clean_text = clean_text.strip("` \n")
        return clean_text

    @staticmethod
    def parse_json_response(raw_text: str, session_number: int) -> Dict[str, Any]:
        """
        Safely parse JSON response from Gemini, handling markdown code fences,
        unescaped internal quotes (via json_repair), normalizing detected_pcs
        and detected_party, and parsing episode_synopsis.
        """
        clean_text = GeminiTTRPGSummarizer.sanitize_raw_json(raw_text)

        data = None
        # 1. Standard json.loads
        try:
            data = json.loads(clean_text)
        except Exception:
            data = None

        # 2. json_repair library (specifically repairs unescaped interior quotes, trailing commas, etc.)
        if data is None:
            try:
                import json_repair
                repaired = json_repair.loads(clean_text)
                if isinstance(repaired, dict):
                    data = repaired
                elif isinstance(repaired, str):
                    try:
                        data = json.loads(repaired)
                    except Exception:
                        pass
            except Exception as repair_err:
                print(f"[Gemini] json_repair error: {repair_err}")
                data = None

        # 3. Outer braces extraction + standard or json_repair
        if data is None:
            match = re.search(r"(\{.*\})", clean_text, flags=re.DOTALL)
            if match:
                candidate = match.group(1)
                try:
                    data = json.loads(candidate)
                except Exception:
                    try:
                        import json_repair
                        repaired = json_repair.loads(candidate)
                        if isinstance(repaired, dict):
                            data = repaired
                    except Exception:
                        data = None

        if data is None:
            print(f"[Gemini] JSON parsing error after all repair attempts. Raw text snippet: {clean_text[:500]}")

        if isinstance(data, dict):
            # Ensure all expected top-level keys exist (support nested session_chapter or flat keys)
            chapter = data.get("session_chapter")
            if not isinstance(chapter, dict):
                if "chronicle_text" in data or "recap_text" in data or "next_session_script" in data or "episode_synopsis" in data or "title" in data:
                    chapter = {
                        "title": data.get("title", f"Sesión #{session_number}"),
                        "recap_text": data.get("next_session_script") or data.get("recap_text", ""),
                        "next_session_script": data.get("next_session_script") or data.get("recap_text", ""),
                        "episode_synopsis": data.get("episode_synopsis", ""),
                        "chronicle_text": data.get("chronicle_text", ""),
                        "closing_expectations": data.get("closing_expectations", ""),
                        "user_coaching": data.get("user_coaching") or data.get("markus_coaching", ""),
                        "markus_coaching": data.get("user_coaching") or data.get("markus_coaching", ""),
                    }
                else:
                    chapter = {}

            recap = (chapter.get("next_session_script") or chapter.get("recap_text") or "").strip()
            synopsis = (chapter.get("episode_synopsis") or data.get("episode_synopsis") or "").strip()
            coaching = (chapter.get("user_coaching") or chapter.get("markus_coaching") or "").strip()

            # Normalize detected PCs / party members
            raw_pcs = data.get("detected_pcs")
            if not raw_pcs or not isinstance(raw_pcs, list):
                raw_pcs = data.get("detected_party") if isinstance(data.get("detected_party"), list) else []

            normalized_pcs = []
            normalized_party = []
            for p in raw_pcs:
                if not isinstance(p, dict):
                    continue
                player = (p.get("jugador") or p.get("player_name") or p.get("player") or "-").strip()
                char = (p.get("personaje") or p.get("character_name") or p.get("character") or p.get("name") or "-").strip()
                species = (p.get("especie") or p.get("species") or p.get("race") or "-").strip()
                cls = (p.get("clase") or p.get("role") or p.get("class") or "-").strip()
                subcls = (p.get("subclase") or p.get("subclass") or "-").strip()
                session_role = (
                    p.get("rol_en_sesion")
                    or p.get("session_role")
                    or p.get("rol_sesion")
                    or p.get("resumen_rol")
                    or "-"
                ).strip()

                debut = p.get("debut_sesion") or p.get("primera_aparicion_sesion") or session_number
                hitos = p.get("hitos_acumulados") or []
                if isinstance(hitos, str):
                    hitos = [hitos]
                elif not isinstance(hitos, list):
                    hitos = []

                # Hard DM Exclusion: DM is strictly narrator/referee, never a PC card
                char_lower = char.lower()
                if not char or char in ("-", "(N/A)", "N/A") or char_lower in ("dm", "(dm)", "dungeon master", "(dungeon master)", "el dm", "master", "narrador"):
                    continue
                if "dungeon master" in char_lower and len(char) <= 18:
                    continue

                # Mutual Exclusivity: A character can never have class "Dungeon Master"
                if cls.lower() in ("dungeon master", "dm", "dungeon master (dm)", "narrador", "master", "árbitro"):
                    cls = "-"

                # Strip out-of-character meta phrases from session role
                for meta_phrase in ("actuó como dungeon master", "actuo como dungeon master", "controló los pnjs", "controlo los pnjs", "dirigió la sesión", "dirigio la sesion", "tiró dados", "tiro dados"):
                    if meta_phrase in session_role.lower():
                        session_role = "-"
                        break

                clean_hitos = []
                for h in hitos:
                    h_lower = str(h).lower()
                    if any(mp in h_lower for mp in ("dungeon master", "controló los pnjs", "controlo los pnjs", "dirigió la sesión", "dirigio la sesion")):
                        continue
                    clean_hitos.append(h)

                pc_aliases = [str(a).strip() for a in (p.get("aliases") or []) if str(a).strip()]
                normalized_pcs.append({
                    "jugador": player,
                    "personaje": char,
                    "aliases": pc_aliases,
                    "especie": species,
                    "clase": cls,
                    "subclase": subcls,
                    "debut_sesion": debut,
                    "hitos_acumulados": clean_hitos,
                    "rol_en_sesion": session_role,
                })
                normalized_party.append({
                    "player_name": player,
                    "character_name": char,
                    "aliases": pc_aliases,
                    "species": species,
                    "role": cls,
                    "subclass": subcls,
                    "debut_sesion": debut,
                    "hitos_acumulados": clean_hitos,
                    "session_role": session_role,
                })

            # Normalize quests (4 Tiers: principal, secundaria, opcional, misterios_abiertos)
            raw_quests = data.get("updated_quests", []) if isinstance(data.get("updated_quests"), list) else []
            normalized_quests = []
            for q_idx, q in enumerate(raw_quests, 1):
                if not isinstance(q, dict):
                    continue
                q_raw_tipo = str(q.get("tipo") or q.get("type") or "principal").lower().strip()
                if q_raw_tipo in ("misterios_abiertos", "misterio", "misterios"):
                    q_tipo = "misterios_abiertos"
                elif q_raw_tipo in ("secundaria", "secundario"):
                    q_tipo = "secundaria"
                elif q_raw_tipo in ("opcional", "opcionales"):
                    q_tipo = "opcional"
                else:
                    q_tipo = "principal"

                subobjs = []
                for s_idx, s in enumerate(q.get("subobjectives", []), 1):
                    if isinstance(s, dict):
                        subobjs.append({
                            "id": s.get("id") or f"s{s_idx}",
                            "text": s.get("text") or s.get("name") or "",
                            "completed": bool(s.get("completed", False)),
                        })
                    elif isinstance(s, str):
                        subobjs.append({
                            "id": f"s{s_idx}",
                            "text": s,
                            "completed": False,
                        })
                normalized_quests.append({
                    "id": q.get("id") or f"q{q_idx}",
                    "title": q.get("title", ""),
                    "tipo": q_tipo,
                    "context": q.get("context", ""),
                    "status": q.get("status", "in_progress"),
                    "subobjectives": subobjs,
                })

            # Normalize NPCs (3 Tiers: importantes, interaccion_contexto, mencionados)
            raw_npcs = data.get("updated_npcs", []) if isinstance(data.get("updated_npcs"), list) else []
            normalized_npcs = []
            for n in raw_npcs:
                if not isinstance(n, dict):
                    continue
                name = (n.get("name") or n.get("nombre") or "").strip()
                if not name:
                    continue
                n_raw_tipo = str(n.get("tipo") or n.get("type") or "").lower().strip()
                if n_raw_tipo in ("importantes", "importante", "principal", "clave"):
                    n_tipo = "importantes"
                elif n_raw_tipo in ("mencionados", "mencionado", "rumor") or "[mencionado" in str(n.get("role", "")).lower() or "mencionado" in str(n.get("notes", "")).lower():
                    n_tipo = "mencionados"
                else:
                    n_tipo = "interaccion_contexto"

                notes = n.get("notes") or []
                if isinstance(notes, str):
                    notes = [notes]
                elif not isinstance(notes, list):
                    notes = []
                npc_aliases = [str(a).strip() for a in (n.get("aliases") or []) if str(a).strip()]
                normalized_npcs.append({
                    "name": name,
                    "aliases": npc_aliases,
                    "role": n.get("role", "Desconocido / PNJ"),
                    "tipo": n_tipo,
                    "notes": notes,
                })

            # Normalize Locations
            raw_locations = data.get("locations", []) if isinstance(data.get("locations"), list) else []
            normalized_locations = []
            for loc in raw_locations:
                if not isinstance(loc, dict):
                    continue
                loc_name = str(loc.get("name") or loc.get("nombre") or "").strip()
                if not loc_name:
                    continue
                assoc = loc.get("associated_characters") or loc.get("personajes_asociados") or []
                if isinstance(assoc, str):
                    assoc = [a.strip() for a in assoc.split(",") if a.strip()]
                elif not isinstance(assoc, list):
                    assoc = []
                normalized_locations.append({
                    "name": loc_name,
                    "type": str(loc.get("type") or loc.get("tipo") or "punto_de_interes").strip(),
                    "description": str(loc.get("description") or loc.get("descripcion") or loc.get("context") or "").strip(),
                    "status": str(loc.get("status") or loc.get("estado") or "explorado").strip(),
                    "associated_characters": [str(a).strip() for a in assoc if str(a).strip()],
                })

            # Normalize Items
            raw_items = data.get("items", []) if isinstance(data.get("items"), list) else []
            normalized_items = []
            for it in raw_items:
                if not isinstance(it, dict):
                    continue
                it_name = str(it.get("name") or it.get("nombre") or "").strip()
                if not it_name:
                    continue
                normalized_items.append({
                    "name": it_name,
                    "type": str(it.get("type") or it.get("tipo") or "artefacto").strip(),
                    "description": str(it.get("description") or it.get("descripcion") or "").strip(),
                    "holder": str(it.get("holder") or it.get("portador") or it.get("poseedor") or "-").strip(),
                    "status": str(it.get("status") or it.get("estado") or "en_posesion").strip(),
                })

            return {
                "session_chapter": {
                    "title": chapter.get("title", f"Sesión #{session_number}"),
                    "recap_text": recap,
                    "next_session_script": recap,
                    "episode_synopsis": synopsis,
                    "chronicle_text": chapter.get("chronicle_text", ""),
                    "closing_expectations": chapter.get("closing_expectations", ""),
                    "user_coaching": coaching,
                    "markus_coaching": coaching,
                },
                "detected_pcs": normalized_pcs,
                "detected_party": normalized_party,
                "updated_quests": normalized_quests,
                "updated_npcs": normalized_npcs,
                "detected_npc_names": data.get("detected_npc_names", []) if isinstance(data.get("detected_npc_names"), list) else [],
                "locations": normalized_locations,
                "items": normalized_items,
            }

        # Fallback if text is not valid JSON
        return {
            "session_chapter": {
                "title": f"Sesión #{session_number}",
                "recap_text": "",
                "next_session_script": "",
                "episode_synopsis": "",
                "chronicle_text": raw_text,
                "closing_expectations": "",
                "user_coaching": "",
                "markus_coaching": "",
            },
            "detected_pcs": [],
            "detected_party": [],
            "updated_quests": [],
            "updated_npcs": [],
            "detected_npc_names": [],
            "locations": [],
            "items": [],
        }


check_has_markus = GeminiTTRPGSummarizer.check_has_markus
check_has_user_character = GeminiTTRPGSummarizer.check_has_user_character
