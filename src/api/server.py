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
from functools import lru_cache
from pathlib import Path
from src.runtime_paths import is_desktop_runtime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from dotenv import load_dotenv
if not is_desktop_runtime():
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
from src.api.support_report import SupportHistory, SupportReportMiddleware
from src.runtime_paths import resolve_runtime_paths
from src.storage.campaign_ingest import CampaignImportConflict
from src.storage.drive_client import GoogleDriveStorage, prepare_google_credentials_for_startup
from src.summarizer.gemini_client import (
    GeminiTTRPGSummarizer,
    GeminiGenerationTimeout,
    GeminiGenerationFailure,
    normalize_academic_sections,
)
from src.summarizer.session_evidence import InsufficientSessionContent, prepare_session_transcript
from src.transcription.audio_recorder import (
    active_recorder,
    get_audio_devices,
    get_audio_levels,
)
from src.transcription.groq_whisper import GroqWhisperTranscriber
from src.transcription.local_whisper import LocalWhisperTranscriber
from src.transcription.roster_normalizer import (
    campaign_name_entries, enrich_roster_aliases, name_alias_map, normalize_transcript_roster,
)
from src.transcription.test_reporter import create_transcription_test_report
from src.transcription.youtube_downloader import download_youtube_audio

project_root = Path(__file__).resolve().parent.parent.parent


def get_data_input_dir() -> Path:
    p = resolve_runtime_paths(resource_dir=project_root).input_dir
    # Keep the existing temporary-input policy for non-packaged Linux deployments.
    if (not is_desktop_runtime() and not os.environ.get("WHISPER_INPUT_DIR")
            and sys.platform != "win32" and os.path.exists("/tmp") and os.path.isdir("/tmp")):
        p = Path("/tmp/whisper_input").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_data_output_dir() -> Path:
    p = resolve_runtime_paths(resource_dir=project_root).output_dir
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_data_campaigns_dir() -> Path:
    p = resolve_runtime_paths(resource_dir=project_root).campaigns_dir
    p.mkdir(parents=True, exist_ok=True)
    return p


def output_search_dirs(legacy_dirs: List[Path]) -> List[Path]:
    """Desktop profiles must not discover or mutate development/container exports."""
    return [get_data_output_dir()] if is_desktop_runtime() else legacy_dirs


def academic_history_paths() -> List[Path]:
    if is_desktop_runtime():
        return [get_data_output_dir() / "apuntes_historial.json"]
    return [project_root / "data" / "apuntes_historial.json", Path("/app/data/apuntes_historial.json")]


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
if is_desktop_runtime():
    _credentials_path = str(prepare_google_credentials_for_startup(project_root))
else:
    _credentials_path = "/app/credentials.json" if (os.name != "nt" and Path("/app").is_dir()) else str(project_root / "credentials.json")
_env_creds = None if is_desktop_runtime() else os.environ.get("GOOGLE_CREDENTIALS_JSON")
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


# Separate, content-free support history; never export the raw server log.


def get_support_history_path() -> Path:
    if is_desktop_runtime():
        return resolve_runtime_paths(resource_dir=project_root).logs_dir / "support-errors.json"
    return get_data_output_dir() / "support-errors.json"


@lru_cache(maxsize=8)
def _support_history_for_path(path: Path):
    return SupportHistory(path)


def get_support_history():
    return _support_history_for_path(get_support_history_path())


app.add_middleware(SupportReportMiddleware, history_provider=get_support_history)


