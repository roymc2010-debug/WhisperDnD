"""FastAPI router for audio devices, live VU monitoring, recording controls, and audio management."""

import asyncio
import datetime
import os
import re
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict
from starlette.concurrency import run_in_threadpool

from src.api import server

router = APIRouter(tags=["audio"])


# ---------------------------------------------------------------------------
# Request/Response Models for Audio Recording
# ---------------------------------------------------------------------------
class StartRecordingRequest(BaseModel):
    mode: str = Field(default="roleplay", description="Recording mode ('roleplay' or 'class')")
    mic_id: Optional[str] = Field(default=None, description="Physical microphone device ID")
    speaker_id: Optional[str] = Field(default=None, description="Playback speaker/headphone device ID for loopback")
    gain_mic: float = Field(default=1.0, description="Software volume multiplier for microphone")
    gain_spk: float = Field(default=1.0, description="Software volume multiplier for speaker loopback")
    campaign_name: Optional[str] = Field(default=None, description="Campaign name for roleplay recording")




class StopAndProcessRequest(BaseModel):
    roster: List[server.PlayerMetadata] = Field(default_factory=list, description="Party roster")
    model_size: str = Field(default="base", description="Whisper model size (tiny, base)")
    engine: str = Field(default="groq", description="Transcription engine ('groq' or 'local')")
    campaign_name: Optional[str] = Field(default=None, description="Name of the campaign")
    session_number: Optional[int] = Field(default=None, description="Optional manual session number")
    task_id: Optional[str] = Field(default=None, description="Task ID for progress tracking")
    recording_mode: str = Field(default="roleplay", description="Recording mode ('roleplay' or 'class')")
    subject: Optional[str] = Field(default="", description="Materia / Asignatura for university lecture")
    topic: Optional[str] = Field(default="", description="Tema de la clase for university lecture")
    target_language: str = Field(default="es", description="Target language ('es' or 'en')")
    audio_language: Optional[str] = Field(default=None, description="Explicit audio language or None for auto-detection")



class DeleteAudioRequest(BaseModel):
    filename: str = Field(..., description="Filename of original audio in data/input to delete")




# Endpoints: Audio Devices & Live VU Monitoring
# ---------------------------------------------------------------------------
@router.get("/api/audio/devices")
async def get_audio_devices_endpoint():
    """List all available physical microphones and speakers/loopback devices."""
    return server.get_audio_devices()


@router.get("/api/discord/participants")
async def get_discord_participants_endpoint():
    """Retrieve list of active participants in the current Discord voice channel via local RPC."""
    try:
        from src.transcription.discord_rpc import discord_tracker
        discord_tracker.ensure_running()
        if not discord_tracker.is_connected:
            for _ in range(3):
                if discord_tracker.is_connected:
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


@router.post("/api/discord/reset-auth")
async def reset_discord_auth_endpoint():
    """Clear cached Discord RPC token to force a fresh authorization prompt in the Discord desktop app."""
    try:
        from src.transcription.discord_rpc import TOKEN_FILE, discord_tracker
        TOKEN_FILE.unlink(missing_ok=True)
        discord_tracker.ensure_running()
        return {"status": "ok", "message": "Token de Discord reiniciado. Revisa la ventana de Discord para autorizar."}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@router.get("/api/audio/test-level")
async def test_audio_level(
    mic_id: Optional[str] = Query(default=None, description="Microphone device ID"),
    speaker_id: Optional[str] = Query(default=None, description="Speaker loopback device ID"),
    gain_mic: Optional[float] = Query(default=None, description="Microphone gain multiplier"),
    gain_spk: Optional[float] = Query(default=None, description="Speaker loopback gain multiplier"),
):
    """
    Capture a ~100ms sample from the selected microphone and speaker loopback
    and return current RMS levels scaled by gain multipliers.
    """
    def _val(v):
        if hasattr(v, "default"):
            return None
        return v

    v_mic = _val(gain_mic)
    v_spk = _val(gain_spk)

    kwargs = {"mic_id": mic_id, "speaker_id": speaker_id}
    if v_mic is not None and v_mic != 1.0:
        kwargs["gain_mic"] = float(v_mic)
    if v_spk is not None and v_spk != 1.0:
        kwargs["gain_spk"] = float(v_spk)

    return server.get_audio_levels(**kwargs)


