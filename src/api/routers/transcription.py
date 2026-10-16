"""FastAPI router for audio transcription, YouTube processing, telemetry uploads, and reprocessing."""

import asyncio
import datetime
import json
import os
import re
import shutil
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, Request
from pydantic import BaseModel, Field, ConfigDict
from starlette.concurrency import run_in_threadpool

from src.api import server

router = APIRouter(tags=["transcription"])


# ---------------------------------------------------------------------------
# Request/Response Models for Transcription
# ---------------------------------------------------------------------------
class YouTubeTranscribeRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: str = Field(..., description="YouTube video URL to transcribe")
    model_size: str = Field(default="base", description="Whisper model size (tiny, base)")
    engine: str = Field(default="groq", description="Transcription engine ('groq' or 'local')")
    campaign_name: Optional[str] = Field(default=None, description="Name of the campaign")
    campaign_id: Optional[str] = Field(default=None, description="Optional campaign ID")
    session_number: Optional[int] = Field(default=None, description="Optional manual session number")
    roster: Optional[List[server.PlayerMetadata]] = Field(default_factory=list, description="Party roster")
    task_id: Optional[str] = Field(default=None, description="Task ID for progress tracking")
    recording_mode: str = Field(default="roleplay", description="Recording mode ('roleplay' or 'class')")
    workspace: Optional[str] = Field(default="dnd", description="Workspace mode ('dnd' or 'work_and_study')")
    subject: Optional[str] = Field(default="", description="Materia / Asignatura for university lecture")
    topic: Optional[str] = Field(default="", description="Tema de la clase for university lecture")
    target_language: str = Field(default="es", description="Target language ('es' or 'en')")
    audio_language: Optional[str] = Field(default=None, description="Explicit audio language or None for Whisper auto-detection")




class TranscribeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str
    segments: List[Dict[str, Any]]
    language: str
    duration: float
    elapsed_time: float
    engine_used: Optional[str] = None
    file_path: Optional[str] = None
    docx_filename: Optional[str] = None
    md_filename: Optional[str] = None
    campaign_name: Optional[str] = None
    session_number: Optional[int] = None
    session_title: Optional[str] = None
    telemetry_events_count: Optional[int] = None
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
    action_items: Optional[List[str]] = None
    key_points: Optional[str] = None




class SwitchLanguageRequest(BaseModel):
    transcript_text: str = Field(..., description="Speech-to-text transcript")
    target_language: str = Field(default="en", description="Target language ('es' or 'en')")
    recording_mode: str = Field(default="roleplay", description="'roleplay' or 'class'")
    campaign_name: Optional[str] = Field(default=None, description="Campaign name")
    session_number: Optional[int] = Field(default=None, description="Session number")
    roster: Optional[List[server.PlayerMetadata]] = Field(default_factory=list, description="Party roster")
    subject: Optional[str] = Field(default="", description="Subject for lecture")
    topic: Optional[str] = Field(default="", description="Topic for lecture")




class ReprocessCampaignRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transcript_text: str = Field(..., description="Speech-to-text transcript")
    campaign_name: Optional[str] = Field(default=None, description="Campaign name")
    session_number: Optional[int] = Field(default=None, description="Session number")
    roster: Optional[List[server.PlayerMetadata]] = Field(default_factory=list, description="Party roster")
    target_language: str = Field(default="es", description="Target language ('es' or 'en')")
    recording_mode: str = Field(default="roleplay", description="'roleplay' or 'class'")
    workspace: Optional[str] = Field(default="dnd", description="'dnd' or 'work_and_study'")
    subject: Optional[str] = Field(default="", description="Subject for lecture")
    topic: Optional[str] = Field(default="", description="Topic for lecture")
    is_youtube: Optional[bool] = Field(default=False, description="Whether this session was ingested from YouTube")


# ---------------------------------------------------------------------------
# Endpoints: Audio Local Recordings, YouTube & Local File Transcription
# ---------------------------------------------------------------------------
@router.get("/api/audio/local-recordings")
async def list_local_recordings():
    """List audio recordings available in data/input directory and campaign recordings folders."""
    input_dir = server.get_data_input_dir()
    search_dirs = [input_dir]
    camp_dir = server.get_data_campaigns_dir()
    if camp_dir.is_dir():
        for c in camp_dir.iterdir():
            if c.is_dir() and (c / "recordings").is_dir():
                search_dirs.append(c / "recordings")

    files = []
    seen_stems = set()
    for s_dir in search_dirs:
        for ext in ("*.wav", "*.mp3", "*.m4a", "*.webm", "*.ogg", "*.flac"):
            for f in s_dir.glob(ext):
                try:
                    if f.name.endswith(".norm_tmp.wav"):
                        continue
                    stat = f.stat()
                    if stat.st_size > 100:  # Skip empty or placeholder files
                        stem = f.stem
                        if stem in seen_stems:
                            continue
                        seen_stems.add(stem)
                        # Check timeline existence
                        has_timeline = (
                            f.with_suffix(".timeline.json").is_file()
                            or (input_dir / f"{stem}.timeline.json").is_file()
                        )
                        files.append({
                            "filename": f.name,
                            "path": str(f.resolve()),
                            "size_mb": round(stat.st_size / (1024 * 1024), 2),
                            "created_at": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M"),
                            "timestamp": stat.st_mtime,
                            "has_timeline": has_timeline,
                            "folder": f.parent.name,
                        })
                except Exception:
                    pass
    files.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"files": files}


