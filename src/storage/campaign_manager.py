"""Campaign manager for Living Campaign Journal persistence and continuity."""

import datetime
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def is_npc_name_match(name1: str, name2: str) -> bool:
    """
    Smart NPC name matching with surname and full-name expansion detection.
    Matches:
      - Exact matches (case-insensitive)
      - Surname expansions (e.g. 'Fothark Vanessa' vs 'Fothark Vanessa Halovar')
      - Core name vs full name (e.g. 'Thiazi' vs 'Thiazi Coldbreaker')
    Does NOT match:
      - Different unnamed NPCs (e.g. '[Sin nombre] Guardia norte' vs '[Sin nombre] Guardia sur')
      - Unrelated NPCs sharing common words (e.g. 'John Smith' vs 'John Doe')
      - Very short tokens (< 4 chars) unless exact
    """
    n1 = (name1 or "").strip()
    n2 = (name2 or "").strip()
    if not n1 or not n2:
        return False

    l1 = n1.lower()
    l2 = n2.lower()
    if l1 == l2:
        return True

    # Unnamed / descriptor characters must match identically
    if "[" in l1 or "[" in l2 or "sin nombre" in l1 or "sin nombre" in l2 or "unnamed" in l1 or "unnamed" in l2:
        return l1 == l2

    clean1 = re.sub(r"[^\w\s]", "", l1)
    clean2 = re.sub(r"[^\w\s]", "", l2)
    if clean1 == clean2:
        return True

    tokens1 = [t for t in clean1.split() if t]
    tokens2 = [t for t in clean2.split() if t]
    if not tokens1 or not tokens2:
        return False

    set1 = set(tokens1)
    set2 = set(tokens2)

    # Identical set of tokens (e.g. "Vanessa Fothark" vs "Fothark Vanessa")
    if set1 == set2:
        return True

    generic_titles = {
        "lord", "lady", "sir", "dame", "king", "queen", "rey", "reina",
        "captain", "capitán", "capitan", "guard", "guardia", "soldier", "soldado",
        "master", "dm", "el", "la", "los", "las", "the", "de", "del", "of"
    }

    # If both have multi-word names and one is a subset of the other:
    # e.g. "Fothark Vanessa" is a subset of "Fothark Vanessa Halovar"
    if len(tokens1) >= 2 and len(tokens2) >= 2:
        non_generic1 = set1 - generic_titles
        non_generic2 = set2 - generic_titles
        if non_generic1 and non_generic2:
            if non_generic1.issubset(non_generic2) or non_generic2.issubset(non_generic1):
                return True

    # If one is a single token (e.g. "Thiazi" vs "Thiazi Coldbreaker"):
    shorter_tokens, longer_tokens = (tokens1, tokens2) if len(tokens1) <= len(tokens2) else (tokens2, tokens1)
    if len(shorter_tokens) == 1:
        st = shorter_tokens[0]
        if len(st) >= 4 and st not in generic_titles:
            if st in longer_tokens:
                return True

    return False


def purge_session_data(campaign_data: dict, session_num: int) -> dict:
    """
    Explicitly purge session records, milestones, and quest completion tags
    for a specific session number before recording new data.
    Uses bilingual regex matching for both Spanish and English milestones.
    """
    # 1. Purge from sessions list (handling int or str)
    campaign_data["sessions"] = [
        s for s in campaign_data.get("sessions", []) 
        if str(s.get("session_number")) != str(session_num)
    ]
    
    # 2. Purge milestones for that specific session (bilingual: Sesión #N, Session #N, etc.)
    milestone_regex = re.compile(rf"^(sesi[oó]n|session)\s*#?{session_num}\s*:", re.IGNORECASE)
    for pc in campaign_data.get("universal_pcs", []):
        pc["hitos_acumulados"] = [
            h for h in pc.get("hitos_acumulados", []) 
            if not milestone_regex.match(str(h).strip())
        ]
        
    # 3. Purge quest milestone tags matching this session
    for q in campaign_data.get("quests", []):
        if str(q.get("completed_session")) == str(session_num):
            q["completed_session"] = None
            q["status"] = "in_progress"

    return campaign_data