@app.get("/api/support/report")
async def download_support_report():
    text = await run_in_threadpool(get_support_history().render, app.version)
    return Response(content=text, media_type="text/plain; charset=utf-8", headers={
        "Content-Disposition": 'attachment; filename="WhisperDnD-reporte-errores.txt"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })


@app.exception_handler(InsufficientSessionContent)
async def insufficient_session_content_handler(request: Request, exc: InsufficientSessionContent):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(CampaignImportConflict)
async def campaign_storage_conflict_handler(request: Request, exc: CampaignImportConflict):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.on_event("startup")
async def on_server_startup():
    """Start Drive synchronization without applying automatic local repair heuristics."""
    if os.environ.get("WHISPER_SKIP_STARTUP_DRIVE_SYNC") == "1":
        return
    async def _async_startup_tasks():
        try:
            drive_storage = await run_in_threadpool(GoogleDriveStorage)
            if await run_in_threadpool(drive_storage.is_connected):
                print("[Server Startup] Google Drive connected. Restoring campaigns and notes from Drive in background...")
                sync_res = await run_in_threadpool(
                    drive_storage.sync_from_google_drive,
                    get_data_campaigns_dir(),
                    get_data_output_dir(),
                )
                print(f"[Server Startup] Drive restore complete: {sync_res.get('message', '')}")
        except Exception as exc:
            print(f"[Server Startup] Drive restore on startup skipped or failed: {exc}")

    schedule_background_job(_async_startup_tasks())


def schedule_background_job(coroutine):
    task = asyncio.create_task(coroutine)
    if is_desktop_runtime():
        if not hasattr(app.state, "desktop_background_tasks"):
            app.state.desktop_background_tasks = set()
        app.state.desktop_background_tasks.add(task)
        task.add_done_callback(app.state.desktop_background_tasks.discard)
    return task


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
    result = {"status": "alive", "timestamp": time.time()}
    identity = getattr(app.state, "desktop_instance_id", None)
    if identity:
        result.update(application="WhisperDnD", instance_id=identity, version=app.version)
    return result


@app.post("/api/shutdown")
@app.get("/api/shutdown")
async def shutdown_server():
    """Cleanly handle shutdown requests without killing multi-user or cloud server instances."""
    if os.environ.get("WHISPER_ENV") in ("test", "testing") or os.environ.get("TESTING") == "1":
        return {"status": "shutdown_simulated", "message": "Test mode: shutdown not executed"}

    # Never kill the server on cloud/container deployments or multi-computer sessions unless explicitly enabled
    if os.environ.get("ALLOW_SERVER_SHUTDOWN") != "1":
        return {
            "status": "ignored",
            "message": "El servidor permanece activo para soportar recargas de página y múltiples dispositivos.",
        }

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
        async def _worker():
            try:
                ds = await run_in_threadpool(GoogleDriveStorage)
                if not await run_in_threadpool(ds.is_connected):
                    return
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

        schedule_background_job(_worker())
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



def extract_academic_sections(chronicle_md: str, document_format: str = "academic") -> Tuple[List[str], str]:
    """
    Extract action items / tasks list and key points / glossary from academic markdown.
    Key points contains strictly Glossary and Techniques without repeating Section 5 or Section 6.
    """
    if not chronicle_md:
        return [], ""

    if document_format == "executive":
        tasks_match = re.search(r"(?m)^#{1,2}\s*3\.\s*[^\n]+\n([\s\S]*?)(?=^#{1,2}\s|\Z)", chronicle_md)
        decisions_match = re.search(r"(?m)^#{1,2}\s*2\.\s*[^\n]+\n([\s\S]*?)(?=^#{1,2}\s|\Z)", chronicle_md)
        tasks = []
        for line in (tasks_match.group(1) if tasks_match else "").splitlines():
            match = re.match(r"^\s*[-*+]\s*(?:\[[ xX]\]\s*)?(.+)$", line)
            if match and not match.group(1).lower().startswith(("no se", "no hay", "ninguna", "none", "no tasks")):
                tasks.append(match.group(1).strip())
        return tasks, decisions_match.group(1).strip() if decisions_match else ""

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


def parse_client_datetime(
    custom_date: Optional[str] = None,
    client_timezone_offset: Optional[Union[int, str]] = None,
) -> Tuple[str, str, datetime.datetime]:
    """
    Parse client provided date/time string or calculate client local time using client_timezone_offset.
    Returns:
        now_str: "YYYYMMDD_HHMMSS" suitable for filenames
        now_formatted: "DD/MM/YYYY HH:MM" suitable for displays, prompts and documents
        effective_dt: datetime object representing local time
    """
    if custom_date and str(custom_date).strip():
        raw = str(custom_date).strip()
        # Pattern 1: DD/MM/YYYY [HH:MM[:SS]]
        m = re.search(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:[T\s]+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?", raw)
        if m:
            d, mo, y, h, mi, s = m.groups()
            local_fallback = None
            if client_timezone_offset is not None:
                try:
                    local_fallback = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=int(client_timezone_offset))
                except Exception:
                    pass
            if local_fallback is None:
                local_fallback = datetime.datetime.now()

            hour = int(h) if h is not None else local_fallback.hour
            minute = int(mi) if mi is not None else local_fallback.minute
            sec = int(s) if s is not None else local_fallback.second
            try:
                dt = datetime.datetime(int(y), int(mo), int(d), hour, minute, sec)
                return dt.strftime("%Y%m%d_%H%M%S"), dt.strftime("%d/%m/%Y %H:%M"), dt
            except Exception:
                pass

        # Pattern 2: YYYY/MM/DD or YYYY-MM-DD [HH:MM[:SS]]
        m2 = re.search(r"^(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})(?:[T\s]+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?", raw)
        if m2:
            y, mo, d, h, mi, s = m2.groups()
            local_fallback = None
            if client_timezone_offset is not None:
                try:
                    local_fallback = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=int(client_timezone_offset))
                except Exception:
                    pass
            if local_fallback is None:
                local_fallback = datetime.datetime.now()

            hour = int(h) if h is not None else local_fallback.hour
            minute = int(mi) if mi is not None else local_fallback.minute
            sec = int(s) if s is not None else local_fallback.second
            try:
                dt = datetime.datetime(int(y), int(mo), int(d), hour, minute, sec)
                return dt.strftime("%Y%m%d_%H%M%S"), dt.strftime("%d/%m/%Y %H:%M"), dt
            except Exception:
                pass

    if client_timezone_offset is not None:
        try:
            offset_mins = int(client_timezone_offset)
            utc_now = datetime.datetime.now(datetime.timezone.utc)
            local_dt = utc_now - datetime.timedelta(minutes=offset_mins)
            local_naive = local_dt.replace(tzinfo=None)
            return local_naive.strftime("%Y%m%d_%H%M%S"), local_naive.strftime("%d/%m/%Y %H:%M"), local_naive
        except Exception:
            pass

    now = datetime.datetime.now()
    return now.strftime("%Y%m%d_%H%M%S"), now.strftime("%d/%m/%Y %H:%M"), now


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
    custom_date: Optional[str] = Field(default=None, description="Custom date string")
    client_timezone_offset: Optional[Union[int, str]] = Field(default=None, description="Client timezone offset in minutes")


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
def raise_session_processing_error(exc: Exception, task_id: Optional[str] = None) -> None:
    """Do not turn rejected/failed campaign work into a successful fallback."""
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, InsufficientSessionContent):
        error_type, message, stage = "InsufficientSessionContent", str(exc), "Validación de transcripción"
        status_code = 422
    elif isinstance(exc, GeminiGenerationFailure):
        error_type, message, stage = exc.failure['kind'], str(exc), exc.failure['stage']
        status_code = exc.failure['http_status']
    elif isinstance(exc, CampaignImportConflict):
        error_type, message, stage = "CampaignStorageConflict", str(exc), "Consistencia de campaña"
        status_code = 409
    else:
        error_type, message, stage = diagnose_exception(exc)
        status_code = 500
    set_task_error(task_id, message, error_type=error_type, stage=stage)
    raise HTTPException(status_code=status_code, detail=message) from exc


