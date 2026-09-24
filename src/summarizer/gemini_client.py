"""Gemini TTRPG Summarizer client for D&D session chronicles."""

import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


from src.summarizer.prompts import (
    build_dnd_session_prompt,
    build_continuity_session_prompt,
    build_academic_lecture_prompt,
)
import json
import re


class GeminiTTRPGSummarizer:
    """Client for generating D&D session chronicles using Gemini API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
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
            lines.append(f"- Jugador: {player} | Personaje: {character}{species_str} | Clase/Rol: {role}{subclass_str}")
        return "\n".join(lines)

    @staticmethod
    def check_has_markus(roster: Optional[List[Dict[str, Any]]]) -> bool:
        """Check if Markus Veyl is present in the party roster."""
        if not roster:
            return False
        for p in roster:
            p_name = str(p.get("player_name", "")).lower()
            c_name = str(p.get("character_name", "")).lower()
            if "markus" in p_name or "markus" in c_name:
                return True
        return False

    def generate_chronicle(
        self,
        transcript_text: str,
        roster: List[Dict[str, str]],
        target_language: str = "es",
        session_number: int = 1,
        user_character: Optional[Dict[str, Any]] = None,
        is_youtube: bool = False,
    ) -> str:
        """
        Generate a D&D session report from transcription and party roster.

        :param transcript_text: The complete speech-to-text transcript.
        :param roster: List of dicts with keys player_name, role, character_name, species, subclass.
        :param target_language: Target output language ('es' or 'en').
        :param session_number: The current session number.
        :param user_character: Optional dict of the user's selected character for coaching.
        :param is_youtube: Whether this report comes from a YouTube video.
        :return: Formatted Markdown report.
        """
        if not transcript_text or not transcript_text.strip():
            return "No hay transcripción de audio disponible para generar la crónica."

        roster_formatted = self.format_roster(roster)
        has_markus = self.check_has_markus(roster)
        prompt = build_dnd_session_prompt(
            roster_formatted=roster_formatted,
            transcript_text=transcript_text,
            has_markus=has_markus,
            target_language=target_language,
            session_number=session_number,
            user_character=user_character,
            is_youtube=is_youtube,
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            return response.text or "No se pudo generar texto de la crónica."
        except Exception as exc:
            # Check for invalid API key or model error
            err_str = str(exc)
            if "API_KEY_INVALID" in err_str or "PERMISSION_DENIED" in err_str:
                raise ValueError(f"Error de autenticación con Gemini API: {err_str}") from exc
            # If primary model is unavailable (503/high demand) or not found (404), try reliable fallbacks
            for fb_model in ["gemini-3.6-flash", "gemini-flash-latest", "gemini-3.5-flash"]:
                if fb_model == self.model_name:
                    continue
                try:
                    fallback_response = self.client.models.generate_content(
                        model=fb_model,
                        contents=prompt,
                    )
                    if fallback_response.text:
                        return fallback_response.text
                except Exception:
                    pass
            raise RuntimeError(f"Error al generar la crónica con Gemini: {exc}") from exc

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
        2. Conceptos Teóricos Fundamentales
        3. Fórmulas, Ecuaciones y Procedimientos
        4. Ejemplos Resueltos en Clase
        5. Avisos Relevantes y Fechas Clave
        6. Guía de Estudio Rápida

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

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            return response.text or "No se pudo generar el texto de la guía académica."
        except Exception as exc:
            err_str = str(exc)
            if "API_KEY_INVALID" in err_str or "PERMISSION_DENIED" in err_str:
                raise ValueError(f"Error de autenticación con Gemini API: {err_str}") from exc
            for fb_model in ["gemini-3.6-flash", "gemini-flash-latest", "gemini-3.5-flash"]:
                if fb_model == self.model_name:
                    continue
                try:
                    fallback_response = self.client.models.generate_content(
                        model=fb_model,
                        contents=prompt,
                    )
                    if fallback_response.text:
                        return fallback_response.text
                except Exception:
                    pass
            raise RuntimeError(f"Error al generar la guía académica con Gemini: {exc}") from exc

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
        has_markus = self.check_has_markus(roster)
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
        )

        generation_config = {
            "temperature": 0.0,
            "top_p": 0.95,
            "response_mime_type": "application/json",
        }

        raw_text = ""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=generation_config,
            )
            raw_text = response.text or ""
        except Exception as exc:
            err_str = str(exc)
            if "API_KEY_INVALID" in err_str or "PERMISSION_DENIED" in err_str:
                raise ValueError(f"Error de autenticación con Gemini API: {err_str}") from exc
            for fb_model in ["gemini-3.6-flash", "gemini-flash-latest", "gemini-3.5-flash"]:
                if fb_model == self.model_name:
                    continue
                try:
                    fallback_response = self.client.models.generate_content(
                        model=fb_model,
                        contents=prompt,
                        config=generation_config,
                    )
                    raw_text = fallback_response.text or ""
                    if raw_text:
                        break
                except Exception:
                    pass
            if not raw_text:
                raise RuntimeError(f"Error al generar la sesión de campaña con Gemini: {exc}") from exc

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

                normalized_pcs.append({
                    "jugador": player,
                    "personaje": char,
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
                normalized_npcs.append({
                    "name": name,
                    "role": n.get("role", "Desconocido / PNJ"),
                    "tipo": n_tipo,
                    "notes": notes,
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
        }


check_has_markus = GeminiTTRPGSummarizer.check_has_markus
