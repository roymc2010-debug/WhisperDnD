"""Campaign manager for Living Campaign Journal persistence and continuity."""

import datetime
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


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
                t1 = {t for t in c1.split() if len(t) >= 3 and t not in generic_titles}
                t2 = {t for t in c2.split() if len(t) >= 3 and t not in generic_titles}
                shared_tokens = (t1 & t2)
                e1_aliases = [str(a).strip().lower() for a in entity1.get("aliases", [])]
                e2_aliases = [str(a).strip().lower() for a in entity2.get("aliases", [])]
                is_alias_match = (l1 in e2_aliases or l2 in e1_aliases)
                if shared_tokens or t1.issubset(t2) or t2.issubset(t1) or c1 in c2 or c2 in c1 or is_alias_match or is_npc_name_match(s1, s2):
                    if len(s1) < len(s2):
                        return True
                    elif len(s1) > len(s2):
                        return False
                    else:
                        def _get_max_session(e):
                            max_s = 0
                            for h in e.get("hitos_acumulados", []):
                                m = re.search(r"(?:sesi[oó]n|session)\s*#?(\d+)", str(h), re.IGNORECASE)
                                if m:
                                    max_s = max(max_s, int(m.group(1)))
                            return max_s
                        ms1 = _get_max_session(entity1)
                        ms2 = _get_max_session(entity2)
                        if ms1 < ms2:
                            return True
                        elif ms1 > ms2:
                            return False
                        return l1 > l2

    if len(s1) >= len(s2):
        return False

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


