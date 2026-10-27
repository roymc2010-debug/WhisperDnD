"""FastAPI router for D&D Campaign Management, Wiki Entities, Quests, Export/Import, and Downloads."""

import asyncio
import datetime
import io
import json
import os
import re
import shutil
import tempfile
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, Request
from fastapi.responses import FileResponse, Response, JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from starlette.concurrency import run_in_threadpool

from src.api import server

router = APIRouter(tags=["campaigns"])


# ---------------------------------------------------------------------------
# Request/Response Models for Campaigns
# ---------------------------------------------------------------------------
class CreateCampaignRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    campaign_name: str = Field(..., description="Name of the campaign")
    dm: Optional[str] = Field(default=None, description="Dungeon Master name")
    dungeon_master: Optional[str] = Field(default=None, description="Dungeon Master name alias")
    dm_name: Optional[str] = Field(default=None, description="Dungeon Master name alias")
    dm_discord: Optional[str] = Field(default=None, description="Dungeon Master Discord user ID alias")
    dm_discord_id: Optional[str] = Field(default=None, description="Dungeon Master Discord user ID")
    dm_discord_user_id: Optional[str] = Field(default=None, description="Dungeon Master Discord user ID alias")
    dm_discord_username: Optional[str] = Field(default=None, description="Dungeon Master Discord username")
    dm_discord_tag: Optional[str] = Field(default=None, description="Dungeon Master Discord tag")
    roster: Optional[List[server.PlayerMetadata]] = Field(default_factory=list, description="Party roster")
    prior_lore: Optional[str] = Field(default="", description="Prior lore / backstory for ongoing campaigns")


class UpdatePriorLoreRequest(BaseModel):
    prior_lore: str = Field(default="", description="Prior lore / backstory for ongoing campaigns")


class SaveRosterRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    campaign_name: Optional[str] = Field(default=None, description="Campaign name")
    dm_name: Optional[str] = Field(default=None, description="Dungeon Master name")
    dm_discord_user_id: Optional[str] = Field(default=None, description="DM Discord user ID")
    dm_discord_id: Optional[str] = Field(default=None, description="DM Discord user ID alias")
    players: Optional[List[Dict[str, Any]]] = Field(default=None, description="Players roster")
    roster: Optional[List[Dict[str, Any]]] = Field(default=None, description="Full roster list")


class KeepTranscriptRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    raw_transcript: Optional[str] = Field(default=None, description="Raw speech-to-text transcript")
    transcript: Optional[str] = Field(default=None, description="Raw transcript alias")
    transcript_text: Optional[str] = Field(default=None, description="Raw transcript alias")


class ProcessCampaignSessionRequest(BaseModel):
    transcript_text: str = Field(..., description="Speech-to-text transcript")
    roster: Optional[List[server.PlayerMetadata]] = Field(default=None, description="Party roster")
    session_number: Optional[int] = Field(default=None, description="Session number override")
    target_language: str = Field(default="es", description="Target language ('es' or 'en')")
    custom_date: Optional[str] = Field(default=None, description="Optional custom date string")
    client_timezone_offset: Optional[int] = Field(default=None, description="Client timezone offset in minutes")


class FinalizeNpcsRequest(BaseModel):
    name_corrections: Dict[str, str] = Field(default_factory=dict, description="Map of old NPC names to user-corrected names")


class UpdateQuestSubobjectiveRequest(BaseModel):
    subobjective_idx: int = Field(..., description="Index of the subobjective to update")
    completed: bool = Field(..., description="Whether the subobjective is completed")


class UpdateQuestStatusRequest(BaseModel):
    status: Optional[str] = Field(default=None, description="'completed', 'in_progress', 'failed', or None to toggle")


class MergeEntitiesRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_name: str = Field(..., description="Name of the entity to merge and remove")
    target_name: str = Field(..., description="Name of the primary entity to keep")
    entity_type: Optional[str] = Field(default="pc", description="Entity type: 'pc' or 'npc'")
    keep_name: Optional[str] = Field(default=None, description="Optional custom target name")


class UpdateNpcRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: Optional[str] = Field(default=None, description="New name for the NPC")
    new_name: Optional[str] = Field(default=None, description="New name for the NPC alias")
    role: Optional[str] = Field(default=None, description="Role or subtitle of the NPC")
    category: Optional[str] = Field(default=None, description="Category: 'clave', 'aliado', 'invocacion', 'amenaza', 'interaccion_contexto'")
    status: Optional[str] = Field(default=None, description="Vital status: 'activo', 'herido', 'abatido', 'desvanecido'")
    tipo: Optional[str] = Field(default=None, description="Legacy tipo: 'importantes', 'interaccion_contexto'")
    aliases: Optional[List[str]] = Field(default=None, description="List of aliases")
    notes: Optional[List[str]] = Field(default=None, description="Historical notes")


# ---------------------------------------------------------------------------
# Endpoints: Living Campaign Journal
# ---------------------------------------------------------------------------
@router.get("/api/campaigns")
async def list_campaigns():
    """List all campaigns in data/campaigns/."""
    manager = server.CampaignManager()
    return JSONResponse(
        content=manager.list_campaigns(),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
    )


@router.get("/api/campaigns/{campaign_name}")
async def get_campaign(campaign_name: str):
    """Get full state and active context for a campaign."""
    manager = server.CampaignManager()
    state = manager.load_campaign(campaign_name)
    active_ctx = manager.get_active_context(campaign_name)
    return JSONResponse(
        content={
            "campaign_state": state,
            "active_context": active_ctx,
        },
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
    )


