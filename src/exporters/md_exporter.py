"""Markdown exporter for Living Campaign Journal."""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional


def sanitize_filename(name: str) -> str:
    """Convert name to safe filename."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name.strip())
    clean = re.sub(r"\s+", "_", clean)
    return clean or "Campana_Principal"


def export_living_journal_md(
    campaign_state: Dict[str, Any],
    output_path: Optional[str] = None,
) -> str:
    """
    Format and export the complete Living Campaign Journal into Markdown.
    Includes Master Quest Table, NPC Directory Table, and Chronological Session Chapters.

    :param campaign_state: Dict containing campaign metadata, quests, npcs, and sessions.
    :param output_path: Destination path. Defaults to data/output/<campaign_name>_Grimorio.md.
    :return: Absolute file path to the generated .md file.
    """
    campaign_name = campaign_state.get("campaign_name", "Campaña Principal")
    safe_name = sanitize_filename(campaign_name)

    if not output_path:
        out_dir = Path(os.environ["WHISPER_OUTPUT_DIR"]).resolve() if os.environ.get("WHISPER_OUTPUT_DIR") else (Path(__file__).resolve().parent.parent.parent / "data" / "output")
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = str((out_dir / f"{safe_name}_Grimorio.md").resolve())

    lines = []
    lines.append(f"# 📜 Grimorio de Campaña: {campaign_name}")
    lines.append(f"*Diario Vivo de Campaña &bull; Última Sesión: #{campaign_state.get('last_session', 0)} &bull; Actualizado: {campaign_state.get('updated_at', '')[:10]}*")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 1. Universal PC Directory (Directorio Universal de Aventureros)
    is_private = (campaign_name or "").strip().lower() in ("campaña principal", "campana principal")
    universal_pcs = campaign_state.get("universal_pcs", [])
    roster = campaign_state.get("roster", [])
    detected_pcs = campaign_state.get("detected_pcs", [])
    detected_party = campaign_state.get("detected_party", [])
    chosen_detected = detected_pcs or detected_party

    if not is_private and chosen_detected:
        if any("markus" in str(p.get("character_name", "")).lower() or "markus" in str(p.get("player_name", "")).lower() for p in roster):
            roster = chosen_detected

    display_party = chosen_detected if (not is_private and chosen_detected) else roster

    if universal_pcs:
        lines.append("## 🛡️ ZONA UNIVERSAL: Directorio Universal de Aventureros (PCs)")
        lines.append("")
        lines.append("| Personaje | Jugador | Especie / Raza | Clase | Subclase | Debut | Hitos Acumulados |")
        lines.append("|---|---|---|---|---|---|---|")
        for pc in universal_pcs:
            char_name = str(pc.get("personaje", "-")).strip()
            player = str(pc.get("jugador", "-")).strip()
            species = str(pc.get("especie", "-")).strip()
            role = str(pc.get("clase", "-")).strip()
            subclass = str(pc.get("subclase", "-")).strip()
            debut_n = pc.get("debut_sesion") or pc.get("primera_aparicion_sesion") or 1
            hitos = "<br>".join(pc.get("hitos_acumulados", [])) if pc.get("hitos_acumulados") else "-"
            lines.append(f"| **{char_name}** | {player} | {species} | {role} | {subclass} | Sesión #{debut_n} | {hitos} |")
        lines.append("")
    elif display_party:
        header_title = "## 👥 Compañía de Aventureros (Personajes Detectados en el Video)" if (not is_private and chosen_detected) else "## 👥 Compañía de Aventureros (Roster de la Mesa)"
        lines.append(header_title)
        lines.append("")
        lines.append("| Jugador | Personaje | Especie | Clase | Subclase |")
        lines.append("|---|---|---|---|---|")
        for p in display_party:
            player = (p.get("jugador") or p.get("player_name", "-") or "-").strip()
            char_name = (p.get("personaje") or p.get("character_name", "-") or "-").strip()
            species = (p.get("especie") or p.get("species", "-") or "-").strip()
            role = (p.get("clase") or p.get("role", "-") or "-").strip()
            subclass = (p.get("subclase") or p.get("subclass", "-") or "-").strip()
            lines.append(f"| {player} | {char_name} | {species} | {role} | {subclass} |")
        lines.append("")

    lines.append("---")
    lines.append("")

    # 2. Universal Zone: Master Quest Log (4 Tiers)
    quests = campaign_state.get("quests", [])
    lines.append("## 🗺️ ZONA UNIVERSAL: Registro Maestro de Misiones (Master Quest Log)")
    lines.append("")
    if not quests:
        lines.append("*Aún no hay misiones registradas en la campaña.*")
        lines.append("")
    else:
        for q in quests:
            status = q.get("status", "in_progress")
            status_badge = "🟢 EN PROGRESO" if status == "in_progress" else ("✅ COMPLETADA" if status == "completed" else "🔴 FALLIDA")
            tipo_val = str(q.get("tipo", "principal")).lower()
            if tipo_val == "secundaria":
                tipo_badge = "⚔️ Secundaria"
            elif tipo_val == "opcional":
                tipo_badge = "🧭 Opcional"
            elif tipo_val in ("misterios_abiertos", "misterio"):
                tipo_badge = "🔮 Misterios Abiertos"
            else:
                tipo_badge = "⭐ Principal"

            lines.append(f"### {q.get('title', 'Misión')} [{tipo_badge}] ({status_badge})")
            lines.append(f"- **ID:** `{q.get('id', '-')}` | **Nivel:** `{tipo_badge}`")
            if q.get("lifecycle_notes"):
                lines.append(f"- **Ciclo de Vida:** {q.get('lifecycle_notes')}")
            if q.get("context"):
                lines.append(f"- **Contexto:** {q.get('context')}")

            subobjectives = q.get("subobjectives", [])
            if subobjectives:
                lines.append("- **Objetivos:**")
                for sub in subobjectives:
                    check = "[x]" if sub.get("completed") else "[ ]"
                    lines.append(f"  - {check} {sub.get('text', '')}")
            lines.append("")

    lines.append("---")
    lines.append("")

    # 3. Universal Zone: NPC Directory (3 Tiers)
    npcs = campaign_state.get("npcs", [])
    lines.append("## 🎭 ZONA UNIVERSAL: Directorio Universal de Personajes (NPCs)")
    lines.append("")
    if not npcs:
        lines.append("*Aún no hay PNJs registrados en el directorio.*")
        lines.append("")
    else:
        lines.append("| Nombre del PNJ | Nivel / Tipo | Ocupación / Rol | Primera Aparición | Historial de Interacciones & Pistas |")
        lines.append("|---|---|---|---|---|")
        for n in npcs:
            name = n.get("name", "Desconocido")
            n_tipo = str(n.get("tipo", "interaccion_contexto")).lower()
            if n_tipo in ("importantes", "importante"):
                tipo_label = "👑 Clave / Importante"
            elif n_tipo in ("mencionados", "mencionado") or "[mencionado" in str(n.get("role", "")).lower():
                tipo_label = "📜 Mencionado"
            else:
                tipo_label = "⚔️ Interacción / Contexto"
            role = n.get("role", "PNJ")
            seen = f"Sesión #{n.get('first_seen_session', 1)}"
            notes = "<br>".join(n.get("notes", [])) if n.get("notes") else "-"
            lines.append(f"| **{name}** | {tipo_label} | {role} | {seen} | {notes} |")
        lines.append("")

    lines.append("---")
    lines.append("")

    # 4. Historical Zone: Chapters
    sessions = campaign_state.get("sessions", [])
    lines.append("## 📚 ZONA HISTÓRICA: Capítulos de Campaña")
    lines.append("")
    if not sessions:
        lines.append("*No se han registrado sesiones aún.*")
        lines.append("")
    else:
        # Guarantee strictly ONE chapter exists per session number (latest wins)
        unique_sessions = []
        seen_sessions = set()
        for s in reversed(sessions):
            num_key = str(s.get("session_number", 1))
            if num_key not in seen_sessions:
                seen_sessions.add(num_key)
                unique_sessions.append(s)
        unique_sessions.reverse()
        unique_sessions.sort(key=lambda s: int(s.get("session_number", 0)) if str(s.get("session_number", 0)).isdigit() else 0)

        for s in unique_sessions:
            num = s.get("session_number", 1)
            title = s.get("title", f"Sesión #{num}")
            date = s.get("date", "")
            lines.append(f"### 📖 Capítulo {num}: {title}")
            if date:
                lines.append(f"*Fecha de Juego: {date}*")
            lines.append("")

            # Protagonistas Detectados for this session
            pcs_list = s.get("detected_pcs") or [
                {
                    "personaje": p.get("character_name", "-"),
                    "jugador": p.get("player_name", "-"),
                    "clase": p.get("role", "-"),
                    "especie": p.get("species", "-"),
                    "rol_en_sesion": p.get("session_role", "-"),
                }
                for p in (s.get("detected_party") or [])
            ]
            if not pcs_list:
                pcs_list = campaign_state.get("detected_pcs") or [
                    {
                        "personaje": p.get("character_name", "-"),
                        "jugador": p.get("player_name", "-"),
                        "clase": p.get("role", "-"),
                        "especie": p.get("species", "-"),
                        "rol_en_sesion": p.get("session_role", "-"),
                    }
                    for p in (campaign_state.get("detected_party") or [])
                ]

            if pcs_list:
                lines.append("#### 🎭 Compañía de Aventureros (Protagonistas Detectados)")
                lines.append("")
                lines.append("| Personaje | Jugador / Rol | Clase / Especie | Rol en la Sesión |")
                lines.append("|---|---|---|---|")
                for pc in pcs_list:
                    char_p = pc.get("personaje", "-")
                    jug_p = pc.get("jugador", "-")
                    c_cls = pc.get("clase", "-")
                    c_esp = pc.get("especie", "-")
                    if c_cls != "-" and c_esp != "-":
                        c_desc = f"{c_cls} / {c_esp}"
                    elif c_cls != "-":
                        c_desc = c_cls
                    else:
                        c_desc = c_esp
                    s_rol = pc.get("rol_en_sesion", "-")
                    lines.append(f"| **{char_p}** | {jug_p} | {c_desc} | {s_rol} |")
                lines.append("")

            sec_num = 1

            # 1. Chronicle
            if s.get("chronicle_text"):
                lines.append(f"#### {sec_num}. Crónica Narrativa y Desglose de Combates")
                lines.append(s["chronicle_text"].strip())
                lines.append("")
                sec_num += 1

            # 2. Closing
            if s.get("closing_expectations"):
                lines.append(f"#### {sec_num}. Cierre de Sesión, Decisiones y Expectativas")
                lines.append(s["closing_expectations"].strip())
                lines.append("")
                sec_num += 1

            # 3. Roleplay Reflection (Conditional: strictly requires selected user character)
            synopsis_text = (s.get("episode_synopsis") or "").strip()
            coaching = (s.get("user_coaching") or s.get("markus_coaching") or "").strip()
            user_char = s.get("user_character", {})
            char_name = (user_char.get("character_name") or user_char.get("name") or "").strip() if isinstance(user_char, dict) else ""
            if not char_name and s.get("markus_coaching") and not synopsis_text:
                char_name = "Markus Veyl"

            if coaching and char_name and not synopsis_text and char_name not in ("-", "(DM)", "Dungeon Master"):
                char_title = f"Reflexión de Rol y Compañerismo: {char_name}"
                lines.append(f"#### {sec_num}. {char_title}")
                lines.append(coaching)
                lines.append("")
                sec_num += 1

            # 4. Episode Synopsis (for YouTube) or Read-Aloud Script (for Live sessions)
            synopsis_text = (s.get("episode_synopsis") or "").strip()
            if synopsis_text:
                lines.append(f"#### {sec_num}. 📌 Sinopsis Ejecutiva del Episodio")
                lines.append(synopsis_text)
                lines.append("")
            else:
                script_text = s.get("next_session_script") or s.get("recap_text")
                if script_text and script_text.strip():
                    next_num = num + 1
                    lines.append(f"#### {sec_num}. 🎙️ Guion para abrir la Sesión #{next_num} (Para leer en voz alta)")
                    lines.append(script_text.strip())
                    lines.append("")

            lines.append("---")
            lines.append("")

    dest_file = Path(output_path).resolve()
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    dest_file.write_text("\n".join(lines), encoding="utf-8")
    return str(dest_file)
