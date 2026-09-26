"""Docx exporter for D&D session chronicles."""

import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT


def render_markdown_to_docx(
    doc: docx.Document,
    md_text: str,
    h1_font: Optional[str] = None,
    h1_color: Optional[RGBColor] = None,
    h2_font: Optional[str] = None,
    h2_color: Optional[RGBColor] = None,
    skip_h1_predicate: Optional[Callable[[str], bool]] = None,
) -> None:
    """
    Renders structured Markdown into a python-docx Document.
    - Code blocks and diagrams (```): Formats with Consolas 8.5 pt, 1.0 line spacing, 0 pt space after.
    - Markdown tables (|...|...|): Formats as native Word tables (Table Grid, centered, bold headers).
    - Headings (#, ##, ###, ####), lists (- / * / 1.), dividers (---), and text paragraphs.
    """
    if not md_text or not md_text.strip():
        return

    lines = md_text.splitlines()
    in_code_block = False
    table_lines: List[str] = []

    def flush_table():
        nonlocal table_lines
        if not table_lines:
            return
        rows: List[List[str]] = []
        for t_line in table_lines:
            s = t_line.strip()
            if not s:
                continue
            if re.match(r"^\|(?:\s*:?-+:?\s*\|)+\s*$", s):
                continue
            raw_cells = s[1:-1].split("|") if (s.startswith("|") and s.endswith("|")) else s.split("|")
            rows.append([c.strip() for c in raw_cells])
        table_lines = []

        if not rows:
            return

        col_count = max(len(r) for r in rows)
        if col_count == 0:
            return

        padded_rows = [r + [""] * (col_count - len(r)) for r in rows]
        tbl = doc.add_table(rows=len(padded_rows), cols=col_count)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.style = "Table Grid"

        # Headers (Row 0)
        for col_idx, cell in enumerate(tbl.rows[0].cells):
            cell.text = padded_rows[0][col_idx]
            for p in cell.paragraphs:
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2)
                for r in p.runs:
                    r.font.bold = True
                    r.font.size = Pt(9.5)
                    r.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

        # Data rows (Row 1+)
        for row_idx, r_data in enumerate(padded_rows[1:], start=1):
            for col_idx, cell in enumerate(tbl.rows[row_idx].cells):
                cell.text = r_data[col_idx]
                for p in cell.paragraphs:
                    p.paragraph_format.space_before = Pt(1)
                    p.paragraph_format.space_after = Pt(1)
                    for r in p.runs:
                        r.font.size = Pt(9)
                        r.font.color.rgb = RGBColor(0x37, 0x41, 0x51)

        p_spacer = doc.add_paragraph()
        p_spacer.paragraph_format.space_before = Pt(0)
        p_spacer.paragraph_format.space_after = Pt(4)

    for line in lines:
        stripped = line.strip()

        # 1. Code blocks / preformatted diagrams
        if stripped.startswith("```"):
            flush_table()
            in_code_block = not in_code_block
            if not in_code_block:
                p_spacer = doc.add_paragraph()
                p_spacer.paragraph_format.space_before = Pt(0)
                p_spacer.paragraph_format.space_after = Pt(4)
            continue

        if in_code_block:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            run = p.add_run(line if line else " ")
            run.font.name = "Consolas"
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
            try:
                rPr = run._r.get_or_add_rPr()
                rFonts = rPr.get_or_add_rFonts()
                rFonts.set(docx.oxml.ns.qn('w:ascii'), 'Consolas')
                rFonts.set(docx.oxml.ns.qn('w:hAnsi'), 'Consolas')
                rFonts.set(docx.oxml.ns.qn('w:cs'), 'Consolas')
            except Exception:
                pass
            continue

        # 2. Markdown tables (|...|...|)
        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2:
            table_lines.append(stripped)
            continue
        else:
            flush_table()

        if not stripped:
            continue

        # 3. Headings, Lists, Dividers, Paragraphs
        if stripped.startswith("# "):
            h_text = stripped[2:].strip()
            if skip_h1_predicate and skip_h1_predicate(h_text):
                continue
            h = doc.add_heading(h_text, level=1)
            h.paragraph_format.space_before = Pt(14)
            h.paragraph_format.space_after = Pt(4)
            if h1_font or h1_color:
                for r in h.runs:
                    if h1_font:
                        r.font.name = h1_font
                    if h1_color:
                        r.font.color.rgb = h1_color
        elif stripped.startswith("## "):
            h = doc.add_heading(stripped[3:].strip(), level=2)
            h.paragraph_format.space_before = Pt(12)
            h.paragraph_format.space_after = Pt(3)
            if h2_font or h2_color:
                for r in h.runs:
                    if h2_font:
                        r.font.name = h2_font
                    if h2_color:
                        r.font.color.rgb = h2_color
        elif stripped.startswith("### "):
            h = doc.add_heading(stripped[4:].strip(), level=3)
            h.paragraph_format.space_before = Pt(8)
            h.paragraph_format.space_after = Pt(2)
        elif stripped.startswith("#### "):
            h = doc.add_heading(stripped[5:].strip(), level=4)
            h.paragraph_format.space_before = Pt(6)
            h.paragraph_format.space_after = Pt(2)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            p = doc.add_paragraph(stripped[2:].strip(), style="List Bullet")
            p.paragraph_format.space_after = Pt(3)
        elif stripped.startswith("1. ") or (len(stripped) > 2 and stripped[:2].isdigit() and stripped[2:4] == ". "):
            idx = stripped.find(". ")
            p = doc.add_paragraph(stripped[idx + 2:].strip(), style="List Number")
            p.paragraph_format.space_after = Pt(3)
        elif stripped == "---":
            continue
        else:
            p = doc.add_paragraph(stripped)
            p.paragraph_format.space_after = Pt(6)

    flush_table()