@router.get("/api/campaigns/{campaign_name}/session/{session_num}")
async def get_campaign_session_endpoint(campaign_name: str, session_num: int):
    """Retrieve full historical session data including chronicle markdown, raw transcript, quests, NPCs, and PCs."""
    manager = server.CampaignManager()
    state = manager.load_campaign(campaign_name)
    if not state:
        raise HTTPException(status_code=404, detail=f"Campaña '{campaign_name}' no encontrada.")

    sessions = state.get("sessions", [])
    target_session = next((s for s in sessions if int(s.get("session_number", 0)) == int(session_num)), None)

    safe_name = manager.sanitize_name(campaign_name)
    custom_tf = target_session.get("raw_transcript_file") if target_session else None
    possible_txt_paths = [
        Path(custom_tf) if custom_tf else None,
        server.project_root / custom_tf if custom_tf else None,
        Path("outputs") / f"{safe_name}_sesion_{session_num}_transcripcion.txt",
        server.get_data_output_dir() / f"{safe_name}_sesion_{session_num}_transcripcion.txt",
        Path("outputs") / f"{campaign_name.lower()}_sesion_{session_num}_transcripcion.txt",
        server.get_data_output_dir() / f"{campaign_name.lower()}_sesion_{session_num}_transcripcion.txt",
    ]
    possible_txt_paths = [p for p in possible_txt_paths if p is not None]
    disk_transcript = ""
    for pt in possible_txt_paths:
        if pt.is_file():
            try:
                content = pt.read_text(encoding="utf-8").strip()
                if content:
                    disk_transcript = content
                    break
            except Exception:
                pass

    if not target_session:
        if disk_transcript:
            target_session = {
                "session_number": int(session_num),
                "title": f"Sesión {session_num}",
                "session_title": f"Sesión {session_num}",
                "date": datetime.datetime.now().strftime("%d/%m/%Y"),
                "raw_transcript": disk_transcript,
                "chronicle_text": "Transcripción de sesión preservada.",
                "chronicle_markdown": f"# Sesión #{session_num}\n\nTranscripción preservada con éxito.",
                "detected_pcs": state.get("roster") or state.get("universal_pcs") or []
            }
            if "sessions" not in state or not isinstance(state["sessions"], list):
                state["sessions"] = []
            state["sessions"].append(target_session)
            if int(session_num) > int(state.get("last_session", 0)):
                state["last_session"] = int(session_num)
            manager.save_campaign(state)
        elif sessions:
            sorted_sessions = sorted(sessions, key=lambda s: int(s.get("session_number", 0)))
            latest_sess = sorted_sessions[-1]
            latest_num = int(latest_sess.get("session_number", 0))
            if len(sessions) == 1 or int(session_num) == latest_num + 1:
                target_session = latest_sess

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
    if (not raw_transcript or raw_transcript.startswith("Transcripción no guardada")) and disk_transcript:
        raw_transcript = disk_transcript
        target_session["raw_transcript"] = disk_transcript
        manager.save_campaign(state)
    elif not raw_transcript:
        raw_transcript = f"Transcripción no guardada para la sesión #{session_num}."

    txt_filename = f"{safe_name}_sesion_{session_num}_transcripcion.txt"
    try:
        txt_path = server.get_data_output_dir() / txt_filename
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
        "title": target_session.get("session_title") or target_session.get("title", f"Sesión {session_num}"),
        "session_title": target_session.get("session_title") or target_session.get("title", f"Sesión {session_num}"),
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


@router.post("/api/campaigns/{campaign_name}/session/{session_num}/keep-transcript")
async def keep_campaign_session_transcript_endpoint(
    campaign_name: str,
    session_num: int,
    payload: KeepTranscriptRequest,
):
    """Explicitly persist the raw transcript into the session state and disk."""
    manager = server.CampaignManager()
    state = manager.load_campaign(campaign_name)
    if not state:
        raise HTTPException(status_code=404, detail=f"Campaña '{campaign_name}' no encontrada.")

    raw_text = (payload.raw_transcript or payload.transcript or payload.transcript_text or "").strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="Texto de transcripción vacío.")

    sessions = state.get("sessions", [])
    target = next((s for s in sessions if int(s.get("session_number", 0)) == int(session_num)), None)
    if not target:
        target = {
            "session_number": int(session_num),
            "title": f"Sesión {session_num}",
            "session_title": f"Sesión {session_num}",
            "date": datetime.datetime.now().strftime("%d/%m/%Y"),
            "raw_transcript": raw_text,
            "chronicle_text": "Transcripción de sesión preservada.",
            "chronicle_markdown": f"# Sesión #{session_num}\n\nTranscripción preservada con éxito.",
            "detected_pcs": state.get("roster") or state.get("universal_pcs") or [],
        }
        if "sessions" not in state or not isinstance(state["sessions"], list):
            state["sessions"] = []
        state["sessions"].append(target)
    else:
        target["raw_transcript"] = raw_text

    if int(session_num) > int(state.get("last_session", 0)):
        state["last_session"] = int(session_num)

    saved_path = manager.save_campaign(state)
    safe_name = manager.sanitize_name(campaign_name)
    try:
        out_file = server.get_data_output_dir() / f"{safe_name}_sesion_{session_num}_transcripcion.txt"
        out_file.write_text(raw_text, encoding="utf-8")
        outputs_file = Path("outputs") / f"{safe_name}_sesion_{session_num}_transcripcion.txt"
        outputs_file.parent.mkdir(parents=True, exist_ok=True)
        outputs_file.write_text(raw_text, encoding="utf-8")
    except Exception as e:
        print(f"[keep_campaign_session_transcript] Warning writing to disk: {e}")

    server.trigger_drive_sync_background([saved_path])
    return {
        "status": "success",
        "message": f"Transcripción de Sesión #{session_num} guardada correctamente.",
        "campaign_state": state,
    }