# ---------------------------------------------------------------------------
# Endpoints: Live Dual-Channel / Mono Recording
# ---------------------------------------------------------------------------
@router.post("/api/record/start")
async def start_recording(payload: Optional[StartRecordingRequest] = None):
    """
    Start recording audio:
    - mode='roleplay': Dual-channel (Mic Left, Discord/Speaker Loopback Right).
    - mode='class': Single-channel (Microphone ONLY, Mono 16kHz).
    """
    rec_mode = payload.mode if payload else "roleplay"
    if rec_mode == "roleplay" and payload and payload.campaign_name is not None and not payload.campaign_name.strip():
        raise HTTPException(status_code=400, detail="Debes seleccionar o crear una campaña antes de iniciar la grabación.")
    mic_id = payload.mic_id if payload else None
    speaker_id = payload.speaker_id if payload else None
    gain_mic = getattr(payload, "gain_mic", 1.0) if payload else 1.0
    gain_spk = getattr(payload, "gain_spk", 1.0) if payload else 1.0
    try:
        rec_kwargs = {
            "mode": rec_mode,
            "mic_id": mic_id,
            "speaker_id": speaker_id,
            "campaign_name": getattr(payload, "campaign_name", None) if payload else None,
        }
        if gain_mic is not None and gain_mic != 1.0:
            rec_kwargs["gain_mic"] = gain_mic
        if gain_spk is not None and gain_spk != 1.0:
            rec_kwargs["gain_spk"] = gain_spk

        wav_path = server.active_recorder.start(**rec_kwargs)
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
            "gain_mic": gain_mic,
            "gain_spk": gain_spk,
            "message": msg,
            "file_path": str(Path(wav_path).name),
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al iniciar grabación: {exc}") from exc


@router.get("/api/record/status")
async def get_recording_status():
    """Return the current recording status and duration."""
    return server.active_recorder.get_status()


@router.post("/api/record/stop")
async def stop_recording_only():
    """Stop live recording without triggering transcription processing."""
    if not server.active_recorder.is_recording:
        return {"status": "idle", "message": "No hay grabación activa."}
    try:
        wav_path = server.active_recorder.stop()
        return {
            "status": "stopped",
            "file_path": str(Path(wav_path).name) if wav_path else None,
            "message": "Grabación detenida con éxito.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/record/stop-and-process")
