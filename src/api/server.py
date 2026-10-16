"""FastAPI server for WhisperDnD live dual-channel recording and AI transcription."""

import asyncio
import datetime
import io
import json
import os
import re
import shutil
import sys
import time
import tempfile
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from starlette.concurrency import run_in_threadpool
from starlette.background import BackgroundTask

from src.exporters.docx_exporter import (
    export_chronicle_docx,
    export_living_journal_docx,
    export_session_docx,
    export_academic_notes_docx,
)
from src.exporters.md_exporter import (
    export_living_journal_md,
    export_session_md,
)
from src.storage.campaign_manager import CampaignManager
from src.storage.drive_client import GoogleDriveStorage
from src.summarizer.gemini_client import (
    GeminiTTRPGSummarizer,
    normalize_academic_sections,
)
from src.transcription.audio_recorder import (
    active_recorder,
    get_audio_devices,
    get_audio_levels,
)
from src.transcription.groq_whisper import GroqWhisperTranscriber
from src.transcription.local_whisper import LocalWhisperTranscriber
from src.transcription.youtube_downloader import download_youtube_audio

project_root = Path(__file__).resolve().parent.parent.parent


def get_data_input_dir() -> Path:
    env_dir = os.environ.get("WHISPER_INPUT_DIR")
    if env_dir:
        p = Path(env_dir).resolve()
    elif os.path.exists("/tmp") and os.path.isdir("/tmp") and sys.platform != "win32":
        p = Path("/tmp/whisper_input").resolve()
    else:
        p = (project_root / "data" / "input").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_data_output_dir() -> Path:
    env_dir = os.environ.get("WHISPER_OUTPUT_DIR")
    if env_dir:
        p = Path(env_dir).resolve()
    elif (project_root / "outputs").is_dir():
        p = (project_root / "outputs").resolve()
    else:
        p = (project_root / "data" / "output").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_data_campaigns_dir() -> Path:
    env_dir = os.environ.get("WHISPER_CAMPAIGNS_DIR")
    if env_dir:
        p = Path(env_dir).resolve()
    else:
        p = (project_root / "data" / "campaigns").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


data_input_dir = get_data_input_dir()
data_output_dir = get_data_output_dir()
data_campaigns_dir = get_data_campaigns_dir()
template_path = project_root / "static" / "index.html"


def get_campaign_path(campaign_name: str) -> Path:
    safe_name = CampaignManager().sanitize_name(str(campaign_name or "Campaña Principal"))
    return get_data_campaigns_dir() / f"{safe_name}.json"


# Ensure runtime directories exist
get_data_input_dir()
get_data_output_dir()
get_data_campaigns_dir()

# Support Google Credentials via Environment Variable (Render Docker / Cloud Run / Local)
_credentials_path = "/app/credentials.json" if (os.name != "nt" and Path("/app").is_dir()) else str(project_root / "credentials.json")
_env_creds = os.environ.get("GOOGLE_CREDENTIALS_JSON")
if _env_creds and not os.path.exists(_credentials_path):
    try:
        os.makedirs(os.path.dirname(_credentials_path), exist_ok=True)
        with open(_credentials_path, "w", encoding="utf-8") as _f:
            _f.write(_env_creds)
        print(f"Archivo {_credentials_path} generado con éxito desde variable de entorno.")
    except Exception as _e:
        print(f"Error escribiendo credentials.json: {_e}")

app = FastAPI(
    title="WhisperDnD - Live Session Recorder & Living Campaign Journal",
    description="Dual-channel audio recording with faster-whisper, Gemini Living Campaign Journal & Google Drive.",
    version="3.0.0",
)


@app.on_event("startup")
async def on_server_startup():
    """Start background sync from Google Drive and retroactive deduplication without blocking HTTP readiness."""
    async def _async_startup_tasks():
        try:
            drive_storage = GoogleDriveStorage()
            if drive_storage.is_connected():
                print("[Server Startup] Google Drive connected. Restoring campaigns and notes from Drive in background...")
                sync_res = await run_in_threadpool(
                    drive_storage.sync_from_google_drive,
                    get_data_campaigns_dir(),
                    get_data_output_dir(),
                )
                print(f"[Server Startup] Drive restore complete: {sync_res.get('message', '')}")
        except Exception as exc:
            print(f"[Server Startup] Drive restore on startup skipped or failed: {exc}")

        try:
            manager = CampaignManager()
            results = manager.deduplicate_all_campaigns()
            if results:
                print(f"[Server Startup] Retroactive entity deduplication applied: {len(results)} campaign(s) cleaned: {results}")
        except Exception as e:
            print(f"[Server Startup] Error during retroactive entity deduplication: {e}")

    asyncio.create_task(_async_startup_tasks())


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = project_root / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/api/ping")
@app.get("/api/health")
async def keep_alive_ping():
    """Lightweight keep-alive heartbeat ping to prevent Render container spindown during active recording."""
    return {"status": "alive", "timestamp": time.time()}


@app.post("/api/shutdown")
@app.get("/api/shutdown")
async def shutdown_server():
    """Cleanly terminate the application server process upon client window close."""
    if os.environ.get("WHISPER_ENV") in ("test", "testing") or os.environ.get("TESTING") == "1":
        return {"status": "shutdown_simulated", "message": "Test mode: shutdown not executed"}

    def _delayed_exit():
        time.sleep(0.75)
        try:
            if active_recorder and active_recorder.is_recording:
                active_recorder.stop()
        except Exception:
            pass
        os._exit(0)

    import threading
    threading.Thread(target=_delayed_exit, daemon=True).start()
    return {"status": "shutting_down", "message": "Servidor finalizado exitosamente."}