def process_session_for_campaign(
    campaign_name: str,
    transcript_text: str,
    roster_dicts: Optional[List[Dict[str, Any]]] = None,
    session_number: Optional[int] = None,
    target_language: str = "es",
    is_youtube: bool = False,
    gemini_api_key: Optional[str] = None,
    on_progress: Optional[Callable[[float, str], None]] = None,
    custom_date: Optional[str] = None,
    client_timezone_offset: Optional[Union[int, str]] = None,
    audio_duration_seconds: Optional[float] = None,
    audio_source: Optional[str] = None,
    source_recordings: Optional[List[Dict[str, Any]]] = None,
    cached_session_data: Optional[Dict[str, Any]] = None,
    recovery_source_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a session transcript for a living campaign:
    1. Get active context (quests, NPCs, last recap, next session #).
    2. Query Gemini for structured session chapter and cumulative updates.
    3. Save a reviewable draft without changing the campaign.
    4. Keep source text and generation artifacts for recovery.
    """
    prepared_transcript = prepare_session_transcript(transcript_text, roster=roster_dicts)
    manager = CampaignManager()
    # record_session replaces the old contribution only after generation succeeds.
    # Persisting a purge here used to delete the session when Gemini failed.
    active_ctx = manager.get_active_context(campaign_name, before_session_number=session_number)
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
    final_roster = enrich_roster_aliases(final_roster, active_ctx)
    prepared_transcript = normalize_transcript_roster(
        prepared_transcript, campaign_name_entries(final_roster, active_ctx))

    # Determine user character (strictly disabled for YouTube; only enabled if star is selected)
    user_character = None
    if not is_youtube:
        user_character = next((p for p in final_roster if p.get("is_user_character") and not p.get("is_absent")), None)
        if user_character is None:
            user_character = None  # Explicitly no user character — coaching disabled

    summarizer = GeminiTTRPGSummarizer(api_key=gemini_api_key)
    from src.storage.quota_tracker import track_audio_processing
    # Save the reusable input before any provider call; failures cannot lose it.
    import uuid
    input_id = uuid.uuid4().hex
    input_dir = get_data_output_dir() / "generation-inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    input_path = input_dir / (input_id + ".json")
    from src.storage.generation_recovery import active_input
    from src.summarizer.generation_diagnostics import GenerationDiagnostics
    def generation_progress(data):
        percent = {"response_parsed": 87, "saving_draft": 95, "completed": 98}.get(data["phase"], 65)
        if task_id:
            update_task_progress(task_id, percent, data["label"], stage="analyzing", generation=data)
        elif on_progress:
            on_progress(percent, data["label"])
    diagnostics = GenerationDiagnostics(input_dir / (input_id + "-diagnostics.json"), summarizer.model_name, generation_progress)
    summarizer.diagnostics = diagnostics
    with active_input(input_id), diagnostics.pipeline():
        input_path.write_text(json.dumps({"campaign_name": campaign_name, "session_number": actual_session_num,
            "raw_transcript": transcript_text, "prepared_transcript": prepared_transcript,
            "roster": final_roster, "context": active_ctx, "target_language": target_language,
            "source_recordings": source_recordings, "custom_date": custom_date,
            "client_timezone_offset": client_timezone_offset, "audio_source": audio_source,
            "is_youtube": is_youtube, "retry_of": recovery_source_id}, ensure_ascii=False), encoding="utf-8")
        summarizer.response_artifact = input_dir / (input_id + "-response.json")
        try:
            if cached_session_data is not None:
                diagnostics.record("response_received")
                session_data = json.loads(json.dumps(cached_session_data))
            else:
                with track_audio_processing(summarizer, audio_duration_seconds, source=audio_source, workspace="dnd"):
                    session_data = summarizer.generate_campaign_session(
                        transcript_text=prepared_transcript,
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

        finally:
            attempts = getattr(summarizer, "_generation_attempts", [])
            (input_dir / (input_id + "-attempts.json")).write_text(json.dumps(
                attempts if isinstance(attempts, list) else [], ensure_ascii=False), encoding="utf-8")
        session_data["session_chapter"].setdefault("generation_metadata", {})["input_artifact"] = input_path.name

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

        now_str, now_formatted, _ = parse_client_datetime(custom_date, client_timezone_offset)
        if custom_date:
            session_data["session_chapter"]["date"] = now_formatted.split(" ")[0]
        elif audio_source in ("file", "recording"):
            previous = next((s for s in manager.load_campaign(campaign_name).get("sessions", [])
                             if s.get("session_number") == actual_session_num), {})
            session_data["session_chapter"]["date"] = previous.get("date") or ""
        elif not session_data["session_chapter"].get("date"):
            session_data.setdefault("session_chapter", {})["date"] = now_formatted.split(" ")[0]
        session_data["session_chapter"]["processed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if source_recordings is not None:
            session_data["session_chapter"]["source_recordings"] = source_recordings

        from src.storage.session_review import stage_review
        diagnostics.record("saving_draft")
        draft = stage_review(manager, get_data_output_dir(), campaign_name, session_data["session_chapter"], session_data, {
            "roster": final_roster, "session_number": actual_session_num,
            "user_character": user_character, "is_youtube": is_youtube,
            "raw_transcript": transcript_text,
        })
        session_data["session_chapter"]["review_id"] = draft["id"]
        session_data["session_chapter"]["review_status"] = "pending"
        campaign_state = manager.load_campaign(campaign_name)

        # A draft is downloadable but cannot replace a campaign or enter continuity.
        draft_path = get_data_output_dir() / "session-reviews" / (draft["id"] + ".md")
        docx_file = None
        md_file = draft_path
        processing_warnings = ["Crónica generada como borrador. Revisa el texto y sus propuestas antes de incorporarlos a la campaña."]

        # Save standalone plain-text transcript to data/output/
        safe_name = manager.sanitize_name(campaign_name)
        txt_filename = f"{draft['id']}_transcripcion.txt"
        try:
            txt_path = get_data_output_dir() / "session-reviews" / txt_filename
            txt_path.write_text(transcript_text, encoding="utf-8")
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
            "docx_filename": Path(docx_file).name if docx_file else None,
            "md_filename": Path(md_file).name if md_file else None,
            "processing_warnings": processing_warnings,
            "txt_filename": txt_filename,
            "file_path": str(Path(docx_file or md_file).resolve()) if (docx_file or md_file) else "",
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
    if isinstance(exc, GeminiGenerationFailure):
        return exc.failure['kind'], str(exc), exc.failure['stage']
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
    if "faster-whisper" in err_lower or "ctranslate2" in err_lower or "localwhisper" in err_lower:
        return (
            "LocalWhisperError",
            f"Error durante la transcripción local con faster-whisper: {err}",
            "Transcripción Local (faster-whisper)",
        )
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
    generation: Optional[Dict[str, Any]] = None,
) -> None:
    """Update progress for a specific task ID with strict monotonic non-decreasing guarantee."""
    if not task_id:
        return
    pct = round(max(0.0, min(100.0, float(percent))), 1)
    prev_task = task_progress_state.get(task_id, {})
    prev_pct = float(prev_task.get("percent", 0.0) or 0.0)
    prev_status = prev_task.get("status")

    # Never allow progress percentage to move backwards during an active run
    if prev_status == "running" and pct > 0.0 and pct < prev_pct:
        pct = prev_pct

    current_status = status or ("completed" if pct >= 100.0 else "running")

    # Infer stage dynamically when not explicitly passed so it never gets stuck on an early stage
    step_lower = f"{step} {message}".lower()
    if stage:
        current_stage = stage
    elif pct >= 100.0:
        current_stage = "done"
    elif any(k in step_lower for k in ("gemini", "crónica", "cronica", "apuntes", "quests", "pnjs", "word", ".docx", "coaching", "sinopsis")):
        current_stage = "analyzing"
    elif any(k in step_lower for k in ("transcrib", "whisper", "groq", "fragmento", "micrófono", "microfono", "discord")):
        current_stage = "transcribing"
    elif any(k in step_lower for k in ("ffmpeg", "segment", "cortando", "bloque", "separando")):
        current_stage = "segmenting"
    elif pct >= 70.0:
        current_stage = "analyzing"
    elif pct >= 25.0:
        current_stage = "transcribing"
    elif pct >= 20.0:
        current_stage = "segmenting"
    else:
        current_stage = prev_task.get("stage") or "audio"

    task_progress_state[task_id] = {
        "task_id": task_id,
        "percent": pct,
        "step": step,
        "message": message or step,
        "timestamp": time.time(),
        "status": current_status,
        "stage": current_stage,
        "generation": generation if generation is not None else prev_task.get("generation"),
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
    previous = task_progress_state.get(task_id, {})
    generation = previous.get("generation")
    if generation:
        generation = {**generation, "finished_at": generation.get("finished_at") or time.time()}
    task_progress_state[task_id] = {
        "generation": generation,
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
    try:
        get_support_history().record('processing', 'TASK', 500, error_type)
    except Exception:
        pass


def is_task_cancelled(task_id: Optional[str]) -> bool:
    """Check if task was marked as cancelled by the client."""
    if not task_id:
        return False
    return task_progress_state.get(task_id, {}).get("status") == "cancelled"


def get_task_progress(task_id: str) -> Dict[str, Any]:
    """Retrieve progress state for a task."""
    data = dict(task_progress_state.get(task_id, {
        "task_id": task_id,
        "percent": 0.0,
        "step": "Iniciando proceso...",
        "message": "Preparando...",
        "status": "pending",
        "stage": "audio",
    }))
    if data.get("generation"):
        from src.summarizer.generation_diagnostics import public_generation_status
        data["generation"] = public_generation_status(data["generation"])
    return data


# ---------------------------------------------------------------------------
# Global Exception Handlers (Always return structured JSON diagnostics)
# ---------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    source = exc.__cause__ if isinstance(exc.__cause__, GeminiGenerationFailure) else exc
    err_type, human_msg, stage = diagnose_exception(source)
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
        missing_groq = require_groq and not groq_key
        missing_gemini = require_gemini and not gemini_key
        missing_both = (not groq_key and not gemini_key) and (require_groq or require_gemini)
        if missing_groq or missing_gemini or missing_both:
            if missing_groq and missing_gemini:
                msg = "Por favor ingresa tus API keys de Groq y Gemini en la sección de Ajustes para continuar."
            elif missing_groq:
                msg = "Por favor ingresa tu API key de Groq en la sección de Ajustes para usar la transcripción en la nube (o selecciona Transcripción local)."
            elif missing_gemini:
                msg = "Por favor ingresa tu API key de Gemini en la sección de Ajustes para la síntesis de crónicas y apuntes."
            else:
                msg = "Por favor ingresa tus credenciales de API en Ajustes para continuar."
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "API_KEYS_REQUIRED",
                    "message": msg,
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

        state = {}
        if campaign_name:
            try:
                state = CampaignManager().load_campaign(campaign_name)
            except Exception as exc:
                print(f"[build_whisper_prompt] Warning loading campaign '{campaign_name}': {exc}")
        names = campaign_name_entries(roster, state)
        mappings = name_alias_map(names)
        for entry in names:
            add_term(entry["character_name"])
            for alias in entry.get("aliases", []):
                if mappings.get(alias.casefold()) == entry["character_name"]:
                    add_term(alias)

        # Characters & Players from provided roster
        for p in (roster or []):
            if isinstance(p, dict):
                add_term(p.get("character_name") or p.get("personaje"))
                add_term(p.get("player_name") or p.get("jugador"))
                add_term(p.get("species") or p.get("especie"))

        # 3. Load Campaign State for NPCs, locations, and lore terms
        if campaign_name:
            try:
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
    selected = []
    for term in terms:
        if len(", ".join([*selected, term])) <= 800:
            selected.append(term)
    return ", ".join(selected) or None


# ---------------------------------------------------------------------------
# Helper: Audio Transcription Pipeline (Groq Cloud vs Local Whisper)
# ---------------------------------------------------------------------------
def _inspect_audio_duration_seconds(audio_path: Union[str, Path]) -> Optional[float]:
    try:
        import wave
        with wave.open(str(audio_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return round(frames / float(rate), 2)
    except Exception:
        pass
    return None


def transcribe_audio_pipeline(audio_path: str, *args, **kwargs) -> Dict[str, Any]:
    """Run preprocessing on an owned temporary copy; never mutate capture originals."""
    from src.transcription.audio_recorder import load_timeline_for_audio
    # Resolve sidecars against the original path before moving into a job directory.
    # speaking_log is the seventh optional positional argument of the worker.
    if len(args) < 7 and kwargs.get("speaking_log") is None:
        kwargs["speaking_log"] = load_timeline_for_audio(audio_path) or []
    with tempfile.TemporaryDirectory(prefix="whisper-processing-") as job:
        working = Path(job) / Path(audio_path).name
        shutil.copy2(audio_path, working)
        result = _transcribe_audio_pipeline(str(working), *args, **kwargs)
        campaign_name = kwargs.get("campaign_name") or (args[9] if len(args) > 9 else None)
        roster = kwargs.get("roster") or (args[7] if len(args) > 7 else None)
        recording_mode = kwargs.get("recording_mode", args[11] if len(args) > 11 else None)
        is_class = recording_mode == "class"
        state = CampaignManager().load_campaign(campaign_name) if campaign_name and not is_class else {}
        names = campaign_name_entries(roster, state) if not is_class else []
        # Keep raw_text untouched as recognition evidence. Speaker identity still
        # uses the real roster, never the NPC spelling entries assembled here.
        for key in ("text", "formatted_transcript"):
            if isinstance(result.get(key), str):
                result[key] = normalize_transcript_roster(result[key], names)
        for segment in result.get("segments", []):
            for key in ("text", "formatted_line"):
                if isinstance(segment.get(key), str):
                    segment[key] = normalize_transcript_roster(segment[key], names)
        source = kwargs.get("source", args[4] if len(args) > 4 else "local")
        if not is_class and source in ("local", "live"):
            from src.transcription.mic_volume_gate import apply_mic_volume_gate
            # Check original levels: preprocessing may amplify the working copy.
            # Both transcription engines go through this boundary.
            result = apply_mic_volume_gate(audio_path, result)
        if result.get("excluded_segments") or result.get("uncertain_segments"):
            # An exclusive new file per run preserves review evidence across
            # retries without changing recordings or campaign documents.
            prefix = "mic-volume-review-" if result.get("excluded_segments") else "recognition-review-"
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=get_data_output_dir(),
                prefix=prefix, suffix=".json", delete=False,
            ) as review:
                json.dump({
                    "source_filename": Path(audio_path).name,
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "gate": result.get("mic_volume_gate"),
                    "excluded_segments": result.get("excluded_segments", []),
                    "uncertain_segments": result.get("uncertain_segments", []),
                }, review, ensure_ascii=False, indent=2)
                result["recognition_review_filename"] = Path(review.name).name
                if result.get("mic_volume_gate"):
                    result["mic_volume_gate"]["review_filename"] = Path(review.name).name
        return result


def _transcribe_audio_pipeline(
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
    reference_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Route transcription to Groq Cloud (whisper-large-v3) or Local faster-whisper.
    Provider failures propagate; no silent switch to another transcription engine.
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

    t_pipeline_start = time.perf_counter()
    audio_dur = _inspect_audio_duration_seconds(audio_path) if audio_path else None
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
                raise ValueError("GROQ_API_KEY no configurada. Ingresa tu API key de Groq en Ajustes o selecciona Transcripción local.")
            lang_label = whisper_lang or "auto-detect"
            print(f"[transcribe_pipeline] Transcribing with Groq Cloud (whisper-large-v3, lang={lang_label}): {audio_path}")
            if whisper_prompt:
                print(f"[transcribe_pipeline] Using Whisper prompt biasing ({len(whisper_prompt)} chars): {whisper_prompt[:120]}...")
            transcriber = GroqWhisperTranscriber(api_key=active_groq_key)
            t_trans_start = time.perf_counter()
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
            t_trans_end = time.perf_counter()
            result["engine_used"] = "groq"
            t_pipeline_end = time.perf_counter()
            final_audio_dur = result.get("duration") or audio_dur
            try:
                report_path = create_transcription_test_report(
                    engine="groq",
                    model_size="whisper-large-v3",
                    source=source,
                    audio_duration_seconds=final_audio_dur,
                    transcription_time_seconds=round(t_trans_end - t_trans_start, 2),
                    total_time_seconds=round(t_pipeline_end - t_pipeline_start, 2),
                    language=result.get("language_code") or whisper_lang,
                    device="cloud",
                    compute_type="fp16",
                    success=True,
                    reference_text=reference_text,
                    hypothesis_text=result.get("text", ""),
                )
                result["test_report_path"] = str(report_path)
                result["test_report_filename"] = report_path.name
            except Exception as rep_err:
                print(f"[transcribe_pipeline] Notice generating Groq test report: {rep_err}")
            return result
        except Exception as exc:
            t_pipeline_end = time.perf_counter()
            try:
                create_transcription_test_report(
                    engine="groq",
                    model_size="whisper-large-v3",
                    source=source,
                    audio_duration_seconds=audio_dur,
                    total_time_seconds=round(t_pipeline_end - t_pipeline_start, 2),
                    language=whisper_lang,
                    device="cloud",
                    compute_type="fp16",
                    success=False,
                    error_summary=str(exc)[:300],
                )
            except Exception:
                pass
            if "cancelado" in str(exc).lower():
                raise
            raise

    chosen_model = (model_size or "base").lower().strip()
    if chosen_model not in ("tiny", "base", "small", "medium", "large-v3"):
        chosen_model = "base"
    local_lang_label = whisper_lang or "auto-detect"
    _safe_progress(2, f"Inicializando faster-whisper local ({chosen_model}, CPU int8)...")
    local_ceiling = 70.0 if source == "youtube" else 55.0
    def local_progress(pct, message):
        _safe_progress(min(75.0, max(0.0, float(pct))) / 75.0 * local_ceiling, message)
    print(f"[transcribe_pipeline] Transcribing with local faster-whisper ({chosen_model}, CPU int8, lang={local_lang_label}): {audio_path}")
    if whisper_prompt:
        print(f"[transcribe_pipeline] Using Whisper initial_prompt biasing ({len(whisper_prompt)} chars): {whisper_prompt[:120]}...")
    t_trans_start = time.perf_counter()
    try:
        transcriber = LocalWhisperTranscriber(
            model_size=chosen_model,
            device="cpu",
            compute_type="int8",
        )
        result = transcriber.transcribe(
            audio_path,
            language=whisper_lang,
            user_char_name=user_char_name,
            speaking_log=speaking_log,
            roster=roster,
            initial_prompt=whisper_prompt,
            on_progress=local_progress,
        )
        t_trans_end = time.perf_counter()
        local_progress(75, f"Transcripción local ({chosen_model}) completada.")
        result["engine_used"] = f"local-{chosen_model}"
        t_pipeline_end = time.perf_counter()
        final_audio_dur = result.get("duration") or audio_dur
        try:
            report_path = create_transcription_test_report(
                engine="local",
                model_size=chosen_model,
                source=source,
                audio_duration_seconds=final_audio_dur,
                transcription_time_seconds=round(t_trans_end - t_trans_start, 2),
                total_time_seconds=round(t_pipeline_end - t_pipeline_start, 2),
                language=result.get("language_code") or whisper_lang,
                device="cpu",
                compute_type="int8",
                vad_enabled=True,
                condition_on_previous_text=False,
                success=True,
                reference_text=reference_text,
                hypothesis_text=result.get("text", ""),
            )
            result["test_report_path"] = str(report_path)
            result["test_report_filename"] = report_path.name
        except Exception as rep_err:
            print(f"[transcribe_pipeline] Notice generating local test report: {rep_err}")
        return result
    except Exception as exc:
        t_pipeline_end = time.perf_counter()
        try:
            create_transcription_test_report(
                engine="local",
                model_size=chosen_model,
                source=source,
                audio_duration_seconds=audio_dur,
                total_time_seconds=round(t_pipeline_end - t_pipeline_start, 2),
                language=whisper_lang,
                device="cpu",
                compute_type="int8",
                vad_enabled=True,
                condition_on_previous_text=False,
                success=False,
                error_summary=str(exc)[:300],
            )
        except Exception:
            pass
        raise



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


