"""Campaign-scoped spelling normalization; never infer a cast or a pronunciation."""
import re
from typing import Any, Dict, List, Optional

# Common roles/objects are unsafe automatic aliases even if a model proposes them.
# Keep the original text for review instead of turning an object into a person.
AMBIGUOUS_NAME_WORDS = frozenset({
    "ataúd", "ataud", "coffin", "guardia", "guard", "capitán", "capitan", "captain",
    "narrador", "master", "grupo", "party", "invitado", "guest", "desconocido",
})
_PLACEHOLDERS = frozenset({"", "-", "(dm)", "dm", "dungeon master", "n/a", "(n/a - dm)"})


def _aliases(member):
    values = member.get("aliases") or []
    return [a.strip() for a in values if isinstance(a, str) and a.strip()] if isinstance(values, list) else []


def campaign_name_entries(roster=None, campaign=None):
    """Read names/aliases from this campaign only; return copies, never mutate state.

    These entries are for spelling/vocabulary, not speaker identity or party roster.
    A stored alias is not independently verified speech or new campaign evidence.
    """
    state = campaign or {}
    groups = [roster or [], state.get("roster", []), state.get("universal_pcs", []),
              state.get("npcs", state.get("known_npcs", []))]
    entries = {}
    player_names = set()
    for group in groups:
        for member in group if isinstance(group, list) else []:
            if not isinstance(member, dict):
                continue
            player = member.get("player_name") or member.get("jugador")
            if player:
                player_names.add(str(player).strip().casefold())
            name = str(member.get("character_name") or member.get("personaje") or member.get("name") or "").strip()
            if name.casefold() in _PLACEHOLDERS:
                continue
            entry = entries.setdefault(name.casefold(), {"character_name": name, "aliases": []})
            rejected = set(entry.get("_rejected_aliases", []))
            rejected.update(str(a).casefold() for a in member.get("_rejected_aliases", []))
            entry["_rejected_aliases"] = sorted(rejected)
            if player:
                entry["player_name"] = str(player)
            for alias in _aliases(member):
                if alias not in entry["aliases"]:
                    entry["aliases"].append(alias)
    for entry in entries.values():
        entry["aliases"] = [a for a in entry["aliases"] if a.casefold() not in entry["_rejected_aliases"]]
        entry["_player_names"] = sorted(player_names)
    return list(entries.values())


def enrich_roster_aliases(roster, campaign):
    names = {r["character_name"].casefold(): r for r in campaign_name_entries(roster, campaign)}
    result = []
    for member in roster or []:
        row = dict(member)
        name = str(row.get("character_name") or row.get("personaje") or "").strip().casefold()
        aliases = names.get(name, {}).get("aliases", [])
        if aliases:
            row["aliases"] = list(aliases)
        result.append(row)
    return result


def name_alias_map(roster):
    entries = campaign_name_entries(roster)
    canonical = {r["character_name"].casefold(): r["character_name"] for r in entries}
    player_names = {str(r.get("player_name") or "").strip().casefold() for r in entries}
    player_names.update(str(p).casefold() for r in roster or [] for p in r.get("_player_names", []))
    player_names.update(str(p).casefold() for r in entries for p in r.get("_player_names", []))
    candidates = {key: {value} for key, value in canonical.items()}
    for entry in entries:
        name = entry["character_name"]
        for alias in _aliases(entry):
            key = alias.casefold()
            if key in canonical and canonical[key] != name:
                continue  # A real character name wins over another entity's alias.
            candidates.setdefault(key, set()).add(name)
    return {key: next(iter(names)) for key, names in candidates.items()
            if len(names) == 1 and len(key) >= 3
            and key not in AMBIGUOUS_NAME_WORDS and key not in player_names}


def normalize_transcript_roster(text: str, roster: Optional[List[Dict[str, Any]]] = None) -> str:
    """Apply unambiguous configured aliases in one pass, with no global defaults."""
    if not text or not roster:
        return text or ""
    mapping = name_alias_map(roster)
    if not mapping:
        return text
    alternatives = "|".join(re.escape(key) for key in sorted(mapping, key=len, reverse=True))
    return re.sub(r"(?<!\w)(?:" + alternatives + r")(?!\w)",
                  lambda match: mapping[match.group().casefold()], text, flags=re.IGNORECASE)


# Compatibility import name; behavior remains entirely campaign-scoped.
normalize_roster_phonetics = normalize_transcript_roster
