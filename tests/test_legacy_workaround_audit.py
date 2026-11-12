"""Regressions for old repair heuristics that can destroy valid campaign data."""
import asyncio
import copy
import json

import pytest

from src.api import server
from src.storage.campaign_manager import CampaignManager, purge_session_data
from test_campaign_ingestion import drive_for, payload


@pytest.fixture
def manager(tmp_path, monkeypatch):
    for key in ("INPUT", "OUTPUT", "CAMPAIGNS", "QUOTA"):
        monkeypatch.setenv(f"WHISPER_{key}_DIR", str(tmp_path / key.lower()))
    return CampaignManager()


def snapshot(manager):
    return {path: path.read_bytes() for path in manager.campaigns_dir.rglob("*.json")}


def test_loading_a_campaign_does_not_delete_an_unmentioned_npc(manager):
    state = payload([1])
    state["npcs"] = [{"name": "Cartógrafa", "first_seen_session": 1,
                      "notes": ["Preparó el mapa, aunque no aparece en la crónica."]}]
    manager.save_campaign(state)
    before = snapshot(manager)
    loaded = manager.load_campaign("Mesa")
    assert loaded["npcs"] == state["npcs"]
    assert snapshot(manager) == before


def test_purging_a_nonexistent_session_is_a_noop():
    state = payload([1])
    state["npcs"] = [{"name": "Cartógrafa", "first_seen_session": 1}]
    before = copy.deepcopy(state)
    purge_session_data(state, 2)
    assert state == before


def test_new_session_preserves_npcs_not_repeated_in_the_latest_transcript(manager):
    state = payload([1])
    state["npcs"] = [{"name": "Cartógrafa", "first_seen_session": 1}]
    manager.save_campaign(state)
    updated = manager.record_session("Mesa", {"title": "Otra aventura"}, session_number=2)
    assert updated["npcs"] == state["npcs"]


def test_rerecording_the_only_session_preserves_manual_fixtures():
    state = payload([1])
    state["npcs"] = [{"name": "Guía", "first_seen_session": 1, "_manual_fields": ["name"]}]
    state["universal_pcs"] = [{"personaje": "Lia", "jugador": "Ana"}]
    purge_session_data(state, 1)
    assert state["npcs"][0]["name"] == "Guía"
    assert state["universal_pcs"][0]["personaje"] == "Lia"


def test_deduplication_cannot_delete_another_campaign_with_the_same_name(manager):
    manager.save_campaign({**payload([]), "campaign_name": "Octus"})
    other_file = manager.get_campaign_path("Octus")
    other_before = other_file.read_bytes()
    state = payload([])
    state["npcs"] = [{"name": "Octus", "notes": []}, {"name": "Octus Taconis", "notes": []}]
    manager.save_campaign(state)
    manager.deduplicate_campaign_entities("Mesa")
    assert other_file.is_file()
    assert other_file.read_bytes() == other_before


def test_explicit_deduplication_preserves_unique_unmentioned_npcs(manager):
    state = payload([1])
    state["npcs"] = [{"name": "Cartógrafa", "first_seen_session": 1}]
    manager.save_campaign(state)
    result = manager.deduplicate_campaign_entities("Mesa")
    assert result["campaign_state"]["npcs"] == state["npcs"]


@pytest.mark.parametrize("damaged", ["legacy", "metadata", "session"])
def test_damaged_existing_history_does_not_become_an_empty_or_partial_campaign(manager, damaged):
    if damaged == "legacy":
        target = manager.get_campaign_path("Mesa")
    else:
        manager.save_campaign(payload([1, 2, 3]))
        paths = manager.get_modular_paths("Mesa")
        target = paths["campaign_meta"] if damaged == "metadata" else paths["sessions_dir"] / "session_2.json"
    target.write_text('{"incomplete":', encoding="utf-8")
    before = snapshot(manager)
    with pytest.raises(ValueError):
        manager.record_session("Mesa", {"title": "No debe sobrescribir"}, session_number=4)
    assert snapshot(manager) == before


def test_failed_drive_download_cannot_overwrite_the_remote_copy(manager):
    manager.save_campaign(payload([1, 2, 3]))
    storage = drive_for(payload([1, 2, 3, 4]), "json")
    def unavailable(file_id):
        raise RuntimeError("Descarga interrumpida")
    storage.download_file_bytes = unavailable
    result = storage.sync_from_google_drive(manager.campaigns_dir, manager.output_dir)
    assert result["status"] == "partial"
    storage.upload_file.assert_not_called()


def test_provided_roster_is_not_replaced_by_a_markus_template_cleanup(manager):
    state = payload([1])
    roster = [{"character_name": "Markus Veyl", "player_name": "Roy"},
              {"character_name": "Lia", "player_name": "Ana"}]
    state["roster"] = roster
    manager.save_campaign(state)
    updated = manager.record_session("Mesa", {"title": "Lia habla"}, session_number=2,
                                     roster=roster, detected_party=[roster[1]])
    assert {r["character_name"] for r in updated["roster"]} == {"Markus Veyl", "Lia"}


