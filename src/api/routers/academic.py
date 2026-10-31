"""Academic study notes router for Work & Study workspace."""

import asyncio
import datetime
import io
import json
import os
import re
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from src.api import server

router = APIRouter(tags=["academic"])


def is_academic_study_note(filename: str, content: str = "") -> bool:
    """
    Strict filter to separate Work & Study notes from D&D Living Campaign grimorios and logs.
    - Exclusion: Immediately discards any file whose filename or first header contains:
      'Grimorio de Campaña', 'grimorio_', 'sesion_', 'cronica_', 'campana_', etc.
    - Inclusion: ONLY list files starting with 'apuntes_' prefix or containing study metadata.
    """
    fname_lower = filename.lower()

    if fname_lower == "manifest.md":
        return False

    # Exclusion: Filename checks (case-insensitive)
    dnd_file_markers = [
        "grimorio",
        "sesion_",
        "sesion-",
        "cronica_",
        "cronica-",
        "campana_",
        "campana-",
        "campaña_",
        "campaña-",
    ]
    for marker in dnd_file_markers:
        if marker in fname_lower:
            return False

    # Exclusion: First header / early lines check
    if content:
        lines = [line.strip() for line in content.splitlines()[:15] if line.strip()]
        header_text = ""
        for line in lines:
            if line.startswith("#"):
                header_text = line.lower()
                break
        if not header_text and lines:
            header_text = lines[0].lower()

        dnd_header_markers = [
            "grimorio de campaña",
            "grimorio de campana",
            "grimorio",
            "sesión",
            "sesion",
            "crónica",
            "cronica",
            "campaña",
            "campana",
            "living campaign",
            "diario vivo de campaña",
            "diario vivo de campana",
            "directorio universal de aventureros",
            "registro maestro de misiones",
        ]
        for marker in dnd_header_markers:
            if marker in header_text:
                return False

    # Inclusion: Must start with 'apuntes_' or contain study metadata
    if fname_lower.startswith("apuntes_"):
        return True

    if content:
        content_sample = content[:3000].lower()
        study_metadata_markers = [
            "executive briefing",
            "briefing ejecutivo",
            "guía de estudio",
            "guia de estudio",
            "study guide",
            "deep study guide",
            "apuntes de clase",
            "notas de clase",
            "🎓",
            "resumen ejecutivo",
            "metadatos de estudio",
            "conceptos clave",
            "preguntas de repaso",
            "preguntas de autoevaluación",
            "glosario de términos",
        ]
        for marker in study_metadata_markers:
            if marker in content_sample:
                return True

    return False


def extract_clean_note_title(filename: str, content: str = "") -> str:
    lines = content.strip().split("\n") if content else []
    if lines:
        for line in lines[:8]:
            line_str = line.strip()
            if line_str.startswith("#"):
                cleaned = re.sub(r"^#+\s*", "", line_str)
                cleaned = re.sub(r"[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf\uFE0F]\s*", "", cleaned)
                prev_cleaned = None
                while prev_cleaned != cleaned:
                    prev_cleaned = cleaned
                    cleaned = re.sub(
                        r"^(?:BRIEFING EJECUTIVO Y GU[ÍI]A DE ESTUDIO PROFUNDA|EXECUTIVE BRIEFING & DEEP STUDY GUIDE|GU[ÍI]A DE ESTUDIO PROFUNDA|DEEP STUDY GUIDE|GU[ÍI]A DE ESTUDIO|STUDY GUIDE|BRIEFING EJECUTIVO|EXECUTIVE BRIEFING|APUNTES DE CLASE|APUNTES|NOTAS DE CLASE|TOPIC|MATERIA|TEMA|RESUMEN DE REUNI[ÓO]N|MEETING SUMMARY|RESUMEN EJECUTIVO|EXECUTIVE SUMMARY)[\s:–—\-]+",
                        "",
                        cleaned,
                        flags=re.IGNORECASE,
                    ).strip()
                if ":" in cleaned:
                    parts = [p.strip() for p in cleaned.split(":") if p.strip()]
                    if len(parts) == 2 and parts[0].lower() == parts[1].lower():
                        cleaned = parts[0]
                    elif len(parts) >= 2 and parts[0].lower() in [
                        "topic", "tema", "materia", "title", "título", "titulo", "subject"
                    ]:
                        cleaned = ": ".join(parts[1:]).strip()
                if cleaned and len(cleaned) > 2:
                    return cleaned
    stem = Path(filename).stem
    stem = re.sub(r"^apuntes_(?:file_)?", "", stem)
    stem = re.sub(r"_\d{8}_\d{6}$", "", stem)
    stem = re.sub(r"_(?:es|en)$", "", stem)
    stem = stem.replace("_", " ").strip()
    return stem or "Apuntes de Clase"


