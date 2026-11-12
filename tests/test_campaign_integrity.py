"""Cross-operation integrity checks using disposable campaigns only."""
import copy
import json
from pathlib import Path

import pytest

from src.storage.campaign_ingest import CampaignImportConflict
from src.storage.campaign_manager import CampaignManager


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setenv("WHISPER_OUTPUT_DIR", str(tmp_path / "output"))
    return CampaignManager(campaigns_dir=str(tmp_path / "campaigns"))


def snapshot(manager):
    return {path.relative_to(manager.campaigns_dir): path.read_bytes()
            for path in manager.campaigns_dir.rglob("*.json")}


@pytest.mark.parametrize("field,original,conflicting", [
    ("prior_lore", "Historia confirmada", "Otra historia"),
    ("user_character_backstory", "Origen confirmado", "Otro origen"),
    ("character_backstories", {"Lira": "Del puerto"}, {"Lira": "Del bosque"}),
])
def test_conflicting_campaign_context_is_preserved(manager, field, original, conflicting):
    state = {"campaign_name": "Mesa ficticia", "sessions": [], field: original}
    manager.save_campaign(state)
    mirror = manager.get_campaign_path(state["campaign_name"])
    other = json.loads(mirror.read_text(encoding="utf-8"))
    other[field] = conflicting
    mirror.write_text(json.dumps(other), encoding="utf-8")
    before = snapshot(manager)
    with pytest.raises(CampaignImportConflict, match=field):
        manager.load_campaign(state["campaign_name"])
    with pytest.raises(CampaignImportConflict, match=field):
        manager.save_campaign(state)
    assert snapshot(manager) == before


def test_failed_session_file_removal_rolls_back_both_formats(manager, monkeypatch):
    name = "Mesa ficticia"
    state = {"campaign_name": name, "last_session": 2,
             "sessions": [{"session_number": 1}, {"session_number": 2}]}
    manager.save_campaign(state)
    before = snapshot(manager)
    stale = manager.get_modular_paths(name)["sessions_dir"] / "session_2.json"
    original_unlink = Path.unlink

    def denied(path, *args, **kwargs):
        if path == stale:
            raise PermissionError("Archivo de sesión bloqueado")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", denied)
    changed = copy.deepcopy(state)
    changed["sessions"] = changed["sessions"][:1]
    changed["last_session"] = 1
    with pytest.raises(PermissionError, match="bloqueado"):
        manager.save_campaign(changed)
    assert snapshot(manager) == before
    assert len(manager.load_campaign(name)["sessions"]) == 2


@pytest.mark.parametrize("numbers", [[1, 1], [1, 0], [1, True]])
def test_normal_save_rejects_invalid_session_identities(manager, numbers):
    state = {"campaign_name": "Mesa ficticia", "sessions": [{"session_number": 1}]}
    manager.save_campaign(state)
    before = snapshot(manager)
    invalid = copy.deepcopy(state)
    invalid["sessions"] = [{"session_number": number} for number in numbers]
    with pytest.raises(ValueError):
        manager.save_campaign(invalid)
    assert snapshot(manager) == before


def test_delete_after_npc_rename_does_not_restore_old_holder(manager):
    name = "Mesa ficticia"
    manager.record_session(name, {"title": "Inicio", "chronicle_text": "Nora tiene la llave."},
        session_number=1, updated_npcs=[{"name": "Nora", "role": "Guía"}],
        detected_npc_names=["Nora"], items=[{"name": "Llave", "holder": "Nora"}])
    manager.record_session(name, {"title": "Entrega", "chronicle_text": "Nora entrega la llave a Sombra."},
        session_number=2, items=[{"name": "Llave", "holder": "Sombra", "status": "equipado"}])
    assert manager.load_campaign(name)["items"][0]["holder"] == "Sombra"
    manager.update_wiki_entity(name, "npc", "Nora", {"name": "Nóra del Mar"})
    state = manager.delete_session(name, 2)["campaign_state"]
    assert state["items"][0]["holder"] == "Nóra del Mar"
    assert manager.load_modular(name)["items"] == json.loads(
        manager.get_campaign_path(name).read_text(encoding="utf-8"))["items"]


def test_delete_after_npc_rename_does_not_restore_old_place_link(manager):
    name = "Mesa ficticia"
    manager.record_session(name, {"title": "Inicio", "chronicle_text": "Nora llegó al puerto."},
        session_number=1, updated_npcs=[{"name": "Nora", "role": "Guía"}],
        locations=[{"name": "Puerto", "associated_characters": ["Nora"]}])
    manager.record_session(name, {"title": "Visita", "chronicle_text": "Sombra visitó el puerto."},
        session_number=2, locations=[{"name": "Puerto", "associated_characters": ["Sombra"]}])
    manager.update_wiki_entity(name, "npc", "Nora", {"name": "Nóra del Mar"})
    state = manager.delete_session(name, 2)["campaign_state"]
    assert state["locations"][0]["associated_characters"] == ["Nóra del Mar"]


def test_rerecord_four_then_delete_five_keeps_both_formats_in_sync(manager):
    name = "Mesa ficticia"
    for number in range(1, 6):
        manager.record_session(name, {"title": f"Capítulo {number}",
            "chronicle_text": f"Visitante {number} llegó al puerto."}, session_number=number,
            updated_npcs=[{"name": f"Visitante {number}", "role": "Guía"}],
            detected_npc_names=[f"Visitante {number}"])

    def assert_synced(numbers):
        modular = manager.load_modular(name)
        mirror = json.loads(manager.get_campaign_path(name).read_text(encoding="utf-8"))
        for key in ("sessions", "npcs", "quests", "items", "locations"):
            assert modular.get(key, []) == mirror.get(key, [])
        assert [chapter["session_number"] for chapter in modular["sessions"]] == numbers
        files = manager.get_modular_paths(name)["sessions_dir"].glob("session_*.json")
        assert sorted(int(file.stem.removeprefix("session_")) for file in files) == numbers
        assert modular["last_session"] == max(numbers)
        return modular

    assert_synced([1, 2, 3, 4, 5])
    for _ in range(2):
        manager.record_session(name, {"title": "Cuarta corregida", "chronicle_text": "Lira encontró el faro."},
            session_number=4, updated_npcs=[{"name": "Lira", "role": "Cartógrafa"}], detected_npc_names=["Lira"])
        state = assert_synced([1, 2, 3, 4, 5])
        assert state["sessions"][4]["title"] == "Capítulo 5"
        assert "Visitante 4" not in {npc["name"] for npc in state["npcs"]}

    manager.update_wiki_entity(name, "npc", "Lira", {"name": "Lira del Faro"})
    manager.delete_session(name, 5)
    state = assert_synced([1, 2, 3, 4])
    assert "Lira del Faro" in state["sessions"][3]["chronicle_text"]
    assert "Visitante 5" not in {npc["name"] for npc in state["npcs"]}
    backups = list((manager.get_campaign_dir(name) / "backups").glob("*.json"))
    assert len(backups) == 4  # two replacements, a rename and a deletion
