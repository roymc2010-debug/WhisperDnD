"""Pure, provenance-aware corrections for campaign history."""
import copy
import json
import re

COLLECTIONS = ("npcs", "locations", "items", "quests")
TEXT_FIELDS = {
    "chronicle_text", "chronicle_markdown", "raw_transcript", "transcript", "summary",
    "recap_text", "next_session_script", "closing_expectations", "episode_synopsis",
    "description", "descripcion", "context", "lifecycle_notes", "notes", "hitos_acumulados",
    "prior_lore", "user_coaching", "markus_coaching", "title", "session_title", "role",
    "rol_en_sesion", "session_role", "text", "note",
}


def entity_name(record):
    return str(record.get("name") or record.get("title") or record.get("personaje") or record.get("id") or "")


def same_entity(left, right):
    if left.get("id") and right.get("id"):
        return left["id"] == right["id"]
    left_names = {entity_name(left).casefold(), *(str(a).casefold() for a in left.get("aliases", []))}
    right_names = {entity_name(right).casefold(), *(str(a).casefold() for a in right.get("aliases", []))}
    return bool((left_names & right_names) - {""})


def collect_entity_changes(before, after, inputs):
    changes = {}
    for collection in COLLECTIONS:
        entries = []
        for current in after.get(collection, []):
            previous = next((record for record in before.get(collection, []) if same_entity(record, current)), None)
            if previous != current:
                entries.append({"before": copy.deepcopy(previous), "after": copy.deepcopy(current)})
        changes[collection] = entries
    return {"version": 1, "collections": changes, "inputs": copy.deepcopy(inputs)}


def protected_player_names(state):
    names = set()
    for person in state.get("roster", []) + state.get("universal_pcs", []):
        for key in ("name", "nombre", "personaje", "character_name", "player_name", "jugador"):
            value = str(person.get(key) or "").strip()
            if value and value not in ("-", "(DM)", "N/A"):
                names.add(value)
    return names


def rename_npc_history(state, old_name, new_name):
    protected = protected_player_names(state)
    if old_name.casefold() in {value.casefold() for value in protected}:
        raise ValueError("Ese nombre coincide con un jugador o protagonista; no se puede sustituir automáticamente en la narración.")
    protected_pattern = "|".join(re.escape(value) for value in sorted(protected, key=len, reverse=True))
    prefix = rf"(?<!\w)(?:{protected_pattern})(?!\w)|" if protected_pattern else ""
    pattern = re.compile(prefix + rf"(?<!\w)(?P<npc>{re.escape(old_name)})(?!\w)", re.IGNORECASE)

    def replace(text):
        return pattern.sub(lambda match: new_name if match.group("npc") else match.group(0), text)

    def walk(value, narrative=False):
        if isinstance(value, str):
            return replace(value) if narrative else value
        if isinstance(value, list):
            return [walk(child, narrative) for child in value]
        if isinstance(value, dict):
            return {key: (new_name if key == "holder" and isinstance(child, str)
                          and child.casefold() == old_name.casefold()
                          else walk(child, key in TEXT_FIELDS)) for key, child in value.items()}
        return value

    corrected = walk(state)
    state.clear()
    state.update(corrected)
    for session in state.get("sessions", []):
        session["detected_npc_names"] = [new_name if str(name).casefold() == old_name.casefold() else name
                                         for name in session.get("detected_npc_names", [])]
        journal = session.get("entity_changes", {})
        for entry in journal.get("collections", {}).get("npcs", []):
            for key in ("before", "after"):
                record = entry.get(key)
                if record and str(record.get("name", "")).casefold() == old_name.casefold():
                    record["name"] = new_name
        for record in journal.get("inputs", {}).get("npcs", []):
            if str(record.get("name", "")).casefold() == old_name.casefold():
                record["name"] = new_name


def _references(session, record):
    names = [entity_name(record), *record.get("aliases", [])]
    text = json.dumps({key: value for key, value in session.items() if key not in {"entity_changes", "canon_evidence", "generation_metadata", "review_id", "review_status", "review_decision"}}, ensure_ascii=False)
    if any(name and re.search(rf"(?<!\w){re.escape(str(name))}(?!\w)", text, re.IGNORECASE) for name in names):
        return True
    return any(same_entity(record, incoming) for values in session.get("entity_changes", {}).get("inputs", {}).values()
               for incoming in values if isinstance(incoming, dict))


def _session_tag(value, number):
    if isinstance(value, dict):
        return str(value.get("session_number", value.get("source_session", ""))) == str(number)
    return bool(re.match(rf"^\s*(?:sesi[oó]n|session)\s*#?\s*{number}(?!\d)\b", str(value), re.IGNORECASE))


