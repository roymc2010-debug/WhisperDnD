"""One entry point for complete campaign states received from files or Drive."""
import copy
import json
from contextlib import contextmanager


class CampaignImportConflict(ValueError):
    """Existing local formats disagree and require explicit reconciliation."""


def validate_campaign_state(incoming):
    if not isinstance(incoming, dict) or not str(incoming.get("campaign_name") or "").strip():
        raise ValueError("La campaña debe tener un nombre.")
    if not isinstance(incoming.get("sessions"), list):
        raise ValueError("Se requiere una campaña completa con una lista de sesiones, no solo metadatos.")
    state = copy.deepcopy(incoming)
    for key in ("sessions", "npcs", "quests", "locations", "items", "roster", "universal_pcs"):
        records = state.get(key, [])
        if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
            raise ValueError(f"Formato inválido en {key}.")
    numbers = []
    for session in state["sessions"]:
        number = session.get("session_number")
        if isinstance(number, bool) or not str(number).isdigit() or int(number) < 1:
            raise ValueError("Cada sesión debe tener un número entero positivo.")
        session["session_number"] = int(number)
        numbers.append(int(number))
    if len(numbers) != len(set(numbers)):
        raise ValueError("La campaña contiene números de sesión duplicados.")
    state["sessions"].sort(key=lambda session: session["session_number"])
    state["last_session"] = max(numbers, default=0)
    state["sessions_count"] = len(numbers)
    return state


def assert_campaign_formats_agree(manager, name):
    paths = manager.get_modular_paths(name)
    mirror = manager.get_campaign_path(name)
    if paths["campaign_meta"].is_file() and mirror.is_file():
        old = manager._load_for_manual_change(name)
        legacy = json.loads(mirror.read_text(encoding="utf-8"))
        for key in ("sessions", "npcs", "quests", "locations", "items", "roster", "universal_pcs"):
            left, right = old.get(key, []), legacy.get(key, [])
            if key == "sessions":
                left = sorted(left, key=lambda session: int(session["session_number"]))
                right = sorted(right, key=lambda session: int(session["session_number"]))
            if left != right:
                raise CampaignImportConflict(
                    f"La campaña '{name}' tiene diferencias entre el JSON y la carpeta modular ({key}). "
                    "No se sobrescribió ninguna versión; requiere reconciliación con respaldo.")
        for key, default in (("prior_lore", ""), ("user_character_backstory", ""),
                             ("character_backstories", {})):
            if old.get(key, default) != legacy.get(key, default):
                raise CampaignImportConflict(
                    f"La campaña '{name}' tiene diferencias entre el JSON y la carpeta modular ({key}). "
                    "No se sobrescribió ninguna versión; requiere reconciliación con respaldo.")


def _state_files(manager, name):
    paths = manager.get_modular_paths(name)
    return {manager.get_campaign_path(name), paths["campaign_meta"],
            *(paths[key] for key in ("npcs", "quests", "locations", "items")),
            *paths["sessions_dir"].glob("session_*.json")}


@contextmanager
def campaign_write_transaction(manager, name):
    """Restore exact previous JSON bytes if either format fails to save."""
    assert_campaign_formats_agree(manager, name)
    before = {path: path.read_bytes() for path in _state_files(manager, name) if path.is_file()}
    try:
        yield
    except Exception:
        for path in _state_files(manager, name) - before.keys():
            if path.is_file():
                path.unlink()
        for path, content in before.items():
            path.write_bytes(content)
        raise


def persist_campaign_import(manager, incoming):
    """Back up the old state, then use the normal dual-format writer."""
    state = validate_campaign_state(incoming)
    name = state["campaign_name"]
    assert_campaign_formats_agree(manager, name)
    paths = manager.get_modular_paths(name)
    if paths["campaign_meta"].is_file() or manager.get_campaign_path(name).is_file():
        old = manager._load_for_manual_change(name)
        manager._backup_manual_change(old, "import")
    manager.save_campaign(state)
    return state


def restore_drive_campaign(manager, incoming):
    """Apply the same freshness rule to JSON and ZIP downloads."""
    state = validate_campaign_state(incoming)
    name = state["campaign_name"]
    assert_campaign_formats_agree(manager, name)
    paths = manager.get_modular_paths(name)
    if paths["campaign_meta"].is_file() or manager.get_campaign_path(name).is_file():
        local = manager._load_for_manual_change(name)
        local_updated = str(local.get("updated_at") or "")
        remote_updated = str(state.get("updated_at") or "")
        if local_updated and remote_updated:
            if local_updated >= remote_updated:
                return False
        elif int(local.get("last_session", 0)) >= state["last_session"]:
            return False
    persist_campaign_import(manager, state)
    return True