@router.post("/api/campaigns/{campaign_name}/roster")
async def save_campaign_roster_endpoint(campaign_name: str, payload: SaveRosterRequest):
    """Save roster, DM info, and player Discord links for a campaign."""
    manager = server.CampaignManager()
    state = manager.load_campaign(campaign_name)
    if not state:
        raise HTTPException(status_code=404, detail=f"Campaña '{campaign_name}' no encontrada.")

    dm_name = payload.dm_name or state.get("dm_name") or state.get("dm") or "Dungeon Master"
    dm_discord_id = payload.dm_discord_user_id or payload.dm_discord_id or state.get("dm_discord_id") or ""

    state["dm"] = dm_name
    state["dungeon_master"] = dm_name
    state["dm_name"] = dm_name
    state["dm_discord_id"] = dm_discord_id
    state["dm_discord_user_id"] = dm_discord_id
    state["dm_discord"] = dm_discord_id

    incoming_players = payload.players if payload.players is not None else payload.roster
    if incoming_players is not None:
        full_roster = []
        has_dm = any(
            p.get("character_name") == "(DM)" or p.get("role") == "Dungeon Master (DM)"
            for p in incoming_players
        )
        if not has_dm:
            dm_entry = {
                "player_name": dm_name,
                "character_name": "(DM)",
                "species": "(N/A - DM)",
                "role": "Dungeon Master (DM)",
                "subclass": "N/A",
                "discord_user_id": dm_discord_id,
                "discord_id": dm_discord_id,
                "is_user": False,
                "is_user_character": False,
                "is_absent": False,
            }
            full_roster.append(dm_entry)

        for p in incoming_players:
            entry = dict(p)
            if entry.get("character_name") == "(DM)" or entry.get("role") == "Dungeon Master (DM)":
                if dm_name and not entry.get("player_name"):
                    entry["player_name"] = dm_name
                if dm_discord_id and not (entry.get("discord_user_id") or entry.get("discord_id")):
                    entry["discord_user_id"] = dm_discord_id
                    entry["discord_id"] = dm_discord_id
            full_roster.append(entry)

        state["roster"] = full_roster

    saved_path = manager.save_campaign(state)
    server.trigger_drive_sync_background([saved_path])

    return {
        "status": "success",
        "message": "Roster de campaña guardado con éxito.",
        "campaign_state": state,
    }


@router.delete("/api/campaigns/{campaign_name}")
async def delete_campaign_endpoint(campaign_name: str):
    """Delete campaign state file and associated exports in data/output/."""
    manager = server.CampaignManager()
    deleted = manager.delete_campaign(campaign_name, delete_exports=True)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Campaña '{campaign_name}' no encontrada.")
    safe_name = manager.sanitize_name(campaign_name)
    try:
        ds = server.GoogleDriveStorage()
        if ds.is_connected():
            asyncio.create_task(run_in_threadpool(ds.delete_file, f"{safe_name}.json", "WhisperDnD"))
    except Exception as exc:
        print(f"[delete_campaign] Warning deleting from Drive: {exc}")
    return {"status": "deleted", "campaign": campaign_name}


@router.post("/api/campaigns")
@router.post("/api/campaigns/save")
async def create_or_init_campaign(payload: CreateCampaignRequest):
    """Create or load campaign state, optionally setting roster, DM, and prior lore."""
    manager = server.CampaignManager()
    state = manager.load_campaign(payload.campaign_name)
    modified = False

    dm_val = payload.dm or payload.dungeon_master or payload.dm_name
    if dm_val is not None:
        clean_dm = dm_val.strip()
        state["dm"] = clean_dm
        state["dungeon_master"] = clean_dm
        state["dm_name"] = clean_dm
        modified = True

    dm_discord_val = payload.dm_discord_id or payload.dm_discord_user_id or payload.dm_discord
    if dm_discord_val is not None:
        clean_disc = dm_discord_val.strip()
        state["dm_discord_id"] = clean_disc
        state["dm_discord_user_id"] = clean_disc
        state["dm_discord"] = clean_disc
        if payload.dm_discord_username:
            state["dm_discord_username"] = payload.dm_discord_username.strip()
        if payload.dm_discord_tag:
            state["dm_discord_tag"] = payload.dm_discord_tag.strip()
        modified = True

    if payload.roster is not None:
        incoming = [p.model_dump() for p in payload.roster]
        existing_roster = state.get("roster", [])

        def _roster_key(entry: dict) -> str:
            return f"{(entry.get('player_name') or '').strip().lower()}|{(entry.get('character_name') or '').strip().lower()}"

        existing_by_key = {
            _roster_key(e): e
            for e in existing_roster
            if (entry_p := (e.get("player_name") or "").strip()) or (e.get("character_name") or "").strip()
        }
        existing_by_player = {
            (e.get("player_name") or "").strip().lower(): e
            for e in existing_roster
            if (e.get("player_name") or "").strip()
        }

        merged_roster = []
        seen_keys = set()
        for new_entry in incoming:
            p_name = (new_entry.get("player_name") or "").strip()
            c_name = (new_entry.get("character_name") or "").strip()
            # Skip completely empty rows (no player name and no character name)
            if not p_name and not c_name:
                continue

            key = _roster_key(new_entry)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            # Match against existing by (player, character) or by player name to retain metadata (discord IDs, is_user_character, etc.)
            match = existing_by_key.get(key)
            if not match and p_name:
                match = existing_by_player.get(p_name.lower())

            if match:
                merged_entry = dict(match)
                for k, v in new_entry.items():
                    if v not in (None, "", [], {}):
                        merged_entry[k] = v
                merged_roster.append(merged_entry)
            else:
                merged_roster.append(new_entry)

        state["roster"] = merged_roster

        # Auto-sync DM info if DM row exists in roster
        dm_row = next(
            (r for r in state["roster"] if r.get("character_name") == "(DM)" or r.get("role") == "Dungeon Master (DM)"),
            None,
        )
        if dm_row:
            dm_p_name = (dm_row.get("player_name") or "").strip()
            if dm_p_name:
                state["dm"] = dm_p_name
                state["dungeon_master"] = dm_p_name
                state["dm_name"] = dm_p_name
            elif state.get("dm_name"):
                dm_row["player_name"] = state["dm_name"]

            dm_disc = (dm_row.get("discord_id") or dm_row.get("discord_user_id") or "").strip()
            if dm_disc:
                state["dm_discord_id"] = dm_disc
                state["dm_discord_user_id"] = dm_disc
                state["dm_discord"] = dm_disc
            elif state.get("dm_discord_id"):
                dm_row["discord_user_id"] = state["dm_discord_id"]
                dm_row["discord_id"] = state["dm_discord_id"]

            if dm_row.get("discord_username"):
                state["dm_discord_username"] = dm_row["discord_username"]
            if dm_row.get("discord_tag"):
                state["dm_discord_tag"] = dm_row["discord_tag"]
        elif state.get("dm_name") or state.get("dm_discord_id"):
            dm_row = {
                "player_name": state.get("dm_name") or state.get("dm") or "",
                "character_name": "(DM)",
                "species": "(N/A - DM)",
                "role": "Dungeon Master (DM)",
                "subclass": "N/A",
                "is_user_character": False,
                "discord_user_id": state.get("dm_discord_id") or "",
                "discord_id": state.get("dm_discord_id") or "",
            }
            state["roster"].insert(0, dm_row)
        modified = True


    if payload.prior_lore is not None and payload.prior_lore.strip():
        state["prior_lore"] = payload.prior_lore.strip()
        modified = True

    if modified:
        saved_path = manager.save_campaign(state)
        server.trigger_drive_sync_background([saved_path])
    return state