def trigger_drive_sync_background(
    file_paths: Optional[List[Union[str, Path]]] = None,
    folder_name: str = "WhisperDnD",
):
    """
    Fire-and-forget background upload of modified file(s) to Google Drive.
    If Google Drive is not connected or in test mode, fails silently and cleanly.
    """
    if os.environ.get("WHISPER_ENV") in ("test", "testing") or os.environ.get("TESTING") == "1":
        return

    try:
        ds = GoogleDriveStorage()
        if not ds.is_connected():
            return

        async def _worker():
            try:
                if file_paths:
                    for fp in file_paths:
                        p = Path(fp).resolve()
                        if p.is_file():
                            # Quality filter: reject tiny test or incomplete notes (<500 bytes or <100 words)
                            if p.name.endswith(".md") and not p.name.lower().endswith("_grimorio.md") and p.name != "manifest.md":
                                if p.stat().st_size < 500:
                                    continue
                                txt_preview = p.read_text(encoding="utf-8", errors="replace")
                                if len(txt_preview.strip().split()) < 100:
                                    continue
                            await run_in_threadpool(ds.upload_file, str(p), folder_name=folder_name)
                else:
                    camp_dir = get_data_campaigns_dir()
                    out_dir = get_data_output_dir()
                    await run_in_threadpool(ds.sync_from_google_drive, camp_dir, out_dir)
            except Exception as e:
                print(f"[DriveBackgroundSync] Warning during background upload: {e}")

        asyncio.create_task(_worker())
    except Exception as exc:
        print(f"[DriveBackgroundSync] Could not schedule background sync: {exc}")


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------
class PlayerMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    player_name: str = Field(default="", description="Name of the player")
    character_name: str = Field(default="-", description="Character name")
    species: Optional[str] = Field(default="", description="Species or race (e.g. Elfo, Humano)")
    role: str = Field(default="Aventurero", description="Role or class (e.g. Dungeon Master, Paladín)")
    subclass: Optional[str] = Field(default="", description="Subclass (e.g. Battle Master)")
    is_user_character: Optional[bool] = Field(default=False, description="Whether this character is the user's personal character for roleplay reflection")
    is_absent: Optional[bool] = Field(default=False, description="Whether this player is absent for the current session (temporary, zero-memory)")
    discord_user_id: Optional[str] = Field(default=None, description="Linked Discord user ID for immutable speaker identification")
    discord_id: Optional[str] = Field(default=None, description="Linked Discord ID")
    discord_username: Optional[str] = Field(default=None, description="Linked Discord username")
    discord_tag: Optional[str] = Field(default=None, description="Linked Discord tag")



def extract_academic_sections(chronicle_md: str) -> Tuple[List[str], str]:
    """
    Extract action items / tasks list and key points / glossary from academic markdown.
    Key points contains strictly Glossary and Techniques without repeating Section 5 or Section 6.
    """
    if not chronicle_md:
        return [], ""

    chronicle_md = normalize_academic_sections(chronicle_md)

    action_items: List[str] = []
    # 1. Search for Section 6 (or Section 5 in legacy notes): Avisos Relevantes / Tareas / Deliverables
    sec_task_match = re.search(
        r'(?:^|\n)#+\s*(?:5|6)\.\s*(?!(?:Conclusiones|Key Takeaways|Resumen|Summary))(?:Avisos Relevantes|Avisos|Tareas y Entregables|Tareas y Próximos Pasos|Tareas|Entregables|Pendientes|Announcements|Deadlines|Deliverables).*?\n(.*?)(?=\n#+\s*\d\.|\Z)',
        chronicle_md,
        re.DOTALL | re.IGNORECASE,
    )
    if sec_task_match:
        content = sec_task_match.group(1).strip()
        for line in content.split('\n'):
            line_str = line.strip()
            m = re.match(r'^(?:[-*+]\s*(?:\[[ xX]\]\s*)?|\d+[\.)]\s+)(.+)$', line_str)
            if m:
                item_text = m.group(1).strip()
                if item_text and not item_text.lower().startswith(('no se anunciaron', 'no se mencionaron', 'no hay tareas', 'no hay', 'ninguna', 'ninguno', 'no assignments', 'none')):
                    action_items.append(item_text)

    # 2. Check for embedded task sub-blocks if no top-level section matched
    if not action_items:
        task_sub = re.search(
            r'\n\s*(?:Tareas y acuerdos|Acuerdos de acción|Acciones pendientes|Tareas pendientes|Tasks).*?\n(.*?)(?=\n\s*[-*+]\s*3\s*(?:a|to)\s*5|\n#+|\Z)',
            chronicle_md,
            re.DOTALL | re.IGNORECASE,
        )
        if task_sub:
            for line in task_sub.group(1).split('\n'):
                m = re.match(r'^(?:[-*+]\s*(?:\[[ xX]\]\s*)?|\d+[\.)]\s+)(.+)$', line.strip())
                if m:
                    item_text = m.group(1).strip()
                    if item_text and not item_text.lower().startswith(('no se anunciaron', 'no se mencionaron', 'no hay', 'ninguna', 'ninguno', 'no assignments', 'none')):
                        action_items.append(item_text)

    # 3. Extract Key Points & Glossary cleanly: ONLY Glossary & Techniques, NO repetition of Section 5 or 6!
    sec2_match = re.search(
        r'(?:^|\n)(?:#{1,2}\s*2\.\s*[^\n]+\n)([\s\S]*?)(?=\n#{1,2}\s*3\.|\Z)',
        chronicle_md,
        re.IGNORECASE,
    )
    key_points = ""
    if sec2_match:
        sec2_body = sec2_match.group(1).strip()
        sec2_body = re.sub(r'\n---+\s*$', '', sec2_body).strip()

        has_glossary_sub = bool(re.search(r'###\s*(?:📖\s*)?Glosario', sec2_body, re.I))
        has_tech_sub = bool(re.search(r'###\s*(?:🛠️\s*)?Técnicas', sec2_body, re.I))

        parts = []
        if has_glossary_sub or has_tech_sub:
            parts.append(sec2_body)
        else:
            body_clean = re.sub(r'^(?:A continuación[^\n]+\n+|To understand[^\n]+\n+)', '', sec2_body, flags=re.I).strip()
            parts.append(f"### 📖 Glosario Conceptual\n{body_clean}")

        if not has_tech_sub:
            tech_snippets = []
            for m in re.finditer(r'(?m)^(###\s*(?:[^\n]*(?:Estrategia|Técnica|Protocol|Step Strategy|Method|Procedimiento)[^\n]*))\n([\s\S]*?)(?=(?:^#{1,3}\s|\Z))', chronicle_md):
                h = m.group(1).strip()
                b = m.group(2).strip()
                if b and len(b) > 40:
                    tech_snippets.append(f"{h}\n{b}")
            if tech_snippets:
                parts.append("### 🛠️ Técnicas y Procedimientos Clave\n" + "\n\n".join(tech_snippets[:2]))

        key_points = "\n\n---\n\n".join(parts)

    return action_items, key_points