def format_note_date(mtime: float, filename: str) -> str:
    ts_match = re.search(r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", filename)
    if ts_match:
        y, m, d, H, M, _ = ts_match.groups()
        return f"{d}/{m}/{y} • {H}:{M}"
    dt = datetime.datetime.fromtimestamp(mtime)
    return dt.strftime("%d/%m/%Y • %H:%M")


def update_consolidated_academic_notes_file() -> Path:
    """
    Consolidate all academic notes from outputs/ into data/apuntes_historial.json.
    Each note entry includes metadata and content for seamless cloud backup and restore.
    """
    output_dir = server.get_data_output_dir()
    project_root = server.project_root

    is_test_mode = os.environ.get("WHISPER_ENV") in ("test", "testing") or os.environ.get("TESTING") == "1" or bool(os.environ.get("WHISPER_OUTPUT_DIR"))

    if is_test_mode:
        historial_file = output_dir / "apuntes_historial.json"
        candidate_output_dirs = [output_dir]
        target_data_dirs = [output_dir]
    else:
        historial_file = project_root / "data" / "apuntes_historial.json"
        historial_file.parent.mkdir(parents=True, exist_ok=True)
        candidate_output_dirs = []
        for d in [output_dir, project_root / "outputs", project_root / "data" / "output", Path("/app/outputs")]:
            try:
                if d.is_dir() and d.resolve() not in [x.resolve() for x in candidate_output_dirs]:
                    candidate_output_dirs.append(d)
            except Exception:
                pass
        if not candidate_output_dirs:
            candidate_output_dirs = [output_dir]
        target_data_dirs = [historial_file.parent]
        container_data = Path("/app/data")
        if container_data.exists() or container_data.parent.exists():
            try:
                container_data.mkdir(parents=True, exist_ok=True)
                if container_data.resolve() not in [x.resolve() for x in target_data_dirs]:
                    target_data_dirs.append(container_data)
            except Exception:
                pass

    existing_notes_map = {}
    for d_dir in target_data_dirs:
        candidate_hist = d_dir / "apuntes_historial.json"
        if candidate_hist.is_file():
            try:
                old_data = json.loads(candidate_hist.read_text(encoding="utf-8"))
                old_list = old_data.get("notes", []) if isinstance(old_data, dict) else []
                for n in old_list:
                    if isinstance(n, dict) and n.get("filename"):
                        if is_academic_study_note(n["filename"], n.get("content", "")):
                            existing_notes_map[n["filename"]] = n
            except Exception:
                pass

    notes_by_filename = {}
    for o_dir in candidate_output_dirs:
        for md_file in o_dir.glob("*.md"):
            if not is_academic_study_note(md_file.name):
                continue
            try:
                stat = md_file.stat()
                if stat.st_size < 500 and not md_file.name.startswith("apuntes_reunion_"):
                    continue
                content = md_file.read_text(encoding="utf-8", errors="replace")
                if not is_academic_study_note(md_file.name, content):
                    continue
                words = len(content.split())
                if words < 100 and not md_file.name.startswith("apuntes_reunion_"):
                    continue
                title = extract_clean_note_title(md_file.name, content)
                formatted_date = format_note_date(stat.st_mtime, md_file.name)

                docx_filename = md_file.name.replace(".md", ".docx")
                txt_filename = md_file.name.replace(".md", "_transcripcion.txt")
                if not (o_dir / txt_filename).is_file():
                    txt_cand = md_file.name.replace(".md", ".txt")
                    if (o_dir / txt_cand).is_file():
                        txt_filename = txt_cand
                    else:
                        txt_filename = None

                lines = content.strip().split("\n")
                clean_lines = [l for l in lines[1:8] if l.strip() and not l.strip().startswith("---") and not l.strip().startswith("#")]
                excerpt = " ".join(clean_lines)[:240] if clean_lines else (content[:240] + "...")

                note_dict = {
                    "filename": md_file.name,
                    "title": title,
                    "topic": title,
                    "date": formatted_date,
                    "created_at": formatted_date,
                    "word_count": words,
                    "timestamp": stat.st_mtime,
                    "size_bytes": stat.st_size,
                    "document_format": "executive" if md_file.name.startswith("apuntes_reunion_") else None,
                    "docx_filename": docx_filename,
                    "txt_filename": txt_filename if txt_filename and (o_dir / txt_filename).is_file() else None,
                    "excerpt": excerpt,
                    "content": content,
                }
                if md_file.name not in notes_by_filename or stat.st_mtime > notes_by_filename[md_file.name].get("timestamp", 0):
                    notes_by_filename[md_file.name] = note_dict
            except Exception:
                continue

    for fname, old_note in existing_notes_map.items():
        if fname not in notes_by_filename and old_note.get("content"):
            if not is_academic_study_note(fname, old_note.get("content", "")):
                continue
            old_size = int(old_note.get("size_bytes") or len(old_note.get("content", "").encode("utf-8")))
            old_words = int(old_note.get("word_count") or len(old_note.get("content", "").split()))
            if (old_size < 500 or old_words < 100) and not fname.startswith("apuntes_reunion_"):
                continue
            old_note["title"] = extract_clean_note_title(fname, old_note.get("content", ""))
            old_note["topic"] = old_note["title"]
            notes_by_filename[fname] = old_note
            try:
                (output_dir / fname).write_text(old_note["content"], encoding="utf-8")
            except Exception:
                pass

    notes = list(notes_by_filename.values())
    notes.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    payload = {
        "updated_at": datetime.datetime.now().isoformat(),
        "total_notes": len(notes),
        "notes": notes,
    }
    payload_str = json.dumps(payload, indent=2, ensure_ascii=False)
    for d_dir in target_data_dirs:
        try:
            (d_dir / "apuntes_historial.json").write_text(payload_str, encoding="utf-8")
        except Exception:
            pass

    return historial_file


@router.get("/api/academic-notes")
@router.get("/api/notes")
async def list_academic_notes():
    """List all saved academic notes and study guides in outputs/ or restored from Google Drive."""
    output_dir = server.get_data_output_dir()
    project_root = server.project_root

    is_test_mode = os.environ.get("WHISPER_ENV") in ("test", "testing") or os.environ.get("TESTING") == "1" or bool(os.environ.get("WHISPER_OUTPUT_DIR"))

    historial_file = None
    candidate_historial = [output_dir / "apuntes_historial.json"] if is_test_mode else [project_root / "data" / "apuntes_historial.json", Path("/app/data/apuntes_historial.json")]
    for h_cand in candidate_historial:
        if h_cand.is_file():
            historial_file = h_cand
            break

    historial_notes = []
    if historial_file and historial_file.is_file():
        try:
            h_data = json.loads(historial_file.read_text(encoding="utf-8"))
            raw_hist_notes = h_data.get("notes", []) if isinstance(h_data, dict) else []
            for n in raw_hist_notes:
                if isinstance(n, dict) and n.get("filename") and n.get("content"):
                    if not is_academic_study_note(n["filename"], n.get("content", "")):
                        continue
                    n_size = int(n.get("size_bytes") or len(n["content"].encode("utf-8")))
                    n_words = int(n.get("word_count") or len(n["content"].split()))
                    if (n_size >= 500 and n_words >= 100) or n["filename"].startswith("apuntes_reunion_"):
                        n["title"] = extract_clean_note_title(n["filename"], n.get("content", ""))
                        n["topic"] = n["title"]
                        historial_notes.append(n)
                        fname = Path(n["filename"]).name
                        target_dirs_selfheal = [output_dir] if is_test_mode else [Path("/app/outputs"), output_dir, project_root / "outputs"]
                        for t_dir in target_dirs_selfheal:
                            try:
                                if t_dir.exists() or t_dir.parent.exists():
                                    t_dir.mkdir(parents=True, exist_ok=True)
                                    t_p = t_dir / fname
                                    if not t_p.is_file():
                                        t_p.write_text(n["content"], encoding="utf-8")
                            except Exception:
                                pass
        except Exception as exc:
            print(f"[list_academic_notes] Warning reading historial_file: {exc}")

    if is_test_mode:
        candidate_dirs = [output_dir]
    else:
        candidate_dirs = []
        for cd in [Path("/app/outputs"), output_dir, project_root / "outputs", project_root / "data" / "output"]:
            try:
                if cd.exists():
                    cd_res = cd.resolve()
                    if cd_res not in [x.resolve() for x in candidate_dirs]:
                        candidate_dirs.append(cd)
            except Exception:
                pass
        if not candidate_dirs:
            candidate_dirs = [output_dir]

    notes = []
    seen_filenames = set()

    for c_dir in candidate_dirs:
        for md_file in c_dir.glob("*.md"):
            if md_file.name in seen_filenames:
                continue
            if not is_academic_study_note(md_file.name):
                continue
            try:
                stat = md_file.stat()
                if stat.st_size < 500 and not md_file.name.startswith("apuntes_reunion_"):
                    continue
                content = md_file.read_text(encoding="utf-8", errors="replace")
                if not is_academic_study_note(md_file.name, content):
                    continue
                words = len(content.split())
                if words < 100 and not md_file.name.startswith("apuntes_reunion_"):
                    continue
                seen_filenames.add(md_file.name)
                title = extract_clean_note_title(md_file.name, content)
                formatted_date = format_note_date(stat.st_mtime, md_file.name)

                docx_filename = md_file.name.replace(".md", ".docx")
                txt_filename = md_file.name.replace(".md", "_transcripcion.txt")
                if not (c_dir / txt_filename).is_file():
                    txt_cand = md_file.name.replace(".md", ".txt")
                    if (c_dir / txt_cand).is_file():
                        txt_filename = txt_cand
                    else:
                        txt_filename = None

                lines = content.strip().split("\n")
                clean_lines = [l for l in lines[1:8] if l.strip() and not l.strip().startswith("---") and not l.strip().startswith("#")]
                excerpt = " ".join(clean_lines)[:240] if clean_lines else (content[:240] + "...")

                notes.append({
                    "filename": md_file.name,
                    "title": title,
                    "topic": title,
                    "date": formatted_date,
                    "created_at": formatted_date,
                    "word_count": words,
                    "timestamp": stat.st_mtime,
                    "size_bytes": stat.st_size,
                    "document_format": "executive" if md_file.name.startswith("apuntes_reunion_") else None,
                    "docx_filename": docx_filename,
                    "txt_filename": txt_filename if txt_filename and (c_dir / txt_filename).is_file() else None,
                    "excerpt": excerpt,
                })
            except Exception:
                continue

    if len(notes) < len(historial_notes):
        for hn in historial_notes:
            if isinstance(hn, dict) and hn.get("filename") and hn["filename"] not in seen_filenames:
                if not is_academic_study_note(hn["filename"], hn.get("content", "")):
                    continue
                seen_filenames.add(hn["filename"])
                hn_clean = dict(hn)
                hn_clean.pop("content", None)
                hn_clean["title"] = extract_clean_note_title(hn_clean["filename"], hn.get("content", ""))
                hn_clean["topic"] = hn_clean["title"]
                notes.append(hn_clean)

    notes.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return {"notes": notes}


@router.get("/api/academic-notes/{filename}")
@router.get("/api/notes/{filename}")
async def get_academic_note(filename: str):
    """Retrieve full content and metadata of a specific academic note."""
    decoded_filename = urllib.parse.unquote(filename)
    safe_filename = Path(decoded_filename).name

    if not is_academic_study_note(safe_filename):
        raise HTTPException(status_code=404, detail="Nota de estudio no encontrada.")

    output_dir = server.get_data_output_dir()
    project_root = server.project_root

    candidate_dirs: List[Path] = []
    for cd in [Path("/app/outputs"), output_dir, project_root / "outputs", project_root / "data" / "output"]:
        try:
            if cd.exists():
                cd_res = cd.resolve()
                if cd_res not in [x.resolve() for x in candidate_dirs]:
                    candidate_dirs.append(cd)
        except Exception:
            pass
    if not candidate_dirs:
        candidate_dirs = [output_dir]

    file_path = None
    for c_dir in candidate_dirs:
        cand_p = c_dir / safe_filename
        if cand_p.is_file():
            file_path = cand_p
            break
        candidates = [
            f"{safe_filename}.md",
            safe_filename.rsplit(".", 1)[0] + ".md" if "." in safe_filename else f"{safe_filename}.md",
            f"apuntes_{safe_filename}",
            f"apuntes_{safe_filename}.md"
        ]
        for c in candidates:
            p = c_dir / c
            if p.is_file():
                file_path = p
                safe_filename = c
                break
        if file_path:
            break

    if not file_path or not file_path.is_file():
        for h_path in [project_root / "data" / "apuntes_historial.json", Path("/app/data/apuntes_historial.json")]:
            if h_path.is_file():
                try:
                    h_data = json.loads(h_path.read_text(encoding="utf-8"))
                    notes_list = h_data.get("notes", []) if isinstance(h_data, dict) else []
                    for n in notes_list:
                        if isinstance(n, dict) and (n.get("filename") == safe_filename or n.get("filename") == f"{safe_filename}.md"):
                            if n.get("content"):
                                file_path = output_dir / Path(n["filename"]).name
                                file_path.write_text(n["content"], encoding="utf-8")
                                safe_filename = file_path.name
                                break
                except Exception:
                    pass
            if file_path and file_path.is_file():
                break

    if not file_path or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Nota de estudio no encontrada.")

    content = file_path.read_text(encoding="utf-8", errors="replace")
    if not is_academic_study_note(safe_filename, content):
        raise HTTPException(status_code=404, detail="Nota de estudio no encontrada.")

    normalized_content = server.normalize_academic_sections(content)
    if normalized_content != content:
        content = normalized_content
        try:
            file_path.write_text(content, encoding="utf-8")
        except Exception:
            pass

    stat = file_path.stat()
    title = extract_clean_note_title(safe_filename, content)
    formatted_date = format_note_date(stat.st_mtime, safe_filename)
    words = len(content.split())

    action_items, key_points = server.extract_academic_sections(content)

    docx_filename = safe_filename.replace(".md", ".docx")
    txt_filename = safe_filename.replace(".md", "_transcripcion.txt")
    if not (output_dir / txt_filename).is_file():
        cand_txt = safe_filename.replace(".md", ".txt")
        if (output_dir / cand_txt).is_file():
            txt_filename = cand_txt
        else:
            txt_filename = None

    return {
        "filename": safe_filename,
        "title": title,
        "topic": title,
        "date": formatted_date,
        "created_at": formatted_date,
        "word_count": words,
        "content": content,
        "action_items": action_items,
        "key_points": key_points,
        "docx_filename": docx_filename,
        "txt_filename": txt_filename,
    }


@router.delete("/api/academic-notes/{filename}")
@router.delete("/api/notes/{filename}")
async def delete_academic_note(filename: str):
    """Permanently delete an academic study note and its associated .docx, .txt, and .json files."""
    decoded_filename = urllib.parse.unquote(filename)
    safe_filename = Path(decoded_filename).name
    if not (safe_filename.endswith(".md") or safe_filename.endswith(".docx") or safe_filename.endswith(".txt")):
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido.")

    check_md_name = safe_filename.replace(".docx", ".md").replace(".txt", ".md").replace("_transcripcion", "")
    if not is_academic_study_note(check_md_name):
        raise HTTPException(status_code=400, detail="Operación no permitida: este endpoint es exclusivo para notas de estudio.")

    stem = Path(safe_filename).stem
    if stem.endswith("_transcripcion"):
        stem = stem[:-14]

    output_dir = server.get_data_output_dir()
    project_root = server.project_root
    candidate_dirs: List[Path] = []
    for cd in [Path("/app/outputs"), output_dir, project_root / "outputs", project_root / "data" / "output"]:
        try:
            if cd.exists():
                cd_res = cd.resolve()
                if cd_res not in [x.resolve() for x in candidate_dirs]:
                    candidate_dirs.append(cd)
        except Exception:
            pass
    if not candidate_dirs:
        candidate_dirs = [output_dir]

    deleted_files = []

    candidates = []
    for c_dir in candidate_dirs:
        candidates.extend([
            c_dir / f"{stem}.md",
            c_dir / f"{stem}.docx",
            c_dir / f"{stem}.json",
            c_dir / f"{stem}_transcripcion.txt",
            c_dir / f"{stem}.txt",
            c_dir / safe_filename,
        ])

    for c in set(candidates):
        try:
            if c.is_file():
                c.unlink()
                if c.name not in deleted_files:
                    deleted_files.append(c.name)
        except Exception as exc:
            print(f"[delete_academic_note] Warning deleting {c}: {exc}")

    if not deleted_files and not any((c_dir / safe_filename).is_file() for c_dir in candidate_dirs):
        raise HTTPException(status_code=404, detail="La nota de estudio no fue encontrada en el servidor.")

    try:
        hist_file = update_consolidated_academic_notes_file()
        server.trigger_drive_sync_background([hist_file])
        ds = server.GoogleDriveStorage()
        if ds.is_connected():
            asyncio.create_task(run_in_threadpool(ds.delete_file, safe_filename, "WhisperDnD"))
            asyncio.create_task(run_in_threadpool(ds.delete_file, safe_filename.replace(".md", ".docx"), "WhisperDnD"))
    except Exception as exc:
        print(f"[delete_academic_note] Warning syncing with Drive: {exc}")

    return {
        "success": True,
        "status": "deleted",
        "deleted_files": deleted_files,
        "message": f"Nota {safe_filename} y archivos asociados eliminados correctamente."
    }


@router.post("/api/notes/save")
@router.post("/api/academic-notes/save")
async def save_academic_note_endpoint(payload: server.SaveAcademicNoteRequest):
    """Save an academic study note, exporting markdown, docx, and optional transcript text."""
    content = server.normalize_academic_sections(payload.content.strip())
    if not content:
        raise HTTPException(status_code=400, detail="El contenido de la nota no puede estar vacío.")

    output_dir = server.get_data_output_dir()
    now_str, now_formatted, _ = server.parse_client_datetime(
        custom_date=getattr(payload, "custom_date", None),
        client_timezone_offset=getattr(payload, "client_timezone_offset", None),
    )
    clean_subj = re.sub(r'[\\/*?:"<>|]', "", (payload.subject or payload.topic or "apuntes").strip())
    safe_subject = re.sub(r"\s+", "_", clean_subj) or "apuntes"

    if payload.filename and payload.filename.strip():
        safe_filename = Path(payload.filename.strip()).name
        if not safe_filename.endswith(".md"):
            safe_filename = f"{safe_filename}.md"
        if not safe_filename.startswith("apuntes_"):
            safe_filename = f"apuntes_{safe_filename}"
    else:
        safe_filename = f"apuntes_{safe_subject}_{now_str}.md"

    md_path = output_dir / safe_filename
    md_path.write_text(content, encoding="utf-8")

    docx_filename = safe_filename.replace(".md", ".docx")
    docx_path = output_dir / docx_filename

    clean_title = extract_clean_note_title(safe_filename, content)
    formatted_date = format_note_date(md_path.stat().st_mtime, safe_filename)
    try:
        await run_in_threadpool(
            server.export_academic_notes_docx,
            notes_md=content,
            document_format="executive" if safe_filename.startswith("apuntes_reunion_") else "academic",
            subject=clean_title,
            topic=clean_title,
            lecture_date=formatted_date,
            output_path=str(docx_path),
        )
    except Exception as exc:
        print(f"[save_academic_note] Warning generating docx: {exc}")

    if payload.transcript and payload.transcript.strip():
        txt_filename = safe_filename.replace(".md", "_transcripcion.txt")
        (output_dir / txt_filename).write_text(payload.transcript.strip(), encoding="utf-8")

    try:
        hist_file = update_consolidated_academic_notes_file()
        sync_files = [hist_file, md_path]
        if docx_path.is_file():
            sync_files.append(docx_path)
        server.trigger_drive_sync_background(sync_files)
    except Exception as exc:
        print(f"[save_academic_note] Warning syncing with Drive: {exc}")

    return {
        "success": True,
        "status": "saved",
        "filename": safe_filename,
        "docx_filename": docx_filename,
        "message": f"Nota '{safe_filename}' guardada exitosamente."
    }


@router.post("/api/academic-notes/import")
@router.post("/api/notes/import")
async def import_academic_note_endpoint(file: UploadFile = File(...)):
    """
    Import an academic study note or backup archive (.md, .json, .zip, or .txt).
    Restores note files, updates data/apuntes_historial.json, and triggers background Google Drive sync.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No se seleccionó ningún archivo.")

    lower_name = file.filename.lower()
    if not (lower_name.endswith(".md") or lower_name.endswith(".json") or lower_name.endswith(".zip") or lower_name.endswith(".txt")):
        raise HTTPException(
            status_code=400,
            detail="Formato de archivo no soportado. Se admiten archivos .md, .json, .zip y .txt de apuntes."
        )

    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(status_code=400, detail="El archivo subido está vacío.")

    output_dir = server.get_data_output_dir()
    project_root = server.project_root
    imported_count = 0
    synced_files = []

    if lower_name.endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(content_bytes), "r") as zf:
                for item in zf.namelist():
                    if item.endswith("/") or item in ["manifest.json"]:
                        continue
                    item_name = Path(item).name
                    if item_name.endswith((".md", ".txt", ".docx", ".json")):
                        item_bytes = zf.read(item)
                        if item_name == "apuntes_historial.json":
                            (project_root / "data" / "apuntes_historial.json").write_bytes(item_bytes)
                        else:
                            target_p = output_dir / item_name
                            target_p.write_bytes(item_bytes)
                            if item_name.endswith(".md"):
                                imported_count += 1
                                synced_files.append(target_p)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="El archivo ZIP está dañado o no es válido.")

    elif lower_name.endswith(".json"):
        try:
            parsed = json.loads(content_bytes.decode("utf-8"))
            if isinstance(parsed, dict) and "notes" in parsed and isinstance(parsed["notes"], list):
                for n in parsed["notes"]:
                    if isinstance(n, dict) and n.get("filename") and n.get("content"):
                        target_p = output_dir / Path(n["filename"]).name
                        target_p.write_text(n["content"], encoding="utf-8")
                        imported_count += 1
                        synced_files.append(target_p)
            elif isinstance(parsed, dict) and ("content" in parsed or "chronicle" in parsed):
                content = parsed.get("content") or parsed.get("chronicle")
                title = parsed.get("title") or parsed.get("topic") or Path(file.filename).stem
                safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
                safe_title = re.sub(r"\s+", "_", safe_title)
                now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                target_filename = f"apuntes_{safe_title}_{now_str}.md"
                target_p = output_dir / target_filename
                target_p.write_text(content, encoding="utf-8")
                imported_count += 1
                synced_files.append(target_p)
            else:
                raise HTTPException(status_code=400, detail="El archivo JSON no contiene notas válidas.")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="El archivo JSON no es válido.")

    else:
        safe_name = Path(file.filename).name
        if not safe_name.startswith("apuntes_"):
            safe_name = f"apuntes_{safe_name}"
        if lower_name.endswith(".txt") and not safe_name.endswith(".md"):
            safe_name = safe_name.rsplit(".", 1)[0] + ".md"

        target_p = output_dir / safe_name
        target_p.write_bytes(content_bytes)
        imported_count += 1
        synced_files.append(target_p)

    hist_file = update_consolidated_academic_notes_file()
    if hist_file and hist_file.is_file():
        synced_files.append(hist_file)

    try:
        if synced_files:
            server.trigger_drive_sync_background(synced_files)
    except Exception as exc:
        print(f"[import_academic_note] Warning triggering drive sync: {exc}")

    return {
        "status": "success",
        "imported_notes": imported_count,
        "message": f"Se importaron exitosamente {imported_count} notas y se respaldaron en Google Drive.",
    }


@router.get("/api/academic-notes/download/{filename}")
@router.get("/api/notes/download/{filename}")
async def download_academic_note_docx(filename: str):
    """Download an academic note Word .docx document, compiling on the fly if needed."""
    decoded_filename = urllib.parse.unquote(filename)
    safe_filename = Path(decoded_filename).name

    md_check_name = safe_filename.replace(".docx", ".md") if safe_filename.endswith(".docx") else safe_filename
    if not is_academic_study_note(md_check_name):
        raise HTTPException(status_code=404, detail="Nota de estudio no encontrada.")

    output_dir = server.get_data_output_dir()
    project_root = server.project_root

    candidate_dirs: List[Path] = []
    for cd in [Path("/app/outputs"), output_dir, project_root / "outputs", project_root / "data" / "output"]:
        try:
            if cd.exists():
                cd_res = cd.resolve()
                if cd_res not in [x.resolve() for x in candidate_dirs]:
                    candidate_dirs.append(cd)
        except Exception:
            pass
    if not candidate_dirs:
        candidate_dirs = [output_dir]

    md_filename = safe_filename.replace(".docx", ".md") if safe_filename.endswith(".docx") else safe_filename
    if not md_filename.endswith(".md"):
        md_filename += ".md"

    md_path = None
    for c_dir in candidate_dirs:
        p = c_dir / md_filename
        if p.is_file():
            md_path = p
            break
        cand = c_dir / f"apuntes_{md_filename}"
        if cand.is_file():
            md_path = cand
            md_filename = cand.name
            break

    if safe_filename.endswith(".docx"):
        for c_dir in candidate_dirs:
            cand_docx = c_dir / safe_filename
            if cand_docx.is_file():
                if md_path and md_path.is_file():
                    if cand_docx.stat().st_mtime >= md_path.stat().st_mtime:
                        return FileResponse(
                            path=cand_docx,
                            filename=safe_filename,
                            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
                        )
                else:
                    return FileResponse(
                        path=cand_docx,
                        filename=safe_filename,
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
                    )

    if not md_path or not md_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo de apuntes (.md) no encontrado para generar docx.")

    content = md_path.read_text(encoding="utf-8", errors="replace")
    clean_title = extract_clean_note_title(md_filename, content)
    formatted_date = format_note_date(md_path.stat().st_mtime, md_filename)
    out_docx_filename = md_filename.replace(".md", ".docx")

    target_docx_path = output_dir / out_docx_filename

    try:
        await run_in_threadpool(
            server.export_academic_notes_docx,
            notes_md=content,
            document_format="executive" if safe_filename.startswith("apuntes_reunion_") else "academic",
            subject=clean_title,
            topic=clean_title,
            lecture_date=formatted_date,
            output_path=str(target_docx_path),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al compilar documento Word: {exc}")

    return FileResponse(
        path=target_docx_path,
        filename=out_docx_filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{out_docx_filename}"'},
    )