class CampaignManager:
    """Manages multi-session D&D campaign states, quests, NPCs, and session history."""

    def __init__(self, campaigns_dir: Optional[str] = None):
        if campaigns_dir:
            self.campaigns_dir = Path(campaigns_dir).resolve()
        elif os.environ.get("WHISPER_CAMPAIGNS_DIR"):
            self.campaigns_dir = Path(os.environ["WHISPER_CAMPAIGNS_DIR"]).resolve()
        else:
            project_root = Path(__file__).resolve().parent.parent.parent
            self.campaigns_dir = project_root / "data" / "campaigns"

        self.campaigns_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sanitize_name(name: str) -> str:
        """Convert a campaign name into a safe filename."""
        clean = re.sub(r'[\\/*?:"<>|]', "", name.strip())
        clean = re.sub(r"\s+", "_", clean).lower()
        return clean or "campana_principal"

    def get_campaign_path(self, name: str) -> Path:
        """Return the JSON file path for a campaign name."""
        filename = f"{self.sanitize_name(name)}.json"
        return self.campaigns_dir / filename

    def list_campaigns(self) -> List[Dict[str, Any]]:
        """List all existing campaigns with high-level statistics."""
        campaigns = []
        for file in self.campaigns_dir.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                name = data.get("campaign_name") or file.stem
                sessions = data.get("sessions", [])
                sessions_count = len(sessions)
                try:
                    mtime_iso = datetime.datetime.fromtimestamp(file.stat().st_mtime).isoformat()
                except Exception:
                    mtime_iso = ""
                last_updated = data.get("updated_at") or data.get("created_at") or mtime_iso

                campaigns.append({
                    "name": name,
                    "campaign_name": name,
                    "sessions_count": sessions_count,
                    "last_updated": last_updated,
                    "filename": file.name,
                    "last_session": data.get("last_session", 0),
                    "total_quests": len(data.get("quests", [])),
                    "active_quests": sum(1 for q in data.get("quests", []) if q.get("status") != "completed"),
                    "total_npcs": len(data.get("npcs", [])),
                    "total_sessions": sessions_count,
                    "updated_at": last_updated,
                    "prior_lore": data.get("prior_lore", ""),
                })
            except Exception as exc:
                print(f"[CampaignManager] Error reading {file}: {exc}")
        return sorted(campaigns, key=lambda c: str(c.get("name", "")).lower())

    def delete_campaign(self, name: str, delete_exports: bool = True) -> bool:
        """
        Delete the campaign JSON file and optionally associated export files in data/output/.
        Returns True if campaign file was found and deleted, False otherwise.
        """
        deleted = False
        target_path = self.get_campaign_path(name)
        if target_path.is_file():
            try:
                target_path.unlink()
                deleted = True
            except Exception as e:
                print(f"[CampaignManager] Error deleting {target_path}: {e}")

        # If not matched by exact sanitized path, search case-insensitively among json files
        if not deleted:
            sanitized = self.sanitize_name(name).lower()
            name_clean = name.strip().lower()
            for file in self.campaigns_dir.glob("*.json"):
                if file.stem.lower() in (sanitized, name_clean):
                    try:
                        file.unlink()
                        deleted = True
                        break
                    except Exception as e:
                        print(f"[CampaignManager] Error deleting {file}: {e}")
                else:
                    try:
                        data = json.loads(file.read_text(encoding="utf-8"))
                        if str(data.get("campaign_name", "")).strip().lower() == name_clean:
                            file.unlink()
                            deleted = True
                            break
                    except Exception:
                        pass

        # Optionally delete exports in output directory
        if delete_exports:
            output_dir = Path(os.environ["WHISPER_OUTPUT_DIR"]).resolve() if os.environ.get("WHISPER_OUTPUT_DIR") else (self.campaigns_dir.parent / "output")
            if output_dir.is_dir():
                safe_name = re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_').lower()
                sanitized_name = self.sanitize_name(name).lower()
                for exp_file in output_dir.glob("*"):
                    fname = exp_file.name.lower()
                    if (
                        f"{safe_name}_grimorio" in fname
                        or f"{sanitized_name}_grimorio" in fname
                        or (safe_name and safe_name in fname and ("grimorio" in fname or exp_file.suffix in (".docx", ".md")))
                    ):
                        try:
                            exp_file.unlink()
                        except Exception as e:
                            print(f"[CampaignManager] Error deleting export file {exp_file}: {e}")

        return deleted

    def load_campaign(self, name: str) -> Dict[str, Any]:
        """
        Load campaign state from disk.
        If it does not exist, initialize a clean default state.
        """
        file_path = self.get_campaign_path(name)
        if file_path.is_file():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                if "universal_pcs" not in data:
                    data["universal_pcs"] = []
                if "prior_lore" not in data:
                    data["prior_lore"] = ""
                return data
            except Exception as exc:
                print(f"[CampaignManager] Error loading {file_path}: {exc}. Initializing fallback.")

        now_iso = datetime.datetime.now().isoformat()
        initial_state: Dict[str, Any] = {
            "campaign_name": name.strip() or "Campaña Principal",
            "campaign_id": self.sanitize_name(name),
            "created_at": now_iso,
            "updated_at": now_iso,
            "last_session": 0,
            "prior_lore": "",
            "roster": [],
            "universal_pcs": [],
            "quests": [],
            "npcs": [],
            "sessions": [],
        }
        return initial_state

    def save_campaign(self, state: Dict[str, Any]) -> Path:
        """Save campaign state to disk."""
        name = state.get("campaign_name", "Campaña Principal")
        state["updated_at"] = datetime.datetime.now().isoformat()
        if "campaign_id" not in state:
            state["campaign_id"] = self.sanitize_name(name)

        file_path = self.get_campaign_path(name)
        file_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        return file_path

    def set_prior_lore(self, name: str, prior_lore: str) -> Dict[str, Any]:
        """Update and persist prior lore for an ongoing campaign."""
        state = self.load_campaign(name)
        state["prior_lore"] = (prior_lore or "").strip()
        self.save_campaign(state)
        return state

    def get_active_context(self, name: str) -> Dict[str, Any]:
        """
        Extract active context for multi-session prompting in Gemini:
        - Active quests
        - Known NPCs
        - Party roster
        - Session number
        - Previous recap
        - Prior lore
        """
        state = self.load_campaign(name)
        last_session = state.get("last_session", 0)
        next_session = last_session + 1
        active_quests = [q for q in state.get("quests", []) if q.get("status") != "completed"]

        last_recap = ""
        if state.get("sessions"):
            last_recap = state["sessions"][-1].get("recap_text", "")

        return {
            "campaign_name": state.get("campaign_name", name),
            "last_session": last_session,
            "session_number": next_session,
            "prior_lore": state.get("prior_lore", ""),
            "active_quests": active_quests,
            "all_quests": state.get("quests", []),
            "known_npcs": state.get("npcs", []),
            "roster": state.get("roster", []),
            "universal_pcs": state.get("universal_pcs", []),
            "last_session_recap": last_recap,
        }

    def purge_session_data(self, campaign_data: dict, session_num: int) -> dict:
        """Purge all existing records, milestones, and quest completion tags for a specific session number."""
        return purge_session_data(campaign_data, session_num)

    def record_session(
        self,
        name: str,
        session_chapter: Dict[str, Any],
        updated_quests: Optional[List[Dict[str, Any]]] = None,
        updated_npcs: Optional[List[Dict[str, Any]]] = None,
        detected_npc_names: Optional[List[str]] = None,
        roster: Optional[List[Dict[str, str]]] = None,
        session_number: Optional[int] = None,
        detected_party: Optional[List[Dict[str, Any]]] = None,
        user_character: Optional[Dict[str, Any]] = None,
        detected_pcs: Optional[List[Dict[str, Any]]] = None,
        is_youtube: bool = False,
        chronicle_markdown: Optional[str] = None,
        raw_transcript: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record a new session chapter and merge cumulative Quest and NPC updates into campaign state.
        """
        state = self.load_campaign(name)
        actual_session_num = session_number or (state.get("last_session", 0) + 1)
        state["last_session"] = max(state.get("last_session", 0), actual_session_num)

        # Explicit Pre-Execution Purge on Re-Record (bilingual: Sesión #N, Session #N)
        self.purge_session_data(state, actual_session_num)

        is_private = (name or "").strip().lower() in ("campaña principal", "campana principal")

        if detected_pcs:
            state["detected_pcs"] = detected_pcs
        if detected_party:
            state["detected_party"] = detected_party

        pcs_as_roster = []
        for p in (detected_pcs or []):
            pcs_as_roster.append({
                "player_name": p.get("jugador") or p.get("player_name") or "-",
                "character_name": p.get("personaje") or p.get("character_name") or "-",
                "species": p.get("especie") or p.get("species") or "-",
                "role": p.get("clase") or p.get("role") or "-",
                "subclass": p.get("subclase") or p.get("subclass") or "-",
            })
        fallback_party = pcs_as_roster if pcs_as_roster else detected_party

        is_yt_campaign = is_youtube or (not is_private and ("youtube" in name.lower() or any("youtube" in str(s.get("source", "")).lower() for s in state.get("sessions", []))))

        if is_yt_campaign:
            # Detect DM if present
            detected_dm_name = None
            for n in (updated_npcs or []):
                n_name = str(n.get("name", "")).strip()
                n_role = str(n.get("role", "")).strip().lower()
                if "brennan" in n_name.lower():
                    detected_dm_name = "Brennan Lee Mulligan"
                    break
                elif "dungeon master" in n_role or n_role in ("dm", "(dm)", "narrador"):
                    detected_dm_name = n_name
                    break

            if not detected_dm_name:
                for n_name in (detected_npc_names or []):
                    if "brennan" in str(n_name).lower():
                        detected_dm_name = "Brennan Lee Mulligan"
                        break

            if not detected_dm_name:
                ch_context = f"{session_chapter.get('title', '')} {session_chapter.get('chronicle_text', '')} {session_chapter.get('episode_synopsis', '')}".lower()
                if "brennan lee mulligan" in ch_context or "brennan" in ch_context:
                    detected_dm_name = "Brennan Lee Mulligan"

            if not detected_dm_name:
                for candidate_list in (detected_party, detected_pcs, roster):
                    for p in (candidate_list or []):
                        pl_name = str(p.get("player_name") or p.get("jugador") or "").strip()
                        ch_name = str(p.get("character_name") or p.get("personaje") or "").strip()
                        rl_name = str(p.get("role") or p.get("clase") or "").strip().lower()
                        if "brennan" in pl_name.lower() or "brennan" in ch_name.lower():
                            detected_dm_name = "Brennan Lee Mulligan"
                            break
                        elif ("dungeon master" in rl_name or rl_name in ("dm", "(dm)", "narrador") or ch_name.lower() in ("(dm)", "dm", "dungeon master")) and pl_name not in ("-", "", "Rodrigo", "Markus", "Liam O'Brien", "Liam"):
                            detected_dm_name = pl_name
                            break
                    if detected_dm_name:
                        break

            # Filter and sanitize Player Characters
            candidate_pcs = fallback_party or roster or []
            clean_pcs = []
            for p in candidate_pcs:
                pl_name = str(p.get("player_name") or p.get("jugador") or "-").strip()
                ch_name = str(p.get("character_name") or p.get("personaje") or "-").strip()
                ch_role = str(p.get("role") or p.get("clase") or "-").strip()
                ch_species = str(p.get("species") or p.get("especie") or "-").strip()
                ch_sub = str(p.get("subclass") or p.get("subclase") or "-").strip()

                # Ensure Liam O'Brien is strictly stored as a Player Character (never dropped as mock DM)
                if "liam" in pl_name.lower():
                    pl_name = "Liam O'Brien"
                    if not ch_name or ch_name.lower() in ("(dm)", "dm", "dungeon master", "-", "(n/a - dm)", "n/a"):
                        ch_name = "Halendiel 'Hal' Fang"
                    if not ch_species or ch_species in ("-", "(N/A - DM)", "N/A", "Desconocido"):
                        ch_species = "Orc"
                    if not ch_role or ch_role.lower() in ("dungeon master (dm)", "dm", "dungeon master", "narrador", "-"):
                        ch_role = "Bard"
                elif "halendiel" in ch_name.lower():
                    if pl_name in ("-", ""):
                        pl_name = "Liam O'Brien"
                    if ch_role.lower() in ("dungeon master (dm)", "dm", "dungeon master", "narrador", "-"):
                        ch_role = "Bard"
                # Filter out mock / placeholder DM entries
                elif (
                    ch_name.lower() in ("(dm)", "dm", "dungeon master", "(n/a - dm)", "n/a", "-")
                    or ch_role.lower() in ("dungeon master (dm)", "dm", "dungeon master", "narrador")
                    or (pl_name in ("Rodrigo", "Markus") and ch_name.lower() in ("(dm)", "dm"))
                ):
                    continue

                clean_pcs.append({
                    "player_name": pl_name,
                    "character_name": ch_name,
                    "species": ch_species,
                    "role": ch_role,
                    "subclass": ch_sub,
                })

            new_roster = []
            if detected_dm_name:
                new_roster.append({
                    "player_name": detected_dm_name,
                    "character_name": "(DM)",
                    "species": "(N/A - DM)",
                    "role": "Dungeon Master (DM)",
                    "subclass": "-",
                })
            new_roster.extend(clean_pcs)
            state["roster"] = new_roster
        elif roster and len(roster) > 0:
            # If external campaign and roster mistakenly has Markus Veyl, replace with detected party
            if not is_private and fallback_party and any("markus" in str(p.get("character_name", "")).lower() or "markus" in str(p.get("player_name", "")).lower() for p in roster):
                state["roster"] = fallback_party
            else:
                state["roster"] = roster
        elif fallback_party:
            state["roster"] = fallback_party

        # 1. Merge or append session chapter
        user_char = user_character or session_chapter.get("user_character")
        recap_text = (session_chapter.get("next_session_script") or session_chapter.get("recap_text") or "").strip()
        synopsis_text = (session_chapter.get("episode_synopsis") or "").strip()
        coaching = (session_chapter.get("user_coaching") or session_chapter.get("markus_coaching") or "").strip()

        chapter_record = {
            "session_number": actual_session_num,
            "date": datetime.datetime.now().strftime("%d/%m/%Y"),
            "title": session_chapter.get("title", f"Sesión {actual_session_num}"),
            "recap_text": recap_text,
            "next_session_script": recap_text,
            "episode_synopsis": synopsis_text,
            "chronicle_text": session_chapter.get("chronicle_text", "").strip(),
            "closing_expectations": session_chapter.get("closing_expectations", "").strip(),
            "user_coaching": coaching,
            "markus_coaching": coaching,
            "user_character": user_char or {},
            "detected_npc_names": detected_npc_names or [],
            "detected_party": detected_party or [],
            "detected_pcs": detected_pcs or [],
            "chronicle_markdown": (chronicle_markdown or session_chapter.get("chronicle_markdown") or "").strip(),
            "raw_transcript": (raw_transcript or session_chapter.get("raw_transcript") or session_chapter.get("transcript", "")).strip(),
        }

        # True replacement: filter out any existing session entry with actual_session_num (no duplicates)
        filtered_sessions = [
            s for s in state.get("sessions", [])
            if str(s.get("session_number")) != str(actual_session_num)
        ]
        filtered_sessions.append(chapter_record)
        filtered_sessions.sort(key=lambda s: int(s.get("session_number", 0)) if str(s.get("session_number", 0)).isdigit() else 0)
        state["sessions"] = filtered_sessions

        # 2. Merge quests
        if updated_quests:
            existing_quests = state.setdefault("quests", [])
            for uq in updated_quests:
                q_id = uq.get("id", "").strip().lower()
                q_title = uq.get("title", "").strip()

                # Find match by id or title
                target_q = None
                if q_id:
                    target_q = next((q for q in existing_quests if q.get("id", "").lower() == q_id), None)
                if not target_q and q_title:
                    target_q = next((q for q in existing_quests if q.get("title", "").lower() == q_title.lower()), None)

                if target_q:
                    # Update existing quest
                    if uq.get("tipo"):
                        target_q["tipo"] = uq["tipo"]
                    if uq.get("status"):
                        target_q["status"] = uq["status"]
                    if uq.get("context"):
                        target_q["context"] = uq["context"]
                    if uq.get("status") in ("completed", "failed") and not target_q.get("completed_session"):
                        target_q["completed_session"] = actual_session_num

                    # Merge subobjectives ensuring unique correlative IDs
                    if uq.get("subobjectives"):
                        existing_sub = {sub["text"].strip().lower(): sub for sub in target_q.get("subobjectives", [])}
                        existing_ids = {sub.get("id") for sub in target_q.get("subobjectives", []) if sub.get("id")}
                        for new_sub in uq["subobjectives"]:
                            sub_text = new_sub.get("text", "").strip()
                            key = sub_text.lower()
                            if key in existing_sub:
                                existing_sub[key]["completed"] = new_sub.get("completed", False)
                            else:
                                sub_id = new_sub.get("id")
                                if not sub_id or sub_id in existing_ids:
                                    next_num = len(target_q.get("subobjectives", [])) + 1
                                    while f"s{next_num}" in existing_ids:
                                        next_num += 1
                                    sub_id = f"s{next_num}"
                                existing_ids.add(sub_id)
                                target_q.setdefault("subobjectives", []).append({
                                    "id": sub_id,
                                    "text": sub_text,
                                    "completed": new_sub.get("completed", False),
                                })

                    # Update lifecycle notes
                    lifecycle = target_q.get("lifecycle_notes", "")
                    if uq.get("status") == "failed":
                        step_note = f"Fracasada en Sesión {actual_session_num}"
                    elif uq.get("status") == "completed":
                        step_note = f"Completada en Sesión {actual_session_num}"
                    else:
                        step_note = f"Progreso en Sesión {actual_session_num}"
                    if step_note not in lifecycle:
                        target_q["lifecycle_notes"] = f"{lifecycle} | {step_note}".strip(" |")
                else:
                    # Add as new quest
                    new_id = q_id or f"q{len(existing_quests) + 1}"
                    is_closed = uq.get("status") in ("completed", "failed")
                    lifecycle = f"Iniciada en Sesión {actual_session_num}"
                    if uq.get("status") == "failed":
                        lifecycle += f" | Fracasada en Sesión {actual_session_num}"
                    elif uq.get("status") == "completed":
                        lifecycle += f" | Completada en Sesión {actual_session_num}"

                    new_subs = []
                    used_sub_ids = set()
                    for s_idx, s in enumerate(uq.get("subobjectives", []), 1):
                        sid = s.get("id")
                        if not sid or sid in used_sub_ids:
                            sid = f"s{s_idx}"
                            while sid in used_sub_ids:
                                s_idx += 1
                                sid = f"s{s_idx}"
                        used_sub_ids.add(sid)
                        new_subs.append({
                            "id": sid,
                            "text": s.get("text", "").strip(),
                            "completed": s.get("completed", False),
                        })

                    new_q = {
                        "id": new_id,
                        "title": q_title or f"Misión {new_id}",
                        "tipo": uq.get("tipo", "principal"),
                        "context": uq.get("context", ""),
                        "status": uq.get("status", "in_progress"),
                        "started_session": actual_session_num,
                        "completed_session": actual_session_num if is_closed else None,
                        "lifecycle_notes": lifecycle,
                        "subobjectives": new_subs,
                    }
                    existing_quests.append(new_q)

        # Enforce quest status auto-completion consistency (SKIP failed quests!)
        for quest in state.get("quests", []):
            if quest.get("status") == "failed":
                continue
            subobjectives = quest.get("subobjectives", [])
            if subobjectives and all(sub.get("completed", False) for sub in subobjectives):
                # If all steps are checked, automatically promote status to completed
                quest["status"] = "completed"
                if not quest.get("completed_session"):
                    quest["completed_session"] = actual_session_num
                lifecycle = quest.get("lifecycle_notes", "")
                step_note = f"Completada en Sesión {actual_session_num}"
                if step_note not in lifecycle:
                    quest["lifecycle_notes"] = f"{lifecycle} | {step_note}".strip(" |")

        # 3. Merge NPCs (with smart surname / multi-word deduplication)
        if updated_npcs:
            existing_npcs = state.setdefault("npcs", [])
            for unpc in updated_npcs:
                npc_name = unpc.get("name", "").strip()
                if not npc_name:
                    continue

                # First try exact match
                matched_npc = next((n for n in existing_npcs if n.get("name", "").strip().lower() == npc_name.lower()), None)
                # If no exact match, try smart fuzzy surname matching
                if not matched_npc:
                    matched_npc = next((n for n in existing_npcs if is_npc_name_match(n.get("name", ""), npc_name)), None)

                if matched_npc:
                    # Update name to more complete version (e.g. 'Fothark Vanessa' -> 'Fothark Vanessa Halovar')
                    if len(npc_name) > len(matched_npc.get("name", "")):
                        matched_npc["name"] = npc_name

                    # Update role if incoming role is more specific
                    curr_role = str(matched_npc.get("role", "")).strip()
                    new_role = str(unpc.get("role", "")).strip()
                    if new_role and (not curr_role or curr_role in ("-", "Desconocido / PNJ", "N/A") or len(new_role) > len(curr_role)):
                        matched_npc["role"] = new_role

                    if unpc.get("tipo") and matched_npc.get("tipo") != "importantes":
                        matched_npc["tipo"] = unpc["tipo"]

                    # Preserve earliest first_seen_session
                    matched_npc["first_seen_session"] = min(
                        matched_npc.get("first_seen_session", actual_session_num),
                        actual_session_num
                    )

                    # Merge notes intelligently without duplicating sentences or text
                    existing_notes = matched_npc.setdefault("notes", [])
                    for note in unpc.get("notes", []):
                        note_clean = note.strip()
                        if not note_clean:
                            continue
                        if any(note_clean.lower() == en.lower() or (len(note_clean) > 20 and note_clean.lower() in en.lower()) for en in existing_notes):
                            continue
                        expanded = False
                        for idx, en in enumerate(existing_notes):
                            if len(en) > 20 and en.lower() in note_clean.lower():
                                existing_notes[idx] = note_clean
                                expanded = True
                                break
                        if not expanded:
                            existing_notes.append(note_clean)
                else:
                    # Add new NPC
                    notes = unpc.get("notes", [])
                    if not notes and unpc.get("role"):
                        notes = [f"Sesión {actual_session_num}: {unpc.get('role')}"]
                    existing_npcs.append({
                        "name": npc_name,
                        "role": unpc.get("role", "Desconocido / PNJ"),
                        "tipo": unpc.get("tipo", "interaccion_contexto"),
                        "first_seen_session": actual_session_num,
                        "notes": notes,
                    })

        # 4. Merge Universal Player Characters (universal_pcs)
        existing_universal_pcs = state.setdefault("universal_pcs", [])
        raw_pcs_for_universal = detected_pcs or []
        if not raw_pcs_for_universal and detected_party:
            for dp in detected_party:
                raw_pcs_for_universal.append({
                    "personaje": dp.get("character_name") or dp.get("personaje") or "-",
                    "jugador": dp.get("player_name") or dp.get("jugador") or "-",
                    "especie": dp.get("species") or dp.get("especie") or "-",
                    "clase": dp.get("role") or dp.get("clase") or "-",
                    "subclase": dp.get("subclass") or dp.get("subclase") or "-",
                    "debut_sesion": dp.get("debut_sesion") or dp.get("primera_aparicion_sesion") or actual_session_num,
                    "hitos_acumulados": dp.get("hitos_acumulados") or [],
                    "rol_en_sesion": dp.get("session_role") or dp.get("rol_en_sesion") or "",
                })
        elif not raw_pcs_for_universal and roster:
            for r in roster:
                raw_pcs_for_universal.append({
                    "personaje": r.get("character_name") or "-",
                    "jugador": r.get("player_name") or "-",
                    "especie": r.get("species") or "-",
                    "clase": r.get("role") or "-",
                    "subclase": r.get("subclass") or "-",
                    "debut_sesion": actual_session_num,
                    "hitos_acumulados": [],
                    "rol_en_sesion": "",
                })

        for upc in raw_pcs_for_universal:
            char_name = str(upc.get("personaje") or upc.get("character_name") or "").strip()
            char_lower = char_name.lower()
            player_name_raw = str(upc.get("jugador") or upc.get("player_name") or "").strip()

            if (
                not char_name
                or char_name in ("-", "(DM)", "Dungeon Master", "(N/A - DM)", "(N/A)", "N/A")
                or char_lower in ("dm", "(dm)", "dungeon master", "(dungeon master)", "el dm", "master", "narrador")
                or ("dungeon master" in char_lower and len(char_name) <= 18)
                or "brennan" in player_name_raw.lower()
            ):
                if "liam" in player_name_raw.lower():
                    char_name = "Halendiel 'Hal' Fang"
                    char_cls = "Bard"
                    upc["personaje"] = "Halendiel 'Hal' Fang"
                    upc["jugador"] = "Liam O'Brien"
                    upc["especie"] = "Orc"
                    upc["clase"] = "Bard"
                else:
                    continue

            # Liam O'Brien preservation (if Liam was passed with generic or missing fields)
            if "liam" in player_name_raw.lower():
                upc["jugador"] = "Liam O'Brien"
                if not char_name or char_name in ("-", "(DM)", "Dungeon Master"):
                    char_name = "Halendiel 'Hal' Fang"
                    upc["personaje"] = char_name

            # Mutual exclusivity: character can never have class Dungeon Master
            char_cls = str(upc.get("clase") or upc.get("role") or "").strip()
            if char_cls.lower() in ("dungeon master", "dm", "narrador", "master", "árbitro"):
                char_cls = "-"

            matched_pc = next((p for p in existing_universal_pcs if str(p.get("personaje", "")).strip().lower() == char_name.lower()), None)
            if not matched_pc:
                matched_pc = next((p for p in existing_universal_pcs if is_npc_name_match(p.get("personaje", ""), char_name)), None)

            session_achievement = str(upc.get("rol_en_sesion") or upc.get("session_role") or "").strip()
            milestone_regex = re.compile(rf"^(sesi[oó]n|session)\s*#?{actual_session_num}\s*:", re.IGNORECASE)

            if not session_achievement and upc.get("hitos_acumulados"):
                for h in upc.get("hitos_acumulados", []):
                    h_str = str(h).strip()
                    m = milestone_regex.match(h_str)
                    if m:
                        session_achievement = h_str[m.end():].strip()
                        break

            if session_achievement in ("-", "N/A") or any(mp in session_achievement.lower() for mp in ("dungeon master", "controló los pnjs", "controlo los pnjs", "dirigió la sesión", "dirigio la sesion")):
                session_achievement = ""

            def _extract_sess(m_text):
                m = re.search(r"^(?:sesi[oó]n|session)\s*#?(\d+)", str(m_text).strip(), re.IGNORECASE)
                return int(m.group(1)) if m else 9999

            if matched_pc:
                # Upgrade character name if incoming name is longer / more complete (e.g. "Octus" -> "Octus Taconis")
                old_pc_name = matched_pc.get("personaje", "")
                if len(char_name) > len(old_pc_name):
                    matched_pc["personaje"] = char_name
                    # Synchronize roster if needed
                    for r in state.get("roster", []):
                        if r.get("character_name") == old_pc_name or is_npc_name_match(r.get("character_name", ""), char_name):
                            r["character_name"] = char_name

                # Preserve earliest debut_sesion
                matched_pc["debut_sesion"] = min(
                    int(matched_pc.get("debut_sesion", actual_session_num)),
                    int(upc.get("debut_sesion") or actual_session_num)
                )

                for attr, key in [("jugador", "jugador"), ("especie", "especie"), ("subclase", "subclase")]:
                    new_val = str(upc.get(attr) or upc.get(key) or "").strip()
                    curr_val = str(matched_pc.get(attr) or "").strip()
                    if new_val and new_val not in ("-", "N/A", "", "Desconocido") and (not curr_val or curr_val in ("-", "N/A", "", "Desconocido")):
                        matched_pc[attr] = new_val

                # Class update
                curr_cls = str(matched_pc.get("clase") or "").strip()
                if char_cls and char_cls not in ("-", "N/A", "", "Desconocido") and (not curr_cls or curr_cls in ("-", "N/A", "", "Desconocido")):
                    matched_pc["clase"] = char_cls

                # True Overwrite on Re-Record: remove/filter out any existing milestone for this session using bilingual regex
                matched_pc["hitos_acumulados"] = [
                    h for h in matched_pc.get("hitos_acumulados", [])
                    if not milestone_regex.match(str(h).strip())
                ]
                if session_achievement:
                    matched_pc["hitos_acumulados"].append(f"Sesión #{actual_session_num}: {session_achievement}")

                matched_pc["hitos_acumulados"].sort(key=_extract_sess)
            else:
                hitos = []
                for h in upc.get("hitos_acumulados", []):
                    h_str = str(h).strip()
                    if not milestone_regex.match(h_str) and h_str not in hitos:
                        hitos.append(h_str)
                if session_achievement:
                    hitos.append(f"Sesión #{actual_session_num}: {session_achievement}")
                hitos.sort(key=_extract_sess)
                debut_val = upc.get("debut_sesion") or upc.get("primera_aparicion_sesion") or actual_session_num
                existing_universal_pcs.append({
                    "personaje": char_name,
                    "jugador": str(upc.get("jugador") or upc.get("player_name") or "-").strip(),
                    "especie": str(upc.get("especie") or upc.get("species") or "-").strip(),
                    "clase": char_cls or "-",
                    "subclase": str(upc.get("subclase") or upc.get("subclass") or "-").strip(),
                    "debut_sesion": int(debut_val),
                    "hitos_acumulados": hitos,
                })

        self.save_campaign(state)
        return state

    def update_quest_subobjective(
        self,
        name: str,
        quest_id: str,
        subobjective_idx: int,
        completed: bool,
    ) -> Dict[str, Any]:
        """Toggle or set completion status of a quest subobjective."""
        state = self.load_campaign(name)
        quest = next((q for q in state.get("quests", []) if q.get("id") == quest_id), None)
        if not quest:
            raise ValueError(f"Misión con id '{quest_id}' no encontrada en campaña '{name}'.")

        subs = quest.get("subobjectives", [])
        if 0 <= subobjective_idx < len(subs):
            subs[subobjective_idx]["completed"] = completed
            # If all subobjectives completed, mark quest completed (unless status is failed)
            if all(s.get("completed", False) for s in subs) and subs and quest.get("status") != "failed":
                quest["status"] = "completed"
                if not quest.get("completed_session"):
                    quest["completed_session"] = state.get("last_session", 1)
            self.save_campaign(state)
        return state

    def toggle_quest_status(
        self,
        name: str,
        quest_id: str,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Toggle or explicitly set status of a quest (in_progress <-> completed, or failed)."""
        state = self.load_campaign(name)
        quest = next((q for q in state.get("quests", []) if q.get("id") == quest_id), None)
        if not quest:
            raise ValueError(f"Misión con id '{quest_id}' no encontrada en campaña '{name}'.")

        if status and status in ("completed", "in_progress", "failed"):
            quest["status"] = status
        else:
            quest["status"] = "in_progress" if quest.get("status") in ("completed", "failed") else "completed"

        last_sess = state.get("last_session", 1)
        if quest["status"] == "completed":
            if not quest.get("completed_session"):
                quest["completed_session"] = last_sess
            lifecycle = quest.get("lifecycle_notes", "")
            step_note = f"Completada manualmente (Sesión {last_sess})"
            if step_note not in lifecycle:
                quest["lifecycle_notes"] = f"{lifecycle} | {step_note}".strip(" |")
        elif quest["status"] == "failed":
            if not quest.get("completed_session"):
                quest["completed_session"] = last_sess
            lifecycle = quest.get("lifecycle_notes", "")
            step_note = f"Fracasada manualmente (Sesión {last_sess})"
            if step_note not in lifecycle:
                quest["lifecycle_notes"] = f"{lifecycle} | {step_note}".strip(" |")
        else:
            quest["completed_session"] = None

        self.save_campaign(state)
        return state

    def update_npc_name(
        self,
        name: str,
        old_name: str,
        new_name: str,
    ) -> Dict[str, Any]:
        """Update an NPC's name across the directory after user spell review."""
        state = self.load_campaign(name)
        clean_new = new_name.strip()
        if not clean_new:
            return state

        for npc in state.get("npcs", []):
            if npc.get("name", "").lower() == old_name.strip().lower():
                npc["name"] = clean_new

        self.save_campaign(state)
        return state