class DriveExportRequest(BaseModel):
    file_path: str = Field(..., description="Local path or filename of the file to upload to Google Drive")




class SaveAcademicNoteRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    filename: Optional[str] = Field(default=None, description="Filename (e.g. apuntes_materia_2026.md)")
    title: Optional[str] = Field(default=None, description="Title of the note")
    subject: Optional[str] = Field(default="Materia Universitaria", description="Subject")
    topic: Optional[str] = Field(default="Tema de Clase", description="Topic")
    content: str = Field(..., description="Markdown content of the note")
    transcript: Optional[str] = Field(default=None, description="Raw audio transcript")


class DriveExportResponse(BaseModel):
    status: str
    web_view_link: str
    file_name: str
    file_id: Optional[str] = None


class DiscardTranscriptRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    filename: Optional[str] = Field(default=None, description="Filename of raw transcript txt to delete")
    campaign_name: Optional[str] = Field(default=None, description="Campaign name")
    session_number: Optional[int] = Field(default=None, description="Session number")
    note_filename: Optional[str] = Field(default=None, description="Note filename")


class RestoreDriveTokenRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    token_data: Optional[Union[Dict[str, Any], str]] = Field(default=None, description="Token JSON or dict from localStorage")


# ---------------------------------------------------------------------------
# Endpoints: Frontend SPA
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the single-page application with cache-busting headers."""
    html_file = project_root / "static" / "index.html"
    if not html_file.is_file():
        raise HTTPException(status_code=404, detail="static/index.html not found.")
    
    response = HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


@app.api_route("/manifest.json", methods=["GET", "HEAD"])
async def get_manifest():
    manifest_file = project_root / "static" / "manifest.json"
    if manifest_file.is_file():
        return FileResponse(manifest_file, media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="manifest.json not found")


@app.api_route("/sw.js", methods=["GET", "HEAD"])
async def get_service_worker():
    sw_file = project_root / "static" / "sw.js"
    if sw_file.is_file():
        return FileResponse(
            sw_file,
            media_type="application/javascript",
            headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"}
        )
    raise HTTPException(status_code=404, detail="sw.js not found")


@app.api_route("/icon-192.png", methods=["GET", "HEAD"])
async def get_icon_192():
    icon_file = project_root / "static" / "icon-192.png"
    if icon_file.is_file():
        return FileResponse(icon_file, media_type="image/png")
    raise HTTPException(status_code=404, detail="icon-192.png not found")


@app.api_route("/icon-512.png", methods=["GET", "HEAD"])
async def get_icon_512():
    icon_file = project_root / "static" / "icon-512.png"
    if icon_file.is_file():
        return FileResponse(icon_file, media_type="image/png")
    raise HTTPException(status_code=404, detail="icon-512.png not found")


# ---------------------------------------------------------------------------
# Helper: Living Campaign Session Processor
# ---------------------------------------------------------------------------
def process_session_for_campaign(
    campaign_name: str,
    transcript_text: str,
    roster_dicts: Optional[List[Dict[str, Any]]] = None,
    session_number: Optional[int] = None,
    target_language: str = "es",
    is_youtube: bool = False,
    gemini_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a session transcript for a living campaign:
    1. Get active context (quests, NPCs, last recap, next session #).
    2. Query Gemini for structured session chapter and cumulative updates.
    3. Record and persist the session in CampaignManager.
    4. Export the unified Living Campaign Journal into .docx and .md.
    """
    manager = CampaignManager()
    active_ctx = manager.get_active_context(campaign_name)
    actual_session_num = session_number or active_ctx["session_number"]

    is_private = (campaign_name or "").strip().lower() in ("campaña principal", "campana principal")

    # Filter out empty or blank rows from roster_dicts
    clean_roster_dicts = [
        p for p in (roster_dicts or [])
        if (p.get("player_name") and p.get("player_name").strip())
        or (p.get("character_name") and p.get("character_name").strip() not in ("", "(DM)", "-"))
    ]

    saved_roster = active_ctx.get("roster", [])
    # If external YouTube campaign and saved_roster has a user character from a live campaign, purge it
    if is_youtube and saved_roster:
        if any(p.get("is_user_character") for p in saved_roster):
            saved_roster = []

    final_roster = clean_roster_dicts if len(clean_roster_dicts) > 0 else saved_roster

    # Determine user character (strictly disabled for YouTube; only enabled if star is selected)
    user_character = None
    if not is_youtube:
        user_character = next((p for p in final_roster if p.get("is_user_character") and not p.get("is_absent")), None)
        if user_character is None:
            user_character = None  # Explicitly no user character — coaching disabled

    summarizer = GeminiTTRPGSummarizer(api_key=gemini_api_key)
    session_data = summarizer.generate_campaign_session(
        transcript_text=transcript_text,
        roster=final_roster,
        existing_quests=active_ctx.get("all_quests", []),
        known_npcs=active_ctx.get("known_npcs", []),
        session_number=actual_session_num,
        target_language=target_language,
        user_character=user_character,
        is_youtube=is_youtube,
        prior_lore=active_ctx.get("prior_lore", ""),
        character_backstory=active_ctx.get("user_character_backstory", ""),
        last_session_recap=active_ctx.get("last_session_recap", ""),
    )

    s_title = session_data.get("session_title") or session_data.get("session_chapter", {}).get("session_title") or session_data.get("session_chapter", {}).get("title")
    if s_title:
        session_data.setdefault("session_chapter", {})["session_title"] = s_title
        session_data["session_chapter"]["title"] = s_title

    detected_party = session_data.get("detected_party", [])
    detected_pcs = session_data.get("detected_pcs", [])

    is_en = str(target_language).lower().startswith("en")
    ch = session_data["session_chapter"]
    chronicle_parts = []
    next_sess_num = actual_session_num + 1

    sec_idx = 1
    # 1. Crónica Narrativa y Combates
    sec1_title = f"## {sec_idx}. Narrative Chronicle & Combat" if is_en else f"## {sec_idx}. Crónica Narrativa y Combates"
    if ch.get("chronicle_text"):
        chronicle_parts.append(f"{sec1_title}\n{ch['chronicle_text']}")
    sec_idx += 1

    # 2. Cierre de Mesa, Decisiones y Expectativas
    if ch.get("closing_expectations"):
        sec2_title = f"## {sec_idx}. Table Closing, Decisions & Expectations" if is_en else f"## {sec_idx}. Cierre de Mesa, Decisiones y Expectativas"
        chronicle_parts.append(f"{sec2_title}\n{ch['closing_expectations']}")
        sec_idx += 1

    if is_youtube:
        # 3. 📌 Sinopsis Ejecutiva del Episodio (Executive Episode Synopsis for YouTube)
        synopsis_text = (ch.get("episode_synopsis") or "").strip()
        if synopsis_text:
            sec3_title = f"## {sec_idx}. 📌 Executive Episode Synopsis" if is_en else f"## {sec_idx}. 📌 Sinopsis Ejecutiva del Episodio"
            chronicle_parts.append(f"{sec3_title}\n{synopsis_text}")
            sec_idx += 1
    else:
        # 3. Reflexión de Rol y Compañerismo (Conditional: only if user_character and coaching exists)
        coaching_text = (ch.get("user_coaching") or ch.get("markus_coaching") or "").strip()
        if user_character and coaching_text:
            char_name = (user_character.get("character_name") or user_character.get("name") or "Personaje").strip()
            sec3_title = f"## {sec_idx}. Roleplay & Comradery Reflection: {char_name}" if is_en else f"## {sec_idx}. Reflexión de Rol y Compañerismo: {char_name}"
            chronicle_parts.append(f"{sec3_title}\n{coaching_text}")
            sec_idx += 1

        # 4. 🎙️ Guion para abrir la Sesión {next_sess_num} (Para leer en voz alta)
        script_text = (ch.get("next_session_script") or ch.get("recap_text") or "").strip()
        if script_text:
            script_title = (
                f"## {sec_idx}. 🎙️ Script to Open Session #{next_sess_num} (Read Aloud)"
                if is_en
                else f"## {sec_idx}. 🎙️ Guion para abrir la Sesión #{next_sess_num} (Para leer en voz alta)"
            )
            chronicle_parts.append(f"{script_title}\n{script_text}")

    pcs_to_show = detected_pcs if detected_pcs else [
        {
            "personaje": p.get("character_name", "-"),
            "jugador": p.get("player_name", "-"),
            "clase": p.get("role", "-"),
            "especie": p.get("species", "-"),
            "rol_en_sesion": p.get("session_role", "-"),
        }
        for p in detected_party
    ]
    if pcs_to_show is None:
        pcs_to_show = []

    # Ensure absent characters from roster are reflected in the table without being eliminated
    existing_char_names = {str(p.get("personaje") or p.get("character_name", "")).strip().lower() for p in (pcs_to_show or [])}
    for r in (final_roster or []):
        r_char = str(r.get("character_name", "")).strip()
        if r.get("is_absent") and r_char and r_char not in ("(DM)", "-", ""):
            absent_role_text = "Ausente en esta sesión (permanece con la compañía)" if not is_en else "Absent this session (remains with the party)"
            if r_char.lower() not in existing_char_names:
                pcs_to_show.append({
                    "personaje": r_char,
                    "jugador": str(r.get("player_name", "-")).strip() or "-",
                    "clase": str(r.get("role", "-")).strip() or "-",
                    "especie": str(r.get("species", "-")).strip() or "-",
                    "rol_en_sesion": absent_role_text,
                })
                existing_char_names.add(r_char.lower())
            else:
                for p in pcs_to_show:
                    if str(p.get("personaje") or p.get("character_name", "")).strip().lower() == r_char.lower():
                        p["rol_en_sesion"] = absent_role_text

    protagonists_table = ""
    if pcs_to_show:
        if is_en:
            proto_title = "### 🎭 Adventuring Company (Detected Protagonists)"
            table_header = "| Character | Player / Role | Class / Species | Session Role |\n|---|---|---|---|"
        else:
            proto_title = "### 🎭 Compañía de Aventureros (Protagonistas Detectados)"
            table_header = "| Personaje | Jugador / Rol | Clase / Especie | Rol en la Sesión |\n|---|---|---|---|"
        rows = []
        for p in pcs_to_show:
            char = p.get("personaje") or "-"
            player = p.get("jugador") or "-"
            cls = p.get("clase") or "-"
            spec = p.get("especie") or "-"
            if cls != "-" and spec != "-":
                cls_spec = f"{cls} / {spec}"
            elif cls != "-":
                cls_spec = cls
            else:
                cls_spec = spec
            sess_role = p.get("rol_en_sesion") or "-"
            rows.append(f"| **{char}** | {player} | {cls_spec} | {sess_role} |")
        if rows:
            protagonists_table = f"{proto_title}\n\n" + table_header + "\n" + "\n".join(rows) + "\n\n---\n"

    chronicle_body = "\n\n".join(chronicle_parts) or ch.get("chronicle_text", "")
    chronicle_md = f"{protagonists_table}\n\n{chronicle_body}".strip() if protagonists_table else chronicle_body

    campaign_state = manager.record_session(
        name=campaign_name,
        session_chapter=session_data["session_chapter"],
        updated_quests=session_data.get("updated_quests"),
        updated_npcs=session_data.get("updated_npcs"),
        detected_npc_names=session_data.get("detected_npc_names"),
        roster=final_roster,
        session_number=actual_session_num,
        detected_party=detected_party,
        user_character=user_character,
        detected_pcs=detected_pcs,
        is_youtube=is_youtube,
        chronicle_markdown=chronicle_md,
        raw_transcript=transcript_text,
        locations=session_data.get("locations"),
        items=session_data.get("items"),
    )

    docx_file = export_living_journal_docx(campaign_state)
    md_file = export_living_journal_md(campaign_state)

    # Save standalone plain-text transcript to data/output/
    safe_name = manager.sanitize_name(campaign_name)
    txt_filename = f"{safe_name}_sesion_{actual_session_num}_transcripcion.txt"
    try:
        txt_path = get_data_output_dir() / txt_filename
        txt_path.write_text(transcript_text, encoding="utf-8")
        # Also maintain generic/latest transcript
        (get_data_output_dir() / f"{safe_name}_transcripcion.txt").write_text(transcript_text, encoding="utf-8")
    except Exception as exc:
        print(f"[process_session_for_campaign] Warning: could not write txt transcript: {exc}")

    return {
        "status": "completed",
        "campaign_name": campaign_name,
        "session_number": actual_session_num,
        "session_chapter": session_data["session_chapter"],
        "detected_pcs": detected_pcs,
        "detected_party": detected_party,
        "updated_quests": session_data.get("updated_quests", []),
        "updated_npcs": session_data.get("updated_npcs", []),
        "detected_npc_names": session_data.get("detected_npc_names", []),
        "campaign_state": campaign_state,
        "docx_filename": Path(docx_file).name,
        "md_filename": Path(md_file).name,
        "txt_filename": txt_filename,
        "file_path": str(Path(docx_file).resolve()),
        "chronicle": chronicle_md,
        "chronicle_markdown": chronicle_md,
        "raw_transcript": transcript_text,
        "target_language": target_language,
    }