def test_loading_a_legacy_campaign_does_not_rewrite_or_migrate_it(manager):
    legacy = manager.get_campaign_path("Mesa")
    legacy.write_text(json.dumps(payload([1])), encoding="utf-8")
    before = snapshot(manager)
    loaded = manager.load_campaign("Mesa")
    assert loaded["sessions"][0]["session_number"] == 1
    assert snapshot(manager) == before
    assert not manager.get_modular_paths("Mesa")["campaign_meta"].exists()


def test_corrupt_modular_session_is_reported_on_read_instead_of_omitted(manager):
    manager.save_campaign(payload([1, 2, 3]))
    (manager.get_modular_paths("Mesa")["sessions_dir"] / "session_2.json").write_text('{"bad":', encoding="utf-8")
    before = snapshot(manager)
    with pytest.raises(ValueError):
        manager.load_campaign("Mesa")
    assert snapshot(manager) == before


def test_startup_does_not_run_destructive_retroactive_repairs(manager, monkeypatch):
    state = payload([1])
    state["npcs"] = [{"name": "Cartógrafa", "first_seen_session": 1}]
    manager.save_campaign(state)
    before = snapshot(manager)
    class OfflineDrive:
        def is_connected(self):
            return False
    monkeypatch.setattr(server, "GoogleDriveStorage", OfflineDrive)
    async def startup():
        await server.on_server_startup()
        await asyncio.sleep(0)
    asyncio.run(startup())
    assert snapshot(manager) == before


def test_backup_json_is_not_listed_as_an_active_campaign(manager):
    manager.save_campaign(payload([1, 2, 3, 4, 5]))
    backup = manager.campaigns_dir / "mesa.pre_fix_backup.json"
    backup.write_text(json.dumps(payload([1, 2, 3])), encoding="utf-8")
    entries = [entry for entry in manager.list_campaigns() if entry["name"] == "Mesa"]
    assert len(entries) == 1
    assert entries[0]["sessions_count"] == 5
    with pytest.raises(ValueError, match="respaldo"):
        manager.load_campaign("Mesa.pre_fix_backup")


def test_drive_does_not_upload_a_backup_as_an_active_campaign(manager):
    manager.save_campaign(payload([1, 2, 3, 4, 5]))
    backup = manager.campaigns_dir / "mesa.pre_fix_backup.json"
    backup.write_text(json.dumps(payload([1, 2, 3])), encoding="utf-8")
    storage = drive_for(payload([1, 2, 3, 4, 5]), "json")
    storage.sync_from_google_drive(manager.campaigns_dir, manager.output_dir)
    assert all(call.args[0] != str(backup.resolve()) for call in storage.upload_file.call_args_list)


@pytest.mark.parametrize("suffix", ["json", "zip"])
def test_remote_backup_cannot_replace_the_active_campaign(manager, suffix):
    manager.save_campaign(payload([1, 2, 3, 4, 5]))
    remote_backup = payload([1, 2, 3])
    remote_backup["updated_at"] = "2199-01-01T00:00:00"
    storage = drive_for(remote_backup, suffix)
    listing = storage._service.files.return_value.list.side_effect
    def backup_listing(*args, **kwargs):
        response = listing(*args, **kwargs)
        for file in response.execute.return_value["files"]:
            if file["id"] == "remote":
                file["name"] = f"mesa.pre_fix_backup.{suffix}"
        return response
    storage._service.files.return_value.list.side_effect = backup_listing
    result = storage.sync_from_google_drive(manager.campaigns_dir, manager.output_dir)
    assert result["downloaded_campaigns"] == 0
    assert [s["session_number"] for s in manager.load_modular("Mesa")["sessions"]] == [1, 2, 3, 4, 5]


def test_opening_the_app_with_an_old_shadow_backup_preserves_five_sessions(manager, monkeypatch):
    from fastapi.testclient import TestClient
    manager.save_campaign(payload([1, 2, 3, 4, 5]))
    backup = manager.campaigns_dir / "mesa.pre_fix_backup.json"
    backup.write_text(json.dumps(payload([1, 2, 3])), encoding="utf-8")
    before = snapshot(manager)
    class OfflineDrive:
        def is_connected(self):
            return False
    monkeypatch.setattr(server, "GoogleDriveStorage", OfflineDrive)
    with TestClient(server.app) as client:
        response = client.get("/api/campaigns/Mesa")
        assert response.status_code == 200
        assert [s["session_number"] for s in response.json()["campaign_state"]["sessions"]] == [1, 2, 3, 4, 5]
    assert snapshot(manager) == before