@router.put("/api/campaigns/{campaign_name}/prior-lore")
async def update_campaign_prior_lore(campaign_name: str, payload: UpdatePriorLoreRequest):
    """Update and persist prior lore for an ongoing campaign."""
    manager = server.CampaignManager()
    state = manager.set_prior_lore(campaign_name, payload.prior_lore)
    saved_path = manager.get_campaign_path(campaign_name)
    server.trigger_drive_sync_background([saved_path])
    return {
        "status": "success",
        "campaign_name": campaign_name,
        "prior_lore": state.get("prior_lore", ""),
        "campaign_state": state,
    }


class UpdateCharacterBackstoryRequest(BaseModel):
    backstory: str = Field(default="", description="Character backstory / personal history for coaching context")
    character_name: Optional[str] = Field(default=None, description="Character name to associate")
    is_user_character: Optional[bool] = Field(default=True, description="Whether to mark as primary user character")


@router.get("/api/characters")
async def list_all_characters():
    """List all player characters across campaigns."""
    manager = server.CampaignManager()
    return manager.get_all_characters()


@router.get("/api/campaigns/{campaign_name}/character-backstory")
async def get_campaign_character_backstory(campaign_name: str, character_name: Optional[str] = None):
    """Get the character backstory for a campaign or specific character."""
    manager = server.CampaignManager()
    backstory = manager.get_character_backstory(campaign_name, character_name=character_name)
    return {
        "status": "success",
        "campaign_name": campaign_name,
        "character_name": character_name,
        "backstory": backstory,
    }


@router.put("/api/campaigns/{campaign_name}/character-backstory")
async def update_campaign_character_backstory(campaign_name: str, payload: UpdateCharacterBackstoryRequest):
    """Update and persist the character backstory for a campaign."""
    manager = server.CampaignManager()
    is_user = True if payload.is_user_character is None else bool(payload.is_user_character)
    state = manager.set_character_backstory(
        campaign_name,
        payload.backstory,
        character_name=payload.character_name,
        is_user_character=is_user
    )
    saved_path = manager.get_campaign_path(campaign_name)
    server.trigger_drive_sync_background([saved_path])
    return {
        "status": "success",
        "campaign_name": campaign_name,
        "character_name": payload.character_name,
        "backstory": state.get("user_character_backstory", ""),
    }


@router.post("/api/campaigns/{campaign_name}/session")
async def process_campaign_session_endpoint(campaign_name: str, payload: ProcessCampaignSessionRequest):
    """Process a session transcript for a campaign."""
    roster_dicts = [p.model_dump() for p in payload.roster] if payload.roster else None
    try:
        result = server.process_session_for_campaign(
            campaign_name=campaign_name,
            transcript_text=payload.transcript_text,
            roster_dicts=roster_dicts,
            session_number=payload.session_number,
            custom_date=payload.custom_date,
            client_timezone_offset=payload.client_timezone_offset,
        )
        manager = server.CampaignManager()
        saved_path = manager.get_campaign_path(campaign_name)
        server.trigger_drive_sync_background([saved_path])
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error procesando sesión de campaña: {exc}") from exc


@router.post("/api/campaigns/{campaign_name}/finalize-npcs")
async def finalize_npcs(campaign_name: str, payload: FinalizeNpcsRequest):
    """Apply user spell-check name corrections to NPCs and re-export documents."""
    manager = server.CampaignManager()
    state = manager.load_campaign(campaign_name)
    for old_name, new_name in payload.name_corrections.items():
        if old_name and new_name and old_name != new_name:
            state = manager.update_npc_name(campaign_name, old_name, new_name)

    # Re-export documents with corrected names
    server.export_living_journal_docx(state)
    server.export_living_journal_md(state)

    # Re-export individual session chronicles
    for sess in state.get("sessions", []):
        try:
            server.export_session_docx(
                session_data=sess,
                campaign_name=state.get("campaign_name", campaign_name),
                roster=state.get("roster", []),
                include_coaching=True,
            )
            server.export_session_md(
                session_data=sess,
                campaign_name=state.get("campaign_name", campaign_name),
                roster=state.get("roster", []),
                include_coaching=True,
            )
        except Exception as e:
            print(f"[finalize_npcs] Warning re-exporting session {sess.get('session_number')}: {e}")

    saved_path = manager.get_campaign_path(campaign_name)
    server.trigger_drive_sync_background([saved_path])

    return {
        "status": "success",
        "message": f"Nombres de PNJs actualizados ({len(payload.name_corrections)} correcciones).",
        "campaign_state": state,
    }