@router.post("/api/transcribe/youtube", response_model=TranscribeResponse)
@router.post("/api/process-youtube", response_model=TranscribeResponse)
async def transcribe_youtube(payload: YouTubeTranscribeRequest, request: Request = None):
    """Download audio from YouTube and transcribe it using Groq Whisper or faster-whisper."""
    groq_key, gemini_key = server.extract_client_api_keys(request)
    server.validate_api_keys_or_raise(request, groq_key, gemini_key, require_gemini=True)

    task_id = payload.task_id
    url = payload.url.strip()
    model_size = payload.model_size or "base"
    engine = payload.engine or "groq"
    start_time = time.time()

    def yt_progress(pct: int, msg: str):
        server.update_task_progress(task_id, pct, "Descargando audio de YouTube...", msg, stage="audio")

    try:
        audio_file_path = await run_in_threadpool(
            server.download_youtube_audio,
            url,
            str(server.get_data_input_dir()),
            on_progress=yt_progress if task_id else None,
        )
    except ValueError as exc:
        server.update_task_progress(task_id, 0, f"Error URL YouTube: {exc}", stage="error")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        server.update_task_progress(task_id, 0, f"Error descargando YouTube: {exc}", stage="error")
        raise HTTPException(status_code=500, detail=f"Error descargando audio de YouTube: {exc}") from exc

    server.update_task_progress(task_id, 25.0, "Descarga completada. Iniciando transcripción...", "Iniciando motor de audio...", stage="transcribing")

    def progress_cb(pct: int, msg: str):
        server.update_task_progress(task_id, pct, msg, stage="transcribing")

    roster_dicts = [p.model_dump() for p in payload.roster] if payload.roster else []
    user_char_name = None
    for p in roster_dicts:
        if p.get("is_user_character"):
            user_char_name = (p.get("character_name") or "").strip()
            break

    try:
        result = await run_in_threadpool(
            server.transcribe_audio_pipeline,
            audio_path=audio_file_path,
            engine=engine,
            model_size=model_size,
            language=getattr(payload, "audio_language", None),
            on_progress=progress_cb,
            source="youtube",
            user_char_name=user_char_name,
            roster=roster_dicts,
            groq_api_key=groq_key,
            campaign_name=getattr(payload, "campaign_name", None),
            recording_mode=payload.recording_mode,
            subject=payload.subject,
            topic=payload.topic,
            task_id=task_id,
        )
    except Exception as exc:
        human_err = server.format_human_error(exc)
        server.set_task_error(task_id, human_err)
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
    detected_pcs = None
    chronicle_md = None

    is_work_study = payload.recording_mode == "class" or payload.workspace == "work_and_study"
    is_academic = is_work_study
    subj = (payload.subject or "").strip() or "Materia Universitaria"
    top = (payload.topic or "").strip() or "Tema de Clase"

    if is_academic:
        server.update_task_progress(task_id, 72.0, "Analizando clase universitaria con Gemini...", "Sintetizando conceptos teóricos y fórmulas...", stage="analyzing")
        subj = (payload.subject or "").strip() or "Materia Universitaria"
        top = (payload.topic or "").strip() or "Tema de Clase"
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        now_formatted = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        try:
            summarizer = server.GeminiTTRPGSummarizer(api_key=gemini_key)
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
            clean_top = re.sub(r'[\\/*?:"<>|]', "", top.strip()) or "Tema"
            safe_top = re.sub(r"\s+", "_", clean_top)

            docx_filename = f"apuntes_youtube_{safe_subj}_{now_str}.docx"
            md_filename = f"apuntes_youtube_{safe_subj}_{now_str}.md"
            txt_filename = f"apuntes_youtube_{safe_subj}_{now_str}_transcripcion.txt"
            docx_out_path = server.get_data_output_dir() / docx_filename
            md_out_path = server.get_data_output_dir() / md_filename
            txt_out_path = server.get_data_output_dir() / txt_filename

            # Store only .md and .txt on disk; docx is generated dynamically on demand
            md_out_path.write_text(chronicle_md, encoding="utf-8")
            txt_out_path.write_text(transcript_text, encoding="utf-8")
            (server.get_data_output_dir() / f"{safe_top}_transcripcion.txt").write_text(transcript_text, encoding="utf-8")
            file_path_str = str(docx_out_path.resolve())
        except Exception as exc:
            chronicle_md = f"# ⚠️ Error generando guía académica con Gemini:\n\n> {exc}\n\n**Texto:**\n\n{transcript_text}"
            print(f"[transcribe_youtube] Warning: academic notes export failed: {exc}")

        server.update_task_progress(task_id, 94.0, "Generando documentos (.docx y .md)...", "Creando archivos de apuntes...", stage="analyzing")
        server.update_task_progress(task_id, 100.0, "¡Completado!", "Guía de estudio generada exitosamente.", stage="done")
    else:
        server.update_task_progress(task_id, 72.0, "Generando crónica / apuntes explicativos con IA...", "Extrayendo hechos e inventario...", stage="analyzing")

        campaign_name = (payload.campaign_name or payload.campaign_id or "").strip()
        if campaign_name:
            try:
                server.update_task_progress(task_id, 80.0, "Actualizando Quest Tracker y Directorio Universal de NPCs...", stage="analyzing")
                camp_res = await run_in_threadpool(
                    server.process_session_for_campaign,
                    campaign_name=campaign_name,
                    transcript_text=transcript_text,
                    roster_dicts=roster_dicts,
                    session_number=payload.session_number,
                    target_language=payload.target_language,
                    is_youtube=True,
                    gemini_api_key=gemini_key,
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
            out_docx_path = server.get_data_output_dir() / f"transcripcion_youtube_{safe_title}_{timestamp}.docx"
            formatted_md = f"# Transcripción de YouTube: {safe_title}\n\n## Texto Completo\n{transcript_text}\n"
            txt_filename = f"transcripcion_youtube_{safe_title}_{timestamp}.txt"
            (server.get_data_output_dir() / txt_filename).write_text(transcript_text, encoding="utf-8")

            try:
                exported_docx = await run_in_threadpool(
                    server.export_chronicle_docx,
                    chronicle_md=formatted_md,
                    roster=roster_dicts or None,
                    session_date=datetime.datetime.now().strftime("%d/%m/%Y"),
                    output_path=str(out_docx_path),
                )
                file_path_str = str(Path(exported_docx).resolve())
                docx_filename = Path(exported_docx).name
            except Exception as exc:
                print(f"[transcribe_youtube] Warning: docx export failed: {exc}")
                out_md_path = server.get_data_output_dir() / f"transcripcion_youtube_{safe_title}_{timestamp}.md"
                out_md_path.write_text(formatted_md, encoding="utf-8")
                file_path_str = str(out_md_path.resolve())
                docx_filename = None
                md_filename = Path(out_md_path).name

        server.update_task_progress(task_id, 94.0, "Generando documentos (.docx y .md)...", "Creando archivos del Grimorio (.docx y .md)...", stage="analyzing")
        server.update_task_progress(task_id, 100.0, "¡Completado!", "Sesión procesada exitosamente.", stage="done")

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

    # Background Drive Sync
    try:
        files_to_sync = []
        if is_work_study:
            hist_path = server.update_consolidated_academic_notes_file()
            if hist_path and hist_path.is_file():
                files_to_sync.append(hist_path)
            if md_filename:
                m_p = server.get_data_output_dir() / md_filename
                if m_p.is_file():
                    files_to_sync.append(m_p)
        else:
            c_name = (payload.campaign_name or payload.campaign_id or "").strip()
            if c_name:
                c_path = server.get_campaign_path(c_name)
                if c_path and c_path.is_file():
                    files_to_sync.append(c_path)
            if md_filename:
                m_p = server.get_data_output_dir() / md_filename
                if m_p.is_file():
                    files_to_sync.append(m_p)
            if file_path_str and Path(file_path_str).is_file():
                files_to_sync.append(Path(file_path_str))
        if files_to_sync:
            server.trigger_drive_sync_background(files_to_sync)
    except Exception as exc:
        print(f"[transcribe_youtube] Warning triggering drive sync: {exc}")
    action_items = None
    key_points = None
    if is_work_study:
        action_items, key_points = server.extract_academic_sections(chronicle_md or "")

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
        updated_quests=updated_quests or [],
        updated_npcs=updated_npcs or [],
        detected_npc_names=detected_npc_names or [],
        detected_party=detected_party or [],
        detected_pcs=detected_pcs or [],
        chronicle=chronicle_md,
        recording_mode="class" if is_work_study else "roleplay",
        subject=subj if is_work_study else None,
        topic=top if is_work_study else None,
        target_language=payload.target_language,
        action_items=action_items,
        key_points=key_points,
    )


