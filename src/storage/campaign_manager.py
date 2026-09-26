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


def is_entity_substring_duplicate(
    short_name: str,
    long_name: str,
    entity1: Optional[Dict[str, Any]] = None,
    entity2: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Detect if short_name represents an incomplete or unexpanded duplicate of long_name.
    For instance: 'Octus' vs 'Octus Taconis', or 'Thiazi' vs 'Thiazi Coldbreaker'.
    Does not match distinct entities sharing common generic words (e.g. 'Lord', 'Guardia')
    or different family members with different first names (e.g. 'Hiro Fang' vs 'Thjazi Fang').
    """
    s1 = (short_name or "").strip()
    s2 = (long_name or "").strip()
    if not s1 or not s2:
        return False
    if s1.lower() == s2.lower():
        return True
    if len(s1) >= len(s2):
        return False

    l1 = s1.lower()
    l2 = s2.lower()

    if "[" in l1 or "sin nombre" in l1 or "unnamed" in l1:
        return False

    generic_titles = {
        "lord", "lady", "sir", "dame", "king", "queen", "rey", "reina",
        "captain", "capitán", "capitan", "guard", "guardia", "soldier", "soldado",
        "master", "dm", "el", "la", "los", "las", "the", "de", "del", "of",
        "don", "doña", "padre", "madre", "hermano", "hermana", "brother", "sister"
    }
    if l1 in generic_titles:
        return False

    # If both entities have player names specified and they match (and not empty / generic)
    if entity1 and entity2:
        pl1 = str(entity1.get("jugador") or entity1.get("player_name") or "").strip().lower()
        pl2 = str(entity2.get("jugador") or entity2.get("player_name") or "").strip().lower()
        if pl1 and pl2 and pl1 not in ("-", "desconocido", "n/a", "") and pl2 not in ("-", "desconocido", "n/a", ""):
            if pl1 == pl2:
                c1 = re.sub(r"[^\w\s]", "", l1)
                c2 = re.sub(r"[^\w\s]", "", l2)
                t1 = set(c1.split())
                t2 = set(c2.split())
                if t1.issubset(t2) or c1 in c2:
                    return True

    c1 = re.sub(r"[^\w\s]", "", l1)
    c2 = re.sub(r"[^\w\s]", "", l2)
    tokens1 = [t for t in c1.split() if t and t not in generic_titles]
    tokens2 = [t for t in c2.split() if t and t not in generic_titles]
    if not tokens1 or not tokens2:
        return False

    set1 = set(tokens1)
    set2 = set(tokens2)
    if set1.issubset(set2) and all(len(t) >= 3 for t in tokens1):
        return True

    if len(c1) >= 3 and re.search(rf"\b{re.escape(c1)}\b", c2):
        return True

    if is_npc_name_match(s1, s2):
        return True

    return False


def _extract_sess_number(milestone_text: Any) -> int:
    m = re.search(r"^(?:sesi[oó]n|session)\s*#?(\d+)", str(milestone_text).strip(), re.IGNORECASE)
    return int(m.group(1)) if m else 9999


def _merge_milestones(h1: Any, h2: Any) -> List[str]:
    combined: List[str] = []
    seen = set()
    list1 = h1 if isinstance(h1, list) else ([h1] if h1 else [])
    list2 = h2 if isinstance(h2, list) else ([h2] if h2 else [])
    for h in list1 + list2:
        h_str = str(h).strip() if isinstance(h, str) else str(h.get("hito") or h.get("text") or h).strip()
        if not h_str:
            continue
        norm = re.sub(r"\s+", " ", h_str).lower()
        if norm not in seen:
            seen.add(norm)
            combined.append(h_str)
    combined.sort(key=_extract_sess_number)
    return combined


def _merge_notes_list(n1: Any, n2: Any) -> List[str]:
    combined: List[str] = []
    seen = set()
    list1 = n1 if isinstance(n1, list) else ([n1] if n1 else [])
    list2 = n2 if isinstance(n2, list) else ([n2] if n2 else [])
    for n in list1 + list2:
        n_str = str(n).strip() if isinstance(n, str) else str(n.get("note") or n.get("text") or n).strip()
        if not n_str:
            continue
        norm = re.sub(r"\s+", " ", n_str).lower()
        if norm not in seen:
            seen.add(norm)
            combined.append(n_str)
    return combined


def deduplicate_campaign_entities(campaign_id: str, campaigns_dir: Optional[str] = None) -> Dict[str, Any]:
    """Standalone wrapper to deduplicate campaign entities."""
    mgr = CampaignManager(campaigns_dir=campaigns_dir)
    return mgr.deduplicate_campaign_entities(campaign_id)


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
                    "dm": data.get("dm") or data.get("dungeon_master") or data.get("dm_name") or "",
                    "dungeon_master": data.get("dm") or data.get("dungeon_master") or data.get("dm_name") or "",
                    "dm_name": data.get("dm") or data.get("dungeon_master") or data.get("dm_name") or "",
                    "dm_discord_id": data.get("dm_discord_id") or data.get("dm_discord_user_id") or data.get("dm_discord") or "",
                    "dm_discord": data.get("dm_discord_id") or data.get("dm_discord_user_id") or data.get("dm_discord") or "",
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
                # Backfill DM fields
                dm_val = data.get("dm") or data.get("dungeon_master") or data.get("dm_name") or ""
                if not dm_val and data.get("roster") and len(data["roster"]) > 0:
                    r0 = data["roster"][0]
                    if r0.get("character_name") == "(DM)" or r0.get("role") == "Dungeon Master (DM)":
                        dm_val = (r0.get("player_name") or "").strip()
                data["dm"] = dm_val
                data["dungeon_master"] = dm_val
                data["dm_name"] = dm_val

                dm_disc = data.get("dm_discord_id") or data.get("dm_discord_user_id") or data.get("dm_discord") or ""
                if not dm_disc and data.get("roster") and len(data["roster"]) > 0:
                    r0 = data["roster"][0]
                    if r0.get("character_name") == "(DM)" or r0.get("role") == "Dungeon Master (DM)":
                        dm_disc = (r0.get("discord_id") or r0.get("discord_user_id") or "").strip()
                data["dm_discord_id"] = dm_disc
                data["dm_discord_user_id"] = dm_disc
                data["dm_discord"] = dm_disc

                # Ensure roster[0] reflects dm_val and dm_disc if it's the DM
                if data.get("roster") and len(data["roster"]) > 0:
                    r0 = data["roster"][0]
                    if r0.get("character_name") == "(DM)" or r0.get("role") == "Dungeon Master (DM)":
                        if dm_val and not (r0.get("player_name") or "").strip():
                            r0["player_name"] = dm_val
                        if dm_disc and not (r0.get("discord_user_id") or r0.get("discord_id") or "").strip():
                            r0["discord_user_id"] = dm_disc
                            r0["discord_id"] = dm_disc

                # Auto-deduplicate entities on campaign load (e.g. Octus -> Octus Taconis)
                merged = self._deduplicate_state(data, campaign_name=data.get("campaign_name", name))
                if merged:
                    data["updated_at"] = datetime.datetime.now().isoformat()
                    try:
                        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                    except Exception as e:
                        print(f"[CampaignManager] Could not save deduplicated state to {file_path}: {e}")
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
            "dm": "",
            "dungeon_master": "",
            "dm_name": "",
            "dm_discord": "",
            "dm_discord_id": "",
            "dm_discord_user_id": "",
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

        raw_title = str(session_chapter.get("session_title") or session_chapter.get("title") or f"Sesión {actual_session_num}").strip()
        clean_title = re.sub(r"^(?:sesi[oó]n|session)\s*#?\d+\s*[:\-]\s*", "", raw_title, flags=re.IGNORECASE).strip() or raw_title

        chapter_record = {
            "session_number": actual_session_num,
            "date": datetime.datetime.now().strftime("%d/%m/%Y"),
            "session_title": clean_title,
            "title": clean_title,
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

    def _clean_entity_disk_files(self, entity_name: str, campaign_name: str):
        """Remove any orphaned entity files from disk matching the incomplete name."""
        clean_stem = self.sanitize_name(entity_name)
        camp_clean = self.sanitize_name(campaign_name)
        candidates = [
            self.campaigns_dir / f"{clean_stem}.json",
            self.campaigns_dir / f"{clean_stem}.md",
            self.campaigns_dir / camp_clean / f"{clean_stem}.json",
            self.campaigns_dir / camp_clean / f"{clean_stem}.md",
            self.campaigns_dir / "entities" / f"{clean_stem}.json",
            self.campaigns_dir / "entities" / f"{clean_stem}.md",
        ]
        out_dir = Path(os.environ.get("WHISPER_OUTPUT_DIR", self.campaigns_dir.parent / "output"))
        if out_dir.is_dir():
            candidates.extend([
                out_dir / f"{clean_stem}.json",
                out_dir / f"{clean_stem}.md",
                out_dir / f"{clean_stem}.docx",
            ])
        for p in candidates:
            if p.is_file():
                try:
                    p.unlink()
                    print(f"[CampaignManager] Deleted duplicate entity disk file: {p}")
                except Exception as e:
                    print(f"[CampaignManager] Could not delete duplicate entity file {p}: {e}")

    def _sync_roster_and_sessions(self, state: dict, source_name: str, target_name: str):
        """Update any reference to source_name with target_name in roster and session chapters."""
        roster = state.get("roster", [])
        new_roster = []
        seen_chars = set()
        for r in roster:
            c_name = str(r.get("character_name", "")).strip()
            if c_name.lower() == source_name.lower():
                r["character_name"] = target_name
                c_name = target_name
            key = c_name.lower()
            if key not in seen_chars:
                seen_chars.add(key)
                new_roster.append(r)
        state["roster"] = new_roster

        for s in state.get("sessions", []):
            for p in s.get("detected_pcs", []):
                if str(p.get("personaje", "")).strip().lower() == source_name.lower():
                    p["personaje"] = target_name
            for p in s.get("detected_party", []):
                if str(p.get("character_name", "")).strip().lower() == source_name.lower():
                    p["character_name"] = target_name
            s["detected_npc_names"] = [
                target_name if str(n).strip().lower() == source_name.lower() else n
                for n in s.get("detected_npc_names", [])
            ]

    def _deduplicate_state(self, state: Dict[str, Any], campaign_name: str = "") -> List[Dict[str, Any]]:
        """
        Inspects universal_pcs and npcs in state for substring duplicates.
        Merges content, hitos/notes, adds alias, removes old duplicate, syncs roster, and deletes orphaned disk files.
        Returns list of merged event records.
        """
        merged_events = []
        camp_name = campaign_name or state.get("campaign_name", "")

        # --- 1. Deduplicate universal_pcs ---
        pcs = state.get("universal_pcs", [])
        i = 0
        while i < len(pcs):
            merged_any = False
            j = 0
            while j < len(pcs):
                if i != j:
                    p1 = pcs[i]
                    p2 = pcs[j]
                    n1 = str(p1.get("personaje") or p1.get("name") or "").strip()
                    n2 = str(p2.get("personaje") or p2.get("name") or "").strip()
                    if is_entity_substring_duplicate(n1, n2, p1, p2):
                        # p1 is shorter duplicate of p2. Merge p1 into p2!
                        aliases = p2.setdefault("aliases", [])
                        if n1 and n1 not in aliases:
                            aliases.append(n1)
                        for a in p1.get("aliases", []):
                            if a not in aliases and a != n2:
                                aliases.append(a)

                        for field in ("jugador", "especie", "clase", "subclase"):
                            v2 = str(p2.get(field) or "").strip()
                            v1 = str(p1.get(field) or "").strip()
                            if (not v2 or v2 in ("-", "Desconocido", "N/A")) and (v1 and v1 not in ("-", "Desconocido", "N/A")):
                                p2[field] = v1

                        d1 = int(p1.get("debut_sesion") or 9999)
                        d2 = int(p2.get("debut_sesion") or 9999)
                        p2["debut_sesion"] = min(d1, d2)

                        p2["hitos_acumulados"] = _merge_milestones(p2.get("hitos_acumulados", []), p1.get("hitos_acumulados", []))

                        pcs.pop(i)
                        self._clean_entity_disk_files(n1, camp_name)
                        self._sync_roster_and_sessions(state, n1, n2)

                        merged_events.append({
                            "type": "pc",
                            "source": n1,
                            "target": n2,
                        })
                        merged_any = True
                        break
                j += 1
            if not merged_any:
                i += 1

        # --- 2. Deduplicate npcs ---
        npcs = state.get("npcs", [])
        i = 0
        while i < len(npcs):
            merged_any = False
            j = 0
            while j < len(npcs):
                if i != j:
                    npc1 = npcs[i]
                    npc2 = npcs[j]
                    n1 = str(npc1.get("name") or "").strip()
                    n2 = str(npc2.get("name") or "").strip()
                    if is_entity_substring_duplicate(n1, n2, npc1, npc2):
                        aliases = npc2.setdefault("aliases", [])
                        if n1 and n1 not in aliases:
                            aliases.append(n1)
                        for a in npc1.get("aliases", []):
                            if a not in aliases and a != n2:
                                aliases.append(a)

                        r2 = str(npc2.get("role") or "").strip()
                        r1 = str(npc1.get("role") or "").strip()
                        if (not r2 or r2 in ("-", "Desconocido / PNJ", "N/A")) and (r1 and r1 not in ("-", "Desconocido / PNJ", "N/A")):
                            npc2["role"] = r1
                        elif r1 and len(r1) > len(r2):
                            npc2["role"] = r1

                        if npc1.get("tipo") == "importantes":
                            npc2["tipo"] = "importantes"

                        f1 = int(npc1.get("first_seen_session") or 9999)
                        f2 = int(npc2.get("first_seen_session") or 9999)
                        npc2["first_seen_session"] = min(f1, f2)

                        npc2["notes"] = _merge_notes_list(npc2.get("notes", []), npc1.get("notes", []))

                        npcs.pop(i)
                        self._clean_entity_disk_files(n1, camp_name)
                        self._sync_roster_and_sessions(state, n1, n2)

                        merged_events.append({
                            "type": "npc",
                            "source": n1,
                            "target": n2,
                        })
                        merged_any = True
                        break
                j += 1
            if not merged_any:
                i += 1

        return merged_events

    def deduplicate_campaign_entities(self, campaign_id: str) -> Dict[str, Any]:
        """
        Scans and merges duplicate entities in a campaign.
        If 'Octus' and 'Octus Taconis' exist:
        1. Merges content, hitos, notes into 'Octus Taconis'.
        2. Adds 'Octus' to aliases: aliases: ['Octus'].
        3. Removes old duplicate 'Octus' and deletes orphaned files.
        4. Saves and returns the clean campaign state.
        """
        file_path = self.get_campaign_path(campaign_id)
        if not file_path.is_file():
            matched = None
            for f in self.campaigns_dir.glob("*.json"):
                if f.stem.lower() == self.sanitize_name(campaign_id).lower():
                    matched = f
                    break
            if matched:
                file_path = matched
            else:
                raise ValueError(f"Campaña con ID/Nombre '{campaign_id}' no encontrada.")

        data = json.loads(file_path.read_text(encoding="utf-8"))
        merged_events = self._deduplicate_state(data, campaign_name=data.get("campaign_name", campaign_id))

        if merged_events:
            data["updated_at"] = datetime.datetime.now().isoformat()
            file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[CampaignManager] Deduplicated {len(merged_events)} entities in '{campaign_id}': {merged_events}")

        return {
            "campaign_id": campaign_id,
            "merged_count": len(merged_events),
            "merged": merged_events,
            "campaign_state": data,
        }

    def deduplicate_all_campaigns(self) -> List[Dict[str, Any]]:
        """Run deduplication on all campaigns in the campaigns directory."""
        results = []
        for file in self.campaigns_dir.glob("*.json"):
            try:
                res = self.deduplicate_campaign_entities(file.stem)
                if res.get("merged_count", 0) > 0:
                    results.append(res)
            except Exception as exc:
                print(f"[CampaignManager] Error deduplicating {file}: {exc}")
        return results

    def merge_entities(
        self,
        campaign_name: str,
        source_name: str,
        target_name: str,
        entity_type: str = "pc",
        keep_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Manually merge two entities in a campaign.
        'source_name' will be absorbed into 'target_name', and recorded as an alias.
        """
        state = self.load_campaign(campaign_name)
        s_clean = source_name.strip()
        t_clean = target_name.strip()
        if not s_clean or not t_clean:
            raise ValueError("Se requieren tanto el personaje origen como el destino.")
        if s_clean.lower() == t_clean.lower():
            raise ValueError("No se puede fusionar un personaje consigo mismo.")

        pcs = state.setdefault("universal_pcs", [])
        npcs = state.setdefault("npcs", [])

        source_pc = next((p for p in pcs if str(p.get("personaje") or p.get("name") or "").strip().lower() == s_clean.lower()), None)
        target_pc = next((p for p in pcs if str(p.get("personaje") or p.get("name") or "").strip().lower() == t_clean.lower()), None)

        source_npc = next((n for n in npcs if str(n.get("name") or "").strip().lower() == s_clean.lower()), None)
        target_npc = next((n for n in npcs if str(n.get("name") or "").strip().lower() == t_clean.lower()), None)

        merged_record = {}

        if target_pc and (source_pc or source_npc):
            aliases = target_pc.setdefault("aliases", [])
            if s_clean not in aliases:
                aliases.append(s_clean)

            if source_pc:
                for a in source_pc.get("aliases", []):
                    if a not in aliases and a != target_pc.get("personaje"):
                        aliases.append(a)
                for field in ("jugador", "especie", "clase", "subclase"):
                    v2 = str(target_pc.get(field) or "").strip()
                    v1 = str(source_pc.get(field) or "").strip()
                    if (not v2 or v2 in ("-", "Desconocido", "N/A")) and (v1 and v1 not in ("-", "Desconocido", "N/A")):
                        target_pc[field] = v1
                d1 = int(source_pc.get("debut_sesion") or 9999)
                d2 = int(target_pc.get("debut_sesion") or 9999)
                target_pc["debut_sesion"] = min(d1, d2)
                target_pc["hitos_acumulados"] = _merge_milestones(target_pc.get("hitos_acumulados", []), source_pc.get("hitos_acumulados", []))
                pcs[:] = [p for p in pcs if p is not source_pc]
            elif source_npc:
                for a in source_npc.get("aliases", []):
                    if a not in aliases and a != target_pc.get("personaje"):
                        aliases.append(a)
                target_pc["hitos_acumulados"] = _merge_milestones(target_pc.get("hitos_acumulados", []), source_npc.get("notes", []))
                npcs[:] = [n for n in npcs if n is not source_npc]

            final_name = keep_name or target_pc.get("personaje") or t_clean
            target_pc["personaje"] = final_name
            self._clean_entity_disk_files(s_clean, campaign_name)
            self._sync_roster_and_sessions(state, s_clean, final_name)
            merged_record = {"type": "pc", "source": s_clean, "target": final_name}

        elif target_npc and (source_npc or source_pc):
            aliases = target_npc.setdefault("aliases", [])
            if s_clean not in aliases:
                aliases.append(s_clean)

            if source_npc:
                for a in source_npc.get("aliases", []):
                    if a not in aliases and a != target_npc.get("name"):
                        aliases.append(a)
                r2 = str(target_npc.get("role") or "").strip()
                r1 = str(source_npc.get("role") or "").strip()
                if (not r2 or r2 in ("-", "Desconocido / PNJ", "N/A")) and (r1 and r1 not in ("-", "Desconocido / PNJ", "N/A")):
                    target_npc["role"] = r1
                elif r1 and len(r1) > len(r2):
                    target_npc["role"] = r1
                if source_npc.get("tipo") == "importantes":
                    target_npc["tipo"] = "importantes"
                f1 = int(source_npc.get("first_seen_session") or 9999)
                f2 = int(target_npc.get("first_seen_session") or 9999)
                target_npc["first_seen_session"] = min(f1, f2)
                target_npc["notes"] = _merge_notes_list(target_npc.get("notes", []), source_npc.get("notes", []))
                npcs[:] = [n for n in npcs if n is not source_npc]
            elif source_pc:
                target_npc["notes"] = _merge_notes_list(target_npc.get("notes", []), source_pc.get("hitos_acumulados", []))
                pcs[:] = [p for p in pcs if p is not source_pc]

            final_name = keep_name or target_npc.get("name") or t_clean
            target_npc["name"] = final_name
            self._clean_entity_disk_files(s_clean, campaign_name)
            self._sync_roster_and_sessions(state, s_clean, final_name)
            merged_record = {"type": "npc", "source": s_clean, "target": final_name}
        elif target_pc and any(s_clean.lower() == str(a).lower() for a in target_pc.get("aliases", [])):
            final_name = keep_name or target_pc.get("personaje") or t_clean
            merged_record = {"type": "pc", "source": s_clean, "target": final_name, "already_merged": True}
        elif target_npc and any(s_clean.lower() == str(a).lower() for a in target_npc.get("aliases", [])):
            final_name = keep_name or target_npc.get("name") or t_clean
            merged_record = {"type": "npc", "source": s_clean, "target": final_name, "already_merged": True}
        else:
            raise ValueError(f"No se pudo encontrar a '{s_clean}' o '{t_clean}' en los personajes de la campaña.")

        self.save_campaign(state)
        return merged_record