def _get_default_output_dir() -> Path:
    if os.environ.get("WHISPER_OUTPUT_DIR"):
        p = Path(os.environ["WHISPER_OUTPUT_DIR"]).resolve()
    else:
        root = Path(__file__).resolve().parent.parent.parent
        if (root / "outputs").is_dir():
            p = (root / "outputs").resolve()
        else:
            p = (root / "data" / "output").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def export_chronicle_docx(
    chronicle_md: str,
    roster: Optional[List[Dict[str, str]]] = None,
    session_date: Optional[str] = None,
    output_path: Optional[str] = None,
) -> str:
    """
    Export a D&D session chronicle and party roster into a styled Word .docx document.

    :param chronicle_md: Markdown text of the chronicle.
    :param roster: List of player dicts (player_name, role, character_name).
    :param session_date: Date string of the session.
    :param output_path: Destination .docx path.
    :return: Absolute file path to the generated .docx.
    """
    if not output_path:
        out_dir = _get_default_output_dir()
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str((out_dir / f"cronica_sesion_{ts}.docx").resolve())

    doc = docx.Document()

    # Set document margins (1 inch)
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Document Title
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(4)
    title_run = title_p.add_run("Crónica de Sesión de Rol - D&D")
    title_run.font.name = "Georgia"
    title_run.font.size = Pt(24)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(0x31, 0x2E, 0x81)  # Deep Indigo

    # Subtitle / Date
    if session_date:
        date_p = doc.add_paragraph()
        date_p.paragraph_format.space_after = Pt(14)
        date_run = date_p.add_run(f"Fecha de Sesión: {session_date}")
        date_run.font.name = "Calibri"
        date_run.font.size = Pt(11)
        date_run.font.italic = True
        date_run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

    # Roster Table
    if roster:
        roster_h = doc.add_heading("👥 Roster de la Mesa", level=2)
        roster_h.paragraph_format.space_before = Pt(10)
        roster_h.paragraph_format.space_after = Pt(6)

        table = doc.add_table(rows=1, cols=5)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = "Table Grid"

        # Headers
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = "Jugador"
        hdr_cells[1].text = "Personaje"
        hdr_cells[2].text = "Especie / Raza"
        hdr_cells[3].text = "Clase"
        hdr_cells[4].text = "Subclase"

        for cell in hdr_cells:
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.bold = True
                    run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

        for p_data in roster:
            row_cells = table.add_row().cells
            row_cells[0].text = p_data.get("player_name", "-")
            row_cells[1].text = p_data.get("character_name", "-")
            row_cells[2].text = p_data.get("species", "-") or "-"
            row_cells[3].text = p_data.get("role", "-")
            row_cells[4].text = p_data.get("subclass", "-") or "-"

        doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # Parse Chronicle Markdown content (with math delimiters cleaned)
    cleaned_chronicle = clean_math_delimiters_for_docx(chronicle_md)
    render_markdown_to_docx(doc, cleaned_chronicle)

    target = Path(output_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(target))
    return str(target)


