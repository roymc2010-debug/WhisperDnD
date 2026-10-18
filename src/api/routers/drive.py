"""Drive router for Google Drive OAuth, backup, sync, and diagnostics."""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool

from src.api import server

router = APIRouter(tags=["drive"])


@router.post("/api/export/drive", response_model=server.DriveExportResponse)
async def export_to_drive(payload: server.DriveExportRequest):
    """Upload a file to Google Drive folder 'Whisper AI - Transcripciones'."""
    raw_path = payload.file_path.strip()
    if not raw_path:
        raise HTTPException(status_code=400, detail="file_path no puede estar vacío.")

    target_file = Path(raw_path)
    if not target_file.is_file():
        # Check relative to output dir
        candidate = server.get_data_output_dir() / target_file.name
        if candidate.is_file():
            target_file = candidate
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Archivo no encontrado en el servidor: {raw_path}",
            )

    try:
        drive_storage = server.GoogleDriveStorage()
        upload_res = drive_storage.upload_file(str(target_file.resolve()))
        return server.DriveExportResponse(
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


import time
from pydantic import BaseModel, Field

class CancelTaskRequest(BaseModel):
    task_id: str = Field(..., description="ID of the task to cancel")


@router.get("/api/task/status")
async def get_task_status_endpoint(task_id: str = Query(..., description="ID of the task to query")):
    """Get granular progress and status of an active or recent task."""
    return server.get_task_progress(task_id)


@router.post("/api/task/cancel")
@router.post("/api/tasks/{task_id}/cancel")
async def cancel_task_endpoint(payload: Optional[CancelTaskRequest] = None, task_id: Optional[str] = None):
    """Mark a running transcription or analysis task as cancelled."""
    tid = (payload.task_id if payload else task_id) or ""
    tid = tid.strip()
    if tid:
        server.task_progress_state[tid] = {
            "task_id": tid,
            "percent": 0.0,
            "step": "Proceso cancelado",
            "message": "Proceso detenido por el usuario.",
            "status": "cancelled",
            "stage": "cancelled",
            "timestamp": time.time(),
        }
    return {"success": True, "message": "Proceso detenido exitosamente."}


@router.get("/api/system/quota")
@router.get("/api/quota")
async def get_system_quota_endpoint():
    """Retrieve current daily API token and audio quota usage and remaining percentage."""
    from src.storage.quota_tracker import get_quota_status
    return get_quota_status()


_keys_cache = {"timestamp": 0.0, "cache_key": "", "data": None}
_drive_user_cache = {"email": None, "timestamp": 0.0}

@router.get("/api/status/keys")
async def check_api_keys(request: Request = None):
    """
    Perform a lightning-fast concurrent check (<1.5s) to verify health and availability of
    Groq, Gemini, and Google Drive credentials.
    Includes in-memory caching to prevent network congestion on repeat polls.
    """
    global _keys_cache, _drive_user_cache
    now = time.time()

    client_groq = (request.headers.get("X-Groq-Api-Key") or "").strip() if request else ""
    client_gemini = (request.headers.get("X-Gemini-Api-Key") or "").strip() if request else ""
    groq_key, gemini_key = server.extract_client_api_keys(request)

    current_cache_key = f"{client_groq}:{client_gemini}:{groq_key}:{gemini_key}"
    if _keys_cache["data"] and _keys_cache["cache_key"] == current_cache_key and (now - _keys_cache["timestamp"] < 35.0):
        cached = dict(_keys_cache["data"])
        cached["oauth_redirect_uri"] = server.get_oauth_redirect_uri(request)
        return cached

    groq_source = "client" if client_groq else ("server" if groq_key else "none")
    gemini_source = "client" if client_gemini else ("server" if gemini_key else "none")

    async def _check_groq_async():
        if not groq_key:
            return False, "GROQ_API_KEY no configurada."
        def _sync_groq():
            import groq
            client = groq.Client(api_key=groq_key, timeout=2.0)
            client.models.list()
            return True
        try:
            await asyncio.wait_for(run_in_threadpool(_sync_groq), timeout=2.5)
            msg = "Tu GROQ_API_KEY personal está activa y verificada." if client_groq else "Groq Whisper API operativa (llave del servidor)."
            return True, msg
        except Exception as exc:
            return False, f"Error validando Groq: {exc}"

    async def _check_gemini_async():
        if not gemini_key:
            return False, "GEMINI_API_KEY no configurada."
        def _sync_gemini():
            from google import genai
            client = genai.Client(api_key=gemini_key)
            for _ in client.models.list():
                break
            return True
        try:
            await asyncio.wait_for(run_in_threadpool(_sync_gemini), timeout=3.0)
            msg = "Tu GEMINI_API_KEY personal está activa y verificada." if client_gemini else "Gemini API operativa (llave del servidor)."
            return True, msg
        except Exception as exc:
            return False, f"Error validando Gemini: {exc}"

    async def _check_drive_async():
        try:
            drive_storage = server.GoogleDriveStorage()
            drive_ok = await run_in_threadpool(drive_storage.is_connected)
            drive_email = None
            if drive_ok:
                if _drive_user_cache["email"] and (now - _drive_user_cache["timestamp"] < 300.0):
                    drive_email = _drive_user_cache["email"]
                else:
                    try:
                        u_info = await asyncio.wait_for(run_in_threadpool(drive_storage.get_user_info), timeout=2.0)
                        if isinstance(u_info, dict) and isinstance(u_info.get("email"), str):
                            drive_email = u_info["email"]
                            _drive_user_cache["email"] = drive_email
                            _drive_user_cache["timestamp"] = now
                    except Exception:
                        pass
            drive_msg = (
                "Google Drive conectado."
                if drive_ok
                else ("Credenciales listas, conexión pendiente." if drive_storage.credentials_path.is_file() else "Falta credentials.json en la raíz del proyecto.")
            )
            return drive_ok, drive_email, drive_storage.credentials_path.is_file(), drive_msg
        except Exception as d_exc:
            return False, None, False, f"Error Drive: {d_exc}"

    # Run all 3 checks concurrently in parallel
    (groq_res, gemini_res, drive_res) = await asyncio.gather(
        _check_groq_async(),
        _check_gemini_async(),
        _check_drive_async(),
        return_exceptions=False,
    )

    groq_ok, groq_msg = groq_res
    gemini_ok, gemini_msg = gemini_res
    drive_ok, drive_email, has_creds, drive_msg = drive_res

    res_data = {
        "groq": groq_ok,
        "gemini": gemini_ok,
        "groq_source": groq_source,
        "gemini_source": gemini_source,
        "drive": drive_ok,
        "drive_email": drive_email,
        "has_credentials": has_creds,
        "oauth_redirect_uri": server.get_oauth_redirect_uri(request),
        "groq_message": groq_msg,
        "gemini_message": gemini_msg,
        "drive_message": drive_msg,
    }

    _keys_cache = {
        "timestamp": now,
        "cache_key": current_cache_key,
        "data": res_data,
    }

    return res_data


@router.get("/api/drive/status")
async def get_drive_status(request: Request = None):
    """Check if Google Drive OAuth is connected and return account details."""
    drive_storage = server.GoogleDriveStorage()
    has_creds = drive_storage.credentials_path.is_file()
    connected = drive_storage.is_connected()
    user_info = {}
    token_dict = None
    if connected:
        try:
            user_info = await run_in_threadpool(drive_storage.get_user_info)
        except Exception as exc:
            print(f"[get_drive_status] Error fetching user info: {exc}")
            user_info = {}
        try:
            if drive_storage.token_path.is_file():
                token_dict = json.loads(drive_storage.token_path.read_text(encoding="utf-8"))
        except Exception:
            token_dict = None

    email = user_info.get("email") if isinstance(user_info, dict) and isinstance(user_info.get("email"), str) else None
    name = user_info.get("name") if isinstance(user_info, dict) and isinstance(user_info.get("name"), str) else None
    photo_link = user_info.get("photo_link") if isinstance(user_info, dict) and isinstance(user_info.get("photo_link"), str) else None

    return {
        "connected": connected,
        "has_credentials": has_creds,
        "email": email,
        "name": name,
        "photo_link": photo_link,
        "token": token_dict,
        "oauth_redirect_uri": server.get_oauth_redirect_uri(request),
        "message": (
            "Google Drive conectado"
            if connected
            else ("Credenciales listas, conexión pendiente" if has_creds else "Falta credentials.json en la raíz del proyecto")
        ),
    }


@router.get("/api/auth/drive/login")
async def drive_login(request: Request = None, redirect_uri: Optional[str] = None):
    """Generate Google Drive OAuth authorization URL without blocking the FastAPI server."""
    drive_storage = server.GoogleDriveStorage()
    target_redirect = server.get_oauth_redirect_uri(request, redirect_uri)
    try:
        auth_url = await run_in_threadpool(
            drive_storage.get_authorization_url,
            target_redirect,
        )
        return {"auth_url": auth_url, "redirect_uri": target_redirect}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error generando URL de autenticación: {exc}") from exc


@router.get("/api/auth/drive/callback")
@router.get("/oauth2callback")
async def drive_callback(
    request: Request = None,
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

    target_redirect = server.get_oauth_redirect_uri(request)

    drive_storage = server.GoogleDriveStorage()
    try:
        await run_in_threadpool(
            drive_storage.exchange_code_for_token,
            code=code,
            redirect_uri=target_redirect,
            state=state,
        )
        # Trigger background pull & restore from Google Drive on successful authentication
        try:
            asyncio.create_task(
                run_in_threadpool(
                    drive_storage.sync_from_google_drive,
                    server.get_data_campaigns_dir(),
                    server.get_data_output_dir(),
                )
            )
        except Exception as _sync_err:
            print(f"[drive_callback] Warning scheduling initial drive sync: {_sync_err}")

        token_str = "{}"
        try:
            if drive_storage.token_path.is_file():
                token_str = drive_storage.token_path.read_text(encoding="utf-8")
            elif Path("/app/token.json").is_file():
                token_str = Path("/app/token.json").read_text(encoding="utf-8")
        except Exception as _tok_err:
            print(f"[drive_callback] Warning reading token.json: {_tok_err}")

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Google Drive Conectado</title>
</head>
<body style="font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #0f172a; color: #f8fafc;">
  <div style="text-align: center; padding: 24px;">
    <h2 style="margin-bottom: 8px;">Conectando Google Drive...</h2>
    <p style="color: #94a3b8; font-size: 14px;">Guardando credenciales para mantener la sesión activa.</p>
  </div>
  <script>
    try {{
      const token = {token_str};
      if (token && Object.keys(token).length > 0) {{
        localStorage.setItem('gdrive_auth_token', JSON.stringify(token));
      }}
    }} catch (e) {{
      console.warn("No se pudo guardar el token en localStorage:", e);
    }}
    window.location.href = '/?drive_connected=true';
  </script>
</body>
</html>"""
        return HTMLResponse(content=html_content, status_code=200)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al canjear código de OAuth: {exc}") from exc


@router.post("/api/drive/connect")
async def connect_drive(request: Request = None):
    """Generate Google Drive authorization URL upfront."""
    drive_storage = server.GoogleDriveStorage()
    if not drive_storage.credentials_path.is_file():
        raise HTTPException(
            status_code=400,
            detail="No se encontró el archivo credentials.json en la raíz del proyecto. Coloca el archivo descargado de Google Cloud Console.",
        )
    target_redirect = server.get_oauth_redirect_uri(request)
    try:
        auth_url = await run_in_threadpool(
            drive_storage.get_authorization_url,
            target_redirect,
        )
        return {
            "status": "success",
            "connected": drive_storage.is_connected(),
            "auth_url": auth_url,
            "redirect_uri": target_redirect,
            "message": "URL de autorización generada.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al iniciar autenticación de Google Drive: {exc}") from exc

@router.post("/api/drive/upload-credentials")
async def upload_credentials_endpoint(
    request: Request = None,
    file: Optional[UploadFile] = File(None),
):
    """
    Upload or paste credentials.json to project root so Google OAuth can function on this machine.
    """
    content = ""
    if file:
        raw_bytes = await file.read()
        content = raw_bytes.decode("utf-8", errors="replace")
    elif request:
        try:
            body = await request.json()
            if isinstance(body, dict):
                content = body.get("credentials_json") or body.get("content") or json.dumps(body)
        except Exception:
            pass

    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="Contenido de credentials.json vacío.")

    try:
        parsed = json.loads(content)
        if not isinstance(parsed, dict) or not any(k in parsed for k in ("installed", "web")):
            raise ValueError("El archivo JSON no tiene la estructura de credenciales OAuth de Google ('installed' o 'web').")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Formato JSON de credenciales inválido: {exc}")

    drive_storage = server.GoogleDriveStorage()
    target_path = drive_storage.credentials_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")

    return {
        "status": "success",
        "message": f"credentials.json guardado exitosamente en el servidor ({target_path.name}).",
        "has_credentials": True,
    }


@router.post("/api/drive/sync")
async def sync_drive_endpoint():
    """Trigger bidirectional sync of campaigns and notes with Google Drive."""
    drive_storage = server.GoogleDriveStorage()
    if not drive_storage.is_connected():
        return {
            "status": "not_connected",
            "synced_campaigns": 0,
            "synced_notes": 0,
            "message": "Google Drive no está conectado. Inicia sesión con Google Drive primero.",
        }
    try:
        camp_dir = server.get_data_campaigns_dir()
        out_dir = server.get_data_output_dir()
        res = await run_in_threadpool(drive_storage.sync_from_google_drive, camp_dir, out_dir)
        return res
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error durante sincronización con Drive: {exc}") from exc


@router.post("/api/auth/gdrive/restore")
@router.post("/api/auth/drive/restore")
async def restore_drive_session_endpoint(payload: Optional[server.RestoreDriveTokenRequest] = None, request: Request = None):
    """
    Restore Google Drive session from client-provided token JSON stored in localStorage.
    Re-establishes drive_storage session without needing to re-login.
    """
    token_data = None
    if payload and payload.token_data is not None:
        token_data = payload.token_data
    elif request:
        try:
            body = await request.json()
            if isinstance(body, dict):
                token_data = body.get("token_data") or body.get("token") or body
        except Exception:
            token_data = None

    if not token_data:
        raise HTTPException(status_code=400, detail="Token de Google Drive no proporcionado.")

    drive_storage = server.GoogleDriveStorage()
    success = await run_in_threadpool(drive_storage.restore_from_client_token, token_data)
    if not success or not drive_storage.is_connected():
        raise HTTPException(status_code=400, detail="No se pudo restaurar la sesión con el token proporcionado.")

    try:
        asyncio.create_task(
            run_in_threadpool(
                drive_storage.sync_from_google_drive,
                server.get_data_campaigns_dir(),
                server.get_data_output_dir(),
            )
        )
    except Exception as _sync_err:
        print(f"[restore_drive_session] Warning scheduling background sync: {_sync_err}")

    return {
        "status": "success",
        "connected": True,
        "message": "Sesión de Google Drive restaurada exitosamente.",
    }


@router.get("/api/drive/token")
@router.get("/api/auth/drive/token")
async def get_drive_token_endpoint():
    """
    Retrieve current Google Drive token JSON so frontend can cache it in localStorage.
    """
    drive_storage = server.GoogleDriveStorage()
    token_path = drive_storage.token_path
    if not token_path.is_file():
        alt_path = Path("/app/token.json")
        if alt_path.is_file():
            token_path = alt_path

    if not token_path.is_file():
        return {
            "status": "not_connected",
            "connected": False,
            "token": None,
            "message": "No hay token almacenado.",
        }

    try:
        token_dict = json.loads(token_path.read_text(encoding="utf-8"))
        return {
            "status": "success",
            "connected": drive_storage.is_connected(),
            "token": token_dict,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error leyendo token: {exc}")


@router.post("/api/drive/disconnect")
@router.post("/api/auth/drive/logout")
async def disconnect_drive():
    """Disconnect Google Drive session, delete token.json and clear active service."""
    drive_storage = server.GoogleDriveStorage()
    success = await run_in_threadpool(drive_storage.disconnect)
    return {
        "status": "disconnected",
        "connected": False,
        "success": success,
        "message": "Google Drive desconectado exitosamente.",
    }


@router.post("/api/transcription/discard")
async def discard_transcription_endpoint(payload: server.DiscardTranscriptRequest):
    """
    Discard raw speech-to-text transcript file (.txt) while retaining structured notes/chronicles.
    Applies to YouTube and file uploads when the user elects not to preserve raw audio text.
    """
    deleted_files = []

    # 1. Delete standalone txt file if filename provided
    if payload.filename:
        safe_name = Path(payload.filename).name
        for target_dir in [server.get_data_output_dir(), server.project_root / "outputs"]:
            cand = target_dir / safe_name
            if cand.is_file():
                try:
                    cand.unlink()
                    deleted_files.append(cand.name)
                except Exception as e:
                    print(f"[discard_transcription] Error deleting {cand}: {e}")

    # 2. If campaign & session specified, clear raw_transcript from session
    if payload.campaign_name and payload.session_number is not None:
        try:
            manager = server.CampaignManager()
            state = manager.load_campaign(payload.campaign_name)
            if state:
                modified = False
                for s in state.get("sessions", []):
                    if int(s.get("session_number", 0)) == int(payload.session_number):
                        s["raw_transcript"] = ""
                        modified = True
                if modified:
                    manager.save_campaign(state)
        except Exception as exc:
            print(f"[discard_transcription] Error updating campaign: {exc}")

    # 3. If note_filename provided, ensure raw transcript is not kept in consolidated json
    if payload.note_filename:
        try:
            for cand_hist in [
                server.project_root / "data" / "apuntes_historial.json",
                Path("/app/data/apuntes_historial.json"),
            ]:
                if cand_hist.is_file():
                    data = json.loads(cand_hist.read_text(encoding="utf-8"))
                    notes = data.get("notes") if isinstance(data.get("notes"), list) else data.get("apuntes", [])
                    modified = False
                    for n in notes:
                        if n.get("filename") == payload.note_filename or n.get("title") == payload.note_filename:
                            if "transcript" in n and n["transcript"]:
                                n["transcript"] = ""
                                modified = True
                    if modified:
                        cand_hist.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            try:
                from src.api.routers.academic import update_consolidated_academic_notes_file
                update_consolidated_academic_notes_file()
            except Exception:
                try:
                    server.update_consolidated_academic_notes_file()
                except Exception:
                    pass
        except Exception as exc:
            print(f"[discard_transcription] Error updating apuntes_historial: {exc}")

    return {
        "status": "success",
        "deleted_files": deleted_files,
        "message": "Transcripción descartada exitosamente.",
    }