# ---------------------------------------------------------------------------
# In-Memory Progress Tracking for Tasks
# ---------------------------------------------------------------------------
task_progress_state: Dict[str, Dict[str, Any]] = {}


def diagnose_exception(exc: Exception) -> tuple[str, str, str]:
    """
    Classify an exception into (error_type, friendly_spanish_message, stage).
    """
    err = str(exc)
    err_lower = err.lower()
    exc_type = type(exc).__name__

    # 1. YouTube issues
    if "yt_dlp" in err_lower or "youtube" in err_lower or "video unavailable" in err_lower or "sign in to confirm" in err_lower:
        return (
            "YouTubeDownloadError",
            f"Error al descargar el audio del enlace de YouTube: {err}",
            "Descarga de YouTube",
        )

    # 2. Transcription with Groq or faster-whisper
    if "groq" in err_lower or "whisper" in err_lower or "transcri" in err_lower:
        if "429" in err or "rate limit" in err_lower:
            return (
                "TranscriptionError",
                "Límite de tasa excedido en la API de Groq Whisper (Rate Limit). Espera unos instantes antes de intentar nuevamente.",
                "Transcripción con Groq",
            )
        if "groq_api_key" in err_lower or "clave de api" in err_lower:
            return (
                "TranscriptionError",
                "Clave de API de Groq no configurada o inválida en el servidor.",
                "Transcripción con Groq",
            )
        return (
            "TranscriptionError",
            f"Fallo durante la transcripción de audio con Groq: {err}",
            "Transcripción con Groq",
        )

    # 3. Gemini API / LLM issues
    if "gemini" in err_lower or "google.api_core" in err_lower or "google.genai" in err_lower or "generativeai" in err_lower or "resource_exhausted" in err_lower:
        if "resource_exhausted" in err_lower or "quota" in err_lower or "429" in err:
            return (
                "GeminiAPIError",
                "Cuota de la API de Google Gemini excedida temporalmente o límite de tasa alcanzado. Intenta nuevamente en un momento.",
                "Síntesis con Gemini",
            )
        return (
            "GeminiAPIError",
            f"Error al generar la crónica o apuntes con Google Gemini: {err}",
            "Síntesis con Gemini",
        )

    # 4. FFmpeg / Audio cutting
    if "ffmpeg" in err_lower:
        return (
            "AudioProcessingError",
            f"Error al procesar o segmentar el archivo de audio con FFmpeg: {err}",
            "Segmentación de audio",
        )

    # 5. Network / Timeout
    if "timeout" in err_lower or "timed out" in err_lower:
        return (
            "TimeoutError",
            "Tiempo de espera agotado al conectar con los servicios en la nube.",
            "Conectividad de red",
        )

    # Default fallback
    fallback_type = "ServerError" if exc_type in ("Exception", "RuntimeError") else exc_type
    return (
        fallback_type,
        f"Error en el procesamiento del servidor: {err}",
        "Procesamiento",
    )