@router.put("/api/campaigns/{campaign_name}/quests/{quest_id}/subobjective")
async def update_quest_subobjective(
    campaign_name: str,
    quest_id: str,
    payload: UpdateQuestSubobjectiveRequest,
):
    """Update quest subobjective status and re-export documents."""
    manager = server.CampaignManager()
    try:
        state = manager.update_quest_subobjective(
            name=campaign_name,
            quest_id=quest_id,
            subobjective_idx=payload.subobjective_idx,
            completed=payload.completed,
        )
        # Re-export documents
        server.export_living_journal_docx(state)
        server.export_living_journal_md(state)

        saved_path = manager.get_campaign_path(campaign_name)
        server.trigger_drive_sync_background([saved_path])

        return {
            "status": "success",
            "campaign_state": state,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/api/campaigns/{campaign_name}/quests/{quest_id}/status")
async def update_quest_status_endpoint(
    campaign_name: str,
    quest_id: str,
    payload: Optional[UpdateQuestStatusRequest] = None,
):
    """Toggle or set status of a quest (in_progress <-> completed) and re-export documents."""
    manager = server.CampaignManager()
    status_val = payload.status if payload else None
    try:
        state = manager.toggle_quest_status(
            name=campaign_name,
            quest_id=quest_id,
            status=status_val,
        )
        server.export_living_journal_docx(state)
        server.export_living_journal_md(state)

        saved_path = manager.get_campaign_path(campaign_name)
        server.trigger_drive_sync_background([saved_path])

        return {
            "status": "success",
            "campaign_state": state,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/campaigns/{campaign_name}/merge-entities")
async def merge_campaign_entities_endpoint(campaign_name: str, payload: MergeEntitiesRequest):
    """Manually merge two entities in a campaign."""
    manager = server.CampaignManager()
    try:
        merged = manager.merge_entities(
            campaign_name=campaign_name,
            source_name=payload.source_name,
            target_name=payload.target_name,
            entity_type=payload.entity_type or "pc",
            keep_name=payload.keep_name,
        )
        updated_state = manager.load_campaign(campaign_name)
        try:
            server.export_living_journal_docx(updated_state)
            server.export_living_journal_md(updated_state)
        except Exception:
            pass

        saved_path = manager.get_campaign_path(campaign_name)
        server.trigger_drive_sync_background([saved_path])

        return {
            "status": "success",
            "message": f"Se fusionó '{payload.source_name}' en '{payload.target_name}' correctamente.",
            "merged": merged,
            "campaign_state": updated_state,
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al fusionar entidades: {e}") from e


@router.put("/api/campaigns/{campaign_name}/npcs/{npc_name}")
async def update_campaign_npc_endpoint(campaign_name: str, npc_name: str, payload: UpdateNpcRequest):
    """Update an NPC's details (name, role, category, status) in a campaign."""
    manager = server.CampaignManager()
    decoded_npc_name = urllib.parse.unquote(npc_name)
    try:
        new_name_val = payload.new_name or payload.name
        updated_npc = manager.update_npc(
            campaign_name=campaign_name,
            npc_name=decoded_npc_name,
            new_name=new_name_val,
            role=payload.role,
            category=payload.category,
            status=payload.status,
            tipo=payload.tipo,
            aliases=payload.aliases,
            notes=payload.notes,
        )
        updated_state = manager.load_campaign(campaign_name)
        try:
            server.export_living_journal_docx(updated_state)
            server.export_living_journal_md(updated_state)
        except Exception:
            pass

        saved_path = manager.get_campaign_path(campaign_name)
        server.trigger_drive_sync_background([saved_path])

        return {
            "status": "success",
            "message": f"PNJ '{decoded_npc_name}' actualizado correctamente.",
            "npc": updated_npc,
            "campaign_state": updated_state,
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve)) from ve
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar PNJ: {e}") from e


@router.post("/api/campaigns/{campaign_name}/deduplicate")
async def deduplicate_campaign_endpoint(campaign_name: str):
    """Run retroactive entity deduplication on a campaign."""
    manager = server.CampaignManager()
    try:
        result = manager.deduplicate_campaign_entities(campaign_name)
        try:
            server.export_living_journal_docx(result["campaign_state"])
            server.export_living_journal_md(result["campaign_state"])
        except Exception:
            pass

        saved_path = manager.get_campaign_path(campaign_name)
        server.trigger_drive_sync_background([saved_path])

        return {
            "status": "success",
            "merged_count": result.get("merged_count", 0),
            "merged": result.get("merged", []),
            "campaign_state": result.get("campaign_state"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al deduplicar campaña: {e}") from e


@router.get("/api/campaigns/{campaign_name}/download-docx")
async def download_campaign_docx(campaign_name: str, include_coaching: bool = Query(True)):
    """Download the consolidated Word document for the campaign."""
    manager = server.CampaignManager()
    state = manager.load_campaign(campaign_name)
    docx_path = server.export_living_journal_docx(state, include_coaching=include_coaching)
    target = Path(docx_path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Archivo Grimorio docx no encontrado.")

    return FileResponse(
        path=target,
        filename=target.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/api/campaigns/{campaign_name}/session/{session_num}/download-docx")
async def download_session_docx(campaign_name: str, session_num: int, include_coaching: bool = Query(True)):
    """Download a single session chronicle as a standalone Word document."""
    manager = server.CampaignManager()
    state = manager.load_campaign(campaign_name)
    sessions = state.get("sessions", [])
    target_session = next((s for s in sessions if int(s.get("session_number", 0)) == int(session_num)), None)
    if not target_session and sessions:
        sorted_sessions = sorted(sessions, key=lambda s: int(s.get("session_number", 0)))
        latest_sess = sorted_sessions[-1]
        latest_num = int(latest_sess.get("session_number", 0))
        if len(sessions) == 1 or int(session_num) == latest_num + 1:
            target_session = latest_sess
    if not target_session:
        raise HTTPException(status_code=404, detail=f"Sesión #{session_num} no encontrada en la campaña '{campaign_name}'.")

    docx_path = server.export_session_docx(
        session_data=target_session,
        campaign_name=state.get("campaign_name", campaign_name),
        roster=state.get("roster", []),
        include_coaching=include_coaching,
    )
    target = Path(docx_path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Archivo de crónica de sesión docx no encontrado.")

    return FileResponse(
        path=target,
        filename=target.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/api/campaigns/{campaign_name}/session/{session_num}/download-md")
async def download_session_md(campaign_name: str, session_num: int, include_coaching: bool = Query(True)):
    """Download a single session chronicle as a standalone Markdown document."""
    manager = server.CampaignManager()
    state = manager.load_campaign(campaign_name)
    sessions = state.get("sessions", [])
    target_session = next((s for s in sessions if int(s.get("session_number", 0)) == int(session_num)), None)
    if not target_session and sessions:
        sorted_sessions = sorted(sessions, key=lambda s: int(s.get("session_number", 0)))
        latest_sess = sorted_sessions[-1]
        latest_num = int(latest_sess.get("session_number", 0))
        if len(sessions) == 1 or int(session_num) == latest_num + 1:
            target_session = latest_sess
    if not target_session:
        raise HTTPException(status_code=404, detail=f"Sesión #{session_num} no encontrada en la campaña '{campaign_name}'.")

    md_path = server.export_session_md(
        session_data=target_session,
        campaign_name=state.get("campaign_name", campaign_name),
        roster=state.get("roster", []),
        include_coaching=include_coaching,
    )
    target = Path(md_path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Archivo de crónica de sesión md no encontrado.")

    return FileResponse(
        path=target,
        filename=target.name,
        media_type="text/markdown",
    )


@router.get("/api/campaigns/{campaign_name}/download-md")
async def download_campaign_md(campaign_name: str):
    """Download the consolidated Markdown document for the campaign."""
    manager = server.CampaignManager()
    state = manager.load_campaign(campaign_name)
    md_path = server.export_living_journal_md(state)
    target = Path(md_path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Archivo Grimorio md no encontrado.")

    return FileResponse(
        path=target,
        filename=target.name,
        media_type="text/markdown",
    )


@router.get("/api/campaigns/{campaign_name}/export")
async def export_campaign_bundle(campaign_name: str):
    """
    Export the entire campaign as a portable ZIP bundle containing:
    1. campaign.json (Roster, DM, universal PCs, Discord bindings, quests, NPCs, locations, sessions metadata).
    2. outputs/ (Consolidated Markdown and Word Grimorios, individual session chronicles and raw transcripts).
    3. manifest.json (Metadata, versions and file index).
    Returns a downloadable ZIP file named Campaña_[Nombre]_[Fecha].zip.
    """
    manager = server.CampaignManager()
    state = None

    # Try direct / sanitized load first
    try:
        file_path = manager.get_campaign_path(campaign_name)
        if file_path.is_file():
            state = manager.load_campaign(campaign_name)
    except Exception:
        state = None

    if not state:
        # Search by campaign_id or case-insensitive name match
        for f in manager.campaigns_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if (
                    data.get("campaign_id") == campaign_name
                    or (data.get("campaign_name", "").strip().lower() == campaign_name.strip().lower())
                    or f.stem.lower() == manager.sanitize_name(campaign_name).lower()
                ):
                    state = data
                    break
            except Exception:
                continue

    if not state:
        raise HTTPException(
            status_code=404,
            detail=f"Campaña '{campaign_name}' no encontrada para exportar."
        )

    real_campaign_name = state.get("campaign_name", campaign_name)
    safe_name = manager.sanitize_name(real_campaign_name)
    now_dt = datetime.datetime.now()
    date_str = now_dt.strftime("%Y-%m-%d")

    # Build ZIP in-memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. campaign.json
        campaign_json_bytes = json.dumps(state, indent=2, ensure_ascii=False).encode("utf-8")
        zf.writestr("campaign.json", campaign_json_bytes)

        # 2. Collect session and output files from output dir
        output_dir = server.get_data_output_dir()
        included_files = ["campaign.json"]

        # Consolidated grimorio files
        grimorio_md_path = output_dir / f"{safe_name}_grimorio.md"
        if grimorio_md_path.is_file():
            zf.write(grimorio_md_path, arcname=f"outputs/{grimorio_md_path.name}")
            included_files.append(f"outputs/{grimorio_md_path.name}")
        else:
            try:
                md_path_str = server.export_living_journal_md(state)
                gen_path = Path(md_path_str)
                if gen_path.is_file():
                    zf.write(gen_path, arcname=f"outputs/{gen_path.name}")
                    included_files.append(f"outputs/{gen_path.name}")
            except Exception as e:
                print(f"[export_campaign] Warning generating md: {e}")

        grimorio_docx_path = output_dir / f"{safe_name}_grimorio.docx"
        if grimorio_docx_path.is_file():
            zf.write(grimorio_docx_path, arcname=f"outputs/{grimorio_docx_path.name}")
            included_files.append(f"outputs/{grimorio_docx_path.name}")
        else:
            try:
                docx_path_str = server.export_living_journal_docx(state)
                gen_docx = Path(docx_path_str)
                if gen_docx.is_file():
                    zf.write(gen_docx, arcname=f"outputs/{gen_docx.name}")
                    included_files.append(f"outputs/{gen_docx.name}")
            except Exception as e:
                print(f"[export_campaign] Warning generating docx: {e}")

        # Individual transcripts & chronicles matching pattern
        for f in output_dir.glob(f"{safe_name}_*"):
            if f.is_file() and f.suffix in [".txt", ".md", ".docx"]:
                arc_name = f"outputs/{f.name}"
                if arc_name not in included_files:
                    zf.write(f, arcname=arc_name)
                    included_files.append(arc_name)

        # Ensure every session in state has individual chronicle & transcript preserved
        for sess in state.get("sessions", []):
            s_num = sess.get("session_number", 0)
            c_md = sess.get("chronicle_markdown") or sess.get("chronicle_text")
            if c_md:
                c_arc = f"sessions/sesion_{s_num}_cronica.md"
                if c_arc not in included_files:
                    zf.writestr(c_arc, c_md.encode("utf-8"))
                    included_files.append(c_arc)
            raw_t = sess.get("raw_transcript") or sess.get("transcript")
            if raw_t:
                t_arc = f"sessions/sesion_{s_num}_transcripcion.txt"
                if t_arc not in included_files:
                    zf.writestr(t_arc, raw_t.encode("utf-8"))
                    included_files.append(t_arc)

        # 3. manifest.json
        manifest = {
            "format": "WhisperDnD_Campaign_Bundle",
            "version": "1.0",
            "exported_at": now_dt.isoformat(),
            "campaign_name": real_campaign_name,
            "campaign_id": state.get("campaign_id", safe_name),
            "dungeon_master": state.get("dm_name") or state.get("dm") or state.get("dungeon_master") or "",
            "dungeon_master_discord": state.get("dm_discord_id") or "",
            "sessions_count": len(state.get("sessions", [])),
            "npcs_count": len(state.get("npcs", [])),
            "quests_count": len(state.get("quests", [])),
            "locations_count": len(state.get("locations", [])),
            "pcs_count": len(state.get("universal_pcs", [])),
            "files": included_files,
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"))

    zip_bytes = zip_buffer.getvalue()

    # Filename format: Campaña_[Nombre]_[Fecha].zip
    clean_title = re.sub(r'[^\w\-]', '_', real_campaign_name).strip('_') or "Principal"
    zip_filename = f"Campaña_{clean_title}_{date_str}.zip"
    ascii_filename = f"Campana_{clean_title}_{date_str}.zip"
    encoded_filename = urllib.parse.quote(zip_filename)

    headers = {
        "Content-Disposition": f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}',
        "Content-Type": "application/zip",
        "Cache-Control": "no-cache",
    }
    return Response(content=zip_bytes, media_type="application/zip", headers=headers)


@router.post("/api/campaigns/import")
async def import_campaign_bundle(
    file: UploadFile = File(...),
):
    """
    Import a full campaign bundle from a .zip or .json file.
    Restores the campaign configuration, roster, wiki entities, session chronicles,
    and transcripts into server directories (data/campaigns/ and data/output/).
    If Google Drive is connected, automatically uploads a backup copy to Google Drive.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No se proporcionó ningún archivo para importar.")

    fname = file.filename.lower()
    if not (fname.endswith(".zip") or fname.endswith(".json")):
        raise HTTPException(
            status_code=400,
            detail="Formato no compatible. Por favor sube un archivo .zip o .json de campaña."
        )

    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(status_code=400, detail="El archivo subido está vacío.")

    manager = server.CampaignManager()
    camp_dir = server.get_data_campaigns_dir()
    out_dir = server.get_data_output_dir()
    wiki_dir = camp_dir / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)

    campaign_state = None
    files_restored = 0

    if fname.endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(content_bytes), "r") as zf:
                namelist = zf.namelist()

                # Look for campaign.json first, or any top-level json with campaign fields
                campaign_json_entry = None
                if "campaign.json" in namelist:
                    campaign_json_entry = "campaign.json"
                else:
                    for name in namelist:
                        if name.endswith(".json") and not name.endswith("manifest.json"):
                            try:
                                candidate = json.loads(zf.read(name).decode("utf-8"))
                                if isinstance(candidate, dict) and (
                                    "campaign_name" in candidate
                                    or "universal_pcs" in candidate
                                    or "sessions" in candidate
                                ):
                                    campaign_json_entry = name
                                    campaign_state = candidate
                                    break
                            except Exception:
                                continue

                if not campaign_state and campaign_json_entry:
                    campaign_state = json.loads(zf.read(campaign_json_entry).decode("utf-8"))

                if not campaign_state:
                    raise HTTPException(
                        status_code=400,
                        detail="El archivo ZIP no contiene una estructura válida de campaña (campaign.json)."
                    )

                c_name = campaign_state.get("campaign_name")
                if not c_name:
                    c_name = Path(file.filename).stem.replace("Campaña_", "").replace("Campana_", "") or "Campaña Importada"
                    campaign_state["campaign_name"] = c_name

                safe_name = manager.sanitize_name(c_name)

                # Save main campaign state
                target_json_path = camp_dir / f"{safe_name}.json"
                target_json_path.write_bytes(json.dumps(campaign_state, indent=2, ensure_ascii=False).encode("utf-8"))
                files_restored += 1

                # Extract outputs, sessions, and wiki files
                for item in namelist:
                    if item.endswith("/") or item in ["campaign.json", "manifest.json"]:
                        continue
                    item_data = zf.read(item)
                    item_path = Path(item)
                    item_name = item_path.name

                    # If inside wiki/
                    if item.startswith("wiki/"):
                        (wiki_dir / item_name).write_bytes(item_data)
                        files_restored += 1
                    # If inside outputs/ or sessions/ or standalone output document
                    elif item.startswith("outputs/") or item.startswith("sessions/") or item.endswith((".md", ".docx", ".txt")):
                        (out_dir / item_name).write_bytes(item_data)
                        files_restored += 1

        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="El archivo ZIP está dañado o no es válido.")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error descomprimiendo el archivo: {str(e)}")

    else:
        # Single .json file
        try:
            parsed = json.loads(content_bytes.decode("utf-8"))
            if not isinstance(parsed, dict) or not (
                "campaign_name" in parsed
                or "universal_pcs" in parsed
                or "sessions" in parsed
                or "roster" in parsed
            ):
                raise HTTPException(
                    status_code=400,
                    detail="El archivo JSON no contiene una estructura de campaña de WhisperDnD válida."
                )
            campaign_state = parsed
            c_name = campaign_state.get("campaign_name")
            if not c_name:
                c_name = Path(file.filename).stem or "Campaña Importada"
                campaign_state["campaign_name"] = c_name

            safe_name = manager.sanitize_name(c_name)
            target_json_path = camp_dir / f"{safe_name}.json"
            target_json_path.write_bytes(json.dumps(campaign_state, indent=2, ensure_ascii=False).encode("utf-8"))
            files_restored += 1
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="El archivo JSON está mal formado o no es válido.")

    # Re-export fresh unified living grimorio documents (.md and .docx) if possible
    c_name = campaign_state.get("campaign_name", "Campaña")
    safe_name = manager.sanitize_name(c_name)
    try:
        server.export_living_journal_md(campaign_state)
    except Exception as e:
        print(f"[import_campaign] Warning generating md: {e}")
    try:
        server.export_living_journal_docx(campaign_state)
    except Exception as e:
        print(f"[import_campaign] Warning generating docx: {e}")

    # Also restore individual session transcript files if not already written
    for sess in campaign_state.get("sessions", []):
        s_num = sess.get("session_number")
        raw_t = sess.get("raw_transcript") or sess.get("transcript")
        if s_num is not None and raw_t:
            t_file = out_dir / f"{safe_name}_sesion_{s_num}_transcripcion.txt"
            if not t_file.is_file():
                try:
                    t_file.write_text(raw_t, encoding="utf-8")
                    files_restored += 1
                except Exception:
                    pass

    # If Google Drive is connected, upload backup copy to Google Drive automatically
    drive_uploaded = False
    try:
        drive_storage = server.GoogleDriveStorage()
        if drive_storage.is_connected():
            target_json_path = camp_dir / f"{safe_name}.json"
            asyncio.create_task(
                run_in_threadpool(
                    drive_storage.upload_file,
                    str(target_json_path.resolve()),
                    "WhisperDnD",
                )
            )
            drive_uploaded = True
    except Exception as e:
        print(f"[import_campaign] Warning backing up to Drive: {e}")

    sess_count = len(campaign_state.get("sessions", []))
    npcs_count = len(campaign_state.get("npcs", []))
    pcs_count = len(campaign_state.get("universal_pcs", []))

    msg = f"Campaña '{c_name}' importada exitosamente con {sess_count} sesiones, {pcs_count} protagonistas y {npcs_count} PNJs."
    if drive_uploaded:
        msg += " Respaldo en Google Drive sincronizado automáticamente."

    return {
        "status": "success",
        "campaign_name": c_name,
        "campaign_id": campaign_state.get("campaign_id", safe_name),
        "sessions_count": sess_count,
        "files_restored": files_restored,
        "drive_backup": drive_uploaded,
        "message": msg,
    }


@router.get("/api/download/transcript/{filename}")
async def download_transcript_txt(filename: str):
    """Download a standalone plain-text transcript file."""
    safe_filename = Path(filename).name
    if not safe_filename or safe_filename.startswith("."):
        raise HTTPException(status_code=400, detail="Nombre de archivo no válido.")

    file_path = server.get_data_output_dir() / safe_filename
    if not file_path.is_file() and not safe_filename.endswith(".txt"):
        alt_path = server.get_data_output_dir() / f"{safe_filename}.txt"
        if alt_path.is_file():
            file_path = alt_path
            safe_filename = alt_path.name

    if not file_path.is_file():
        m = re.match(r"^(.+)_sesion_(\d+)_transcripcion\.txt$", safe_filename)
        if m:
            camp_name, sess_num = m.group(1), int(m.group(2))
            mgr = server.CampaignManager()
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


@router.get("/api/download/audio/{filename}")
async def download_audio_file(filename: str):
    """Download a recorded audio WAV file."""
    safe_filename = Path(filename).name
    if not safe_filename or safe_filename.startswith("."):
        raise HTTPException(status_code=400, detail="Nombre de archivo no válido.")

    file_path = server.get_data_input_dir() / safe_filename
    if not file_path.is_file():
        file_path = server.get_data_output_dir() / safe_filename

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Audio '{safe_filename}' no encontrado en el servidor.")

    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type="audio/wav",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


@router.post("/api/campaigns/{campaign_name}/export-drive", response_model=server.DriveExportResponse)
async def export_campaign_to_drive(campaign_name: str):
    """Upload the campaign Grimorio .docx to Google Drive folder 'Whisper AI - Transcripciones'."""
    manager = server.CampaignManager()
    state = manager.load_campaign(campaign_name)
    docx_path = server.export_living_journal_docx(state)
    target_file = Path(docx_path)
    if not target_file.is_file():
        raise HTTPException(status_code=404, detail=f"Grimorio docx no encontrado para campaña {campaign_name}.")

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


