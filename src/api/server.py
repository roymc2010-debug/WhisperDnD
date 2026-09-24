"""FastAPI server for WhisperDnD live dual-channel recording and AI transcription."""

import asyncio
import datetime
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from src.exporters.docx_exporter import (
    export_chronicle_docx,
    export_living_journal_docx,
    export_academic_notes_docx,
)
from src.exporters.md_exporter import export_living_journal_md
from src.storage.campaign_manager import CampaignManager
from src.storage.drive_client import GoogleDriveStorage
from src.summarizer.gemini_client import GeminiTTRPGSummarizer
from src.transcription.audio_recorder import (
    active_recorder,
    get_audio_devices,
    get_audio_levels,
)
from src.transcription.groq_whisper import GroqWhisperTranscriber
from src.transcription.local_whisper import LocalWhisperTranscriber
from src.transcription.youtube_downloader import download_youtube_audio

project_root = Path(__file__).resolve().parent.parent.parent
data_input_dir = Path(os.environ.get("WHISPER_INPUT_DIR", project_root / "data" / "input"))
data_output_dir = Path(os.environ.get("WHISPER_OUTPUT_DIR", project_root / "data" / "output"))
data_campaigns_dir = Path(os.environ.get("WHISPER_CAMPAIGNS_DIR", project_root / "data" / "campaigns"))
template_path = Path(__file__).resolve().parent / "templates" / "index.html"