def format_human_error(exc: Exception) -> str:
    """Format exceptions into clear, actionable human-readable messages."""
    _, msg, _ = diagnose_exception(exc)
    return msg


def update_task_progress(
    task_id: Optional[str],
    percent: Union[int, float],
    step: str,
    message: str = "",
    status: Optional[str] = None,
    stage: Optional[str] = None,
) -> None:
    """Update progress for a specific task ID."""
    if not task_id:
        return
    pct = round(max(0.0, min(100.0, float(percent))), 1)
    current_status = status or ("completed" if pct >= 100.0 else "running")

    # Determine or preserve stage
    prev_task = task_progress_state.get(task_id, {})
    current_stage = stage or prev_task.get("stage")
    if not current_stage:
        if pct < 20.0:
            current_stage = "audio"
        elif pct < 30.0:
            current_stage = "segmenting"
        elif pct < 80.0:
            current_stage = "transcribing"
        elif pct < 100.0:
            current_stage = "analyzing"
        else:
            current_stage = "done"

    task_progress_state[task_id] = {
        "task_id": task_id,
        "percent": pct,
        "step": step,
        "message": message or step,
        "timestamp": time.time(),
        "status": current_status,
        "stage": current_stage,
    }


def set_task_error(
    task_id: Optional[str],
    error_message: str,
    error_type: str = "ServerError",
    stage: str = "Procesamiento",
    details: str = "",
) -> None:
    """Register an error state for a task so frontend displays prominent error card."""
    if not task_id:
        return
    task_progress_state[task_id] = {
        "task_id": task_id,
        "percent": 0.0,
        "step": f"Error en {stage}",
        "message": error_message,
        "error_message": error_message,
        "error_type": error_type,
        "stage": stage,
        "details": details or error_message,
        "timestamp": time.time(),
        "status": "error",
        "success": False,
    }