async def stop_and_process(payload: StopAndProcessRequest, request: Request = None):
    """
    Stop live recording, run faster-whisper, generate Gemini chronicle/campaign updates with roster,
    and produce downloadable .docx and .md Grimorio files.
    """
    groq_key, gemini_key = server.extract_client_api_keys(request)
    server.validate_api_keys_or_raise(request, groq_key, gemini_key, require_gemini=True)

    has_active = server.active_recorder.is_recording
    has_recent_file = (
        bool(server.active_recorder._file_path)
        and Path(server.active_recorder._file_path).is_file()
        and Path(server.active_recorder._file_path).stat().st_size > 1000
    )

    if not has_active and not has_recent_file:
        raise HTTPException(status_code=400, detail="No hay ninguna sesión de grabación activa ni archivo reciente para procesar.")

    is_class_mode_check = (payload.recording_mode == "class") or (getattr(server.active_recorder, "mode", "roleplay") == "class")
    if not is_class_mode_check and payload.campaign_name is not None and not payload.campaign_name.strip():
        raise HTTPException(status_code=400, detail="Debes seleccionar o crear una campaña antes de procesar la sesión.")

    task_id = payload.task_id
    server.update_task_progress(task_id, 20.0, "Preparando grabación en el servidor...", "Finalizando captura de audio...", stage="audio")
    start_time = time.time()

    # 1. Stop audio recording if active, or use recently finalized file
    if has_active:
        try:
            wav_path = server.active_recorder.stop()
        except Exception as exc:
            err_type, human_err, stage = server.diagnose_exception(exc)
            import traceback
            server.set_task_error(task_id, human_err, error_type=err_type, stage=stage, details=traceback.format_exc())
            raise HTTPException(status_code=500, detail=human_err) from exc
    else:
        wav_path = server.active_recorder._file_path

    if not wav_path or not Path(wav_path).is_file():
        server.set_task_error(task_id, "El archivo de audio grabado no se encontró en disco.", error_type="AudioFileError", stage="Grabación en Vivo")
        raise HTTPException(status_code=500, detail="El archivo de audio grabado no se encontró en disco.")

    server.update_task_progress(task_id, 10.0, "Preparando audio en el servidor...", "Verificando canales estéreo y niveles RMS...", stage="audio")

    def progress_cb(pct: float, msg: str):
        server.update_task_progress(task_id, pct, msg, stage="transcribing")

    # 2. Run Whisper Transcription (Groq Cloud or Local faster-whisper)
    model_size = payload.model_size or "base"
    engine = payload.engine or "groq"
    roster_dicts = [p.model_dump() for p in payload.roster] if payload.roster else []
    user_char_name = None
    if not roster_dicts and payload.campaign_name:
        try:
            from src.storage.campaign_manager import CampaignManager
            c_data = CampaignManager().load_campaign(payload.campaign_name)
            roster_dicts = c_data.get("roster", []) or []
        except Exception as camp_roster_err:
            print(f"[audio.py] Notice loading campaign roster: {camp_roster_err}")

    for p in roster_dicts:
        if isinstance(p, dict) and (p.get("is_user_character") or p.get("is_user")):
            user_char_name = (p.get("character_name") or "").strip()
            break

    speaking_log = getattr(server.active_recorder, "speaking_log", None)

    try:
        transcription_result = await run_in_threadpool(
            server.transcribe_audio_pipeline,
            audio_path=wav_path,
            engine=engine,
            model_size=model_size,
            language=getattr(payload, "audio_language", None),
            on_progress=progress_cb,
            source="live",
            user_char_name=user_char_name,
            speaking_log=speaking_log,
            roster=roster_dicts,
            groq_api_key=groq_key,
            campaign_name=payload.campaign_name,
            recording_mode=payload.recording_mode,
            subject=payload.subject,
            topic=payload.topic,
            task_id=task_id,
        )
    except Exception as exc:
        err_type, human_err, stage = server.diagnose_exception(exc)
        import traceback
        server.set_task_error(task_id, human_err, error_type=err_type, stage=stage, details=traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=human_err,
        ) from exc

    transcript_text = (transcription_result.get("formatted_transcript") or transcription_result.get("text") or "").strip()

    # 3. Check Mode: In-Person University Lecture vs D&D Roleplay
    is_class_mode = (payload.recording_mode == "class") or (getattr(server.active_recorder, "mode", "roleplay") == "class")
    if is_class_mode:
        server.update_task_progress(task_id, 72.0, "Generando guía académica con Gemini...", "Sintetizando conceptos teóricos y fórmulas...", stage="analyzing")
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
        except Exception as exc:
            chronicle_md = (
                f"# ⚠️ Error generando guía académica con Gemini:\n\n> {exc}\n\n"
                f"**Transcripción obtenida:**\n\n{transcript_text}"
            )

        server.update_task_progress(task_id, 94.0, "Generando documentos (.docx y .md)...", "Creando archivos de apuntes...", stage="analyzing")
        clean_subj = re.sub(r'[\\/*?:"<>|]', "", subj.strip()) or "Materia"
        safe_subj = re.sub(r"\s+", "_", clean_subj)
        docx_filename = f"apuntes_{safe_subj}_{now_str}.docx"
        md_filename = f"apuntes_{safe_subj}_{now_str}.md"
        txt_filename = f"apuntes_{safe_subj}_{now_str}_transcripcion.txt"
        docx_out_path = server.get_data_output_dir() / docx_filename
        md_out_path = server.get_data_output_dir() / md_filename
        txt_out_path = server.get_data_output_dir() / txt_filename
        try:
            # Store only .md and .txt in disk; docx is generated dynamically on demand
            md_out_path.write_text(chronicle_md, encoding="utf-8")
            txt_out_path.write_text(transcript_text, encoding="utf-8")
            (server.get_data_output_dir() / f"{safe_subj}_transcripcion.txt").write_text(transcript_text, encoding="utf-8")
        except Exception as exc:
            print(f"[!] Warning: academic notes export failed: {exc}")

        # Update consolidated academic notes and sync to Drive in background
        files_to_sync = []
        try:
            hist_path = server.update_consolidated_academic_notes_file()
            if hist_path and hist_path.is_file():
                files_to_sync.append(hist_path)
        except Exception as exc:
            print(f"[!] Warning: error updating consolidated academic notes: {exc}")
        if md_out_path and md_out_path.is_file():
            files_to_sync.append(md_out_path)
        if files_to_sync:
            server.trigger_drive_sync_background(files_to_sync)

        server.update_task_progress(task_id, 100.0, "¡Completado!", "Guía de estudio generada exitosamente.", stage="done")
        elapsed_time = round(time.time() - start_time, 2)
        language_code = transcription_result.get("language_code") or (
            transcription_result["language"]["code"]
            if isinstance(transcription_result.get("language"), dict)
            else str(transcription_result.get("language", ""))
        )

        action_items, key_points = server.extract_academic_sections(chronicle_md)
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
            "action_items": action_items,
            "key_points": key_points,
        }

    # 4. Roleplay Mode: Living Campaign Journal or Single Session Chronicle
    server.update_task_progress(task_id, 72.0, "Generando crónica / apuntes explicativos con IA...", "Extrayendo hechos e inventario...", stage="analyzing")
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
            server.update_task_progress(task_id, 80.0, "Actualizando Quest Tracker y Directorio Universal de NPCs...", stage="analyzing")
            camp_res = await run_in_threadpool(
                server.process_session_for_campaign,
                campaign_name=payload.campaign_name,
                transcript_text=transcript_text,
                roster_dicts=roster_dicts,
                session_number=payload.session_number,
                target_language=payload.target_language,
                gemini_api_key=gemini_key,
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
            summarizer = server.GeminiTTRPGSummarizer(api_key=gemini_key)
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
            docx_out_path = server.get_data_output_dir() / docx_filename

            await run_in_threadpool(
                server.export_chronicle_docx,
                chronicle_md=chronicle_md,
                roster=roster_dicts,
                session_date=now_formatted,
                output_path=str(docx_out_path),
            )
        except Exception as exc:
            print(f"[!] Warning: docx export failed: {exc}")

    server.update_task_progress(task_id, 94.0, "Generando documentos (.docx y .md)...", "Creando archivos del Grimorio (.docx y .md)...", stage="analyzing")
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
            (server.get_data_output_dir() / txt_filename).write_text(transcript_text, encoding="utf-8")
        except Exception as exc:
            print(f"[!] Warning: txt export failed: {exc}")

    server.update_task_progress(task_id, 100.0, "¡Completado!", "Sesión procesada exitosamente.", stage="done")

    # Background Drive Sync and Campaign Folder Mirroring
    files_to_sync = []
    if payload.campaign_name:
        c_path = server.get_campaign_path(payload.campaign_name)
        if c_path and c_path.is_file():
            files_to_sync.append(c_path)
        # Mirror exports to dedicated data/campaigns/<campaign>/exports/
        try:
            import shutil
            safe_c = re.sub(r'[\\/*?:"<>|]', "", payload.campaign_name.strip())
            safe_c = re.sub(r"\s+", "_", safe_c).lower() or "campana_principal"
            camp_exports = server.project_root / "data" / "campaigns" / safe_c / "exports"
            camp_exports.mkdir(parents=True, exist_ok=True)
            if md_filename and (server.get_data_output_dir() / md_filename).is_file():
                shutil.copyfile(server.get_data_output_dir() / md_filename, camp_exports / md_filename)
            if docx_out_path and docx_out_path.is_file():
                shutil.copyfile(docx_out_path, camp_exports / docx_out_path.name)
            if txt_filename and (server.get_data_output_dir() / txt_filename).is_file():
                shutil.copyfile(server.get_data_output_dir() / txt_filename, camp_exports / txt_filename)
        except Exception as camp_exp_err:
            print(f"[stop_and_process] Notice mirroring campaign exports: {camp_exp_err}")
    if md_filename:
        m_p = server.get_data_output_dir() / md_filename
        if m_p.is_file():
            files_to_sync.append(m_p)
    if docx_out_path and docx_out_path.is_file():
        files_to_sync.append(docx_out_path)
    if files_to_sync:
        server.trigger_drive_sync_background(files_to_sync)

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


@router.get("/api/record/download-docx")
async def download_docx(filename: str = Query(..., description="Name of the docx file")):
    """Download a generated session chronicle or academic study notes Word document."""
    safe_filename = Path(filename).name
    file_path = server.get_data_output_dir() / safe_filename

    # If direct path does not exist, check alternative output directories
    if not file_path.is_file():
        alt_dirs = [
            server.project_root / "outputs",
            server.project_root / "data" / "output",
        ]
        for ad in alt_dirs:
            cand = ad / safe_filename
            if cand.is_file():
                file_path = cand
                break

    # If still not found, check if a corresponding .md file exists to compile on demand
    if not file_path.is_file():
        md_candidates = [
            file_path.with_suffix(".md"),
            (server.project_root / "outputs" / safe_filename).with_suffix(".md"),
            (server.project_root / "data" / "output" / safe_filename).with_suffix(".md"),
        ]
        found_md = next((p for p in md_candidates if p.is_file()), None)
        if found_md:
            try:
                md_content = found_md.read_text(encoding="utf-8")
                if safe_filename.startswith("apuntes_"):
                    clean_subj = safe_filename.replace("apuntes_", "").replace(".docx", "")
                    clean_subj = re.sub(r"_\d{8}_\d{6}$", "", clean_subj)
                    subj = clean_subj.replace("_", " ").strip() or "Materia Universitaria"
                    server.export_academic_notes_docx(
                        notes_md=md_content,
                        subject=subj,
                        topic="Apuntes de Clase",
                        output_path=str(file_path),
                    )
                else:
                    server.export_chronicle_docx(
                        chronicle_md=md_content,
                        output_path=str(file_path),
                    )
            except Exception as exc:
                print(f"[download_docx] Warning compiling docx on demand from {found_md.name}: {exc}")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo docx no encontrado.")

    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/api/record/download-md")
async def download_md(filename: str = Query(..., description="Name of the md file")):
    """Download a generated session chronicle or academic study notes markdown document."""
    safe_filename = Path(filename).name
    file_path = server.get_data_output_dir() / safe_filename

    if not file_path.is_file():
        alt_dirs = [
            server.project_root / "outputs",
            server.project_root / "data" / "output",
        ]
        for ad in alt_dirs:
            cand = ad / safe_filename
            if cand.is_file():
                file_path = cand
                break

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo markdown no encontrado.")

    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type="text/markdown",
    )


@router.post("/api/record/delete-audio")
async def delete_recording_audio(payload: DeleteAudioRequest):
    """
    Manually delete an original master recording from data/input/ upon user request.
    Preserves live recordings by default unless explicitly deleted here.
    """
    safe_filename = Path(payload.filename).name
    target_path = server.get_data_input_dir() / safe_filename
    if not target_path.is_file():
        raise HTTPException(status_code=404, detail=f"Archivo '{safe_filename}' no encontrado en el servidor.")
    try:
        target_path.unlink()
        return {"status": "success", "message": f"Audio original '{safe_filename}' eliminado correctamente."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al eliminar audio: {exc}") from exc