def export_living_journal_docx(
    campaign_state: Dict[str, Any],
    output_path: Optional[str] = None,
) -> str:
    """
    Format and export the complete Living Campaign Journal into a styled Word .docx document.
    Includes Master Quest Table, NPC Directory Table, and Chronological Session Chapters.

    :param campaign_state: Dict containing campaign metadata, quests, npcs, and sessions.
    :param output_path: Destination path. Defaults to data/output/<campaign_name>_Grimorio.docx.
    :return: Absolute file path to the generated .docx file.
    """
    import re
    campaign_name = campaign_state.get("campaign_name", "Campaña Principal")
    clean_name = re.sub(r'[\\/*?:"<>|]', "", campaign_name.strip())
    safe_name = re.sub(r"\s+", "_", clean_name) or "Campana_Principal"

    if not output_path:
        out_dir = _get_default_output_dir()
        output_path = str((out_dir / f"{safe_name}_Grimorio.docx").resolve())

    doc = docx.Document()

    # 1-inch margins
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Title Page / Header
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(4)
    title_run = title_p.add_run(f"📜 Grimorio de Campaña: {campaign_name}")
    title_run.font.name = "Georgia"
    title_run.font.size = Pt(24)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(0x31, 0x2E, 0x81)  # Deep Indigo

    # Subtitle
    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(14)
    last_sess = campaign_state.get("last_session", 0)
    upd_date = campaign_state.get("updated_at", "")[:10]
    sub_run = sub_p.add_run(f"Diario Vivo de Campaña • Última Sesión: #{last_sess} • Actualizado: {upd_date}")
    sub_run.font.name = "Calibri"
    sub_run.font.size = Pt(11)
    sub_run.font.italic = True
    sub_run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

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
        pc_heading = doc.add_heading("🛡️ ZONA UNIVERSAL: Directorio Universal de Aventureros (PCs)", level=1)
        pc_heading.paragraph_format.space_before = Pt(12)
        pc_heading.paragraph_format.space_after = Pt(6)

        pc_table = doc.add_table(rows=1, cols=7)
        pc_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        pc_table.style = "Table Grid"

        hdr_cells = pc_table.rows[0].cells
        hdr_cells[0].text = "Personaje"
        hdr_cells[1].text = "Jugador"
        hdr_cells[2].text = "Especie / Raza"
        hdr_cells[3].text = "Clase"
        hdr_cells[4].text = "Subclase"
        hdr_cells[5].text = "Debut"
        hdr_cells[6].text = "Hitos Acumulados"

        for cell in hdr_cells:
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.bold = True
                    run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

        for pc in universal_pcs:
            row_cells = pc_table.add_row().cells
            row_cells[0].text = str(pc.get("personaje", "-")).strip()
            row_cells[0].paragraphs[0].runs[0].font.bold = True
            row_cells[1].text = str(pc.get("jugador", "-")).strip()
            row_cells[2].text = str(pc.get("especie", "-")).strip()
            row_cells[3].text = str(pc.get("clase", "-")).strip()
            row_cells[4].text = str(pc.get("subclase", "-")).strip()
            debut_n = pc.get("debut_sesion") or pc.get("primera_aparicion_sesion") or 1
            row_cells[5].text = f"Sesión #{debut_n}"
            hitos = pc.get("hitos_acumulados", [])
            row_cells[6].text = "\n".join(hitos) if hitos else "-"
            if row_cells[6].paragraphs[0].runs:
                row_cells[6].paragraphs[0].runs[0].font.size = Pt(9.5)

        doc.add_paragraph().paragraph_format.space_after = Pt(12)
    elif display_party:
        header_title = "👥 Compañía de Aventureros (Personajes Detectados en el Video)" if (not is_private and chosen_detected) else "👥 Compañía de Aventureros (Roster de la Mesa)"
        roster_h = doc.add_heading(header_title, level=2)
        roster_h.paragraph_format.space_before = Pt(10)
        roster_h.paragraph_format.space_after = Pt(6)

        table = doc.add_table(rows=1, cols=5)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = "Table Grid"

        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = "Jugador"
        hdr_cells[1].text = "Personaje"
        hdr_cells[2].text = "Especie / Raza"
        hdr_cells[3].text = "Clase"
        hdr_cells[4].text = "Subclase"

        for cell in hdr_cells:
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.bold = True
                    run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

        for p_data in display_party:
            row_cells = table.add_row().cells
            row_cells[0].text = (p_data.get("jugador") or p_data.get("player_name", "-") or "-").strip()
            row_cells[1].text = (p_data.get("personaje") or p_data.get("character_name", "-") or "-").strip()
            row_cells[2].text = (p_data.get("especie") or p_data.get("species", "-") or "-").strip()
            row_cells[3].text = (p_data.get("clase") or p_data.get("role", "-") or "-").strip()
            row_cells[4].text = (p_data.get("subclase") or p_data.get("subclass", "-") or "-").strip()

        doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # 2. Universal Zone: Master Quest Log (4 Tiers)
    quests = campaign_state.get("quests", [])
    q_heading = doc.add_heading("🗺️ ZONA UNIVERSAL: Registro Maestro de Misiones (Master Quest Log)", level=1)
    q_heading.paragraph_format.space_before = Pt(14)
    q_heading.paragraph_format.space_after = Pt(6)

    if not quests:
        p = doc.add_paragraph("Aún no hay misiones registradas en la campaña.")
        p.runs[0].font.italic = True
    else:
        q_table = doc.add_table(rows=1, cols=5)
        q_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        q_table.style = "Table Grid"

        q_hdrs = q_table.rows[0].cells
        q_hdrs[0].text = "ID"
        q_hdrs[1].text = "Nivel / Tipo"
        q_hdrs[2].text = "Misión & Contexto"
        q_hdrs[3].text = "Estado & Ciclo de Vida"
        q_hdrs[4].text = "Sub-objetivos"

        for cell in q_hdrs:
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.bold = True
                    run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

        for q in quests:
            q_cells = q_table.add_row().cells
            q_cells[0].text = q.get("id", "-")

            # Tipo
            tipo_val = str(q.get("tipo", "principal")).lower()
            tipo_label = "⭐ Principal"
            if tipo_val == "secundaria":
                tipo_label = "⚔️ Secundaria"
            elif tipo_val == "opcional":
                tipo_label = "🧭 Opcional"
            elif tipo_val in ("misterios_abiertos", "misterio"):
                tipo_label = "🔮 Misterios Abiertos"
            q_cells[1].text = tipo_label
            if q_cells[1].paragraphs[0].runs:
                q_cells[1].paragraphs[0].runs[0].font.bold = True
                q_cells[1].paragraphs[0].runs[0].font.size = Pt(9.5)

            # Title + Context
            p_desc = q_cells[2].paragraphs[0]
            run_title = p_desc.add_run(q.get("title", "Misión") + "\n")
            run_title.font.bold = True
            if q.get("context"):
                run_ctx = p_desc.add_run(q.get("context", ""))
                run_ctx.font.size = Pt(9.5)
                run_ctx.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)

            # Status + Lifecycle
            p_stat = q_cells[3].paragraphs[0]
            status_str = q.get("status", "in_progress")
            status_text = "EN PROGRESO" if status_str == "in_progress" else ("COMPLETADA" if status_str == "completed" else "FALLIDA")
            run_st = p_stat.add_run(f"[{status_text}]\n")
            run_st.font.bold = True
            if status_str == "completed":
                run_st.font.color.rgb = RGBColor(0x05, 0x96, 0x69)
            elif status_str == "in_progress":
                run_st.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)

            if q.get("lifecycle_notes"):
                run_life = p_stat.add_run(q.get("lifecycle_notes", ""))
                run_life.font.size = Pt(9)
                run_life.font.italic = True

            # Subobjectives
            p_sub = q_cells[4].paragraphs[0]
            subs = q.get("subobjectives", [])
            if subs:
                for idx, sub in enumerate(subs):
                    check = "☑ " if sub.get("completed") else "☐ "
                    run_sub = p_sub.add_run(f"{check}{sub.get('text', '')}" + ("\n" if idx < len(subs) - 1 else ""))
                    run_sub.font.size = Pt(9.5)
            else:
                p_sub.text = "-"

    doc.add_paragraph().paragraph_format.space_after = Pt(14)

    # 3. Universal Zone: NPC Directory (3 Tiers)
    npcs = campaign_state.get("npcs", [])
    npc_heading = doc.add_heading("🎭 ZONA UNIVERSAL: Directorio Universal de Personajes (NPCs)", level=1)
    npc_heading.paragraph_format.space_before = Pt(14)
    npc_heading.paragraph_format.space_after = Pt(6)

    if not npcs:
        p = doc.add_paragraph("Aún no hay personajes no jugadores registrados.")
        p.runs[0].font.italic = True
    else:
        npc_table = doc.add_table(rows=1, cols=5)
        npc_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        npc_table.style = "Table Grid"

        npc_hdrs = npc_table.rows[0].cells
        npc_hdrs[0].text = "Nombre"
        npc_hdrs[1].text = "Nivel / Tipo"
        npc_hdrs[2].text = "Rol / Ocupación"
        npc_hdrs[3].text = "Primera Aparición"
        npc_hdrs[4].text = "Historial de Interacciones & Pistas"

        for cell in npc_hdrs:
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.bold = True
                    run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

        for n in npcs:
            n_cells = npc_table.add_row().cells
            n_cells[0].text = n.get("name", "Desconocido")
            n_cells[0].paragraphs[0].runs[0].font.bold = True

            # Tipo
            n_tipo = str(n.get("tipo", "interaccion_contexto")).lower()
            if n_tipo in ("importantes", "importante"):
                n_label = "👑 Clave / Importante"
            elif n_tipo in ("mencionados", "mencionado") or "[mencionado" in str(n.get("role", "")).lower():
                n_label = "📜 Mencionado"
            else:
                n_label = "⚔️ Interacción / Contexto"
            n_cells[1].text = n_label
            if n_cells[1].paragraphs[0].runs:
                n_cells[1].paragraphs[0].runs[0].font.bold = True
                n_cells[1].paragraphs[0].runs[0].font.size = Pt(9.5)

            n_cells[2].text = n.get("role", "PNJ")
            n_cells[3].text = f"Sesión #{n.get('first_seen_session', 1)}"
            n_notes = n.get("notes", [])
            n_cells[4].text = "\n".join(n_notes) if n_notes else "-"
            n_cells[4].paragraphs[0].runs[0].font.size = Pt(9.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(14)

    # 4. Historical Zone: Chapters
    sessions = campaign_state.get("sessions", [])
    h_heading = doc.add_heading("📚 ZONA HISTÓRICA: Capítulos de Campaña", level=1)
    h_heading.paragraph_format.space_before = Pt(16)
    h_heading.paragraph_format.space_after = Pt(8)

    if not sessions:
        p = doc.add_paragraph("No se han registrado sesiones aún.")
        p.runs[0].font.italic = True
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

            ch_h = doc.add_heading(f"📖 Capítulo {num}: {title}", level=2)
            ch_h.paragraph_format.space_before = Pt(16)
            ch_h.paragraph_format.space_after = Pt(4)

            if date:
                dp = doc.add_paragraph(f"Fecha de Juego: {date}")
                dp.paragraph_format.space_after = Pt(8)
                dp.runs[0].font.italic = True
                dp.runs[0].font.size = Pt(10)
                dp.runs[0].font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

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
                proto_h = doc.add_heading("🎭 Compañía de Aventureros (Protagonistas Detectados)", level=3)
                proto_h.paragraph_format.space_before = Pt(8)
                proto_h.paragraph_format.space_after = Pt(4)

                proto_table = doc.add_table(rows=1, cols=4)
                proto_table.alignment = WD_TABLE_ALIGNMENT.CENTER
                proto_table.style = "Table Grid"

                p_hdrs = proto_table.rows[0].cells
                p_hdrs[0].text = "Personaje"
                p_hdrs[1].text = "Jugador / Rol"
                p_hdrs[2].text = "Clase / Especie"
                p_hdrs[3].text = "Rol en la Sesión"

                for cell in p_hdrs:
                    for p_cell in cell.paragraphs:
                        for run in p_cell.runs:
                            run.font.bold = True
                            run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

                for pc in pcs_list:
                    pc_cells = proto_table.add_row().cells
                    pc_cells[0].text = pc.get("personaje", "-")
                    if pc_cells[0].paragraphs[0].runs:
                        pc_cells[0].paragraphs[0].runs[0].font.bold = True
                    pc_cells[1].text = pc.get("jugador", "-")
                    c_cls = pc.get("clase", "-")
                    c_esp = pc.get("especie", "-")
                    if c_cls != "-" and c_esp != "-":
                        pc_cells[2].text = f"{c_cls} / {c_esp}"
                    elif c_cls != "-":
                        pc_cells[2].text = c_cls
                    else:
                        pc_cells[2].text = c_esp
                    pc_cells[3].text = pc.get("rol_en_sesion", "-")
                    if pc_cells[3].paragraphs[0].runs:
                        pc_cells[3].paragraphs[0].runs[0].font.size = Pt(9.5)

                doc.add_paragraph().paragraph_format.space_after = Pt(8)

            sec_num = 1

            # 1. Narrative Chronicle & Combat
            if s.get("chronicle_text"):
                ch_title = doc.add_heading(f"{sec_num}. Crónica Narrativa y Desglose de Combates", level=3)
                ch_title.paragraph_format.space_before = Pt(10)
                ch_title.paragraph_format.space_after = Pt(3)
                render_markdown_to_docx(doc, clean_math_delimiters_for_docx(s["chronicle_text"]))
                sec_num += 1

            # 2. Closing & Expectations
            if s.get("closing_expectations"):
                cl_h = doc.add_heading(f"{sec_num}. Cierre de Sesión, Decisiones y Expectativas", level=3)
                cl_h.paragraph_format.space_before = Pt(10)
                cl_h.paragraph_format.space_after = Pt(3)
                cp = doc.add_paragraph(s["closing_expectations"])
                cp.paragraph_format.space_after = Pt(6)
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
                mc_h = doc.add_heading(f"{sec_num}. {char_title}", level=3)
                mc_h.paragraph_format.space_before = Pt(10)
                mc_h.paragraph_format.space_after = Pt(3)
                for line in coaching.split("\n"):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if stripped.startswith("- ") or stripped.startswith("* "):
                        doc.add_paragraph(stripped[2:], style="List Bullet")
                    else:
                        doc.add_paragraph(stripped)
                sec_num += 1

            # 4. Episode Synopsis (for YouTube) or Read-Aloud Script (for Live sessions)
            synopsis_text = (s.get("episode_synopsis") or "").strip()
            if synopsis_text:
                syn_h = doc.add_heading(f"{sec_num}. 📌 Sinopsis Ejecutiva del Episodio", level=3)
                syn_h.paragraph_format.space_before = Pt(10)
                syn_h.paragraph_format.space_after = Pt(3)
                for line in synopsis_text.split("\n"):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    sp = doc.add_paragraph(stripped)
                    sp.paragraph_format.space_after = Pt(4)
                sec_num += 1
            else:
                script_text = s.get("next_session_script") or s.get("recap_text")
                if script_text and script_text.strip():
                    next_num = num + 1
                    rh = doc.add_heading(f"{sec_num}. 🎙️ Guion para abrir la Sesión #{next_num} (Para leer en voz alta)", level=3)
                    rh.paragraph_format.space_before = Pt(10)
                    rh.paragraph_format.space_after = Pt(3)
                    rp = doc.add_paragraph(script_text.strip())
                    rp.paragraph_format.space_after = Pt(6)

            doc.add_paragraph().paragraph_format.space_after = Pt(12)

    target = Path(output_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(target))
    return str(target)


def clean_math_delimiters_for_docx(text: str) -> str:
    """
    Clean LaTeX and $$ math delimiters so mathematical equations appear
    as clean, human-readable formatted text in Word rather than raw code.
    """
    if not text:
        return text
    import re
    # Strip block $$...$$ equations
    cleaned = re.sub(r'\$\$\s*([\s\S]*?)\s*\$\$', r'\1', text)
    # Remove any stray $$
    cleaned = cleaned.replace("$$", "")
    # Remove inline math delimiters \(...\) and \[...\]
    cleaned = re.sub(r'\\\[\s*([\s\S]*?)\s*\\\]', r'\1', cleaned)
    cleaned = re.sub(r'\\\(\s*([\s\S]*?)\s*\\\)', r'\1', cleaned)
    # Unescape escaped currency dollar signs (\$1,000 -> $1,000)
    cleaned = cleaned.replace(r"\$", "$")
    # Simplify common LaTeX text formatting inside math
    cleaned = re.sub(r'\\text\{([^}]+)\}', r'\1', cleaned)
    cleaned = re.sub(r'\\mathbf\{([^}]+)\}', r'\1', cleaned)
    cleaned = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', cleaned)
    # Replace common LaTeX operators with readable unicode
    cleaned = cleaned.replace(r"\cdot", "·").replace(r"\times", "×")
    cleaned = cleaned.replace(r"\neq", "≠").replace(r"\neg", "¬")
    cleaned = cleaned.replace(r"\leq", "≤").replace(r"\le", "≤").replace(r"\geq", "≥").replace(r"\ge", "≥")
    cleaned = cleaned.replace(r"\approx", "≈").replace(r"\pm", "±")
    return cleaned


def export_academic_notes_docx(
    notes_md: str,
    subject: str = "Materia Universitaria",
    topic: str = "Tema de Clase",
    lecture_date: Optional[str] = None,
    output_path: Optional[str] = None,
) -> str:
    """
    Export an Academic Study Guide into a cleanly formatted university-style Word .docx document.

    :param notes_md: Markdown text of the academic study guide.
    :param subject: Course / Subject title.
    :param topic: Class topic.
    :param lecture_date: Optional lecture date string.
    :param output_path: Destination .docx path.
    :return: Absolute file path to the generated .docx file.
    """
    import datetime
    import re

    clean_subj = re.sub(r'[\\/*?:"<>|]', "", subject.strip()) or "Materia"
    safe_subj = re.sub(r"\s+", "_", clean_subj)
    clean_top = re.sub(r'[\\/*?:"<>|]', "", topic.strip()) or "Tema"
    safe_top = re.sub(r"\s+", "_", clean_top)

    if not output_path:
        out_dir = _get_default_output_dir()
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str((out_dir / f"apuntes_{safe_subj}_{safe_top}_{ts}.docx").resolve())

    doc = docx.Document()

    # Document margins: 1 inch
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # University Header: Subject
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(2)
    title_run = title_p.add_run(f"🎓 {subject}")
    title_run.font.name = "Georgia"
    title_run.font.size = Pt(22)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)  # Navy Blue

    # Subtitle: Topic
    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(6)
    sub_run = sub_p.add_run(f"Apuntes de Clase • {topic}")
    sub_run.font.name = "Calibri"
    sub_run.font.size = Pt(14)
    sub_run.font.bold = True
    sub_run.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)  # Accent Blue

    # Metadata badge: Date
    date_val = lecture_date or datetime.datetime.now().strftime("%d/%m/%Y")
    meta_p = doc.add_paragraph()
    meta_p.paragraph_format.space_after = Pt(16)
    meta_run = meta_p.add_run(f"Fecha de la sesión: {date_val} • Guía de Estudio Universitaria")
    meta_run.font.name = "Calibri"
    meta_run.font.size = Pt(10)
    meta_run.font.italic = True
    meta_run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

    # Clean $$ math delimiters for clean readable Word text
    cleaned_md = clean_math_delimiters_for_docx(notes_md)

    # Parse and style Markdown lines (including code blocks with Consolas and native tables)
    render_markdown_to_docx(
        doc,
        cleaned_md,
        h1_font="Georgia",
        h1_color=RGBColor(0x1E, 0x3A, 0x8A),
        h2_font="Calibri",
        h2_color=RGBColor(0x25, 0x63, 0xEB),
        skip_h1_predicate=lambda h: subject.lower() in h.lower() and "guía de estudio" in h.lower(),
    )

    target = Path(output_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(target))
    return str(target)