@router.post("/api/upload", response_model=TranscribeResponse)
@router.post("/api/transcribe", response_model=TranscribeResponse)
@router.post("/api/transcribe/file", response_model=TranscribeResponse)
async def transcribe_file(
    file: Optional[UploadFile] = File(default=None),
    existing_filename: Optional[str] = Form(default=None),
    timeline_file: Optional[UploadFile] = File(default=None),
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
    audio_language: Optional[str] = Form(default=None),
    request: Request = None,
):
    """Accept an uploaded audio file or existing local recording and transcribe it using Groq Whisper or faster-whisper."""
    groq_key, gemini_key = server.extract_client_api_keys(request)
    server.validate_api_keys_or_raise(request, groq_key, gemini_key, require_gemini=True)

    start_time = time.time()
    clean_filename = ""
    save_dest = None

    if existing_filename and existing_filename.strip():
        clean_filename = Path(existing_filename.strip()).name
        # Look in data/input and campaign recordings folders
        cand_dest = server.get_data_input_dir() / clean_filename
        if not cand_dest.is_file():
            camp_dir = server.get_data_campaigns_dir()
            for c in camp_dir.iterdir():
                if c.is_dir() and (c / "recordings" / clean_filename).is_file():
                    cand_dest = c / "recordings" / clean_filename
                    break
        save_dest = cand_dest
        if not save_dest.is_file():
            raise HTTPException(status_code=404, detail=f"Archivo no encontrado: {clean_filename}")
        server.update_task_progress(task_id, 20.0, f"Cargando archivo local: {clean_filename}...", "Iniciando motor de audio...", stage="segmenting")
    elif file and getattr(file, "filename", None):
        clean_filename = Path(file.filename).name

        # Safeguard: If user uploads a JSON timeline file as the primary file
        if clean_filename.lower().endswith(".json"):
            base_stem = clean_filename[:-5]
            if base_stem.lower().endswith(".timeline"):
                base_stem = base_stem[:-9]
            
            # Save the JSON as timeline file in data/input
            timeline_dest = server.get_data_input_dir() / f"{base_stem}.timeline.json"
            try:
                with open(timeline_dest, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
            except Exception as j_err:
                print(f"[transcribe_file] Notice saving json timeline: {j_err}")
            finally:
                await file.close()

            # Search if audio with matching stem exists in data/input or campaign recordings
            matched_audio = None
            for ext in (".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"):
                cand = server.get_data_input_dir() / f"{base_stem}{ext}"
                if cand.is_file():
                    matched_audio = cand
                    break
            if not matched_audio and campaign_name:
                try:
                    from src.storage.campaign_manager import CampaignManager
                    safe_c = CampaignManager.sanitize_name(campaign_name)
                    camp_rec = server.project_root / "data" / "campaigns" / safe_c / "recordings"
                    for ext in (".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"):
                        cand = camp_rec / f"{base_stem}{ext}"
                        if cand.is_file():
                            matched_audio = cand
                            break
                except Exception:
                    pass

            if matched_audio and matched_audio.is_file():
                save_dest = matched_audio
                clean_filename = matched_audio.name
                server.update_task_progress(task_id, 20.0, f"Timeline recibido. Usando audio asociado: {clean_filename}...", "Iniciando motor de audio...", stage="segmenting")
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Has seleccionado un archivo de timeline ('{clean_filename}'), pero falta el archivo de audio (.wav o .mp3). Por favor selecciona el archivo de audio correspondiente."
                )
        else:
            server.update_task_progress(task_id, 20.0, "Segmentando archivo en el servidor...", "Guardando en almacenamiento local...", stage="segmenting")
            save_dest = server.get_data_input_dir() / clean_filename
            try:
                with open(save_dest, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
            except Exception as exc:
                err_type, human_err, stage = server.diagnose_exception(exc)
                import traceback
                server.set_task_error(task_id, human_err, error_type=err_type, stage=stage, details=traceback.format_exc())
                raise HTTPException(status_code=500, detail=human_err) from exc
            finally:
                await file.close()
    else:
        raise HTTPException(status_code=400, detail="Por favor selecciona un archivo o grabación local para procesar.")

    # Save optional timeline file (.timeline.json) if uploaded
    if timeline_file and getattr(timeline_file, "filename", None):
        target_t_name = f"{save_dest.stem}.timeline.json" if save_dest else Path(timeline_file.filename).name
        timeline_dest = server.get_data_input_dir() / target_t_name
        try:
            with open(timeline_dest, "wb") as t_buf:
                shutil.copyfileobj(timeline_file.file, t_buf)
            print(f"[transcribe_file] Timeline file uploaded and saved to: {timeline_dest}")
        except Exception as t_exc:
            print(f"[transcribe_file] Warning saving timeline_file: {t_exc}")
        finally:
            await timeline_file.close()

    # Mirror audio and timeline to campaign recordings if campaign_name is present
    if campaign_name and save_dest and save_dest.is_file():
        try:
            from src.storage.campaign_manager import CampaignManager
            safe_c = CampaignManager.sanitize_name(campaign_name)
            camp_rec = server.project_root / "data" / "campaigns" / safe_c / "recordings"
            camp_rec.mkdir(parents=True, exist_ok=True)
            camp_audio = camp_rec / save_dest.name
            if not camp_audio.exists():
                shutil.copyfile(save_dest, camp_audio)
            t_cand = server.get_data_input_dir() / f"{save_dest.stem}.timeline.json"
            if t_cand.is_file():
                shutil.copyfile(t_cand, camp_rec / t_cand.name)
        except Exception as mirror_err:
            print(f"[transcribe_file] Notice mirroring audio to campaign: {mirror_err}")

    server.update_task_progress(task_id, 20.0, "Segmentando archivo en el servidor...", "Iniciando motor de audio...", stage="segmenting")

    import json
    roster_dicts = []
    user_char_name = None
    if roster_json:
        try:
            roster_dicts = json.loads(roster_json)
            if isinstance(roster_dicts, list):
                for p in roster_dicts:
                    if isinstance(p, dict) and (p.get("is_user_character") or p.get("is_user")):
                        user_char_name = (p.get("character_name") or "").strip()
                        break
        except Exception:
            roster_dicts = []

    if not roster_dicts and campaign_name:
        try:
            from src.storage.campaign_manager import CampaignManager
            c_data = CampaignManager().load_campaign(campaign_name)
            roster_dicts = c_data.get("roster", []) or []
            for p in roster_dicts:
                if isinstance(p, dict) and (p.get("is_user_character") or p.get("is_user")):
                    user_char_name = (p.get("character_name") or "").strip()
                    break
        except Exception as camp_roster_err:
            print(f"[transcribe_file] Notice loading campaign roster: {camp_roster_err}")

    def progress_cb(pct: float, msg: str):
        server.update_task_progress(task_id, pct, msg, stage="transcribing")

    try:
        result = await run_in_threadpool(
            server.transcribe_audio_pipeline,
            audio_path=str(save_dest),
            engine=engine,
            model_size=model_size,
            language=audio_language,
            on_progress=progress_cb,
            source="local",
            user_char_name=user_char_name,
            roster=roster_dicts,
            groq_api_key=groq_key,
            campaign_name=campaign_name,
            recording_mode=recording_mode,
            subject=subject,
            topic=topic,
            task_id=task_id,
        )
    except Exception as exc:
        err_type, human_err, stage = server.diagnose_exception(exc)
        import traceback
        server.set_task_error(task_id, human_err, error_type=err_type, stage=stage, details=traceback.format_exc())
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
        server.update_task_progress(task_id, 72.0, "Generando crónica / apuntes explicativos con IA...", "Sintetizando conceptos teóricos y fórmulas...", stage="analyzing")
        subj = (subject or "").strip() or "Materia Universitaria"
        top = (topic or "").strip() or "Tema de Clase"
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        now_formatted = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        try:
            summarizer = server.GeminiTTRPGSummarizer(api_key=gemini_key)
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

        server.update_task_progress(task_id, 94.0, "Generando documentos (.docx y .md)...", "Creando archivos de apuntes...", stage="analyzing")
        clean_subj = re.sub(r'[\\/*?:"<>|]', "", subj.strip()) or "Materia"
        safe_subj = re.sub(r"\s+", "_", clean_subj)
        docx_filename = f"apuntes_file_{safe_subj}_{now_str}.docx"
        md_filename = f"apuntes_file_{safe_subj}_{now_str}.md"
        txt_filename = f"apuntes_file_{safe_subj}_{now_str}_transcripcion.txt"
        docx_out_path = server.get_data_output_dir() / docx_filename
        md_out_path = server.get_data_output_dir() / md_filename
        txt_out_path = server.get_data_output_dir() / txt_filename
        try:
            # Store only .md and .txt in disk; docx is generated dynamically on demand
            md_out_path.write_text(chronicle_md, encoding="utf-8")
            txt_out_path.write_text(transcript_text, encoding="utf-8")
            (server.get_data_output_dir() / f"{safe_subj}_transcripcion.txt").write_text(transcript_text, encoding="utf-8")
            file_path_str = str(docx_out_path.resolve())
        except Exception as exc:
            print(f"[transcribe_file] Warning: academic notes export failed: {exc}")

        # Background Drive Sync for academic notes
        try:
            files_to_sync = []
            hist_path = server.update_consolidated_academic_notes_file()
            if hist_path and hist_path.is_file():
                files_to_sync.append(hist_path)
            if md_out_path and md_out_path.is_file():
                files_to_sync.append(md_out_path)
            if files_to_sync:
                server.trigger_drive_sync_background(files_to_sync)
        except Exception as exc:
            print(f"[transcribe_file] Warning triggering drive sync: {exc}")

        server.update_task_progress(task_id, 100.0, "¡Completado!", "Guía de estudio generada exitosamente.", stage="done")
        action_items, key_points = server.extract_academic_sections(chronicle_md or "")
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
            action_items=action_items,
            key_points=key_points,
        )

    server.update_task_progress(task_id, 72.0, "Generando crónica / apuntes explicativos con IA...", "Extrayendo hechos e inventario...", stage="analyzing")

    detected_pcs = None
    if campaign_name:
        try:
            server.update_task_progress(task_id, 80.0, "Actualizando Quest Tracker y Directorio Universal de NPCs...", stage="analyzing")
            camp_res = await run_in_threadpool(
                server.process_session_for_campaign,
                campaign_name=campaign_name,
                transcript_text=transcript_text,
                roster_dicts=roster_dicts,
                session_number=session_number,
                target_language=target_language,
                gemini_api_key=gemini_key,
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
            chronicle_md = f"# ⚠️ Error generando crónica con Gemini:\n\n> {exc}\n\n**Texto de Transcripción:**\n\n{transcript_text}"
    else:
        try:
            server.update_task_progress(task_id, 80.0, "Generando crónica narrativa con Gemini...", stage="analyzing")
            summarizer = server.GeminiTTRPGSummarizer(api_key=gemini_key)
            chronicle_md = await run_in_threadpool(
                summarizer.generate_chronicle,
                transcript_text=transcript_text,
                roster=roster_dicts or [],
                target_language=target_language,
                session_number=session_number or 1,
            )
        except Exception as exc:
            print(f"[transcribe_file] Warning: standalone chronicle generation failed: {exc}")
            chronicle_md = f"# ⚠️ Error generando crónica con Gemini:\n\n> {exc}\n\n**Texto de Transcripción:**\n\n{transcript_text}"

    if not file_path_str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = Path(clean_filename).stem[:40]
        out_docx_path = server.get_data_output_dir() / f"cronica_{safe_title}_{timestamp}.docx"
        formatted_md = chronicle_md or f"# Transcripción de Audio: {safe_title}\n\n## Texto Completo\n{transcript_text}\n"
        md_filename = f"cronica_{safe_title}_{timestamp}.md"
        txt_filename = f"transcripcion_{safe_title}_{timestamp}.txt"
        (server.get_data_output_dir() / md_filename).write_text(formatted_md, encoding="utf-8")
        (server.get_data_output_dir() / txt_filename).write_text(transcript_text, encoding="utf-8")

        try:
            exported_docx = await run_in_threadpool(
                server.export_chronicle_docx,
                chronicle_md=formatted_md,
                roster=roster_dicts or None,
                session_date=datetime.datetime.now().strftime("%d/%m/%Y"),
                output_path=str(out_docx_path),
            )
            file_path_str = str(Path(exported_docx).resolve())
            docx_filename = Path(exported_docx).name
        except Exception as exc:
            print(f"[transcribe_file] Warning: docx export failed: {exc}")
            file_path_str = str((server.get_data_output_dir() / md_filename).resolve())
            docx_filename = None

    server.update_task_progress(task_id, 100.0, "¡Completado!", "Sesión procesada exitosamente.", stage="done")

    # Mirror exports to dedicated data/campaigns/<campaign>/exports/
    if campaign_name:
        try:
            safe_c = re.sub(r'[\\/*?:"<>|]', "", campaign_name.strip())
            safe_c = re.sub(r"\s+", "_", safe_c).lower() or "campana_principal"
            camp_exports = server.project_root / "data" / "campaigns" / safe_c / "exports"
            camp_exports.mkdir(parents=True, exist_ok=True)
            if md_filename and (server.get_data_output_dir() / md_filename).is_file():
                shutil.copyfile(server.get_data_output_dir() / md_filename, camp_exports / md_filename)
            if docx_filename and (server.get_data_output_dir() / docx_filename).is_file():
                shutil.copyfile(server.get_data_output_dir() / docx_filename, camp_exports / docx_filename)
            elif file_path_str and Path(file_path_str).is_file():
                shutil.copyfile(Path(file_path_str), camp_exports / Path(file_path_str).name)
            if txt_filename and (server.get_data_output_dir() / txt_filename).is_file():
                shutil.copyfile(server.get_data_output_dir() / txt_filename, camp_exports / txt_filename)
        except Exception as camp_exp_err:
            print(f"[transcribe_file] Notice mirroring campaign exports: {camp_exp_err}")

    # Background Drive Sync for campaign files and session documents
    try:
        files_to_sync = []
        if campaign_name:
            c_path = server.get_campaign_path(campaign_name)
            if c_path and c_path.is_file():
                files_to_sync.append(c_path)
        if md_filename:
            m_p = server.get_data_output_dir() / md_filename
            if m_p.is_file():
                files_to_sync.append(m_p)
        if file_path_str and Path(file_path_str).is_file():
            files_to_sync.append(Path(file_path_str))
        if files_to_sync:
            server.trigger_drive_sync_background(files_to_sync)
    except Exception as exc:
        print(f"[transcribe_file] Warning triggering drive sync: {exc}")

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


@router.post("/api/sessions/upload-with-telemetry", response_model=TranscribeResponse)
async def upload_session_with_telemetry(
    audio_file: Optional[UploadFile] = File(default=None),
    file: Optional[UploadFile] = File(default=None),
    events_file: Optional[UploadFile] = File(default=None),
    discord_events: Optional[str] = Form(default=None),
    campaign_name: Optional[str] = Form(default=None),
    session_number: Optional[int] = Form(default=None),
    roster_json: Optional[str] = Form(default=None),
    task_id: Optional[str] = Form(default=None),
    recording_mode: str = Form(default="roleplay"),
    target_language: str = Form(default="es"),
    engine: str = Form(default="groq"),
    model_size: str = Form(default="base"),
    gemini_api_key: Optional[str] = Form(default=None),
    groq_api_key: Optional[str] = Form(default=None),
    subject: Optional[str] = Form(default=None),
    topic: Optional[str] = Form(default=None),
    audio_language: Optional[str] = Form(default=None),
    request: Request = None,
):
    """
    Accept stereo audio (.wav/.mp3) + Discord Voice Activity telemetry (events_file or discord_events)
    uploaded from the local client bridge.
    Transcribes audio with Groq or local faster-whisper, cross-references speaking timestamps with discord_user_id,
    maps to Campaign Roster characters, and delivers the 100% pre-tagged transcript to Gemini for chronicle
    and Living Campaign Journal generation.
    """
    groq_hdr, gemini_hdr = server.extract_client_api_keys(request)
    groq_key = (groq_api_key or "").strip() or groq_hdr
    gemini_key = (gemini_api_key or "").strip() or gemini_hdr
    server.validate_api_keys_or_raise(request, groq_key, gemini_key, require_gemini=True)

    actual_audio = audio_file or file
    if not actual_audio or not actual_audio.filename:
        raise HTTPException(status_code=400, detail="No se proporcionó ningún archivo de audio (audio_file).")

    server.update_task_progress(task_id, 10.0, "Recibiendo audio y telemetría de Discord...", "Guardando archivos temporales...", stage="segmenting")
    clean_audio_name = Path(actual_audio.filename).name
    save_dest = server.get_data_input_dir() / clean_audio_name
    start_time = time.time()

    try:
        with open(save_dest, "wb") as buffer:
            shutil.copyfileobj(actual_audio.file, buffer)
    except Exception as exc:
        err_type, human_err, stage = server.diagnose_exception(exc)
        server.set_task_error(task_id, human_err, error_type=err_type, stage=stage)
        raise HTTPException(status_code=500, detail=human_err) from exc
    finally:
        await actual_audio.close()

    # Parse Discord Telemetry
    telemetry_raw: Any = {}
    if events_file and events_file.filename:
        try:
            content = await events_file.read()
            telemetry_raw = json.loads(content.decode("utf-8"))
        except Exception as exc:
            print(f"[upload-with-telemetry] Warning: could not parse events_file: {exc}")
        finally:
            await events_file.close()
    elif discord_events:
        try:
            telemetry_raw = json.loads(discord_events)
        except Exception as exc:
            print(f"[upload-with-telemetry] Warning: could not parse discord_events form: {exc}")

    speaking_log: List[Dict[str, Any]] = []
    participants: List[Dict[str, Any]] = []
    if isinstance(telemetry_raw, list):
        speaking_log = telemetry_raw
    elif isinstance(telemetry_raw, dict):
        speaking_log = (
            telemetry_raw.get("events")
            or telemetry_raw.get("speaking_log")
            or telemetry_raw.get("telemetry", {}).get("events")
            or []
        )
        parts_val = (
            telemetry_raw.get("participants")
            or telemetry_raw.get("telemetry", {}).get("participants")
            or []
        )
        if isinstance(parts_val, dict):
            participants = list(parts_val.values())
        elif isinstance(parts_val, list):
            participants = parts_val

    # Parse roster and link with campaign context
    roster_dicts: List[Dict[str, Any]] = []
    user_char_name = None
    if roster_json:
        try:
            parsed = json.loads(roster_json)
            if isinstance(parsed, list):
                roster_dicts = parsed
        except Exception as exc:
            print(f"[upload-with-telemetry] Warning: could not parse roster_json: {exc}")

    camp_mgr = server.CampaignManager()
    active_camp_state = None
    if campaign_name:
        try:
            active_ctx = camp_mgr.get_active_context(campaign_name)
            active_camp_state = camp_mgr.load_campaign(campaign_name)
            if not roster_dicts:
                roster_dicts = active_ctx.get("roster", []) or []
        except Exception as exc:
            print(f"[upload-with-telemetry] Warning loading campaign context: {exc}")

    # Auto-match Discord participant user_ids with Roster entries if not mapped yet
    roster_updated = False
    if participants and roster_dicts:
        for part in participants:
            uid = str(part.get("user_id") or "").strip()
            if not uid:
                continue
            u_name = str(part.get("username") or "").strip().lower()
            d_name = str(part.get("display_name") or "").strip().lower()

            for r_entry in roster_dicts:
                curr_uid = str(r_entry.get("discord_user_id") or r_entry.get("discord_id") or "").strip()
                if not curr_uid:
                    p_name = str(r_entry.get("player_name") or r_entry.get("jugador") or "").strip().lower()
                    c_name = str(r_entry.get("character_name") or r_entry.get("personaje") or "").strip().lower()
                    if (p_name and (p_name == u_name or p_name == d_name or p_name in d_name or d_name in p_name)) or \
                       (c_name and c_name not in ("-", "(dm)", "dm") and (c_name == u_name or c_name == d_name)):
                        r_entry["discord_user_id"] = uid
                        roster_updated = True
                        print(f"[upload-with-telemetry] Auto-mapped participant '{u_name or d_name}' -> roster '{p_name or c_name}' (ID: {uid})")

    if roster_updated and campaign_name and active_camp_state:
        try:
            active_camp_state["roster"] = roster_dicts
            camp_mgr.save_campaign(active_camp_state)
        except Exception as exc:
            print(f"[upload-with-telemetry] Warning persisting auto-mapped roster: {exc}")

    for p in roster_dicts:
        if isinstance(p, dict) and p.get("is_user_character"):
            user_char_name = (p.get("character_name") or "").strip()
            break

    server.update_task_progress(task_id, 25.0, "Segmentando audio y ejecutando transcripción...", "Iniciando motor de audio...", stage="segmenting")

    def progress_cb(pct: float, msg: str):
        server.update_task_progress(task_id, pct, msg, stage="transcribing")

    try:
        result = await run_in_threadpool(
            server.transcribe_audio_pipeline,
            audio_path=str(save_dest),
            engine=engine,
            model_size=model_size,
            language=audio_language,
            on_progress=progress_cb,
            source="live" if speaking_log else "local",
            user_char_name=user_char_name,
            speaking_log=speaking_log or None,
            roster=roster_dicts or None,
            groq_api_key=groq_key,
            campaign_name=campaign_name,
            recording_mode=recording_mode,
            subject=subject,
            topic=topic,
            task_id=task_id,
        )
    except Exception as exc:
        err_type, human_err, stage = server.diagnose_exception(exc)
        import traceback
        server.set_task_error(task_id, human_err, error_type=err_type, stage=stage, details=traceback.format_exc())
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
    detected_pcs = None
    chronicle_md = None
    session_title = None

    if recording_mode == "class":
        server.update_task_progress(task_id, 72.0, "Generando apuntes académicos con IA...", "Sintetizando conceptos teóricos...", stage="analyzing")
        subj = (subject or "").strip() or "Materia Universitaria"
        top = (topic or "").strip() or "Tema de Clase"
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        now_formatted = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        try:
            summarizer = server.GeminiTTRPGSummarizer(api_key=gemini_key)
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

        server.update_task_progress(task_id, 94.0, "Generando documentos (.docx y .md)...", "Creando archivos de apuntes...", stage="analyzing")
        clean_subj = re.sub(r'[\\/*?:"<>|]', "", subj.strip()) or "Materia"
        safe_subj = re.sub(r"\s+", "_", clean_subj)
        docx_filename = f"apuntes_telemetria_{safe_subj}_{now_str}.docx"
        md_filename = f"apuntes_telemetria_{safe_subj}_{now_str}.md"
        txt_filename = f"apuntes_telemetria_{safe_subj}_{now_str}_transcripcion.txt"
        docx_out_path = server.get_data_output_dir() / docx_filename
        md_out_path = server.get_data_output_dir() / md_filename
        txt_out_path = server.get_data_output_dir() / txt_filename
        try:
            md_out_path.write_text(chronicle_md, encoding="utf-8")
            txt_out_path.write_text(transcript_text, encoding="utf-8")
            (server.get_data_output_dir() / f"{safe_subj}_transcripcion.txt").write_text(transcript_text, encoding="utf-8")
            file_path_str = str(docx_out_path.resolve())
        except Exception as exc:
            print(f"[upload-with-telemetry] Warning exporting academic notes: {exc}")

        try:
            files_to_sync = []
            hist_path = server.update_consolidated_academic_notes_file()
            if hist_path and hist_path.is_file():
                files_to_sync.append(hist_path)
            if md_out_path and md_out_path.is_file():
                files_to_sync.append(md_out_path)
            if files_to_sync:
                server.trigger_drive_sync_background(files_to_sync)
        except Exception as exc:
            print(f"[upload-with-telemetry] Warning triggering drive sync: {exc}")

        server.update_task_progress(task_id, 100.0, "¡Completado!", "Guía de estudio generada exitosamente.", stage="done")
        action_items, key_points = server.extract_academic_sections(chronicle_md or "")
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
            action_items=action_items,
            key_points=key_points,
            telemetry_events_count=len(speaking_log),
        )

    # Roleplay Mode: Living Campaign Journal or single session chronicle
    server.update_task_progress(task_id, 72.0, "Generando crónica con IA y atribución exacta...", "Extrayendo hechos e inventario...", stage="analyzing")

    if campaign_name:
        try:
            server.update_task_progress(task_id, 80.0, "Actualizando Quest Tracker y Directorio Universal de NPCs...", stage="analyzing")
            camp_res = await run_in_threadpool(
                server.process_session_for_campaign,
                campaign_name=campaign_name,
                transcript_text=transcript_text,
                roster_dicts=roster_dicts,
                session_number=session_number,
                target_language=target_language,
                gemini_api_key=gemini_key,
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
            if session_chapter and isinstance(session_chapter, dict):
                session_title = session_chapter.get("session_title") or session_chapter.get("title")
        except Exception as exc:
            print(f"[upload-with-telemetry] Warning: campaign session processing failed: {exc}")

    if not file_path_str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = Path(clean_audio_name).stem[:40]
        out_docx_path = server.get_data_output_dir() / f"transcripcion_{safe_title}_{timestamp}.docx"
        formatted_md = f"# Transcripción de Audio: {safe_title}\n\n## Texto Completo (Diarizado)\n{transcript_text}\n"
        txt_filename = f"transcripcion_{safe_title}_{timestamp}.txt"
        (server.get_data_output_dir() / txt_filename).write_text(transcript_text, encoding="utf-8")

        try:
            exported_docx = await run_in_threadpool(
                server.export_chronicle_docx,
                chronicle_md=formatted_md,
                roster=roster_dicts or None,
                session_date=datetime.datetime.now().strftime("%d/%m/%Y"),
                output_path=str(out_docx_path),
            )
            file_path_str = str(Path(exported_docx).resolve())
            docx_filename = Path(exported_docx).name
        except Exception as exc:
            print(f"[upload-with-telemetry] Warning: docx export failed: {exc}")
            out_md_path = server.get_data_output_dir() / f"transcripcion_{safe_title}_{timestamp}.md"
            out_md_path.write_text(formatted_md, encoding="utf-8")
            file_path_str = str(out_md_path.resolve())
            docx_filename = None
            md_filename = Path(out_md_path).name

    server.update_task_progress(task_id, 100.0, "¡Completado!", "Sesión procesada exitosamente con telemetría de Discord.", stage="done")

    # Background Drive Sync
    try:
        files_to_sync = []
        if campaign_name:
            c_path = server.get_campaign_path(campaign_name)
            if c_path and c_path.is_file():
                files_to_sync.append(c_path)
        if md_filename:
            m_p = server.get_data_output_dir() / md_filename
            if m_p.is_file():
                files_to_sync.append(m_p)
        if file_path_str and Path(file_path_str).is_file():
            files_to_sync.append(Path(file_path_str))
        if files_to_sync:
            server.trigger_drive_sync_background(files_to_sync)
    except Exception as exc:
        print(f"[upload-with-telemetry] Warning triggering drive sync: {exc}")

    actual_sess_num = session_number
    if actual_sess_num is None and session_chapter and isinstance(session_chapter, dict):
        actual_sess_num = session_chapter.get("session_number")

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
        campaign_name=campaign_name,
        session_number=actual_sess_num,
        session_title=session_title or (f"Sesión {actual_sess_num}" if actual_sess_num else "Sesión D&D"),
        telemetry_events_count=len(speaking_log),
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


@router.post("/api/summarize/switch-language", response_model=TranscribeResponse)
async def switch_summary_language(payload: SwitchLanguageRequest, request: Request = None):
    """
    Re-generate the chronicle or academic notes in a new target language (ES/EN)
    using the cached transcript text, in ~5-10 seconds without re-downloading or re-transcribing audio.
    """
    _, gemini_key = server.extract_client_api_keys(request)
    server.validate_api_keys_or_raise(request, None, gemini_key, require_gemini=True)

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

    summarizer = server.GeminiTTRPGSummarizer(api_key=gemini_key)

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
        docx_out_path = server.get_data_output_dir() / docx_filename
        md_out_path = server.get_data_output_dir() / md_filename
        (server.get_data_output_dir() / txt_filename).write_text(transcript_text, encoding="utf-8")
        try:
            # Store only .md and .txt in disk; docx is generated dynamically on demand
            md_out_path.write_text(chronicle_md, encoding="utf-8")
            file_path_str = str(docx_out_path.resolve())
        except Exception as exc:
            print(f"[switch_language] Warning: docx export failed: {exc}")
    else:
        roster_dicts = [p.model_dump() for p in payload.roster] if payload.roster else []
        detected_pcs = None
        txt_filename = None
        session_num = payload.session_number
        if payload.campaign_name:
            manager = server.CampaignManager()
            active_ctx = manager.get_active_context(payload.campaign_name)
            session_num = payload.session_number or (active_ctx["last_session"] if active_ctx.get("last_session", 0) > 0 else 1)
            try:
                camp_res = await run_in_threadpool(
                    server.process_session_for_campaign,
                    campaign_name=payload.campaign_name,
                    transcript_text=transcript_text,
                    roster_dicts=roster_dicts,
                    session_number=session_num,
                    target_language=target_lang,
                    gemini_api_key=gemini_key,
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
            docx_out_path = server.get_data_output_dir() / docx_filename
            txt_filename = f"cronica_sesion_{target_lang}_{now_str}_transcripcion.txt"
            (server.get_data_output_dir() / txt_filename).write_text(transcript_text, encoding="utf-8")
            try:
                await run_in_threadpool(
                    server.export_chronicle_docx,
                    chronicle_md=chronicle_md,
                    roster=roster_dicts,
                    session_date=now_formatted,
                    output_path=str(docx_out_path),
                )
                file_path_str = str(docx_out_path.resolve())
            except Exception as exc:
                print(f"[switch_language] Warning: single docx export failed: {exc}")

    elapsed_time = round(time.time() - start_time, 2)
    action_items = None
    key_points = None
    if is_class_mode:
        action_items, key_points = server.extract_academic_sections(chronicle_md or "")

    # Background Drive Sync
    try:
        files_to_sync = []
        if is_class_mode:
            hist_path = server.update_consolidated_academic_notes_file()
            if hist_path and hist_path.is_file():
                files_to_sync.append(hist_path)
            if md_filename:
                m_p = server.get_data_output_dir() / md_filename
                if m_p.is_file():
                    files_to_sync.append(m_p)
        else:
            if payload.campaign_name:
                c_path = server.get_campaign_path(payload.campaign_name)
                if c_path and c_path.is_file():
                    files_to_sync.append(c_path)
            if md_filename:
                m_p = server.get_data_output_dir() / md_filename
                if m_p.is_file():
                    files_to_sync.append(m_p)
            if file_path_str and Path(file_path_str).is_file():
                files_to_sync.append(Path(file_path_str))
        if files_to_sync:
            server.trigger_drive_sync_background(files_to_sync)
    except Exception as exc:
        print(f"[switch_language] Warning triggering drive sync: {exc}")

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
        campaign_name=payload.campaign_name,
        session_number=session_num if payload.campaign_name else payload.session_number,
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
        action_items=action_items,
        key_points=key_points,
    )


@router.post("/api/campaign/reprocess", response_model=TranscribeResponse)
@router.post("/api/regenerate", response_model=TranscribeResponse)
async def reprocess_campaign(payload: ReprocessCampaignRequest, request: Request = None):
    """
    Re-run ONLY the Gemini summarizer step using the cached transcript in ~10-15s
    (does NOT invoke Whisper or YouTube).
    Returns updated TranscribeResponse with populated chronicle, campaign_state,
    updated_quests, updated_npcs, detected_npc_names.
    """
    _, gemini_key = server.extract_client_api_keys(request)
    server.validate_api_keys_or_raise(request, None, gemini_key, require_gemini=True)

    transcript_text = payload.transcript_text.strip()
    if not transcript_text:
        raise HTTPException(status_code=400, detail="El texto de transcripción está vacío.")

    target_lang = (payload.target_language or "es").lower().strip()
    is_class_mode = payload.recording_mode == "class" or payload.workspace == "work_and_study"
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

    summarizer = server.GeminiTTRPGSummarizer(api_key=gemini_key)

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
        docx_out_path = server.get_data_output_dir() / docx_filename
        md_out_path = server.get_data_output_dir() / md_filename
        (server.get_data_output_dir() / txt_filename).write_text(transcript_text, encoding="utf-8")
        try:
            # Store only .md and .txt in disk; docx is generated dynamically on demand
            md_out_path.write_text(chronicle_md, encoding="utf-8")
            file_path_str = str(docx_out_path.resolve())
        except Exception as exc:
            print(f"[reprocess_campaign] Warning: docx export failed: {exc}")
    else:
        campaign_name = (payload.campaign_name or "").strip()
        if not campaign_name:
            raise HTTPException(status_code=400, detail="Debes especificar una campaña para regenerar.")
        manager = server.CampaignManager()
        active_ctx = manager.get_active_context(campaign_name)
        session_num = payload.session_number or (active_ctx["last_session"] if active_ctx.get("last_session", 0) > 0 else 1)
        roster_dicts = [p.model_dump() for p in payload.roster] if payload.roster else active_ctx.get("roster", [])

        try:
            camp_res = await run_in_threadpool(
                server.process_session_for_campaign,
                campaign_name=campaign_name,
                transcript_text=transcript_text,
                roster_dicts=roster_dicts,
                session_number=session_num,
                target_language=target_lang,
                is_youtube=bool(payload.is_youtube),
                gemini_api_key=gemini_key,
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
    action_items = None
    key_points = None
    if is_class_mode:
        action_items, key_points = server.extract_academic_sections(chronicle_md or "")

    # Background Drive Sync
    try:
        files_to_sync = []
        if is_class_mode:
            hist_path = server.update_consolidated_academic_notes_file()
            if hist_path and hist_path.is_file():
                files_to_sync.append(hist_path)
            if md_filename:
                m_p = server.get_data_output_dir() / md_filename
                if m_p.is_file():
                    files_to_sync.append(m_p)
        else:
            if campaign_name:
                c_path = server.get_campaign_path(campaign_name)
                if c_path and c_path.is_file():
                    files_to_sync.append(c_path)
            if md_filename:
                m_p = server.get_data_output_dir() / md_filename
                if m_p.is_file():
                    files_to_sync.append(m_p)
            if file_path_str and Path(file_path_str).is_file():
                files_to_sync.append(Path(file_path_str))
        if files_to_sync:
            server.trigger_drive_sync_background(files_to_sync)
    except Exception as exc:
        print(f"[reprocess_campaign] Warning triggering drive sync: {exc}")

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
        campaign_name=campaign_name if not is_class_mode else None,
        session_number=session_num if not is_class_mode else None,
        campaign_state=campaign_state,
        session_chapter=session_chapter,
        updated_quests=updated_quests,
        updated_npcs=updated_npcs,
        detected_npc_names=detected_npc_names,
        detected_party=detected_party,
        detected_pcs=detected_pcs,
        chronicle=chronicle_md,
        recording_mode="class" if is_class_mode else "roleplay",
        subject=subj if is_class_mode else None,
        topic=top if is_class_mode else None,
        target_language=target_lang,
        action_items=action_items,
        key_points=key_points,
    )