def are_items_duplicate(it1: Dict[str, Any], it2: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Check if two items are duplicates across Spanish/English names, aliases, or common variants.
    Returns (is_duplicate, canonical_name).
    """
    name1 = str(it1.get("name") or "").strip()
    name2 = str(it2.get("name") or "").strip()
    if not name1 or not name2:
        return False, None

    n1 = name1.lower()
    n2 = name2.lower()
    if n1 == n2:
        return True, name1

    # 1. Special Case E10: Rosario Sagrado de Zun / Collar o Medallón del Pozo
    zun_tokens = {"zun"}
    pozo_tokens = {"pozo", "medallon", "medallón", "collar"}
    is_zun1 = any(t in n1 for t in zun_tokens) or (any(t in n1 for t in pozo_tokens) and ("collar" in n1 or "medall" in n1 or "zun" in n1))
    is_zun2 = any(t in n2 for t in zun_tokens) or (any(t in n2 for t in pozo_tokens) and ("collar" in n2 or "medall" in n2 or "zun" in n2))
    if (("zun" in n1 and ("zun" in n2 or "pozo" in n2 or "collar" in n2)) or
        ("zun" in n2 and ("zun" in n1 or "pozo" in n1 or "collar" in n1)) or
        ("pozo" in n1 and "pozo" in n2 and ("collar" in n1 or "medall" in n1) and ("collar" in n2 or "medall" in n2))):
        return True, "Collar / Rosario Sagrado de Zun (Medallón del Pozo)"

    # 2. Studded Leather Armor
    leather_terms = ("cuero tachonado", "studded leather", "studied leather")
    if any(t in n1 for t in leather_terms) and any(t in n2 for t in leather_terms):
        return True, "Armadura de Cuero Tachonado (Studded Leather Armor)"

    # 3. Heavy Crossbow
    crossbow_terms = ("ballesta pesada", "heavy crossbow")
    if any(t in n1 for t in crossbow_terms) and any(t in n2 for t in crossbow_terms):
        return True, "Ballesta Pesada (Heavy Crossbow)"

    # 4. Orcus Statuette
    if "orcus" in n1 and "orcus" in n2:
        statuette_terms = ("estatuilla", "statuette", "statue", "estatua", "ídolo", "idolo")
        if any(t in n1 for t in statuette_terms) and any(t in n2 for t in statuette_terms):
            return True, "Estatuilla Blasfema de Orcus (Orcus Statuette)"

    # 5. Baroness Diary
    if ("baronesa" in n1 or "baroness" in n1) and ("baronesa" in n2 or "baroness" in n2):
        diary_terms = ("diario", "diary", "journal")
        if any(t in n1 for t in diary_terms) and any(t in n2 for t in diary_terms):
            return True, "Diario de la Baronesa Brantifax"

    # 6. Bilingual / Substring parenthetical matching
    clean1 = re.sub(r"[^\w\s]", "", n1)
    clean2 = re.sub(r"[^\w\s]", "", n2)
    if clean1 and clean2:
        if clean1 in clean2:
            return True, name2 if len(name2) >= len(name1) else name1
        if clean2 in clean1:
            return True, name1 if len(name1) >= len(name2) else name2

    # 7. Word translation mapping
    translation_dict = {
        "armadura": "armor", "armor": "armadura",
        "ballesta": "crossbow", "crossbow": "ballesta",
        "pesada": "heavy", "heavy": "pesada",
        "estatuilla": "statuette", "statuette": "estatuilla",
        "diario": "diary", "diary": "diario",
        "espejo": "mirror", "mirror": "espejo",
        "mano": "hand", "hand": "mano",
        "pluma": "feather", "feather": "pluma",
    }
    words1 = {translation_dict.get(w, w) for w in clean1.split() if len(w) >= 3}
    words2 = {translation_dict.get(w, w) for w in clean2.split() if len(w) >= 3}
    if words1 and words2:
        overlap = words1 & words2
        if len(overlap) >= 2 and (overlap == words1 or overlap == words2):
            preferred = name1 if len(name1) >= len(name2) else name2
            return True, preferred

    return False, None


def merge_two_items(target: Dict[str, Any], source: Dict[str, Any], canonical_name: Optional[str] = None) -> Dict[str, Any]:
    """Merge content of source item into target item."""
    if canonical_name:
        target["name"] = canonical_name
    elif len(str(source.get("name", ""))) > len(str(target.get("name", ""))):
        target["name"] = source["name"]

    d_curr = str(target.get("description", "")).strip()
    d_src = str(source.get("description", "")).strip()
    if d_src and (not d_curr or len(d_src) > len(d_curr)):
        target["description"] = d_src

    # Holder: prefer player character over generic
    generic_holders = {"-", "", "none", "none [destroyed]", "ninguno", "grupo", "desconocido"}
    curr_holder = str(target.get("holder", "")).strip()
    src_holder = str(source.get("holder", "")).strip()
    if curr_holder.lower() in generic_holders and src_holder.lower() not in generic_holders:
        target["holder"] = src_holder
    elif src_holder.lower() not in generic_holders:
        if source.get("status") == "equipado" and target.get("status") != "equipado":
            target["holder"] = src_holder
        elif target.get("holder", "").lower() in generic_holders:
            target["holder"] = src_holder

    # Status: consumido > equipado > en_posesion
    curr_st = str(target.get("status", "")).strip().lower()
    src_st = str(source.get("status", "")).strip().lower()
    if "consumido" in (curr_st, src_st) or "destruido" in (curr_st, src_st):
        target["status"] = "consumido"
    elif "equipado" in (curr_st, src_st):
        target["status"] = "equipado"
    elif src_st and src_st not in generic_holders:
        target["status"] = source["status"]

    # Type: prefer specific types over generic artefacto
    generic_types = {"", "artefacto", "objeto"}
    if target.get("type", "").lower() in generic_types and source.get("type", "").lower() not in generic_types:
        target["type"] = source["type"]

    return target


def are_locations_duplicate(loc1: Dict[str, Any], loc2: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Check if two locations are duplicates across Spanish/English names or common variants.
    Returns (is_duplicate, canonical_name).
    """
    name1 = str(loc1.get("name") or "").strip()
    name2 = str(loc2.get("name") or "").strip()
    if not name1 or not name2:
        return False, None

    n1 = name1.lower()
    n2 = name2.lower()
    if n1 == n2:
        return True, name1

    # 1. Brantifax Chalet / Manor
    brantifax_residence = ("chalet", "manor", "mansión", "mansion", "residencia", "hunting lodge")
    if "brantifax" in n1 and "brantifax" in n2:
        if any(t in n1 for t in brantifax_residence) and any(t in n2 for t in brantifax_residence):
            return True, "Chalet Brantifax (Brantifax Manor)"

    # 2. Brantifax Cemetery
    cemetery_terms = ("cemetery", "cementerio", "graveyard", "tumbas", "camposanto")
    if "brantifax" in n1 and "brantifax" in n2:
        if any(t in n1 for t in cemetery_terms) and any(t in n2 for t in cemetery_terms):
            return True, "Cementerio Brantifax (Brantifax Cemetery)"

    # 3. Substring matching
    clean1 = re.sub(r"[^\w\s]", "", n1)
    clean2 = re.sub(r"[^\w\s]", "", n2)
    if clean1 and clean2:
        if clean1 in clean2:
            return True, name2 if len(name2) >= len(name1) else name1
        if clean2 in clean1:
            return True, name1 if len(name1) >= len(name2) else name2

    # 4. Bilingual translation overlap
    loc_translations = {
        "cementerio": "cemetery", "cemetery": "cementerio",
        "chalet": "manor", "manor": "chalet",
        "mansión": "manor", "mansion": "manor",
        "castillo": "castle", "castle": "castillo",
        "torre": "tower", "tower": "torre",
        "biblioteca": "library", "library": "biblioteca",
        "mazmorra": "dungeon", "dungeon": "mazmorra",
        "portal": "portal", "mausoleo": "mausoleum", "mausoleum": "mausoleo",
    }
    w1 = {loc_translations.get(w, w) for w in clean1.split() if len(w) >= 3}
    w2 = {loc_translations.get(w, w) for w in clean2.split() if len(w) >= 3}
    if w1 and w2:
        overlap = w1 & w2
        if len(overlap) >= 2 and (overlap == w1 or overlap == w2):
            preferred = name1 if len(name1) >= len(name2) else name2
            return True, preferred

    return False, None


def merge_two_locations(
    target: Dict[str, Any],
    source: Dict[str, Any],
    canonical_name: Optional[str] = None,
    known_pc_names: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Merge content of source location into target location."""
    if canonical_name:
        target["name"] = canonical_name
    elif len(str(source.get("name", ""))) > len(str(target.get("name", ""))):
        target["name"] = source["name"]

    d_curr = str(target.get("description", "")).strip()
    d_src = str(source.get("description", "")).strip()
    if d_src and (not d_curr or len(d_src) > len(d_curr)):
        target["description"] = d_src

    # Associated characters: merge unique
    curr_ac = set(str(a).strip() for a in target.get("associated_characters", []) if str(a).strip())
    for a in source.get("associated_characters", []):
        if a and str(a).strip():
            curr_ac.add(str(a).strip())

    target["associated_characters"] = sorted(list(curr_ac))

    # Type: prefer specific type over generic punto_de_interes
    if target.get("type", "").lower() in ("", "punto_de_interes") and source.get("type", "").lower() not in ("", "punto_de_interes"):
        target["type"] = source["type"]

    # Status: update with incoming status if provided
    if source.get("status"):
        target["status"] = source["status"]

    return target


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

    @property
    def output_dir(self) -> Path:
        """Resolve output directory honoring WHISPER_OUTPUT_DIR, outputs, or data/output."""
        if os.environ.get("WHISPER_OUTPUT_DIR"):
            p = Path(os.environ["WHISPER_OUTPUT_DIR"]).resolve()
        else:
            root = Path(__file__).resolve().parent.parent.parent
            if (root / "outputs").is_dir():
                p = (root / "outputs").resolve()
            else:
                p = (root / "data" / "output").resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

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

    def get_campaign_dir(self, name: str) -> Path:
        """Return dedicated campaign directory data/campaigns/<safe_name>/ with recordings and exports subfolders."""
        safe_name = self.sanitize_name(name)
        cdir = self.campaigns_dir / safe_name
        (cdir / "recordings").mkdir(parents=True, exist_ok=True)
        (cdir / "exports").mkdir(parents=True, exist_ok=True)
        return cdir

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
            output_dir = self.output_dir
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
                if "user_character_backstory" not in data:
                    data["user_character_backstory"] = ""
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
            "user_character_backstory": "",
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
        """Save campaign state to disk and ensure campaign folder hierarchy exists."""
        name = state.get("campaign_name", "Campaña Principal")
        state["updated_at"] = datetime.datetime.now().isoformat()
        if "campaign_id" not in state:
            state["campaign_id"] = self.sanitize_name(name)

        if "roster" in state and isinstance(state["roster"], list):
            for m in state["roster"]:
                if isinstance(m, dict):
                    m.pop("is_absent", None)
                    m.pop("absent", None)
        if "universal_pcs" in state and isinstance(state["universal_pcs"], list):
            for m in state["universal_pcs"]:
                if isinstance(m, dict):
                    m.pop("is_absent", None)
                    m.pop("absent", None)

        # Ensure campaign directory hierarchy:
        # data/campaigns/<safe_name>/recordings/
        # data/campaigns/<safe_name>/exports/
        cdir = self.get_campaign_dir(name)

        file_path = self.get_campaign_path(name)
        state_json = json.dumps(state, indent=2, ensure_ascii=False)
        file_path.write_text(state_json, encoding="utf-8")

        # Mirror inside campaign folder as campaign.json
        try:
            (cdir / "campaign.json").write_text(state_json, encoding="utf-8")
        except Exception:
            pass

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
            "user_character_backstory": state.get("user_character_backstory", ""),
            "active_quests": active_quests,
            "all_quests": state.get("quests", []),
            "known_npcs": state.get("npcs", []),
            "roster": state.get("roster", []),
            "universal_pcs": state.get("universal_pcs", []),
            "last_session_recap": last_recap,
        }

    def get_character_backstory(self, name: str, character_name: Optional[str] = None) -> str:
        """Return the character backstory for a campaign or specific character."""
        state = self.load_campaign(name)
        if character_name and character_name.strip():
            cname = character_name.strip()
            # 1. From character_backstories dict
            backstories = state.get("character_backstories", {})
            if cname in backstories and backstories[cname]:
                return backstories[cname]
            for k, v in backstories.items():
                if k.lower() == cname.lower() and v:
                    return v
            # 2. From roster member
            for m in state.get("roster", []):
                if isinstance(m, dict) and (m.get("character_name") or "").strip().lower() == cname.lower():
                    if m.get("backstory"):
                        return m["backstory"]
                    if m.get("is_user_character") or m.get("is_user"):
                        return state.get("user_character_backstory", "")
            # 3. From universal_pcs
            for u in state.get("universal_pcs", []):
                if isinstance(u, dict) and (u.get("personaje") or "").strip().lower() == cname.lower():
                    if u.get("trasfondo"):
                        return u["trasfondo"]
        return state.get("user_character_backstory", "")

    def set_character_backstory(
        self,
        name: str,
        backstory: str,
        character_name: Optional[str] = None,
        is_user_character: bool = True
    ) -> Dict[str, Any]:
        """Update and persist character backstory for a campaign, supporting multiple characters."""
        state = self.load_campaign(name)
        b_clean = (backstory or "").strip()
        state.setdefault("character_backstories", {})

        if character_name and character_name.strip():
            cname = character_name.strip()
            state["character_backstories"][cname] = b_clean
            roster = state.setdefault("roster", [])
            found = False
            for m in roster:
                if isinstance(m, dict):
                    if (m.get("character_name") or "").strip().lower() == cname.lower():
                        m["backstory"] = b_clean
                        if is_user_character:
                            m["is_user_character"] = True
                            m["is_user"] = True
                        found = True
                    elif is_user_character and (m.get("is_user_character") or m.get("is_user")):
                        m["is_user_character"] = False
                        m["is_user"] = False
            if not found:
                roster.append({
                    "player_name": "Roy",
                    "character_name": cname,
                    "species": "",
                    "role": "",
                    "subclass": "",
                    "is_user_character": is_user_character,
                    "is_user": is_user_character,
                    "backstory": b_clean,
                })

            for u in state.get("universal_pcs", []):
                if isinstance(u, dict) and (u.get("personaje") or "").strip().lower() == cname.lower():
                    u["trasfondo"] = b_clean

            if is_user_character:
                state["user_character_backstory"] = b_clean
        else:
            state["user_character_backstory"] = b_clean

        self.save_campaign(state)
        return state

    def get_all_characters(self) -> List[Dict[str, Any]]:
        """Return a list of all player characters across campaigns with their specific backstories."""
        campaigns = self.list_campaigns()
        results: List[Dict[str, Any]] = []
        seen = set()

        for c in campaigns:
            camp_name = c.get("campaign_name") or c.get("name")
            if not camp_name:
                continue
            state = self.load_campaign(camp_name)
            user_backstory = state.get("user_character_backstory", "")
            char_backstories = state.get("character_backstories", {})
            roster = state.get("roster", [])

            for m in roster:
                if not isinstance(m, dict):
                    continue
                cname = (m.get("character_name") or "").strip()
                if not cname or cname.lower() in ("(dm)", "dm", "dungeon master"):
                    continue
                is_user = bool(m.get("is_user_character") or m.get("is_user"))
                key = (camp_name.lower(), cname.lower())
                if key in seen:
                    continue
                seen.add(key)
                c_backstory = m.get("backstory") or char_backstories.get(cname) or ""
                if not c_backstory and is_user:
                    c_backstory = user_backstory

                results.append({
                    "character_name": cname,
                    "campaign_name": camp_name,
                    "player_name": m.get("player_name", ""),
                    "species": m.get("species", ""),
                    "role": m.get("role", ""),
                    "subclass": m.get("subclass", ""),
                    "is_user_character": is_user,
                    "has_backstory": bool(c_backstory),
                    "backstory": c_backstory,
                })

            for upc in state.get("universal_pcs", []):
                if not isinstance(upc, dict):
                    continue
                cname = (upc.get("personaje") or upc.get("character_name") or "").strip()
                if not cname or cname.lower() in ("(dm)", "dm", "dungeon master"):
                    continue
                key = (camp_name.lower(), cname.lower())
                if key in seen:
                    continue
                seen.add(key)
                c_backstory = upc.get("trasfondo") or char_backstories.get(cname) or ""
                results.append({
                    "character_name": cname,
                    "campaign_name": camp_name,
                    "player_name": upc.get("jugador") or upc.get("player_name", ""),
                    "species": upc.get("raza") or upc.get("species", ""),
                    "role": upc.get("clase") or upc.get("role", ""),
                    "subclass": upc.get("subclase") or upc.get("subclass", ""),
                    "is_user_character": False,
                    "has_backstory": bool(c_backstory),
                    "backstory": c_backstory,
                })

        results.sort(key=lambda x: (not x["is_user_character"], not x["has_backstory"], x["campaign_name"].lower(), x["character_name"].lower()))
        return results

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
        locations: Optional[List[Dict[str, Any]]] = None,
        items: Optional[List[Dict[str, Any]]] = None,
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

        # Purge legacy stray root fields if present, but preserve detected_party if explicitly passed
        state.pop("detected_pcs", None)
        if detected_party is not None:
            state["detected_party"] = detected_party
        else:
            state.pop("detected_party", None)

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

            existing_roster = state.get("roster", [])
            merged_players = []
            for r in existing_roster:
                if r.get("character_name") == "(DM)" or r.get("role") == "Dungeon Master (DM)":
                    continue
                # Purge mock DM Rodrigo/Markus if external campaign
                if r.get("player_name") in ("Rodrigo", "Markus") and not (r.get("is_user_character") or r.get("is_user")):
                    continue
                merged_players.append(dict(r))

            for cp in clean_pcs:
                cp_pl = cp["player_name"].strip().lower()
                cp_char = cp["character_name"].strip().lower()
                if "invitado" in cp_pl or "guest" in cp_pl or "invitado" in cp_char or "guest" in cp_char:
                    continue
                match = None
                for mp in merged_players:
                    mp_pl = (mp.get("player_name") or "").strip().lower()
                    mp_char = (mp.get("character_name") or "").strip().lower()
                    if cp_pl and cp_pl not in ("-", "desconocido", "") and mp_pl == cp_pl:
                        match = mp
                        break
                    if cp_char and cp_char not in ("-", "") and (mp_char == cp_char or is_npc_name_match(mp_char, cp_char)):
                        match = mp
                        break
                if match:
                    for attr in ("species", "role", "subclass"):
                        if cp.get(attr) and cp[attr] not in ("-", "Desconocido", "N/A", ""):
                            match[attr] = cp[attr]
                    if cp["character_name"] and cp["character_name"] not in ("-", "") and len(cp["character_name"]) > len(match.get("character_name", "")):
                        match["character_name"] = cp["character_name"]
                    if cp["player_name"] and cp["player_name"] not in ("-", "") and len(cp["player_name"]) > len(match.get("player_name", "")):
                        match["player_name"] = cp["player_name"]
                else:
                    merged_players.append(cp)

            # Synchronize any missing players from universal_pcs
            for upc in state.get("universal_pcs", []):
                upc_char = str(upc.get("personaje") or "").strip()
                upc_pl = str(upc.get("jugador") or "").strip()
                if not upc_char or upc_char in ("-", "(DM)", "Dungeon Master"):
                    continue
                has_in_roster = any(
                    (str(r.get("character_name", "")).strip().lower() == upc_char.lower())
                    or (str(r.get("character_name", "")).strip().lower() in [str(a).strip().lower() for a in upc.get("aliases", [])])
                    or (upc_pl and upc_pl not in ("-", "Desconocido", "") and str(r.get("player_name", "")).strip().lower() == upc_pl.lower())
                    for r in merged_players
                )
                if not has_in_roster:
                    merged_players.append({
                        "player_name": upc_pl or "-",
                        "character_name": upc_char,
                        "species": str(upc.get("especie") or "-").strip(),
                        "role": str(upc.get("clase") or "-").strip(),
                        "subclass": str(upc.get("subclase") or "-").strip(),
                        "is_user_character": False,
                        "is_user": False,
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
            elif existing_roster and (existing_roster[0].get("character_name") == "(DM)" or existing_roster[0].get("role") == "Dungeon Master (DM)"):
                new_roster.append(dict(existing_roster[0]))
            new_roster.extend(merged_players)
            state["roster"] = new_roster
        elif roster and len(roster) > 0:
            roster_has_user_char = any(p.get("is_user_character") or p.get("is_user") for p in roster)
            roster_has_markus = any("markus" in str(p.get("character_name", "")).lower() or "markus" in str(p.get("player_name", "")).lower() for p in roster)
            detected_has_markus = any("markus" in str(p.get("character_name", "") or p.get("personaje", "")).lower() or "markus" in str(p.get("player_name", "") or p.get("jugador", "")).lower() for p in (fallback_party or []))

            # Only purge/replace if external campaign mistakenly carried over Markus from template without being starred or detected
            if (not is_private or is_yt_campaign) and fallback_party and roster_has_markus and not detected_has_markus and not roster_has_user_char:
                state["roster"] = fallback_party
            else:
                # Merge incoming roster with existing roster to preserve rotating/absent players
                existing_roster = state.get("roster", [])
                if existing_roster:
                    merged_r = []
                    dm_entry = existing_roster[0] if existing_roster and (existing_roster[0].get("character_name") == "(DM)" or existing_roster[0].get("role") == "Dungeon Master (DM)") else None
                    if dm_entry:
                        merged_r.append(dict(dm_entry))
                    curr_players = [dict(r) for r in existing_roster if r != dm_entry and r.get("character_name") != "(DM)"]
                    for inc in roster:
                        if inc.get("character_name") == "(DM)" or inc.get("role") == "Dungeon Master (DM)":
                            continue
                        inc_pl = str(inc.get("player_name", "")).strip().lower()
                        inc_char = str(inc.get("character_name", "")).strip().lower()
                        m = next((p for p in curr_players if (inc_pl and inc_pl not in ("-", "") and str(p.get("player_name", "")).strip().lower() == inc_pl) or (inc_char and inc_char not in ("-", "") and str(p.get("character_name", "")).strip().lower() == inc_char)), None)
                        if m:
                            for k, v in inc.items():
                                if v not in (None, "", "-", "N/A"):
                                    m[k] = v
                        else:
                            curr_players.append(inc)
                    merged_r.extend(curr_players)
                    state["roster"] = merged_r
                else:
                    state["roster"] = roster
        elif fallback_party:
            existing_roster = state.get("roster", [])
            if existing_roster:
                # Merge fallback_party without dropping existing roster
                dm_entry = existing_roster[0] if existing_roster and (existing_roster[0].get("character_name") == "(DM)" or existing_roster[0].get("role") == "Dungeon Master (DM)") else None
                curr_players = [dict(r) for r in existing_roster if r != dm_entry and r.get("character_name") != "(DM)"]
                for fb in fallback_party:
                    fb_pl = str(fb.get("player_name") or fb.get("jugador") or "").strip().lower()
                    fb_char = str(fb.get("character_name") or fb.get("personaje") or "").strip().lower()
                    if "invitado" in fb_pl or "guest" in fb_pl or "invitado" in fb_char or "guest" in fb_char:
                        continue
                    m = next((p for p in curr_players if (fb_pl and fb_pl not in ("-", "") and str(p.get("player_name", "")).strip().lower() == fb_pl) or (fb_char and fb_char not in ("-", "") and str(p.get("character_name", "")).strip().lower() == fb_char)), None)
                    if not m:
                        curr_players.append({
                            "player_name": str(fb.get("player_name") or fb.get("jugador") or "-").strip(),
                            "character_name": str(fb.get("character_name") or fb.get("personaje") or "-").strip(),
                            "species": str(fb.get("species") or fb.get("especie") or "-").strip(),
                            "role": str(fb.get("role") or fb.get("clase") or "-").strip(),
                            "subclass": str(fb.get("subclass") or fb.get("subclase") or "-").strip(),
                        })
                merged_all = []
                if dm_entry:
                    merged_all.append(dict(dm_entry))
                merged_all.extend(curr_players)
                state["roster"] = merged_all
            else:
                state["roster"] = [p for p in fallback_party if not any(x in str(p.get("character_name") or p.get("personaje", "")).lower() or x in str(p.get("player_name") or p.get("jugador", "")).lower() for x in ("invitado", "guest"))]

        # Clean is_absent from state["roster"] so absence is NEVER remembered permanently across sessions
        if state.get("roster"):
            clean_roster = []
            for member in state["roster"]:
                if isinstance(member, dict):
                    m = dict(member)
                    m.pop("is_absent", None)
                    m.pop("absent", None)
                    clean_roster.append(m)
                else:
                    clean_roster.append(member)
            state["roster"] = clean_roster

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
            "detected_party": [] if detected_pcs else (detected_party or []),
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

                    # Update semantic category and vital status
                    if unpc.get("category"):
                        if matched_npc.get("category") != "clave" or unpc.get("category") == "clave":
                            matched_npc["category"] = unpc["category"]
                    elif not matched_npc.get("category"):
                        matched_npc["category"] = "clave" if matched_npc.get("tipo") == "importantes" else "interaccion_contexto"

                    if unpc.get("status"):
                        matched_npc["status"] = unpc["status"]
                    elif not matched_npc.get("status"):
                        matched_npc["status"] = "activo"

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

                    # Merge aliases
                    npc_aliases = matched_npc.setdefault("aliases", [])
                    for al in unpc.get("aliases", []):
                        al_clean = str(al).strip()
                        if al_clean and al_clean not in npc_aliases and al_clean.lower() != matched_npc.get("name", "").lower():
                            npc_aliases.append(al_clean)
                else:
                    # Add new NPC
                    notes = unpc.get("notes", [])
                    if not notes and unpc.get("role"):
                        notes = [f"Sesión {actual_session_num}: {unpc.get('role')}"]
                    existing_npcs.append({
                        "name": npc_name,
                        "aliases": [str(al).strip() for al in unpc.get("aliases", []) if str(al).strip()],
                        "role": unpc.get("role", "Desconocido / PNJ"),
                        "tipo": unpc.get("tipo", "interaccion_contexto"),
                        "category": unpc.get("category") or ("clave" if unpc.get("tipo") == "importantes" else "interaccion_contexto"),
                        "status": unpc.get("status") or "activo",
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
                or "invitado" in char_lower
                or "invitada" in char_lower
                or "guest" in char_lower
                or "invitado" in player_name_raw.lower()
                or "guest" in player_name_raw.lower()
                or "invitado" in str(upc.get("rol_en_sesion", "")).lower()
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
            if not matched_pc:
                # Match against aliases
                for p in existing_universal_pcs:
                    aliases_clean = [str(a).strip().lower() for a in p.get("aliases", [])]
                    if char_lower in aliases_clean:
                        matched_pc = p
                        break
            if not matched_pc and player_name_raw and player_name_raw.lower() not in ("-", "desconocido", "n/a", ""):
                # Match by player name with shared tokens or name match
                for p in existing_universal_pcs:
                    pl = str(p.get("jugador") or p.get("player_name") or "").strip().lower()
                    if pl == player_name_raw.lower():
                        p_char = str(p.get("personaje") or "").strip()
                        c1 = re.sub(r"[^\w\s]", "", p_char.lower())
                        c2 = re.sub(r"[^\w\s]", "", char_lower)
                        t1 = {t for t in c1.split() if len(t) >= 3 and t not in generic_titles}
                        t2 = {t for t in c2.split() if len(t) >= 3 and t not in generic_titles}
                        p_aliases = [str(a).strip().lower() for a in p.get("aliases", [])]
                        if (t1 and t2 and (t1 & t2)) or char_lower in p_aliases or is_npc_name_match(p_char, char_name):
                            matched_pc = p
                            break

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
                if len(char_name) > len(old_pc_name) and char_name.lower() != old_pc_name.lower():
                    pc_aliases = matched_pc.setdefault("aliases", [])
                    if old_pc_name and old_pc_name not in pc_aliases:
                        pc_aliases.append(old_pc_name)
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

                # Merge aliases
                pc_aliases = matched_pc.setdefault("aliases", [])
                for al in upc.get("aliases", []):
                    al_clean = str(al).strip()
                    if al_clean and al_clean not in pc_aliases and al_clean.lower() != matched_pc.get("personaje", "").lower():
                        pc_aliases.append(al_clean)

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
                    "aliases": [str(al).strip() for al in upc.get("aliases", []) if str(al).strip()],
                    "jugador": str(upc.get("jugador") or upc.get("player_name") or "-").strip(),
                    "especie": str(upc.get("especie") or upc.get("species") or "-").strip(),
                    "clase": char_cls or "-",
                    "subclase": str(upc.get("subclase") or upc.get("subclass") or "-").strip(),
                    "debut_sesion": int(debut_val),
                    "hitos_acumulados": hitos,
                })

        # 5. Merge Locations
        if locations:
            existing_locations = state.setdefault("locations", [])
            for loc in locations:
                if not isinstance(loc, dict):
                    continue
                loc_name = str(loc.get("name") or "").strip()
                if not loc_name:
                    continue

                raw_assoc = [str(ac).strip() for ac in loc.get("associated_characters", []) if str(ac).strip()]
                loc["associated_characters"] = raw_assoc

                matched_loc = next((l for l in existing_locations if are_locations_duplicate(l, loc)[0]), None)
                if matched_loc:
                    _, canonical = are_locations_duplicate(matched_loc, loc)
                    merge_two_locations(matched_loc, loc, canonical_name=canonical)
                else:
                    existing_locations.append({
                        "name": loc_name,
                        "type": loc.get("type", "punto_de_interes"),
                        "description": loc.get("description", ""),
                        "status": loc.get("status", "explorado"),
                        "associated_characters": raw_assoc,
                    })

        # 6. Merge Items
        if items:
            existing_items = state.setdefault("items", [])
            for it in items:
                if not isinstance(it, dict):
                    continue
                it_name = str(it.get("name") or "").strip()
                if not it_name:
                    continue
                matched_it = next((i for i in existing_items if are_items_duplicate(i, it)[0]), None)
                if matched_it:
                    _, canonical = are_items_duplicate(matched_it, it)
                    merge_two_items(matched_it, it, canonical_name=canonical)
                else:
                    existing_items.append({
                        "name": it_name,
                        "type": it.get("type", "artefacto"),
                        "description": it.get("description", ""),
                        "holder": it.get("holder", "-"),
                        "status": it.get("status", "en_posesion"),
                    })

        self._deduplicate_state(state, campaign_name=name)
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
        """Update an NPC's name across the directory, sessions, quests, locations, and items after user spell review."""
        state = self.load_campaign(name)
        clean_new = new_name.strip()
        clean_old = old_name.strip()
        if not clean_new or not clean_old or clean_new.lower() == clean_old.lower():
            return state

        # Collect tokens to match: full old name, slash parts, and known aliases
        tokens_to_match = [clean_old]
        if "/" in clean_old:
            tokens_to_match.extend([p.strip() for p in clean_old.split("/") if len(p.strip()) >= 3])

        # Also find target npc in state to check its existing aliases
        for npc in state.get("npcs", []):
            if (npc.get("name") or "").strip().lower() == clean_old.lower():
                for al in npc.get("aliases", []):
                    al_s = str(al).strip()
                    if len(al_s) >= 3 and al_s.lower() != clean_new.lower() and al_s not in tokens_to_match:
                        tokens_to_match.append(al_s)
                break

        patterns = [
            re.compile(rf"\b{re.escape(tok)}\b", re.IGNORECASE)
            for tok in sorted(set(tokens_to_match), key=len, reverse=True)
        ]

        def _sub_text(text: Any) -> Any:
            if not isinstance(text, str):
                return text
            res = text
            for pat in patterns:
                res = pat.sub(clean_new, res)
            return res

        # 1. Update in NPCs directory
        for npc in state.get("npcs", []):
            npc_name = (npc.get("name") or "").strip()
            if npc_name.lower() == clean_old.lower():
                npc["name"] = clean_new
                aliases = npc.setdefault("aliases", [])
                if clean_old not in aliases and clean_old.lower() != clean_new.lower():
                    aliases.append(clean_old)
            elif any(pat.search(npc_name) for pat in patterns):
                for pat in patterns:
                    npc_name = pat.sub(clean_new, npc_name)
                npc["name"] = npc_name

            if "notes" in npc and isinstance(npc["notes"], list):
                npc["notes"] = [_sub_text(note) for note in npc["notes"]]
            if "role" in npc:
                npc["role"] = _sub_text(npc["role"])
            if "description" in npc:
                npc["description"] = _sub_text(npc["description"])

        # 2. Update across session records and chronicles
        for session in state.get("sessions", []):
            if "detected_npc_names" in session and isinstance(session["detected_npc_names"], list):
                updated_detected = []
                for det in session["detected_npc_names"]:
                    det_str = str(det).strip()
                    if det_str.lower() == clean_old.lower():
                        if clean_new not in updated_detected:
                            updated_detected.append(clean_new)
                    elif any(pat.search(det_str) for pat in patterns):
                        subbed = _sub_text(det_str)
                        if subbed not in updated_detected:
                            updated_detected.append(subbed)
                    else:
                        if det_str not in updated_detected:
                            updated_detected.append(det_str)
                session["detected_npc_names"] = updated_detected

            for key in (
                "chronicle_text",
                "chronicle_markdown",
                "recap_text",
                "next_session_script",
                "closing_expectations",
                "episode_synopsis",
                "session_title",
                "title",
            ):
                if key in session and isinstance(session[key], str):
                    session[key] = _sub_text(session[key])

            # Update detected_pcs roles and hitos
            for pc in session.get("detected_pcs", []):
                if "rol_en_sesion" in pc and isinstance(pc["rol_en_sesion"], str):
                    pc["rol_en_sesion"] = _sub_text(pc["rol_en_sesion"])
                if "hitos_acumulados" in pc and isinstance(pc["hitos_acumulados"], list):
                    pc["hitos_acumulados"] = [_sub_text(h) for h in pc["hitos_acumulados"]]

            # Update detected_party
            for p in session.get("detected_party", []):
                if "rol_en_sesion" in p and isinstance(p["rol_en_sesion"], str):
                    p["rol_en_sesion"] = _sub_text(p["rol_en_sesion"])
                if "session_role" in p and isinstance(p["session_role"], str):
                    p["session_role"] = _sub_text(p["session_role"])

        # 3. Update in quests
        for quest in state.get("quests", []):
            for key in ("title", "context", "lifecycle_notes"):
                if key in quest and isinstance(quest[key], str):
                    quest[key] = _sub_text(quest[key])
            for sub in quest.get("subobjectives", []):
                if isinstance(sub, dict) and "text" in sub:
                    sub["text"] = _sub_text(sub["text"])

        # 4. Update in locations
        for loc in state.get("locations", []):
            if "associated_characters" in loc and isinstance(loc["associated_characters"], list):
                updated_assoc = []
                for ac in loc["associated_characters"]:
                    ac_str = str(ac).strip()
                    if ac_str.lower() == clean_old.lower():
                        if clean_new not in updated_assoc:
                            updated_assoc.append(clean_new)
                    elif pattern.search(ac_str):
                        subbed = pattern.sub(clean_new, ac_str)
                        if subbed not in updated_assoc:
                            updated_assoc.append(subbed)
                    else:
                        if ac_str not in updated_assoc:
                            updated_assoc.append(ac_str)
                loc["associated_characters"] = updated_assoc
            if "description" in loc and isinstance(loc["description"], str):
                loc["description"] = _sub_text(loc["description"])

        # 5. Update in items
        for item in state.get("items", []):
            if "holder" in item and isinstance(item["holder"], str):
                item["holder"] = _sub_text(item["holder"])
            if "description" in item and isinstance(item["description"], str):
                item["description"] = _sub_text(item["description"])

        # 6. Update in universal_pcs hitos and session_role
        for upc in state.get("universal_pcs", []):
            if "session_role" in upc and isinstance(upc["session_role"], str):
                upc["session_role"] = _sub_text(upc["session_role"])
            if "hitos_acumulados" in upc and isinstance(upc["hitos_acumulados"], list):
                upc["hitos_acumulados"] = [_sub_text(h) for h in upc["hitos_acumulados"]]

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
        out_dir = self.output_dir
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

        # Synchronize roster with universal_pcs so absent rotating party members are preserved in the table
        roster = state.get("roster", [])
        if roster:
            for pc in pcs:
                p_char = str(pc.get("personaje") or "").strip()
                p_pl = str(pc.get("jugador") or "").strip()
                if not p_char or p_char in ("-", "(DM)", "Dungeon Master"):
                    continue
                has_in_roster = any(
                    (str(r.get("character_name", "")).strip().lower() == p_char.lower())
                    or (str(r.get("character_name", "")).strip().lower() in [str(a).strip().lower() for a in pc.get("aliases", [])])
                    or (p_pl and p_pl not in ("-", "Desconocido", "") and str(r.get("player_name", "")).strip().lower() == p_pl.lower())
                    for r in roster
                )
                if not has_in_roster:
                    roster.append({
                        "player_name": p_pl or "-",
                        "character_name": p_char,
                        "species": str(pc.get("especie") or "-").strip(),
                        "role": str(pc.get("clase") or "-").strip(),
                        "subclass": str(pc.get("subclase") or "-").strip(),
                        "is_user_character": False,
                        "is_user": False,
                    })

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

                        # Preserve semantic category and status
                        cat1 = npc1.get("category")
                        cat2 = npc2.get("category")
                        if cat1 == "clave" or (cat1 and not cat2):
                            npc2["category"] = cat1
                        elif not cat2:
                            npc2["category"] = "clave" if npc2.get("tipo") == "importantes" else "interaccion_contexto"

                        st1 = npc1.get("status")
                        st2 = npc2.get("status")
                        if st1 and (not st2 or st2 == "activo"):
                            npc2["status"] = st1
                        elif not st2:
                            npc2["status"] = "activo"

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

        # --- 3. Deduplicate items ---
        items = state.get("items", [])
        i = 0
        while i < len(items):
            merged_any = False
            j = 0
            while j < len(items):
                if i != j:
                    it1 = items[i]
                    it2 = items[j]
                    is_dup, canonical = are_items_duplicate(it1, it2)
                    if is_dup:
                        n1 = str(it1.get("name", "")).strip()
                        n2 = str(it2.get("name", "")).strip()
                        merge_two_items(it1, it2, canonical_name=canonical)
                        items.pop(j)
                        merged_events.append({
                            "type": "item",
                            "source": n2,
                            "target": it1.get("name", n1),
                        })
                        merged_any = True
                        break
                j += 1
            if not merged_any:
                i += 1

        for it in items:
            it_n = str(it.get("name", "")).strip().lower()
            if "zun" in it_n or (("pozo" in it_n or "collar" in it_n or "medall" in it_n) and ("reliquia" in it_n or "rosario" in it_n or "sagrado" in it_n)):
                it["name"] = "Collar / Rosario Sagrado de Zun (Medallón del Pozo)"

        # --- 4. Deduplicate locations ---
        locs = state.get("locations", [])
        i = 0
        while i < len(locs):
            merged_any = False
            j = 0
            while j < len(locs):
                if i != j:
                    l1 = locs[i]
                    l2 = locs[j]
                    is_dup, canonical = are_locations_duplicate(l1, l2)
                    if is_dup:
                        n1 = str(l1.get("name", "")).strip()
                        n2 = str(l2.get("name", "")).strip()
                        merge_two_locations(l1, l2, canonical_name=canonical)
                        locs.pop(j)
                        merged_events.append({
                            "type": "location",
                            "source": n2,
                            "target": l1.get("name", n1),
                        })
                        merged_any = True
                        break
                j += 1
            if not merged_any:
                i += 1

        # --- 5. Clean redundant detected_party in sessions (E8) ---
        for s in state.get("sessions", []):
            if s.get("detected_party") and s.get("detected_pcs"):
                s["detected_party"] = []
                merged_events.append({
                    "type": "session_cleanup",
                    "session_number": s.get("session_number"),
                })

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
                
                # Category merge
                s_cat = source_npc.get("category")
                t_cat = target_npc.get("category")
                if s_cat and not t_cat:
                    target_npc["category"] = s_cat
                elif s_cat == "clave":
                    target_npc["category"] = "clave"
                    target_npc["tipo"] = "importantes"
                elif s_cat in ("aliado", "invocacion", "amenaza") and t_cat in ("interaccion_contexto", None, ""):
                    target_npc["category"] = s_cat

                # Status merge
                s_status = source_npc.get("status")
                if s_status and (not target_npc.get("status") or target_npc.get("status") == "activo"):
                    target_npc["status"] = s_status

                if "category" not in target_npc:
                    target_npc["category"] = "clave" if target_npc.get("tipo") == "importantes" else "interaccion_contexto"
                if "status" not in target_npc:
                    target_npc["status"] = "activo"

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

    def update_npc(
        self,
        campaign_name: str,
        npc_name: str,
        new_name: Optional[str] = None,
        role: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        tipo: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        notes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Actualiza los datos de un PNJ existente en la campaña."""
        state = self.load_campaign(campaign_name)
        npcs = state.setdefault("npcs", [])

        target_npc = None
        for n in npcs:
            if str(n.get("name", "")).strip().lower() == npc_name.strip().lower():
                target_npc = n
                break

        if not target_npc:
            for n in npcs:
                if any(str(a).strip().lower() == npc_name.strip().lower() for a in n.get("aliases", [])):
                    target_npc = n
                    break

        if not target_npc:
            raise ValueError(f"No se encontró el PNJ '{npc_name}' en la campaña '{campaign_name}'.")

        old_name = target_npc.get("name", npc_name)
        if new_name and new_name.strip() and new_name.strip() != old_name:
            final_new_name = new_name.strip()
            target_aliases = target_npc.setdefault("aliases", [])
            if old_name not in target_aliases:
                target_aliases.append(old_name)
            target_npc["name"] = final_new_name
            self._sync_roster_and_sessions(state, old_name, final_new_name)

        if role is not None:
            target_npc["role"] = role.strip()

        if category is not None:
            cat_clean = category.strip().lower()
            target_npc["category"] = cat_clean
            if cat_clean == "clave":
                target_npc["tipo"] = "importantes"
            elif cat_clean in ("aliado", "invocacion", "amenaza", "interaccion_contexto"):
                target_npc["tipo"] = "interaccion_contexto"

        if tipo is not None and category is None:
            target_npc["tipo"] = tipo.strip().lower()
            if target_npc["tipo"] == "importantes" and target_npc.get("category") != "clave":
                target_npc["category"] = "clave"

        if status is not None:
            target_npc["status"] = status.strip().lower()

        if aliases is not None:
            target_npc["aliases"] = [a.strip() for a in aliases if a and a.strip()]

        if notes is not None:
            target_npc["notes"] = notes

        if not target_npc.get("category"):
            target_npc["category"] = "clave" if target_npc.get("tipo") == "importantes" else "interaccion_contexto"
        if not target_npc.get("status"):
            target_npc["status"] = "activo"

        self.save_campaign(state)
        return target_npc