def _undo_fields(current, before, after, claimed):
    before = before or {}
    manual = current.get("_manual_fields", [])
    for field, previous_after in after.items():
        if field in ("name", "id", "aliases", "first_seen_session", "started_session", "_manual_fields") or field in manual:
            continue
        previous_before = before.get(field)
        if previous_before == previous_after:
            continue
        if isinstance(previous_after, list) and isinstance(current.get(field), list):
            original = previous_before if isinstance(previous_before, list) else []
            claims = [item for payload in claimed for item in payload.get(field, [])] if all(isinstance(payload.get(field, []), list) for payload in claimed) else []
            current[field] = [item for item in current[field] if item not in previous_after or item in original or item in claims]
            for item in original:
                if item not in previous_after and item not in current[field]:
                    current[field].append(copy.deepcopy(item))
        elif current.get(field) == previous_after and not any(field in payload for payload in claimed):
            if field in before:
                current[field] = copy.deepcopy(previous_before)
            else:
                current.pop(field, None)


def remove_session_contributions(state, number):
    """Mutate an in-memory state and return an auditable cleanup report."""
    selected = next((session for session in state.get("sessions", []) if str(session.get("session_number")) == str(number)), None)
    if selected is None:
        raise FileNotFoundError(f"No existe la sesión #{number}.")
    remaining = [session for session in state["sessions"] if session is not selected]
    journal = selected.get("entity_changes", {})
    report = {"removed": {key: [] for key in COLLECTIONS}, "shared": {key: [] for key in COLLECTIONS},
              "unattributed": {key: [] for key in COLLECTIONS}, "legacy_provenance": journal.get("version") != 1}
    removed_npcs = set()
    for collection in COLLECTIONS:
        kept = []
        for record in state.get(collection, []):
            references = [session for session in remaining if _references(session, record)]
            changes = next((entry for entry in journal.get("collections", {}).get(collection, [])
                            if entry.get("after") and same_entity(entry["after"], record)), None)
            origin_field = "started_session" if collection == "quests" else "first_seen_session"
            origin = record.get(origin_field)
            introduced = (changes is not None and changes.get("before") is None) or str(origin) == str(number)
            manual = bool(record.get("_manual_fields"))
            if introduced and not references and not manual:
                report["removed"][collection].append(entity_name(record))
                if collection == "npcs":
                    removed_npcs.update(str(value).casefold() for value in [entity_name(record), *record.get("aliases", [])])
                continue
            if references:
                report["shared"][collection].append(entity_name(record))
            if report["legacy_provenance"] and (origin is None or not introduced):
                report["unattributed"][collection].append(entity_name(record))
            if changes:
                claimed = [incoming for session in remaining
                           if int(session["session_number"]) > int(number)
                           for incoming in session.get("entity_changes", {}).get("inputs", {}).get(collection, [])
                           if same_entity(incoming, record)]
                _undo_fields(record, changes.get("before"), changes["after"], claimed)
            for field in ("notes", "hitos_acumulados", "history", "events"):
                if isinstance(record.get(field), list):
                    record[field] = [value for value in record[field] if not _session_tag(value, number)]
            if introduced and references:
                record[origin_field] = min(int(session["session_number"]) for session in references)
            if collection == "quests":
                if str(record.get("completed_session")) == str(number):
                    record["completed_session"] = None
                    record["status"] = "in_progress"
                if record.get("lifecycle_notes"):
                    record["lifecycle_notes"] = " | ".join(part.strip() for part in record["lifecycle_notes"].split("|")
                        if not re.search(rf"\b(?:sesi[oó]n|session)\s*#?\s*{number}(?!\d)\b", part, re.IGNORECASE))
            kept.append(record)
        state[collection] = kept
    for pc in state.get("universal_pcs", []):
        pc["hitos_acumulados"] = [value for value in pc.get("hitos_acumulados", []) if not _session_tag(value, number)]
    for place in state.get("locations", []):
        for field in ("associated_characters", "manual_associated_characters"):
            if field in place:
                place[field] = [value for value in place[field] if str(value).casefold() not in removed_npcs]
    for item in state.get("items", []):
        if str(item.get("holder", "")).casefold() in removed_npcs:
            item["holder"] = "-"
    # Rebase later undo records as well: otherwise deleting a later session would
    # restore a value whose originating session has already been removed.
    for session in remaining:
        if int(session["session_number"]) <= int(number):
            continue
        later = session.get("entity_changes", {})
        for collection in COLLECTIONS:
            for entry in later.get("collections", {}).get(collection, []):
                for side in ("before", "after"):
                    snapshot = entry.get(side)
                    if not snapshot:
                        continue
                    deleted_change = next((change for change in journal.get("collections", {}).get(collection, [])
                        if change.get("after") and same_entity(change["after"], snapshot)), None)
                    if deleted_change:
                        claims = [incoming for other in remaining
                            if int(number) < int(other["session_number"]) < int(session["session_number"]) + (side == "after")
                            for incoming in other.get("entity_changes", {}).get("inputs", {}).get(collection, [])
                            if same_entity(incoming, snapshot)]
                        _undo_fields(snapshot, deleted_change.get("before"), deleted_change["after"], claims)
                    for field in ("notes", "hitos_acumulados"):
                        if isinstance(snapshot.get(field), list):
                            snapshot[field] = [value for value in snapshot[field] if not _session_tag(value, number)]
    state["sessions"] = remaining
    state["last_session"] = max((int(session["session_number"]) for session in remaining), default=0)
    state["sessions_count"] = len(remaining)
    return report