def is_task_cancelled(task_id: Optional[str]) -> bool:
    """Check if task was marked as cancelled by the client."""
    if not task_id:
        return False
    return task_progress_state.get(task_id, {}).get("status") == "cancelled"


def get_task_progress(task_id: str) -> Dict[str, Any]:
    """Retrieve progress state for a task."""
    return task_progress_state.get(task_id, {
        "task_id": task_id,
        "percent": 0.0,
        "step": "Iniciando proceso...",
        "message": "Preparando...",
        "status": "pending",
        "stage": "audio",
    })


# ---------------------------------------------------------------------------
# Global Exception Handlers (Always return structured JSON diagnostics)
# ---------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    err_type, human_msg, stage = diagnose_exception(exc)
    detail = exc.detail
    details_str = str(detail)
    if isinstance(detail, dict):
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_type": err_type,
            "message": str(detail) if detail else human_msg,
            "stage": stage,
            "details": details_str,
            "detail": str(detail) if detail else human_msg,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    tb = traceback.format_exc()
    err_type, human_msg, stage = diagnose_exception(exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error_type": err_type,
            "message": human_msg,
            "stage": stage,
            "details": tb,
            "detail": human_msg,
        },
    )


# ---------------------------------------------------------------------------
# Multi-Tenant Client API Keys & Dynamic OAuth Helpers
# ---------------------------------------------------------------------------
def extract_client_api_keys(request: Optional[Request] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract multi-tenant client API keys:
    Prioritize HTTP request headers ('X-Groq-Api-Key', 'X-Gemini-Api-Key') over server environment variables.
    """
    if request:
        groq_key = (request.headers.get("X-Groq-Api-Key") or os.environ.get("GROQ_API_KEY", "")).strip() or None
        gemini_key = (request.headers.get("X-Gemini-Api-Key") or os.environ.get("GEMINI_API_KEY", "")).strip() or None
    else:
        groq_key = os.environ.get("GROQ_API_KEY", "").strip() or None
        gemini_key = os.environ.get("GEMINI_API_KEY", "").strip() or None
    return groq_key, gemini_key


def validate_api_keys_or_raise(
    request: Optional[Request],
    groq_key: Optional[str],
    gemini_key: Optional[str],
    require_gemini: bool = True,
    require_groq: bool = False,
) -> None:
    """
    If running via an HTTP request and neither key is provided, or if Gemini key is required and missing,
    raise HTTP 401 with a clear multi-tenant message.
    """
    if request is not None:
        if (not groq_key and not gemini_key) or (require_gemini and not gemini_key) or (require_groq and not groq_key):
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "API_KEYS_REQUIRED",
                    "message": "Por favor ingresa tus API keys de Groq y Gemini en la sección de Ajustes para continuar.",
                },
            )


def get_oauth_redirect_uri(request: Optional[Request] = None, custom_redirect: Optional[str] = None) -> str:
    """
    Dynamically build OAuth redirect_uri:
    1. custom_redirect if provided.
    2. RENDER_EXTERNAL_URL if running on Render.
    3. Host/Scheme headers from incoming HTTP request.
    4. Fallback to http://localhost:8080.
    """
    if custom_redirect:
        return custom_redirect
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        base = render_url.rstrip("/")
    elif request:
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc or "localhost:8080"
        scheme = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
        base = f"{scheme}://{host}".rstrip("/")
    else:
        base = "http://localhost:8080"

    path = "/api/auth/drive/callback" if (request and request.url.path.endswith("/api/auth/drive/callback")) else "/oauth2callback"
    return f"{base}{path}"


def build_whisper_prompt(
    campaign_name: Optional[str] = None,
    roster: Optional[List[Dict[str, Any]]] = None,
    language: Optional[str] = None,
    recording_mode: Optional[str] = None,
    subject: Optional[str] = None,
    topic: Optional[str] = None,
) -> Optional[str]:
    """
    Build a compact vocabulary prompt for Whisper (Groq/Faster-Whisper) to bias phonetic
    recognition toward campaign proper nouns, player character names, NPCs, technical terms, and topics.
    Keeps within Whisper's ~224 token limit without introducing repetitive edition hallucination prefixes (e.g. '5e:').
    Does NOT output language instructions or dummy conversational phrases that cause translation loops or Spanglish drift.
    """
    terms: List[str] = []
    seen = set()

    def add_term(term: Any):
        t = str(term or "").strip()
        # Filter out placeholders, DM tags, short noise, bracketed names
        if not t or len(t) < 2 or "[" in t or t.lower() in seen or t.lower() in ("-", "(dm)", "dm", "dungeon master", "n/a", "(n/a - dm)"):
            return
        seen.add(t.lower())
        terms.append(t)

    is_academic = (recording_mode == "class") or bool(subject or topic)

    if is_academic:
        if subject:
            add_term(subject)
        if topic:
            add_term(topic)
    else:
        # 1. Campaign Name
        if campaign_name:
            add_term(campaign_name)

        # 2. Characters & Players from provided roster
        for p in (roster or []):
            if isinstance(p, dict):
                add_term(p.get("character_name") or p.get("personaje"))
                add_term(p.get("player_name") or p.get("jugador"))
                add_term(p.get("species") or p.get("especie"))

        # 3. Load Campaign State for NPCs, locations, and lore terms
        if campaign_name:
            try:
                manager = CampaignManager()
                state = manager.load_campaign(campaign_name)
                # Roster stored in campaign
                for p in state.get("roster", []):
                    if isinstance(p, dict):
                        add_term(p.get("character_name") or p.get("personaje"))
                        add_term(p.get("player_name") or p.get("jugador"))
                        add_term(p.get("species") or p.get("especie"))
                # Known NPCs
                for n in state.get("npcs", []):
                    if isinstance(n, dict):
                        add_term(n.get("name"))
                # Universal PCs
                for upc in state.get("universal_pcs", []):
                    if isinstance(upc, dict):
                        add_term(upc.get("personaje"))
                        add_term(upc.get("especie") or upc.get("species"))
                # Known Quests (keywords)
                for q in state.get("quests", []):
                    if isinstance(q, dict):
                        add_term(q.get("title"))
                # Locations
                for loc in state.get("locations", []):
                    if isinstance(loc, dict):
                        add_term(loc.get("name"))
                    elif isinstance(loc, str):
                        add_term(loc)
                # Glossary and Lore terms
                for g in state.get("glossary", []):
                    if isinstance(g, dict):
                        add_term(g.get("term") or g.get("name"))
                    elif isinstance(g, str):
                        add_term(g)
            except Exception as exc:
                print(f"[build_whisper_prompt] Warning loading campaign '{campaign_name}': {exc}")

    if not terms:
        return None

    # Construct concise prompt (max ~200 tokens / 800 chars) with vocabulary ONLY
    prompt_text = ", ".join(terms)
    if len(prompt_text) > 800:
        prompt_text = prompt_text[:797] + "..."
    return prompt_text


# ---------------------------------------------------------------------------
# Helper: Audio Transcription Pipeline (Groq Cloud vs Local Whisper)
# ---------------------------------------------------------------------------
def transcribe_audio_pipeline(
    audio_path: str,
    engine: str = "groq",
    model_size: str = "base",
    language: Optional[str] = None,
    on_progress: Optional[Callable[[int, str], None]] = None,
    source: str = "local",
    user_char_name: Optional[str] = None,
    speaking_log: Optional[List[Dict[str, Any]]] = None,
    roster: Optional[List[Dict[str, Any]]] = None,
    groq_api_key: Optional[str] = None,
    campaign_name: Optional[str] = None,
    prompt: Optional[str] = None,
    recording_mode: Optional[str] = None,
    subject: Optional[str] = None,
    topic: Optional[str] = None,
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Route transcription to Groq Cloud (whisper-large-v3) or Local faster-whisper.
    Falls back gracefully to local whisper if Groq is requested but fails or lacks API key.
    Includes campaign vocabulary biasing (prompt / initial_prompt) for fantasy entity recognition.
    Supports audio language auto-detection when language is None or 'auto'.
    """
    if task_id and is_task_cancelled(task_id):
        raise RuntimeError("Proceso cancelado por el usuario.")

    def _safe_progress(pct: int, msg: str):
        if task_id and is_task_cancelled(task_id):
            raise RuntimeError("Proceso cancelado por el usuario.")
        if on_progress:
            on_progress(pct, msg)

    engine_choice = (engine or "groq").lower().strip()
    whisper_lang = None
    if language and str(language).lower() not in ("auto", "none", ""):
        whisper_lang = str(language).lower().strip()

    # Automatically load timeline speaking_log for local audio reprocessing
    if speaking_log is None and audio_path:
        try:
            from src.transcription.audio_recorder import load_timeline_for_audio
            speaking_log = load_timeline_for_audio(audio_path)
            if speaking_log:
                print(f"[transcribe_pipeline] Loaded {len(speaking_log)} events from timeline file for {audio_path}")
        except Exception as tl_exc:
            print(f"[transcribe_pipeline] Timeline load notice: {tl_exc}")

    whisper_prompt = prompt or build_whisper_prompt(
        campaign_name=campaign_name,
        roster=roster,
        language=whisper_lang,
        recording_mode=recording_mode,
        subject=subject,
        topic=topic,
    )

    # Auto-level dual-channel audio before chunking or Whisper diarization
    try:
        from src.transcription.audio_recorder import normalize_dual_channel_audio
        if audio_path and Path(audio_path).is_file() and str(audio_path).lower().endswith(".wav"):
            normalize_dual_channel_audio(audio_path)
    except Exception as norm_exc:
        print(f"[transcribe_pipeline] Audio normalization notice: {norm_exc}")

    if engine_choice == "groq":
        try:
            active_groq_key = (groq_api_key or os.getenv("GROQ_API_KEY", "")).strip()
            if not active_groq_key:
                print("[transcribe_pipeline] Warning: GROQ_API_KEY not configured. Falling back to local whisper.")
                raise ValueError("GROQ_API_KEY no configurada")
            lang_label = whisper_lang or "auto-detect"
            print(f"[transcribe_pipeline] Transcribing with Groq Cloud (whisper-large-v3, lang={lang_label}): {audio_path}")
            if whisper_prompt:
                print(f"[transcribe_pipeline] Using Whisper prompt biasing ({len(whisper_prompt)} chars): {whisper_prompt[:120]}...")
            transcriber = GroqWhisperTranscriber(api_key=active_groq_key)
            result = transcriber.transcribe(
                audio_path,
                language=whisper_lang,
                on_progress=_safe_progress,
                source=source,
                user_char_name=user_char_name,
                speaking_log=speaking_log,
                roster=roster,
                prompt=whisper_prompt,
            )
            result["engine_used"] = "groq"
            return result
        except Exception as exc:
            if "cancelado" in str(exc).lower():
                raise
            print(f"[transcribe_pipeline] Groq transcription failed ({exc}). Falling back to local whisper.")

    lang_label = whisper_lang or "auto-detect"
    _safe_progress(40, f"Transcribiendo con faster-whisper local ({model_size}, lang={lang_label})...")
    print(f"[transcribe_pipeline] Transcribing with local faster-whisper ({model_size}, lang={lang_label}): {audio_path}")
    if whisper_prompt:
        print(f"[transcribe_pipeline] Using Whisper initial_prompt biasing ({len(whisper_prompt)} chars): {whisper_prompt[:120]}...")
    transcriber = LocalWhisperTranscriber(model_size=model_size)
    result = transcriber.transcribe(
        audio_path,
        language=whisper_lang,
        user_char_name=user_char_name,
        speaking_log=speaking_log,
        roster=roster,
        initial_prompt=whisper_prompt,
    )
    _safe_progress(75, "Transcripción local completada.")
    result["engine_used"] = "local"
    return result



# ---------------------------------------------------------------------------
# Routers: Audio Devices, VU Monitoring & Recording Controls
# ---------------------------------------------------------------------------
from src.api.routers.audio import (
    router as audio_router,
    StartRecordingRequest,
    StopAndProcessRequest,
    DeleteAudioRequest,
    get_audio_devices_endpoint,
    get_discord_participants_endpoint,
    reset_discord_auth_endpoint,
    test_audio_level,
    start_recording,
    get_recording_status,
    stop_recording_only,
    stop_and_process,
    download_docx,
    download_md,
    delete_recording_audio,
)
app.include_router(audio_router)

# ---------------------------------------------------------------------------
# Routers: Academic Notes (Work & Study)
# ---------------------------------------------------------------------------
from src.api.routers.academic import (
    router as academic_router,
    is_academic_study_note,
    extract_clean_note_title,
    format_note_date,
    update_consolidated_academic_notes_file,
    list_academic_notes,
    get_academic_note,
    delete_academic_note,
    save_academic_note_endpoint,
    import_academic_note_endpoint,
    download_academic_note_docx,
)
app.include_router(academic_router)


# ---------------------------------------------------------------------------
# Routers: Audio Transcription, YouTube & Local File Processing
# ---------------------------------------------------------------------------
from src.api.routers.transcription import (
    router as transcription_router,
    YouTubeTranscribeRequest,
    TranscribeResponse,
    SwitchLanguageRequest,
    ReprocessCampaignRequest,
    list_local_recordings,
    transcribe_youtube,
    transcribe_file,
    upload_session_with_telemetry,
    switch_summary_language,
    reprocess_campaign,
)
app.include_router(transcription_router)

# ---------------------------------------------------------------------------
# Routers: D&D Campaign Management & Downloads
# ---------------------------------------------------------------------------
from src.api.routers.campaigns import (
    router as campaigns_router,
    CreateCampaignRequest,
    UpdatePriorLoreRequest,
    ProcessCampaignSessionRequest,
    FinalizeNpcsRequest,
    UpdateQuestSubobjectiveRequest,
    UpdateQuestStatusRequest,
    MergeEntitiesRequest,
    UpdateCharacterBackstoryRequest,
    list_campaigns,
    get_campaign,
    get_campaign_session_endpoint,
    delete_campaign_endpoint,
    create_or_init_campaign,
    update_campaign_prior_lore,
    list_all_characters,
    get_campaign_character_backstory,
    update_campaign_character_backstory,
    process_campaign_session_endpoint,
    finalize_npcs,
    update_quest_subobjective,
    update_quest_status_endpoint,
    merge_campaign_entities_endpoint,
    deduplicate_campaign_endpoint,
    download_campaign_docx,
    download_campaign_md,
    export_campaign_bundle,
    import_campaign_bundle,
    download_transcript_txt,
    download_audio_file,
    export_campaign_to_drive,
)
app.include_router(campaigns_router)

# ---------------------------------------------------------------------------
# Routers: Drive & Cloud Sync
# ---------------------------------------------------------------------------
from src.api.routers.drive import (
    router as drive_router,
    export_to_drive,
    get_task_status_endpoint,
    check_api_keys,
    get_drive_status,
    drive_login,
    drive_callback,
    connect_drive,
    sync_drive_endpoint,
    restore_drive_session_endpoint,
    get_drive_token_endpoint,
    disconnect_drive,
    discard_transcription_endpoint,
)
app.include_router(drive_router)