def get_data_input_dir() -> Path:
    p = Path(os.environ.get("WHISPER_INPUT_DIR", project_root / "data" / "input"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_data_output_dir() -> Path:
    p = Path(os.environ.get("WHISPER_OUTPUT_DIR", project_root / "data" / "output"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_data_campaigns_dir() -> Path:
    p = Path(os.environ.get("WHISPER_CAMPAIGNS_DIR", project_root / "data" / "campaigns"))
    p.mkdir(parents=True, exist_ok=True)
    return p


# Ensure runtime directories exist
get_data_input_dir()
get_data_output_dir()
get_data_campaigns_dir()

app = FastAPI(
    title="WhisperDnD - Live Session Recorder & Living Campaign Journal",
    description="Dual-channel audio recording with faster-whisper, Gemini Living Campaign Journal & Google Drive.",
    version="3.0.0",
)

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


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------
class PlayerMetadata(BaseModel):
    player_name: str = Field(default="", description="Name of the player")
    character_name: str = Field(default="-", description="Character name")
    species: Optional[str] = Field(default="", description="Species or race (e.g. Elfo, Humano)")
    role: str = Field(default="Aventurero", description="Role or class (e.g. Dungeon Master, Paladín)")
    subclass: Optional[str] = Field(default="", description="Subclass (e.g. Battle Master)")
    is_user_character: Optional[bool] = Field(default=False, description="Whether this character is the user's personal character for roleplay reflection")
    discord_user_id: Optional[str] = Field(default=None, description="Linked Discord user ID for immutable speaker identification")


class StartRecordingRequest(BaseModel):
    mode: str = Field(default="roleplay", description="Recording mode ('roleplay' or 'class')")
    mic_id: Optional[str] = Field(default=None, description="Physical microphone device ID")
    speaker_id: Optional[str] = Field(default=None, description="Playback speaker/headphone device ID for loopback")


class StopAndProcessRequest(BaseModel):
    roster: List[PlayerMetadata] = Field(default_factory=list, description="Party roster")
    model_size: str = Field(default="base", description="Whisper model size (tiny, base)")
    engine: str = Field(default="groq", description="Transcription engine ('groq' or 'local')")
    campaign_name: Optional[str] = Field(default="Campaña Principal", description="Name of the campaign")
    session_number: Optional[int] = Field(default=None, description="Optional manual session number")
    task_id: Optional[str] = Field(default=None, description="Task ID for progress tracking")
    recording_mode: str = Field(default="roleplay", description="Recording mode ('roleplay' or 'class')")
    subject: Optional[str] = Field(default="", description="Materia / Asignatura for university lecture")
    topic: Optional[str] = Field(default="", description="Tema de la clase for university lecture")
    target_language: str = Field(default="es", description="Target language ('es' or 'en')")


class YouTubeTranscribeRequest(BaseModel):
    url: str = Field(..., description="YouTube video URL to transcribe")
    model_size: str = Field(default="base", description="Whisper model size (tiny, base)")
    engine: str = Field(default="groq", description="Transcription engine ('groq' or 'local')")
    campaign_name: Optional[str] = Field(default="Campaña Principal", description="Name of the campaign")
    session_number: Optional[int] = Field(default=None, description="Optional manual session number")
    roster: Optional[List[PlayerMetadata]] = Field(default_factory=list, description="Party roster")
    task_id: Optional[str] = Field(default=None, description="Task ID for progress tracking")
    recording_mode: str = Field(default="roleplay", description="Recording mode ('roleplay' or 'class')")
    subject: Optional[str] = Field(default="", description="Materia / Asignatura for university lecture")
    topic: Optional[str] = Field(default="", description="Tema de la clase for university lecture")
    target_language: str = Field(default="es", description="Target language ('es' or 'en')")


class TranscribeResponse(BaseModel):
    text: str
    segments: List[Dict[str, Any]]
    language: str
    duration: float
    elapsed_time: float
    engine_used: Optional[str] = None
    file_path: Optional[str] = None
    docx_filename: Optional[str] = None
    md_filename: Optional[str] = None
    campaign_state: Optional[Dict[str, Any]] = None
    session_chapter: Optional[Dict[str, Any]] = None
    updated_quests: Optional[List[Dict[str, Any]]] = None
    updated_npcs: Optional[List[Dict[str, Any]]] = None
    detected_npc_names: Optional[List[str]] = None
    chronicle: Optional[str] = None
    recording_mode: Optional[str] = "roleplay"
    subject: Optional[str] = None
    topic: Optional[str] = None
    wav_filename: Optional[str] = None
    target_language: Optional[str] = "es"
    detected_party: Optional[List[Dict[str, Any]]] = None
    detected_pcs: Optional[List[Dict[str, Any]]] = None
    txt_filename: Optional[str] = None


class CreateCampaignRequest(BaseModel):
    campaign_name: str = Field(..., description="Name of the campaign")
    roster: Optional[List[PlayerMetadata]] = Field(default_factory=list, description="Party roster")
    prior_lore: Optional[str] = Field(default="", description="Prior lore / backstory for ongoing campaigns")


class UpdatePriorLoreRequest(BaseModel):
    prior_lore: str = Field(default="", description="Prior lore / backstory for ongoing campaigns")


class ProcessCampaignSessionRequest(BaseModel):
    transcript_text: str = Field(..., description="Speech-to-text transcript")
    roster: Optional[List[PlayerMetadata]] = Field(default=None, description="Party roster")
    session_number: Optional[int] = Field(default=None, description="Session number override")
    target_language: str = Field(default="es", description="Target language ('es' or 'en')")


class FinalizeNpcsRequest(BaseModel):
    name_corrections: Dict[str, str] = Field(default_factory=dict, description="Map of old NPC names to user-corrected names")


class UpdateQuestSubobjectiveRequest(BaseModel):
    subobjective_idx: int = Field(..., description="Index of the subobjective to update")
    completed: bool = Field(..., description="Whether the subobjective is completed")


class UpdateQuestStatusRequest(BaseModel):
    status: Optional[str] = Field(default=None, description="'completed', 'in_progress', 'failed', or None to toggle")


class DriveExportRequest(BaseModel):
    file_path: str = Field(..., description="Local path or filename of the file to upload to Google Drive")


class DeleteAudioRequest(BaseModel):
    filename: str = Field(..., description="Filename of original audio in data/input to delete")


class SwitchLanguageRequest(BaseModel):
    transcript_text: str = Field(..., description="Speech-to-text transcript")
    target_language: str = Field(default="en", description="Target language ('es' or 'en')")
    recording_mode: str = Field(default="roleplay", description="'roleplay' or 'class'")
    campaign_name: Optional[str] = Field(default="Campaña Principal", description="Campaign name")
    session_number: Optional[int] = Field(default=None, description="Session number")
    roster: Optional[List[PlayerMetadata]] = Field(default_factory=list, description="Party roster")
    subject: Optional[str] = Field(default="", description="Subject for lecture")
    topic: Optional[str] = Field(default="", description="Topic for lecture")


class ReprocessCampaignRequest(BaseModel):
    transcript_text: str = Field(..., description="Speech-to-text transcript")
    campaign_name: Optional[str] = Field(default="Campaña Principal", description="Campaign name")
    session_number: Optional[int] = Field(default=None, description="Session number")
    roster: Optional[List[PlayerMetadata]] = Field(default_factory=list, description="Party roster")
    target_language: str = Field(default="es", description="Target language ('es' or 'en')")
    recording_mode: str = Field(default="roleplay", description="'roleplay' or 'class'")
    subject: Optional[str] = Field(default="", description="Subject for lecture")
    topic: Optional[str] = Field(default="", description="Topic for lecture")
    is_youtube: Optional[bool] = Field(default=False, description="Whether this session was ingested from YouTube")


class DriveExportResponse(BaseModel):
    status: str
    web_view_link: str
    file_name: str
    file_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints: Frontend SPA
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the single-page application with cache-busting headers."""
    html_file = project_root / "static" / "index.html"
    if not html_file.is_file():
        html_file = template_path
    if not html_file.is_file():
        raise HTTPException(status_code=404, detail="Template index.html not found.")
    
    response = HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


@app.get("/manifest.json")
async def get_manifest():
    manifest_file = project_root / "static" / "manifest.json"
    if manifest_file.is_file():
        return FileResponse(manifest_file, media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="manifest.json not found")


@app.get("/sw.js")
async def get_service_worker():
    sw_file = project_root / "static" / "sw.js"
    if sw_file.is_file():
        return FileResponse(
            sw_file,
            media_type="application/javascript",
            headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"}
        )
    raise HTTPException(status_code=404, detail="sw.js not found")


@app.get("/icon-192.png")
async def get_icon_192():
    icon_file = project_root / "static" / "icon-192.png"
    if icon_file.is_file():
        return FileResponse(icon_file, media_type="image/png")
    raise HTTPException(status_code=404, detail="icon-192.png not found")


@app.get("/icon-512.png")
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
    # If external campaign and saved_roster contains Markus Veyl from a legacy bug, purge it
    if not is_private and saved_roster:
        if any("markus" in str(p.get("character_name", "")).lower() or "markus" in str(p.get("player_name", "")).lower() for p in saved_roster):
            saved_roster = []

    final_roster = clean_roster_dicts if len(clean_roster_dicts) > 0 else saved_roster

    # Determine user character (strictly disabled for YouTube; only enabled if star is selected)
    user_character = None
    if not is_youtube:
        user_character = next((p for p in final_roster if p.get("is_user_character")), None)
        if user_character is None:
            user_character = {}  # Explicitly empty: 0 selected characters, disable default Markus coaching

    summarizer = GeminiTTRPGSummarizer()
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
    )

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


def update_task_progress(
    task_id: Optional[str],
    percent: int,
    step: str,
    message: str = "",
    status: Optional[str] = None,
    stage: Optional[str] = None,
) -> None:
    """Update progress for a specific task ID."""
    if not task_id:
        return
    pct = max(0, min(100, int(percent)))
    current_status = status or ("completed" if pct >= 100 else "running")

    # Determine or preserve stage
    prev_task = task_progress_state.get(task_id, {})
    current_stage = stage or prev_task.get("stage")
    if not current_stage:
        if pct < 30:
            current_stage = "audio"
        elif pct < 75:
            current_stage = "transcribing"
        elif pct < 100:
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


def set_task_error(task_id: Optional[str], error_message: str) -> None:
    """Register an error state for a task so frontend displays prominent error card."""
    if not task_id:
        return
    task_progress_state[task_id] = {
        "task_id": task_id,
        "percent": 0,
        "step": "Error en el proceso",
        "message": error_message,
        "error_message": error_message,
        "timestamp": time.time(),
        "status": "error",
        "stage": "error",
    }


def format_human_error(exc: Exception) -> str:
    """Format exceptions into clear, actionable human-readable messages."""
    err = str(exc)
    err_lower = err.lower()
    if "rate limit" in err_lower or "429" in err:
        return f"Límite de tasa excedido en la API (Rate Limit): {err}"
    if "quota" in err_lower or "resource_exhausted" in err_lower:
        return f"Cuota de API agotada o excedida temporalmente: {err}"
    if "ffmpeg" in err_lower:
        return f"Error al procesar/dividir el audio con FFmpeg: {err}"
    if "timeout" in err_lower or "timed out" in err_lower:
        return f"Tiempo de espera agotado al comunicar con el servicio: {err}"
    if "invalid_request_error" in err_lower:
        return f"Petición no válida a la API: {err}"
    return f"Error en el procesamiento: {err}"


def get_task_progress(task_id: str) -> Dict[str, Any]:
    """Retrieve progress state for a task."""
    return task_progress_state.get(task_id, {
        "task_id": task_id,
        "percent": 0,
        "step": "Iniciando proceso...",
        "message": "Preparando...",
        "status": "pending",
        "stage": "audio",
    })


# ---------------------------------------------------------------------------
# Helper: Audio Transcription Pipeline (Groq Cloud vs Local Whisper)
# ---------------------------------------------------------------------------
def transcribe_audio_pipeline(
    audio_path: str,
    engine: str = "groq",
    model_size: str = "base",
    on_progress: Optional[Callable[[int, str], None]] = None,
    source: str = "local",
    user_char_name: Optional[str] = None,
    speaking_log: Optional[List[Dict[str, Any]]] = None,
    roster: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Route transcription to Groq Cloud (whisper-large-v3) or Local faster-whisper.
    Falls back gracefully to local whisper if Groq is requested but fails or lacks API key.
    """
    engine_choice = (engine or "groq").lower().strip()

    if engine_choice == "groq":
        try:
            groq_key = os.getenv("GROQ_API_KEY", "").strip()
            if not groq_key:
                print("[transcribe_pipeline] Warning: GROQ_API_KEY not configured. Falling back to local whisper.")
                raise ValueError("GROQ_API_KEY no configurada en .env")
            print(f"[transcribe_pipeline] Transcribing with Groq Cloud (whisper-large-v3): {audio_path}")
            transcriber = GroqWhisperTranscriber()
            result = transcriber.transcribe(
                audio_path,
                on_progress=on_progress,
                source=source,
                user_char_name=user_char_name,
                speaking_log=speaking_log,
                roster=roster,
            )
            result["engine_used"] = "groq"
            return result
        except Exception as exc:
            print(f"[transcribe_pipeline] Groq transcription failed ({exc}). Falling back to local whisper.")

    if on_progress:
        on_progress(40, f"Transcribiendo con faster-whisper local ({model_size})...")
    print(f"[transcribe_pipeline] Transcribing with local faster-whisper ({model_size}): {audio_path}")
    transcriber = LocalWhisperTranscriber(model_size=model_size)
    result = transcriber.transcribe(
        audio_path,
        user_char_name=user_char_name,
        speaking_log=speaking_log,
        roster=roster,
    )
    if on_progress:
        on_progress(75, "Transcripción local completada.")
    result["engine_used"] = "local"
    return result


# ---------------------------------------------------------------------------
# Endpoints: Audio Devices & Live VU Monitoring
# ---------------------------------------------------------------------------
@app.get("/api/audio/devices")
async def get_audio_devices_endpoint():
    """List all available physical microphones and speakers/loopback devices."""
    return get_audio_devices()


@app.get("/api/discord/participants")
async def get_discord_participants_endpoint():
    """Retrieve list of active participants in the current Discord voice channel via local RPC."""
    try:
        from src.transcription.discord_rpc import discord_tracker
        discord_tracker.ensure_running()
        if not discord_tracker.is_connected or discord_tracker.current_channel_id is None:
            for _ in range(15):
                if discord_tracker.is_connected and discord_tracker.current_channel_id:
                    break
                await asyncio.sleep(0.1)
        return discord_tracker.get_active_participants()
    except Exception as exc:
        return {
            "connected": False,
            "channel_id": None,
            "channel_name": None,
            "participants": [],
            "error": str(exc),
        }


@app.get("/api/audio/test-level")
async def test_audio_level(
    mic_id: Optional[str] = Query(default=None, description="Microphone device ID"),
    speaker_id: Optional[str] = Query(default=None, description="Speaker loopback device ID"),
):
    """
    Capture a ~100ms sample from the selected microphone and speaker loopback
    and return current RMS levels.
    """
    return get_audio_levels(mic_id=mic_id, speaker_id=speaker_id)


# ---------------------------------------------------------------------------
# Endpoints: Live Dual-Channel / Mono Recording
# ---------------------------------------------------------------------------
@app.post("/api/record/start")
async def start_recording(payload: Optional[StartRecordingRequest] = None):
    """
    Start recording audio:
    - mode='roleplay': Dual-channel (Mic Left, Discord/Speaker Loopback Right).
    - mode='class': Single-channel (Microphone ONLY, Mono 16kHz).
    """
    rec_mode = payload.mode if payload else "roleplay"
    mic_id = payload.mic_id if payload else None
    speaker_id = payload.speaker_id if payload else None
    try:
        wav_path = active_recorder.start(
            mode=rec_mode,
            mic_id=mic_id,
            speaker_id=speaker_id,
        )
        msg = (
            "Grabación de clase universitaria iniciada (micrófono mono)."
            if rec_mode == "class"
            else "Grabación de dos canales iniciada (D&D / Discord)."
        )
        return {
            "status": "recording",
            "mode": rec_mode,
            "mic_id": mic_id,
            "speaker_id": speaker_id,
            "message": msg,
            "file_path": str(Path(wav_path).name),
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al iniciar grabación: {exc}") from exc


@app.get("/api/record/status")
async def get_recording_status():
    """Return the current recording status and duration."""
    return active_recorder.get_status()


@app.post("/api/record/stop-and-process")
async def stop_and_process(payload: StopAndProcessRequest):
    """
    Stop live recording, run faster-whisper, generate Gemini chronicle/campaign updates with roster,
    and produce downloadable .docx and .md Grimorio files.
    """
    if not active_recorder.is_recording:
        raise HTTPException(status_code=400, detail="No hay ninguna sesión de grabación activa.")

    task_id = payload.task_id
    update_task_progress(task_id, 2, "Deteniendo grabación de audio...", "Finalizando captura de audio...", stage="transcribing")
    start_time = time.time()

    # 1. Stop audio recording
    try:
        wav_path = active_recorder.stop()
    except Exception as exc:
        update_task_progress(task_id, 0, f"Error deteniendo grabación: {exc}", stage="error")
        raise HTTPException(status_code=500, detail=f"Error al detener la grabación: {exc}") from exc

    if not wav_path or not Path(wav_path).is_file():
        update_task_progress(task_id, 0, "Audio no encontrado en disco.", stage="error")
        raise HTTPException(status_code=500, detail="El archivo de audio grabado no se encontró en disco.")

    update_task_progress(task_id, 5, "Audio guardado. Iniciando transcripción...", "Iniciando motor de audio...", stage="transcribing")

    def progress_cb(pct: int, msg: str):
        update_task_progress(task_id, pct, msg, stage="transcribing")

    # 2. Run Whisper Transcription (Groq Cloud or Local faster-whisper)
    model_size = payload.model_size or "base"
    engine = payload.engine or "groq"
    roster_dicts = [p.model_dump() for p in payload.roster] if payload.roster else []
    user_char_name = None
    for p in roster_dicts:
        if p.get("is_user_character"):
            user_char_name = (p.get("character_name") or "").strip()
            break

    speaking_log = getattr(active_recorder, "speaking_log", None)

    try:
        transcription_result = await run_in_threadpool(
            transcribe_audio_pipeline,
            audio_path=wav_path,
            engine=engine,
            model_size=model_size,
            on_progress=progress_cb,
            source="live",
            user_char_name=user_char_name,
            speaking_log=speaking_log,
            roster=roster_dicts,
        )
    except Exception as exc:
        human_err = format_human_error(exc)
        set_task_error(task_id, human_err)
        raise HTTPException(
            status_code=500,
            detail=human_err,
        ) from exc

    transcript_text = transcription_result.get("text", "").strip()

    # 3. Check Mode: In-Person University Lecture vs D&D Roleplay
    is_class_mode = (payload.recording_mode == "class") or (getattr(active_recorder, "mode", "roleplay") == "class")
    if is_class_mode:
        update_task_progress(task_id, 80, "Analizando clase universitaria con Gemini...", "Sintetizando conceptos teóricos y fórmulas...")
        subj = (payload.subject or "").strip() or "Materia Universitaria"
        top = (payload.topic or "").strip() or "Tema de Clase"
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        now_formatted = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        try:
            summarizer = GeminiTTRPGSummarizer()
            chronicle_md = await run_in_threadpool(
                summarizer.generate_academic_notes,
                transcript_text=transcript_text,
                subject=subj,
                topic=top,
                date_str=now_formatted,
                target_language=payload.target_language,
            )
        except Exception as exc:
            chronicle_md = (
                f"# ⚠️ Error generando guía académica con Gemini:\n\n> {exc}\n\n"
                f"**Transcripción obtenida:**\n\n{transcript_text}"
            )

        update_task_progress(task_id, 95, "Generando documento y preparando exportación...", "Creando archivos de apuntes...")
        clean_subj = re.sub(r'[\\/*?:"<>|]', "", subj.strip()) or "Materia"
        safe_subj = re.sub(r"\s+", "_", clean_subj)
        docx_filename = f"apuntes_{safe_subj}_{now_str}.docx"
        md_filename = f"apuntes_{safe_subj}_{now_str}.md"
        txt_filename = f"apuntes_{safe_subj}_{now_str}_transcripcion.txt"
        docx_out_path = get_data_output_dir() / docx_filename
        md_out_path = get_data_output_dir() / md_filename
        txt_out_path = get_data_output_dir() / txt_filename

        try:
            await run_in_threadpool(
                export_academic_notes_docx,
                notes_md=chronicle_md,
                subject=subj,
                topic=top,
                lecture_date=now_formatted,
                output_path=str(docx_out_path),
            )
            md_out_path.write_text(chronicle_md, encoding="utf-8")
            txt_out_path.write_text(transcript_text, encoding="utf-8")
            (get_data_output_dir() / f"{safe_subj}_transcripcion.txt").write_text(transcript_text, encoding="utf-8")
        except Exception as exc:
            print(f"[!] Warning: academic notes export failed: {exc}")

        update_task_progress(task_id, 100, "¡Completado!", "Guía de estudio generada exitosamente.")
        elapsed_time = round(time.time() - start_time, 2)
        language_code = transcription_result.get("language_code") or (
            transcription_result["language"]["code"]
            if isinstance(transcription_result.get("language"), dict)
            else str(transcription_result.get("language", ""))
        )

        return {
            "status": "completed",
            "recording_mode": "class",
            "subject": subj,
            "topic": top,
            "engine_used": transcription_result.get("engine_used", engine),
            "chronicle": chronicle_md,
            "transcript": transcript_text,
            "segments": transcription_result.get("segments", []),
            "language": language_code,
            "duration": transcription_result.get("duration", 0.0),
            "elapsed_time": elapsed_time,
            "file_path": str(docx_out_path.resolve()) if docx_out_path and docx_out_path.is_file() else "",
            "docx_filename": docx_filename,
            "md_filename": md_filename,
            "txt_filename": txt_filename,
            "wav_filename": Path(wav_path).name,
            "target_language": payload.target_language,
        }

    # 4. Roleplay Mode: Living Campaign Journal or Single Session Chronicle
    update_task_progress(task_id, 80, "Analizando narrativa, misiones y NPCs con Gemini...", "Extrayendo hechos e inventario...", stage="analyzing")
    if not roster_dicts and payload.roster:
        roster_dicts = [p.model_dump() for p in payload.roster]
    chronicle_md = ""
    docx_filename = ""
    md_filename = None
    docx_out_path = None
    campaign_state = None
    session_chapter = None
    updated_quests = None
    updated_npcs = None
    detected_npc_names = None
    detected_party = None
    detected_pcs = None

    if payload.campaign_name:
        try:
            update_task_progress(task_id, 85, "Actualizando Quest Tracker y Directorio Universal de NPCs...", stage="analyzing")
            camp_res = await run_in_threadpool(
                process_session_for_campaign,
                campaign_name=payload.campaign_name,
                transcript_text=transcript_text,
                roster_dicts=roster_dicts,
                session_number=payload.session_number,
                target_language=payload.target_language,
            )
            campaign_state = camp_res.get("campaign_state")
            session_chapter = camp_res.get("session_chapter")
            updated_quests = camp_res.get("updated_quests")
            updated_npcs = camp_res.get("updated_npcs")
            detected_npc_names = camp_res.get("detected_npc_names")
            detected_party = camp_res.get("detected_party")
            detected_pcs = camp_res.get("detected_pcs")
            docx_filename = camp_res.get("docx_filename", "")
            md_filename = camp_res.get("md_filename")
            docx_out_path = Path(camp_res.get("file_path", ""))
            chronicle_md = camp_res.get("chronicle", "")
        except Exception as exc:
            print(f"[!] Warning: Living Campaign processing failed: {exc}. Falling back to single session chronicle.")

    if not docx_filename:
        try:
            summarizer = GeminiTTRPGSummarizer()
            chronicle_md = await run_in_threadpool(
                summarizer.generate_chronicle,
                transcript_text=transcript_text,
                roster=roster_dicts,
                target_language=payload.target_language,
            )
        except Exception as exc:
            chronicle_md = (
                f"### ⚠️ No se pudo generar la crónica automática con Gemini:\n\n"
                f"> {exc}\n\n"
                f"**Transcripción obtenida:**\n\n{transcript_text}"
            )

        try:
            now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            now_formatted = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            docx_filename = f"cronica_sesion_{now_str}.docx"
            docx_out_path = get_data_output_dir() / docx_filename

            await run_in_threadpool(
                export_chronicle_docx,
                chronicle_md=chronicle_md,
                roster=roster_dicts,
                session_date=now_formatted,
                output_path=str(docx_out_path),
            )
        except Exception as exc:
            print(f"[!] Warning: docx export failed: {exc}")

    update_task_progress(task_id, 95, "Generando documento y preparando exportación...", "Creando archivos del Grimorio (.docx y .md)...", stage="analyzing")
    elapsed_time = round(time.time() - start_time, 2)
    language_code = transcription_result.get("language_code") or (
        transcription_result["language"]["code"]
        if isinstance(transcription_result.get("language"), dict)
        else str(transcription_result.get("language", ""))
    )
    txt_filename = None
    if payload.campaign_name and 'camp_res' in locals() and camp_res:
        txt_filename = camp_res.get("txt_filename")
    if not txt_filename:
        now_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_filename = f"cronica_sesion_{now_ts}_transcripcion.txt"
        try:
            (get_data_output_dir() / txt_filename).write_text(transcript_text, encoding="utf-8")
        except Exception as exc:
            print(f"[!] Warning: txt export failed: {exc}")

    update_task_progress(task_id, 100, "¡Completado!", "Sesión procesada exitosamente.", stage="done")

    return {
        "status": "completed",
        "engine_used": transcription_result.get("engine_used", engine),
        "chronicle": chronicle_md,
        "transcript": transcript_text,
        "segments": transcription_result.get("segments", []),
        "language": language_code,
        "duration": transcription_result.get("duration", 0.0),
        "elapsed_time": elapsed_time,
        "docx_filename": docx_filename,
        "md_filename": md_filename,
        "txt_filename": txt_filename,
        "file_path": str(docx_out_path.resolve()) if docx_out_path and docx_out_path.is_file() else "",
        "wav_filename": Path(wav_path).name,
        "campaign_state": campaign_state,
        "session_chapter": session_chapter,
        "detected_party": detected_party,
        "detected_pcs": detected_pcs,
        "updated_quests": updated_quests,
        "updated_npcs": updated_npcs,
        "target_language": payload.target_language,
    }


@app.get("/api/record/download-docx")
async def download_docx(filename: str = Query(..., description="Name of the docx file")):
    """Download a generated session chronicle or academic study notes Word document."""
    safe_filename = Path(filename).name
    file_path = get_data_output_dir() / safe_filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo docx no encontrado.")

    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/api/record/download-md")
async def download_md(filename: str = Query(..., description="Name of the md file")):
    """Download a generated session chronicle or academic study notes markdown document."""
    safe_filename = Path(filename).name
    file_path = get_data_output_dir() / safe_filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo markdown no encontrado.")

    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type="text/markdown",
    )


@app.post("/api/record/delete-audio")
async def delete_recording_audio(payload: DeleteAudioRequest):
    """
    Manually delete an original master recording from data/input/ upon user request.
    Preserves live recordings by default unless explicitly deleted here.
    """
    safe_filename = Path(payload.filename).name
    target_path = get_data_input_dir() / safe_filename
    if not target_path.is_file():
        raise HTTPException(status_code=404, detail=f"Archivo '{safe_filename}' no encontrado en el servidor.")
    try:
        target_path.unlink()
        return {"status": "success", "message": f"Audio original '{safe_filename}' eliminado correctamente."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al eliminar audio: {exc}") from exc


# ---------------------------------------------------------------------------
# Endpoints: YouTube & Local File Transcription
# ---------------------------------------------------------------------------
@app.post("/api/transcribe/youtube", response_model=TranscribeResponse)
async def transcribe_youtube(payload: YouTubeTranscribeRequest):
    """Download audio from YouTube and transcribe it using Groq Whisper or faster-whisper."""
    task_id = payload.task_id
    url = payload.url.strip()
    model_size = payload.model_size or "base"
    engine = payload.engine or "groq"
    start_time = time.time()

    def yt_progress(pct: int, msg: str):
        update_task_progress(task_id, pct, "Descargando audio de YouTube...", msg, stage="audio")

    try:
        audio_file_path = await run_in_threadpool(
            download_youtube_audio,
            url,
            str(get_data_input_dir()),
            on_progress=yt_progress if task_id else None,
        )
    except ValueError as exc:
        update_task_progress(task_id, 0, f"Error URL YouTube: {exc}", stage="error")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        update_task_progress(task_id, 0, f"Error descargando YouTube: {exc}", stage="error")
        raise HTTPException(status_code=500, detail=f"Error descargando audio de YouTube: {exc}") from exc

    update_task_progress(task_id, 30, "Descarga completada. Iniciando transcripción...", "Iniciando motor de audio...", stage="transcribing")

    def progress_cb(pct: int, msg: str):
        update_task_progress(task_id, pct, msg, stage="transcribing")

    roster_dicts = [p.model_dump() for p in payload.roster] if payload.roster else []
    user_char_name = None
    for p in roster_dicts:
        if p.get("is_user_character"):
            user_char_name = (p.get("character_name") or "").strip()
            break

    try:
        result = await run_in_threadpool(
            transcribe_audio_pipeline,
            audio_path=audio_file_path,
            engine=engine,
            model_size=model_size,
            on_progress=progress_cb,
            source="youtube",
            user_char_name=user_char_name,
            roster=roster_dicts,
        )
    except Exception as exc:
        human_err = format_human_error(exc)
        set_task_error(task_id, human_err)
        raise HTTPException(status_code=500, detail=human_err) from exc

    elapsed_time = round(time.time() - start_time, 2)
    language_code = result.get("language_code") or (
        result["language"]["code"] if isinstance(result.get("language"), dict) else str(result.get("language", ""))
    )
    transcript_text = result.get("formatted_transcript") or result["text"]
    file_path_str = ""
    docx_filename = None
    md_filename = None
    txt_filename = None
    campaign_state = None
    session_chapter = None
    updated_quests = None
    updated_npcs = None
    detected_npc_names = None
    detected_party = None
    chronicle_md = None

    if payload.recording_mode == "class":
        update_task_progress(task_id, 80, "Analizando clase universitaria con Gemini...", "Sintetizando conceptos teóricos y fórmulas...")
        subj = (payload.subject or "").strip() or "Materia Universitaria"
        top = (payload.topic or "").strip() or "Tema de Clase"
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        now_formatted = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        try:
            summarizer = GeminiTTRPGSummarizer()
            chronicle_md = await run_in_threadpool(
                summarizer.generate_academic_notes,
                transcript_text=transcript_text,
                subject=subj,
                topic=top,
                date_str=now_formatted,
                target_language=payload.target_language,
            )
            clean_subj = re.sub(r'[\\/*?:"<>|]', "", subj.strip()) or "Materia"
            safe_subj = re.sub(r"\s+", "_", clean_subj)
            docx_filename = f"apuntes_{safe_subj}_{payload.target_language}_{now_str}.docx"
            md_filename = f"apuntes_{safe_subj}_{payload.target_language}_{now_str}.md"
            txt_filename = f"apuntes_{safe_subj}_{payload.target_language}_{now_str}_transcripcion.txt"
            docx_out_path = get_data_output_dir() / docx_filename
            md_out_path = get_data_output_dir() / md_filename
            txt_out_path = get_data_output_dir() / txt_filename

            await run_in_threadpool(
                export_academic_notes_docx,
                notes_md=chronicle_md,
                subject=subj,
                topic=top,
                lecture_date=now_formatted,
                output_path=str(docx_out_path),
            )
            md_out_path.write_text(chronicle_md, encoding="utf-8")
            txt_out_path.write_text(transcript_text, encoding="utf-8")
            (get_data_output_dir() / f"{safe_subj}_transcripcion.txt").write_text(transcript_text, encoding="utf-8")
            file_path_str = str(docx_out_path.resolve())
        except Exception as exc:
            chronicle_md = f"# ⚠️ Error generando guía académica con Gemini:\n\n> {exc}\n\n**Texto:**\n\n{transcript_text}"
            print(f"[transcribe_youtube] Warning: academic notes export failed: {exc}")

        update_task_progress(task_id, 100, "¡Completado!", "Guía de estudio generada exitosamente.", stage="done")
    else:
        update_task_progress(task_id, 80, "Analizando narrativa, NPCs y misiones con Gemini...", "Extrayendo hechos e inventario...", stage="analyzing")

        detected_pcs = None
        if payload.campaign_name:
            try:
                update_task_progress(task_id, 85, "Actualizando Quest Tracker y Directorio Universal de NPCs...", stage="analyzing")
                camp_res = await run_in_threadpool(
                    process_session_for_campaign,
                    campaign_name=payload.campaign_name,
                    transcript_text=transcript_text,
                    roster_dicts=roster_dicts,
                    session_number=payload.session_number,
                    target_language=payload.target_language,
                    is_youtube=True,
                )
                campaign_state = camp_res.get("campaign_state")
                session_chapter = camp_res.get("session_chapter")
                updated_quests = camp_res.get("updated_quests")
                updated_npcs = camp_res.get("updated_npcs")
                detected_npc_names = camp_res.get("detected_npc_names")
                detected_party = camp_res.get("detected_party")
                detected_pcs = camp_res.get("detected_pcs")
                docx_filename = camp_res.get("docx_filename")
                md_filename = camp_res.get("md_filename")
                txt_filename = camp_res.get("txt_filename")
                file_path_str = camp_res.get("file_path", "")
                chronicle_md = camp_res.get("chronicle")
            except Exception as exc:
                print(f"[transcribe_youtube] Warning: campaign session processing failed: {exc}")

        if not file_path_str:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = Path(audio_file_path).stem[:40]
            out_docx_path = get_data_output_dir() / f"transcripcion_youtube_{safe_title}_{timestamp}.docx"
            formatted_md = f"# Transcripción de YouTube: {safe_title}\n\n## Texto Completo\n{transcript_text}\n"
            txt_filename = f"transcripcion_youtube_{safe_title}_{timestamp}.txt"
            (get_data_output_dir() / txt_filename).write_text(transcript_text, encoding="utf-8")

            try:
                exported_docx = await run_in_threadpool(
                    export_chronicle_docx,
                    chronicle_md=formatted_md,
                    roster=roster_dicts or None,
                    session_date=datetime.datetime.now().strftime("%d/%m/%Y"),
                    output_path=str(out_docx_path),
                )
                file_path_str = str(Path(exported_docx).resolve())
                docx_filename = Path(exported_docx).name
            except Exception as exc:
                print(f"[transcribe_youtube] Warning: docx export failed: {exc}")
                out_md_path = get_data_output_dir() / f"transcripcion_youtube_{safe_title}_{timestamp}.md"
                out_md_path.write_text(formatted_md, encoding="utf-8")
                file_path_str = str(out_md_path.resolve())
                docx_filename = None
                md_filename = Path(out_md_path).name

        update_task_progress(task_id, 95, "Generando documento y preparando exportación...", "Creando archivos del Grimorio (.docx y .md)...", stage="analyzing")
        update_task_progress(task_id, 100, "¡Completado!", "Sesión procesada exitosamente.", stage="done")

    # Auto-Delete YouTube Audio:
    # Once the campaign chapter is successfully generated and exported to Drive/Output,
    # delete the downloaded YouTube master audio file from data/input/ (saving ~400MB of disk space).
    try:
        yt_p = Path(audio_file_path)
        if yt_p.is_file():
            yt_p.unlink()
            print(f"[transcribe_youtube] Auto-deleted downloaded YouTube master audio: {yt_p.name}")
    except Exception as exc:
        print(f"[transcribe_youtube] Warning: could not auto-delete YouTube audio: {exc}")

    return TranscribeResponse(
        text=transcript_text,
        segments=result["segments"],
        language=language_code,
        duration=result["duration"],
        elapsed_time=elapsed_time,
        engine_used=result.get("engine_used", engine),
        file_path=file_path_str,
        docx_filename=docx_filename,
        md_filename=md_filename,
        txt_filename=txt_filename,
        campaign_state=campaign_state,
        session_chapter=session_chapter,
        updated_quests=updated_quests,
        updated_npcs=updated_npcs,
        detected_npc_names=detected_npc_names,
        detected_party=detected_party,
        detected_pcs=detected_pcs,
        chronicle=chronicle_md,
        target_language=payload.target_language,
    )


@app.post("/api/transcribe/file", response_model=TranscribeResponse)
async def transcribe_file(
    file: UploadFile = File(...),
    model_size: str = Form(default="base"),
    engine: str = Form(default="groq"),
    campaign_name: Optional[str] = Form(default=None),
    session_number: Optional[int] = Form(default=None),
    roster_json: Optional[str] = Form(default=None),
    task_id: Optional[str] = Form(default=None),
    recording_mode: str = Form(default="roleplay"),
    subject: Optional[str] = Form(default=None),
    topic: Optional[str] = Form(default=None),
    target_language: str = Form(default="es"),
):
    """Accept an uploaded audio file and transcribe it using Groq Whisper or faster-whisper."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    update_task_progress(task_id, 2, "Guardando archivo de audio...", "Guardando en almacenamiento local...", stage="transcribing")
    clean_filename = Path(file.filename).name
    save_dest = get_data_input_dir() / clean_filename
    start_time = time.time()

    try:
        with open(save_dest, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        update_task_progress(task_id, 0, f"Error al guardar archivo: {exc}", stage="error")
        raise HTTPException(status_code=500, detail=f"Error al guardar archivo: {exc}") from exc
    finally:
        await file.close()

    update_task_progress(task_id, 5, "Archivo guardado. Preparando motor de transcripción...", stage="transcribing")

    import json
    roster_dicts = []
    user_char_name = None
    if roster_json:
        try:
            roster_dicts = json.loads(roster_json)
            if isinstance(roster_dicts, list):
                for p in roster_dicts:
                    if isinstance(p, dict) and p.get("is_user_character"):
                        user_char_name = (p.get("character_name") or "").strip()
                        break
        except Exception:
            roster_dicts = []

    def progress_cb(pct: int, msg: str):
        update_task_progress(task_id, pct, msg, stage="transcribing")

    try:
        result = await run_in_threadpool(
            transcribe_audio_pipeline,
            audio_path=str(save_dest),
            engine=engine,
            model_size=model_size,
            on_progress=progress_cb,
            source="local",
            user_char_name=user_char_name,
            roster=roster_dicts,
        )
    except Exception as exc:
        human_err = format_human_error(exc)
        set_task_error(task_id, human_err)
        raise HTTPException(status_code=500, detail=human_err) from exc

    elapsed_time = round(time.time() - start_time, 2)
    language_code = result.get("language_code") or (
        result["language"]["code"] if isinstance(result.get("language"), dict) else str(result.get("language", ""))
    )
    transcript_text = result.get("formatted_transcript") or result["text"]

    file_path_str = ""
    docx_filename = None
    md_filename = None
    txt_filename = None
    campaign_state = None
    session_chapter = None
    updated_quests = None
    updated_npcs = None
    detected_npc_names = None
    detected_party = None
    chronicle_md = None

    if recording_mode == "class":
        update_task_progress(task_id, 80, "Analizando clase universitaria con Gemini...", "Sintetizando conceptos teóricos y fórmulas...")
        subj = (subject or "").strip() or "Materia Universitaria"
        top = (topic or "").strip() or "Tema de Clase"
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        now_formatted = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        try:
            summarizer = GeminiTTRPGSummarizer()
            chronicle_md = await run_in_threadpool(
                summarizer.generate_academic_notes,
                transcript_text=transcript_text,
                subject=subj,
                topic=top,
                date_str=now_formatted,
                target_language=target_language,
            )
        except Exception as exc:
            chronicle_md = f"# ⚠️ Error generando guía académica con Gemini:\n\n> {exc}\n\n**Texto:**\n\n{transcript_text}"

        update_task_progress(task_id, 95, "Generando documento y preparando exportación...", "Creando archivos de apuntes...")
        clean_subj = re.sub(r'[\\/*?:"<>|]', "", subj.strip()) or "Materia"
        safe_subj = re.sub(r"\s+", "_", clean_subj)
        docx_filename = f"apuntes_file_{safe_subj}_{now_str}.docx"
        md_filename = f"apuntes_file_{safe_subj}_{now_str}.md"
        txt_filename = f"apuntes_file_{safe_subj}_{now_str}_transcripcion.txt"
        docx_out_path = get_data_output_dir() / docx_filename
        md_out_path = get_data_output_dir() / md_filename
        txt_out_path = get_data_output_dir() / txt_filename

        try:
            await run_in_threadpool(
                export_academic_notes_docx,
                notes_md=chronicle_md,
                subject=subj,
                topic=top,
                lecture_date=now_formatted,
                output_path=str(docx_out_path),
            )
            md_out_path.write_text(chronicle_md, encoding="utf-8")
            txt_out_path.write_text(transcript_text, encoding="utf-8")
            (get_data_output_dir() / f"{safe_subj}_transcripcion.txt").write_text(transcript_text, encoding="utf-8")
            file_path_str = str(docx_out_path.resolve())
        except Exception as exc:
            print(f"[transcribe_file] Warning: academic notes export failed: {exc}")

        update_task_progress(task_id, 100, "¡Completado!", "Guía de estudio generada exitosamente.")
        return TranscribeResponse(
            text=transcript_text,
            segments=result["segments"],
            language=language_code,
            duration=result["duration"],
            elapsed_time=elapsed_time,
            engine_used=result.get("engine_used", engine),
            file_path=file_path_str,
            docx_filename=docx_filename,
            md_filename=md_filename,
            txt_filename=txt_filename,
            recording_mode="class",
            subject=subj,
            topic=top,
            chronicle=chronicle_md,
            target_language=target_language,
        )

    update_task_progress(task_id, 80, "Analizando narrativa, misiones y NPCs con Gemini...", "Extrayendo hechos e inventario...", stage="analyzing")

    detected_pcs = None
    if campaign_name:
        try:
            update_task_progress(task_id, 85, "Actualizando Quest Tracker y Directorio Universal de NPCs...", stage="analyzing")
            camp_res = await run_in_threadpool(
                process_session_for_campaign,
                campaign_name=campaign_name,
                transcript_text=transcript_text,
                roster_dicts=roster_dicts,
                session_number=session_number,
                target_language=target_language,
            )
            campaign_state = camp_res.get("campaign_state")
            session_chapter = camp_res.get("session_chapter")
            updated_quests = camp_res.get("updated_quests")
            updated_npcs = camp_res.get("updated_npcs")
            detected_npc_names = camp_res.get("detected_npc_names")
            detected_party = camp_res.get("detected_party")
            detected_pcs = camp_res.get("detected_pcs")
            docx_filename = camp_res.get("docx_filename")
            md_filename = camp_res.get("md_filename")
            txt_filename = camp_res.get("txt_filename")
            file_path_str = camp_res.get("file_path", "")
            chronicle_md = camp_res.get("chronicle")
        except Exception as exc:
            print(f"[transcribe_file] Warning: campaign session processing failed: {exc}")

    if not file_path_str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = Path(clean_filename).stem[:40]
        out_docx_path = get_data_output_dir() / f"transcripcion_{safe_title}_{timestamp}.docx"
        formatted_md = f"# Transcripción de Audio: {safe_title}\n\n## Texto Completo\n{transcript_text}\n"
        txt_filename = f"transcripcion_{safe_title}_{timestamp}.txt"
        (get_data_output_dir() / txt_filename).write_text(transcript_text, encoding="utf-8")

        try:
            exported_docx = await run_in_threadpool(
                export_chronicle_docx,
                chronicle_md=formatted_md,
                roster=roster_dicts or None,
                session_date=datetime.datetime.now().strftime("%d/%m/%Y"),
                output_path=str(out_docx_path),
            )
            file_path_str = str(Path(exported_docx).resolve())
            docx_filename = Path(exported_docx).name
        except Exception as exc:
            print(f"[transcribe_file] Warning: docx export failed: {exc}")
            out_md_path = get_data_output_dir() / f"transcripcion_{safe_title}_{timestamp}.md"
            out_md_path.write_text(formatted_md, encoding="utf-8")
            file_path_str = str(out_md_path.resolve())
            docx_filename = None
            md_filename = Path(out_md_path).name

    update_task_progress(task_id, 95, "Generando documento y preparando exportación...", "Creando archivos del Grimorio (.docx y .md)...", stage="analyzing")
    update_task_progress(task_id, 100, "¡Completado!", "Sesión procesada exitosamente.", stage="done")

    return TranscribeResponse(
        text=transcript_text,
        segments=result["segments"],
        language=language_code,
        duration=result["duration"],
        elapsed_time=elapsed_time,
        engine_used=result.get("engine_used", engine),
        file_path=file_path_str,
        docx_filename=docx_filename,
        md_filename=md_filename,
        txt_filename=txt_filename,
        campaign_state=campaign_state,
        session_chapter=session_chapter,
        updated_quests=updated_quests,
        updated_npcs=updated_npcs,
        detected_npc_names=detected_npc_names,
        detected_party=detected_party,
        detected_pcs=detected_pcs,
        chronicle=chronicle_md,
        recording_mode="roleplay",
        target_language=target_language,
    )


@app.post("/api/summarize/switch-language", response_model=TranscribeResponse)
async def switch_summary_language(payload: SwitchLanguageRequest):
    """
    Re-generate the chronicle or academic notes in a new target language (ES/EN)
    using the cached transcript text, in ~5-10 seconds without re-downloading or re-transcribing audio.
    """
    transcript_text = payload.transcript_text.strip()
    if not transcript_text:
        raise HTTPException(status_code=400, detail="El texto de transcripción está vacío.")

    target_lang = (payload.target_language or "es").lower().strip()
    is_class_mode = payload.recording_mode == "class"
    start_time = time.time()
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    now_formatted = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    file_path_str = ""
    docx_filename = None
    md_filename = None
    campaign_state = None
    session_chapter = None
    updated_quests = None
    updated_npcs = None
    detected_npc_names = None
    detected_party = None
    detected_pcs = None
    chronicle_md = ""

    summarizer = GeminiTTRPGSummarizer()

    if is_class_mode:
        subj = (payload.subject or "").strip() or "Materia Universitaria"
        top = (payload.topic or "").strip() or "Tema de Clase"
        chronicle_md = await run_in_threadpool(
            summarizer.generate_academic_notes,
            transcript_text=transcript_text,
            subject=subj,
            topic=top,
            date_str=now_formatted,
            target_language=target_lang,
        )
        clean_subj = re.sub(r'[\\/*?:"<>|]', "", subj.strip()) or "Materia"
        safe_subj = re.sub(r"\s+", "_", clean_subj)
        docx_filename = f"apuntes_{safe_subj}_{target_lang}_{now_str}.docx"
        md_filename = f"apuntes_{safe_subj}_{target_lang}_{now_str}.md"
        txt_filename = f"apuntes_{safe_subj}_{target_lang}_{now_str}_transcripcion.txt"
        docx_out_path = get_data_output_dir() / docx_filename
        md_out_path = get_data_output_dir() / md_filename
        (get_data_output_dir() / txt_filename).write_text(transcript_text, encoding="utf-8")

        try:
            await run_in_threadpool(
                export_academic_notes_docx,
                notes_md=chronicle_md,
                subject=subj,
                topic=top,
                lecture_date=now_formatted,
                output_path=str(docx_out_path),
            )
            md_out_path.write_text(chronicle_md, encoding="utf-8")
            file_path_str = str(docx_out_path.resolve())
        except Exception as exc:
            print(f"[switch_language] Warning: docx export failed: {exc}")
    else:
        roster_dicts = [p.model_dump() for p in payload.roster] if payload.roster else []
        detected_pcs = None
        txt_filename = None
        if payload.campaign_name:
            try:
                camp_res = await run_in_threadpool(
                    process_session_for_campaign,
                    campaign_name=payload.campaign_name,
                    transcript_text=transcript_text,
                    roster_dicts=roster_dicts,
                    session_number=payload.session_number,
                    target_language=target_lang,
                )
                campaign_state = camp_res.get("campaign_state")
                session_chapter = camp_res.get("session_chapter")
                updated_quests = camp_res.get("updated_quests")
                updated_npcs = camp_res.get("updated_npcs")
                detected_npc_names = camp_res.get("detected_npc_names")
                detected_party = camp_res.get("detected_party")
                detected_pcs = camp_res.get("detected_pcs")
                docx_filename = camp_res.get("docx_filename")
                md_filename = camp_res.get("md_filename")
                txt_filename = camp_res.get("txt_filename")
                file_path_str = camp_res.get("file_path", "")
                chronicle_md = camp_res.get("chronicle", "")
            except Exception as exc:
                print(f"[switch_language] Warning: campaign processing failed: {exc}")

        if not chronicle_md:
            chronicle_md = await run_in_threadpool(
                summarizer.generate_chronicle,
                transcript_text=transcript_text,
                roster=roster_dicts,
                target_language=target_lang,
            )
            docx_filename = f"cronica_sesion_{target_lang}_{now_str}.docx"
            docx_out_path = get_data_output_dir() / docx_filename
            txt_filename = f"cronica_sesion_{target_lang}_{now_str}_transcripcion.txt"
            (get_data_output_dir() / txt_filename).write_text(transcript_text, encoding="utf-8")
            try:
                await run_in_threadpool(
                    export_chronicle_docx,
                    chronicle_md=chronicle_md,
                    roster=roster_dicts,
                    session_date=now_formatted,
                    output_path=str(docx_out_path),
                )
                file_path_str = str(docx_out_path.resolve())
            except Exception as exc:
                print(f"[switch_language] Warning: single docx export failed: {exc}")

    elapsed_time = round(time.time() - start_time, 2)
    return TranscribeResponse(
        text=transcript_text,
        segments=[],
        language=target_lang,
        duration=0.0,
        elapsed_time=elapsed_time,
        engine_used="gemini-resynthesize",
        file_path=file_path_str,
        docx_filename=docx_filename,
        md_filename=md_filename,
        txt_filename=txt_filename,
        campaign_state=campaign_state,
        session_chapter=session_chapter,
        updated_quests=updated_quests,
        updated_npcs=updated_npcs,
        detected_npc_names=detected_npc_names,
        detected_party=detected_party,
        detected_pcs=detected_pcs,
        chronicle=chronicle_md,
        recording_mode=payload.recording_mode,
        subject=payload.subject,
        topic=payload.topic,
        target_language=target_lang,
    )


@app.post("/api/campaign/reprocess", response_model=TranscribeResponse)
async def reprocess_campaign(payload: ReprocessCampaignRequest):
    """
    Re-run ONLY the Gemini summarizer step using the cached transcript in ~10-15s
    (does NOT invoke Whisper or YouTube).
    Returns updated TranscribeResponse with populated chronicle, campaign_state,
    updated_quests, updated_npcs, detected_npc_names.
    """
    transcript_text = payload.transcript_text.strip()
    if not transcript_text:
        raise HTTPException(status_code=400, detail="El texto de transcripción está vacío.")

    target_lang = (payload.target_language or "es").lower().strip()
    is_class_mode = payload.recording_mode == "class"
    start_time = time.time()
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    now_formatted = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    file_path_str = ""
    docx_filename = None
    md_filename = None
    txt_filename = None
    campaign_state = None
    session_chapter = None
    updated_quests = None
    updated_npcs = None
    detected_npc_names = None
    detected_party = None
    detected_pcs = None
    chronicle_md = ""

    summarizer = GeminiTTRPGSummarizer()

    if is_class_mode:
        subj = (payload.subject or "").strip() or "Materia Universitaria"
        top = (payload.topic or "").strip() or "Tema de Clase"
        chronicle_md = await run_in_threadpool(
            summarizer.generate_academic_notes,
            transcript_text=transcript_text,
            subject=subj,
            topic=top,
            date_str=now_formatted,
            target_language=target_lang,
        )
        clean_subj = re.sub(r'[\\/*?:"<>|]', "", subj.strip()) or "Materia"
        safe_subj = re.sub(r"\s+", "_", clean_subj)
        docx_filename = f"apuntes_{safe_subj}_{target_lang}_{now_str}.docx"
        md_filename = f"apuntes_{safe_subj}_{target_lang}_{now_str}.md"
        txt_filename = f"apuntes_{safe_subj}_{target_lang}_{now_str}_transcripcion.txt"
        docx_out_path = get_data_output_dir() / docx_filename
        md_out_path = get_data_output_dir() / md_filename
        (get_data_output_dir() / txt_filename).write_text(transcript_text, encoding="utf-8")

        try:
            await run_in_threadpool(
                export_academic_notes_docx,
                notes_md=chronicle_md,
                subject=subj,
                topic=top,
                lecture_date=now_formatted,
                output_path=str(docx_out_path),
            )
            md_out_path.write_text(chronicle_md, encoding="utf-8")
            file_path_str = str(docx_out_path.resolve())
        except Exception as exc:
            print(f"[reprocess_campaign] Warning: docx export failed: {exc}")
    else:
        campaign_name = payload.campaign_name or "Campaña Principal"
        manager = CampaignManager()
        active_ctx = manager.get_active_context(campaign_name)
        session_num = payload.session_number or (active_ctx["last_session"] if active_ctx.get("last_session", 0) > 0 else 1)
        roster_dicts = [p.model_dump() for p in payload.roster] if payload.roster else active_ctx.get("roster", [])

        try:
            camp_res = await run_in_threadpool(
                process_session_for_campaign,
                campaign_name=campaign_name,
                transcript_text=transcript_text,
                roster_dicts=roster_dicts,
                session_number=session_num,
                target_language=target_lang,
                is_youtube=bool(payload.is_youtube),
            )
            campaign_state = camp_res.get("campaign_state")
            session_chapter = camp_res.get("session_chapter")
            updated_quests = camp_res.get("updated_quests")
            updated_npcs = camp_res.get("updated_npcs")
            detected_npc_names = camp_res.get("detected_npc_names")
            detected_party = camp_res.get("detected_party")
            detected_pcs = camp_res.get("detected_pcs")
            docx_filename = camp_res.get("docx_filename")
            md_filename = camp_res.get("md_filename")
            txt_filename = camp_res.get("txt_filename")
            file_path_str = camp_res.get("file_path", "")
            chronicle_md = camp_res.get("chronicle", "")
        except Exception as exc:
            print(f"[reprocess_campaign] Warning: campaign processing failed: {exc}")
            raise HTTPException(status_code=500, detail=f"Error al procesar la campaña con Gemini: {exc}")

    elapsed_time = round(time.time() - start_time, 2)
    return TranscribeResponse(
        text=transcript_text,
        segments=[],
        language=target_lang,
        duration=0.0,
        elapsed_time=elapsed_time,
        engine_used="gemini-reprocess",
        file_path=file_path_str,
        docx_filename=docx_filename,
        md_filename=md_filename,
        txt_filename=txt_filename,
        campaign_state=campaign_state,
        session_chapter=session_chapter,
        updated_quests=updated_quests,
        updated_npcs=updated_npcs,
        detected_npc_names=detected_npc_names,
        detected_party=detected_party,
        detected_pcs=detected_pcs,
        chronicle=chronicle_md,
        recording_mode=payload.recording_mode,
        subject=payload.subject,
        topic=payload.topic,
        target_language=target_lang,
    )



# ---------------------------------------------------------------------------
# Endpoints: Living Campaign Journal
# ---------------------------------------------------------------------------
@app.get("/api/campaigns")
async def list_campaigns():
    """List all campaigns in data/campaigns/."""
    manager = CampaignManager()
    return manager.list_campaigns()


@app.get("/api/campaigns/{campaign_name}")
async def get_campaign(campaign_name: str):
    """Get full state and active context for a campaign."""
    manager = CampaignManager()
    state = manager.load_campaign(campaign_name)
    active_ctx = manager.get_active_context(campaign_name)
    return {
        "campaign_state": state,
        "active_context": active_ctx,
    }


@app.get("/api/campaigns/{campaign_name}/session/{session_num}")
async def get_campaign_session_endpoint(campaign_name: str, session_num: int):
    """Retrieve full historical session data including chronicle markdown, raw transcript, quests, NPCs, and PCs."""
    manager = CampaignManager()
    state = manager.load_campaign(campaign_name)
    if not state:
        raise HTTPException(status_code=404, detail=f"Campaña '{campaign_name}' no encontrada.")

    sessions = state.get("sessions", [])
    target_session = next((s for s in sessions if int(s.get("session_number", 0)) == int(session_num)), None)
    if not target_session:
        raise HTTPException(status_code=404, detail=f"Sesión #{session_num} no encontrada en la campaña '{campaign_name}'.")

    # Resolve chronicle_markdown
    chronicle_md = (target_session.get("chronicle_markdown") or "").strip()
    if not chronicle_md or (not chronicle_md.startswith("#") and target_session.get("chronicle_text")):
        parts = []
        pcs = target_session.get("detected_pcs") or target_session.get("detected_party") or []
        if pcs:
            proto_title = "### 🎭 Compañía de Aventureros (Protagonistas Detectados)"
            table_header = "| Personaje | Jugador / Rol | Clase / Especie | Rol en la Sesión |\n|---|---|---|---|"
            rows = []
            for p in pcs:
                char = p.get("personaje") or p.get("character_name") or "-"
                player = p.get("jugador") or p.get("player_name") or "-"
                cls = p.get("clase") or p.get("role") or "-"
                spec = p.get("especie") or p.get("species") or "-"
                cls_spec = f"{cls} / {spec}" if cls != "-" and spec != "-" else (cls if cls != "-" else spec)
                sess_role = p.get("rol_en_sesion") or p.get("session_role") or "-"
                rows.append(f"| **{char}** | {player} | {cls_spec} | {sess_role} |")
            if rows:
                parts.append(f"{proto_title}\n\n{table_header}\n" + "\n".join(rows) + "\n\n---")

        if target_session.get("chronicle_text"):
            parts.append(f"## 1. Crónica Narrativa y Combates\n{target_session['chronicle_text']}")
        if target_session.get("closing_expectations"):
            parts.append(f"## 2. Cierre de Mesa, Decisiones y Expectativas\n{target_session['closing_expectations']}")
        coaching = target_session.get("user_coaching") or target_session.get("markus_coaching")
        if coaching:
            u_char = target_session.get("user_character", {})
            c_name = u_char.get("character_name") or u_char.get("name") or "Personaje"
            parts.append(f"## 3. Reflexión de Rol y Compañerismo: {c_name}\n{coaching}")
        next_script = target_session.get("next_session_script") or target_session.get("recap_text")
        if next_script:
            parts.append(f"## 4. 🎙️ Guion para abrir la Sesión #{session_num + 1} (Para leer en voz alta)\n{next_script}")

        chronicle_md = "\n\n".join(parts) or target_session.get("chronicle_text", "")

    # Resolve raw_transcript
    raw_transcript = (target_session.get("raw_transcript") or "").strip()
    if not raw_transcript:
        raw_transcript = f"Transcripción no guardada para la sesión #{session_num}."

    safe_name = manager.sanitize_name(campaign_name)
    txt_filename = f"{safe_name}_sesion_{session_num}_transcripcion.txt"
    try:
        txt_path = get_data_output_dir() / txt_filename
        if not txt_path.is_file():
            content_to_write = raw_transcript if (raw_transcript and not raw_transcript.startswith("Transcripción no guardada")) else (target_session.get("chronicle_text") or raw_transcript)
            if content_to_write:
                txt_path.write_text(content_to_write, encoding="utf-8")
    except Exception as exc:
        print(f"[get_campaign_session_endpoint] Warning writing txt: {exc}")

    pcs_list = target_session.get("detected_pcs") or target_session.get("detected_party") or state.get("roster") or []
    recap = target_session.get("recap_text") or target_session.get("next_session_script") or ""

    return {
        "campaign_name": campaign_name,
        "session_number": int(session_num),
        "title": target_session.get("title", f"Sesión {session_num}"),
        "date": target_session.get("date", ""),
        "chronicle_markdown": chronicle_md,
        "raw_transcript": raw_transcript,
        "quests": state.get("quests", []),
        "npcs": state.get("npcs", []),
        "pcs": pcs_list,
        "recap": recap,
        "session_chapter": target_session,
        "campaign_state": state,
        "txt_filename": txt_filename,
        "wav_filename": target_session.get("wav_filename"),
    }


@app.delete("/api/campaigns/{campaign_name}")
async def delete_campaign_endpoint(campaign_name: str):
    """Delete campaign state file and associated exports in data/output/."""
    manager = CampaignManager()
    deleted = manager.delete_campaign(campaign_name, delete_exports=True)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Campaña '{campaign_name}' no encontrada.")
    return {"status": "deleted", "campaign": campaign_name}


@app.post("/api/campaigns")
async def create_or_init_campaign(payload: CreateCampaignRequest):
    """Create or load campaign state, optionally setting roster and prior lore."""
    manager = CampaignManager()
    state = manager.load_campaign(payload.campaign_name)
    modified = False
    if payload.roster:
        state["roster"] = [p.model_dump() for p in payload.roster]
        modified = True
    if payload.prior_lore is not None and payload.prior_lore.strip():
        state["prior_lore"] = payload.prior_lore.strip()
        modified = True
    if modified:
        manager.save_campaign(state)
    return state


@app.put("/api/campaigns/{campaign_name}/prior-lore")
async def update_campaign_prior_lore(campaign_name: str, payload: UpdatePriorLoreRequest):
    """Update and persist prior lore for an ongoing campaign."""
    manager = CampaignManager()
    state = manager.set_prior_lore(campaign_name, payload.prior_lore)
    return {
        "status": "success",
        "campaign_name": campaign_name,
        "prior_lore": state.get("prior_lore", ""),
        "campaign_state": state,
    }


@app.post("/api/campaigns/{campaign_name}/session")
async def process_campaign_session_endpoint(campaign_name: str, payload: ProcessCampaignSessionRequest):
    """Process a session transcript for a campaign."""
    roster_dicts = [p.model_dump() for p in payload.roster] if payload.roster else None
    try:
        result = process_session_for_campaign(
            campaign_name=campaign_name,
            transcript_text=payload.transcript_text,
            roster_dicts=roster_dicts,
            session_number=payload.session_number,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error procesando sesión de campaña: {exc}") from exc


@app.post("/api/campaigns/{campaign_name}/finalize-npcs")
async def finalize_npcs(campaign_name: str, payload: FinalizeNpcsRequest):
    """Apply user spell-check name corrections to NPCs and re-export documents."""
    manager = CampaignManager()
    state = manager.load_campaign(campaign_name)
    for old_name, new_name in payload.name_corrections.items():
        if old_name and new_name and old_name != new_name:
            state = manager.update_npc_name(campaign_name, old_name, new_name)

    # Re-export documents with corrected names
    export_living_journal_docx(state)
    export_living_journal_md(state)

    return {
        "status": "success",
        "message": f"Nombres de PNJs actualizados ({len(payload.name_corrections)} correcciones).",
        "campaign_state": state,
    }


@app.put("/api/campaigns/{campaign_name}/quests/{quest_id}/subobjective")
async def update_quest_subobjective(
    campaign_name: str,
    quest_id: str,
    payload: UpdateQuestSubobjectiveRequest,
):
    """Update quest subobjective status and re-export documents."""
    manager = CampaignManager()
    try:
        state = manager.update_quest_subobjective(
            name=campaign_name,
            quest_id=quest_id,
            subobjective_idx=payload.subobjective_idx,
            completed=payload.completed,
        )
        # Re-export documents
        export_living_journal_docx(state)
        export_living_journal_md(state)
        return {
            "status": "success",
            "campaign_state": state,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/campaigns/{campaign_name}/quests/{quest_id}/status")
async def update_quest_status_endpoint(
    campaign_name: str,
    quest_id: str,
    payload: Optional[UpdateQuestStatusRequest] = None,
):
    """Toggle or set status of a quest (in_progress <-> completed) and re-export documents."""
    manager = CampaignManager()
    status_val = payload.status if payload else None
    try:
        state = manager.toggle_quest_status(
            name=campaign_name,
            quest_id=quest_id,
            status=status_val,
        )
        export_living_journal_docx(state)
        export_living_journal_md(state)
        return {
            "status": "success",
            "campaign_state": state,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/campaigns/{campaign_name}/download-docx")
async def download_campaign_docx(campaign_name: str):
    """Download the consolidated Word document for the campaign."""
    manager = CampaignManager()
    state = manager.load_campaign(campaign_name)
    docx_path = export_living_journal_docx(state)
    target = Path(docx_path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Archivo Grimorio docx no encontrado.")

    return FileResponse(
        path=target,
        filename=target.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/api/campaigns/{campaign_name}/download-md")
async def download_campaign_md(campaign_name: str):
    """Download the consolidated Markdown document for the campaign."""
    manager = CampaignManager()
    state = manager.load_campaign(campaign_name)
    md_path = export_living_journal_md(state)
    target = Path(md_path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Archivo Grimorio md no encontrado.")

    return FileResponse(
        path=target,
        filename=target.name,
        media_type="text/markdown",
    )


@app.get("/api/download/transcript/{filename}")
async def download_transcript_txt(filename: str):
    """Download a standalone plain-text transcript file."""
    safe_filename = Path(filename).name
    if not safe_filename or safe_filename.startswith("."):
        raise HTTPException(status_code=400, detail="Nombre de archivo no válido.")

    file_path = get_data_output_dir() / safe_filename
    if not file_path.is_file() and not safe_filename.endswith(".txt"):
        alt_path = get_data_output_dir() / f"{safe_filename}.txt"
        if alt_path.is_file():
            file_path = alt_path
            safe_filename = alt_path.name

    if not file_path.is_file():
        m = re.match(r"^(.+)_sesion_(\d+)_transcripcion\.txt$", safe_filename)
        if m:
            camp_name, sess_num = m.group(1), int(m.group(2))
            mgr = CampaignManager()
            state = mgr.load_campaign(camp_name)
            if state:
                for s in state.get("sessions", []):
                    if int(s.get("session_number", 0)) == sess_num:
                        content = s.get("raw_transcript") or s.get("chronicle_text") or f"Transcripción no guardada para la sesión #{sess_num}."
                        try:
                            file_path.write_text(content, encoding="utf-8")
                            break
                        except Exception:
                            pass

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Transcripción '{safe_filename}' no encontrada en data/output/.")

    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


@app.get("/api/download/audio/{filename}")
async def download_audio_file(filename: str):
    """Download a recorded audio WAV file."""
    safe_filename = Path(filename).name
    if not safe_filename or safe_filename.startswith("."):
        raise HTTPException(status_code=400, detail="Nombre de archivo no válido.")

    file_path = get_data_input_dir() / safe_filename
    if not file_path.is_file():
        file_path = get_data_output_dir() / safe_filename

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Audio '{safe_filename}' no encontrado en el servidor.")

    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type="audio/wav",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


@app.post("/api/campaigns/{campaign_name}/export-drive", response_model=DriveExportResponse)
async def export_campaign_to_drive(campaign_name: str):
    """Upload the campaign Grimorio .docx to Google Drive folder 'Whisper AI - Transcripciones'."""
    manager = CampaignManager()
    state = manager.load_campaign(campaign_name)
    docx_path = export_living_journal_docx(state)
    target_file = Path(docx_path)
    if not target_file.is_file():
        raise HTTPException(status_code=404, detail=f"Grimorio docx no encontrado para campaña {campaign_name}.")

    try:
        drive_storage = GoogleDriveStorage()
        upload_res = drive_storage.upload_file(str(target_file.resolve()))
        return DriveExportResponse(
            status="success",
            web_view_link=upload_res.get("web_view_link", ""),
            file_name=upload_res.get("file_name", target_file.name),
            file_id=upload_res.get("file_id", ""),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error al subir a Google Drive: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Endpoints: Google Drive Export (Generic)
# ---------------------------------------------------------------------------
@app.post("/api/export/drive", response_model=DriveExportResponse)
async def export_to_drive(payload: DriveExportRequest):
    """Upload a file to Google Drive folder 'Whisper AI - Transcripciones'."""
    raw_path = payload.file_path.strip()
    if not raw_path:
        raise HTTPException(status_code=400, detail="file_path no puede estar vacío.")

    target_file = Path(raw_path)
    if not target_file.is_file():
        # Check relative to output dir
        candidate = get_data_output_dir() / target_file.name
        if candidate.is_file():
            target_file = candidate
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Archivo no encontrado en el servidor: {raw_path}",
            )

    try:
        drive_storage = GoogleDriveStorage()
        upload_res = drive_storage.upload_file(str(target_file.resolve()))
        return DriveExportResponse(
            status="success",
            web_view_link=upload_res.get("web_view_link", ""),
            file_name=upload_res.get("file_name", target_file.name),
            file_id=upload_res.get("file_id", ""),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error al subir a Google Drive: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Endpoints: Task Progress & Upfront Google Drive Auth & Diagnostics
# ---------------------------------------------------------------------------
@app.get("/api/task/status")
async def get_task_status_endpoint(task_id: str = Query(..., description="ID of the task to query")):
    """Get granular progress and status of an active or recent task."""
    return get_task_progress(task_id)


@app.get("/api/status/keys")
async def check_api_keys():
    """
    Perform a lightweight 1-second ping to verify health and availability of
    Groq, Gemini, and Google Drive credentials.
    """
    # 1. Groq Check
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    groq_ok = False
    groq_msg = ""
    if not groq_key:
        groq_msg = "GROQ_API_KEY no configurada."
    else:
        def _check_groq():
            import groq
            client = groq.Client(api_key=groq_key, timeout=2.0)
            client.models.list()
            return True

        try:
            groq_ok = await run_in_threadpool(_check_groq)
            groq_msg = "Groq Whisper API operativa."
        except Exception as exc:
            groq_ok = False
            groq_msg = f"Error validando Groq: {exc}"

    # 2. Gemini Check
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_ok = False
    gemini_msg = ""
    if not gemini_key:
        gemini_msg = "GEMINI_API_KEY no configurada."
    else:
        def _check_gemini():
            from google import genai
            client = genai.Client(api_key=gemini_key)
            for _ in client.models.list():
                break
            return True

        try:
            gemini_ok = await run_in_threadpool(_check_gemini)
            gemini_msg = "Gemini API operativa."
        except Exception as exc:
            gemini_ok = False
            gemini_msg = f"Error validando Gemini: {exc}"

    # 3. Drive Check
    drive_storage = GoogleDriveStorage()
    drive_ok = await run_in_threadpool(drive_storage.is_connected)
    drive_msg = (
        "Google Drive conectado."
        if drive_ok
        else ("Credenciales listas, conexión pendiente." if drive_storage.credentials_path.is_file() else "Falta credentials.json en la raíz del proyecto.")
    )

    return {
        "groq": groq_ok,
        "gemini": gemini_ok,
        "drive": drive_ok,
        "groq_message": groq_msg,
        "gemini_message": gemini_msg,
        "drive_message": drive_msg,
    }


@app.get("/api/drive/status")
async def get_drive_status():
    """Check if Google Drive OAuth is connected and credentials.json is present."""
    drive_storage = GoogleDriveStorage()
    has_creds = drive_storage.credentials_path.is_file()
    connected = drive_storage.is_connected()
    return {
        "connected": connected,
        "has_credentials": has_creds,
        "message": (
            "Google Drive conectado"
            if connected
            else ("Credenciales listas, conexión pendiente" if has_creds else "Falta credentials.json en la raíz del proyecto")
        ),
    }


@app.get("/api/auth/drive/login")
async def drive_login(redirect_uri: Optional[str] = None):
    """Generate Google Drive OAuth authorization URL without blocking the FastAPI server."""
    drive_storage = GoogleDriveStorage()
    target_redirect = redirect_uri or "http://localhost:8080/api/auth/drive/callback"
    try:
        auth_url = await run_in_threadpool(
            drive_storage.get_authorization_url,
            target_redirect,
        )
        return {"auth_url": auth_url}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error generando URL de autenticación: {exc}") from exc


@app.get("/api/auth/drive/callback")
async def drive_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """
    Handle Google Drive OAuth redirect callback, exchange code for token.json,
    and redirect back to frontend.
    """
    if error and isinstance(error, str):
        raise HTTPException(status_code=400, detail=f"Google OAuth denegado: {error}")
    if not code or not isinstance(code, str):
        raise HTTPException(status_code=400, detail="Código de autorización ausente en el callback.")

    drive_storage = GoogleDriveStorage()
    try:
        await run_in_threadpool(
            drive_storage.exchange_code_for_token,
            code=code,
            redirect_uri="http://localhost:8080/api/auth/drive/callback",
            state=state,
        )
        return RedirectResponse(url="/?drive_connected=true", status_code=302)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al canjear código de OAuth: {exc}") from exc


@app.post("/api/drive/connect")
async def connect_drive():
    """Generate Google Drive authorization URL upfront."""
    drive_storage = GoogleDriveStorage()
    if not drive_storage.credentials_path.is_file():
        raise HTTPException(
            status_code=400,
            detail="No se encontró el archivo credentials.json en la raíz del proyecto. Coloca el archivo descargado de Google Cloud Console.",
        )
    try:
        auth_url = await run_in_threadpool(
            drive_storage.get_authorization_url,
            "http://localhost:8080/api/auth/drive/callback",
        )
        return {
            "status": "success",
            "connected": drive_storage.is_connected(),
            "auth_url": auth_url,
            "message": "URL de autorización generada.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al iniciar autenticación de Google Drive: {exc}") from exc


