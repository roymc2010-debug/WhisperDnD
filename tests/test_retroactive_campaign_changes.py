import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.storage.campaign_manager import CampaignManager


@pytest.fixture
def journal(tmp_path, monkeypatch):
    for key in ("INPUT", "OUTPUT", "CAMPAIGNS", "QUOTA"):
        monkeypatch.setenv(f"WHISPER_{key}_DIR", str(tmp_path / key.lower()))
    manager = CampaignManager()
    state = {"campaign_name": "Mesa", "last_session": 2,
        "roster": [{"character_name": "Nora Veyl", "player_name": "Ana"}],
        "universal_pcs": [{"personaje": "Nora Veyl", "jugador": "Ana", "hitos_acumulados": ["Sesión #1: Nora ayudó.", "Sesión #2: Encontró la llave."]}],
        "npcs": [{"name": "Nora", "first_seen_session": 1, "notes": ["Sesión #1: Abrió la puerta.", "Sesión #2: Dio la llave."]},
                 {"name": "Sombra", "first_seen_session": 2, "notes": ["Sesión #2: Atacó."]}],
        "locations": [{"name": "Puerto", "first_seen_session": 1, "associated_characters": ["Nora"]},
                      {"name": "Torre", "first_seen_session": 2, "description": "Sede de Sombra"}],
        "items": [{"name": "Llave", "first_seen_session": 2, "holder": "Nora"}],
        "quests": [{"id": "q2", "title": "Atrapar a Sombra", "started_session": 2},
                   {"id": "q1", "title": "Viajar", "started_session": 1, "completed_session": 2, "status": "completed"}],
        "sessions": [{"session_number": 1, "title": "Nora y Nora Veyl", "chronicle_text": "Nora guió a Nora Veyl. Noralia no cambió.",
                      "raw_transcript": "Ana: Nora ayudó a Nora Veyl.", "detected_npc_names": ["Nora"]},
                     {"session_number": 2, "chronicle_markdown": "**Nora** entregó la Llave en la Torre. Sombra atacó.",
                      "raw_transcript": "Nora y Sombra", "detected_npc_names": ["Nora", "Sombra"]}]}
    manager.save_campaign(state)
    return manager, TestClient(app), tmp_path


def test_npc_rename_rewrites_historical_text_without_renaming_players(journal):
    manager, client, _ = journal
    response = client.put("/api/campaigns/Mesa/entities/npc", json={"original_name": "Nora", "name": "Nóra del Mar"})
    assert response.status_code == 200
    state = response.json()["campaign_state"]
    assert state["sessions"][0]["chronicle_text"] == "Nóra del Mar guió a Nora Veyl. Noralia no cambió."
    assert state["sessions"][0]["raw_transcript"] == "Ana: Nóra del Mar ayudó a Nora Veyl."
    assert "**Nóra del Mar**" in state["sessions"][1]["chronicle_markdown"]
    assert state["roster"][0]["character_name"] == "Nora Veyl"
    assert state["universal_pcs"][0]["personaje"] == "Nora Veyl"
    assert state["locations"][0]["associated_characters"] == ["Nóra del Mar"]
    assert state["items"][0]["holder"] == "Nóra del Mar"
    backup = json.loads((manager.get_campaign_dir("Mesa") / "backups" / response.json()["backup_id"]).read_text(encoding="utf-8"))
    assert "Nora guió" in backup["campaign_state"]["sessions"][0]["chronicle_text"]


@pytest.mark.parametrize("change", [{"name": "Otro nombre"}, {"player_name": "Otra jugadora"}])
def test_player_character_cannot_be_renamed_from_wiki(journal, change):
    manager, client, _ = journal
    before = manager.get_campaign_path("Mesa").read_bytes()
    response = client.put("/api/campaigns/Mesa/entities/pc", json={"original_name": "Nora Veyl", **change})
    assert response.status_code == 422
    assert manager.get_campaign_path("Mesa").read_bytes() == before


def test_legacy_npc_editor_uses_the_same_retroactive_rule(journal, monkeypatch):
    from src.api import server
    monkeypatch.setattr(server, "trigger_drive_sync_background", lambda paths: None)
    _, client, _ = journal
    response = client.put("/api/campaigns/Mesa/npcs/Nora", json={"new_name": "Nóra del Mar"})
    assert response.status_code == 200
    assert "Nóra del Mar guió" in response.json()["campaign_state"]["sessions"][0]["chronicle_text"]


def test_delete_session_removes_its_exclusive_entities_and_shared_notes(journal):
    manager, client, _ = journal
    response = client.delete("/api/campaigns/Mesa/session/2")
    assert response.status_code == 200
    state = response.json()["campaign_state"]
    assert [npc["name"] for npc in state["npcs"]] == ["Nora"]
    assert state["npcs"][0]["notes"] == ["Sesión #1: Abrió la puerta."]
    assert [place["name"] for place in state["locations"]] == ["Puerto"]
    assert state["items"] == []
    assert [quest["id"] for quest in state["quests"]] == ["q1"]
    assert state["quests"][0]["status"] == "in_progress"
    assert state["universal_pcs"][0]["hitos_acumulados"] == ["Sesión #1: Nora ayudó."]
    assert state["roster"][0]["character_name"] == "Nora Veyl"
    assert response.json()["cleanup_report"]["legacy_provenance"] is True


def test_delete_session_keeps_entities_used_by_other_sessions(journal):
    manager, client, _ = journal
    state = manager.load_modular("Mesa")
    state["sessions"].append({"session_number": 3, "chronicle_text": "Sombra regresó a la Torre con la Llave.", "detected_npc_names": ["Sombra"]})
    state["npcs"][1]["notes"].append("Session #3: Regresó.")
    manager.save_campaign(state)
    response = client.delete("/api/campaigns/Mesa/session/2")
    assert response.status_code == 200
    state = response.json()["campaign_state"]
    assert state["npcs"][1]["name"] == "Sombra"
    assert state["npcs"][1]["notes"] == ["Session #3: Regresó."]
    assert state["npcs"][1]["first_seen_session"] == 3
    assert state["locations"][1]["name"] == "Torre"
    assert state["items"][0]["name"] == "Llave"


def test_deleted_session_does_not_resolve_to_previous_session(journal):
    _, client, _ = journal
    assert client.delete("/api/campaigns/Mesa/session/2").status_code == 200
    assert client.get("/api/campaigns/Mesa/session/2").status_code == 404
    assert client.get("/api/campaigns/Mesa/session/2/download-md").status_code == 404
    assert client.get("/api/campaigns/Mesa/session/2/download-docx").status_code == 404


def test_deletion_preview_is_read_only_and_lists_exclusive_entities(journal):
    manager, client, _ = journal
    before = manager.get_campaign_path("Mesa").read_bytes()
    response = client.get("/api/campaigns/Mesa/session/2/deletion-preview")
    assert response.status_code == 200
    assert response.json()["removed"]["npcs"] == ["Sombra"]
    assert manager.get_campaign_path("Mesa").read_bytes() == before
    assert not (manager.get_campaign_dir("Mesa") / "backups").exists()


def test_new_session_records_changes_so_untagged_updates_can_be_reverted(tmp_path, monkeypatch):
    monkeypatch.setenv("WHISPER_OUTPUT_DIR", str(tmp_path / "output"))
    manager = CampaignManager(campaigns_dir=str(tmp_path / "campaigns"))
    manager.record_session("Mesa", {"title": "Inicio", "chronicle_text": "Nora es guía."}, session_number=1,
        updated_npcs=[{"name": "Nora", "role": "Guía", "notes": ["Conoce el puerto"]}], detected_npc_names=["Nora"])
    manager.record_session("Mesa", {"title": "Cambio", "chronicle_text": "Nora tomó el mando."}, session_number=2,
        updated_npcs=[{"name": "Nora", "role": "Capitana del puerto", "notes": ["Tiene una llave"]}], detected_npc_names=["Nora"])
    assert "entity_changes" in manager.load_modular("Mesa")["sessions"][1]
    result = manager.delete_session("Mesa", 2)
    npc = result["campaign_state"]["npcs"][0]
    assert npc["role"] == "Guía"
    assert npc["notes"] == ["Conoce el puerto"]


def test_npc_rename_refreshes_managed_exports_and_archives_originals(journal):
    from docx import Document
    from src.exporters.md_exporter import export_session_md
    from src.exporters.docx_exporter import export_session_docx
    manager, client, temporary = journal
    state = manager.load_modular("Mesa")
    output = temporary / "output"
    md = export_session_md(state["sessions"][0], "Mesa", state["roster"])
    docx = export_session_docx(state["sessions"][0], "Mesa", state["roster"])
    transcript = output / "mesa_sesion_1_transcripcion.txt"
    transcript.write_text(state["sessions"][0]["raw_transcript"], encoding="utf-8")
    original_docx = Path(docx).read_bytes()
    response = client.put("/api/campaigns/Mesa/entities/npc", json={"original_name": "Nora", "name": "Nóra del Mar"})
    assert response.status_code == 200
    assert "Nóra del Mar" in Path(md).read_text(encoding="utf-8")
    assert "Nóra del Mar" in "\n".join(p.text for p in Document(docx).paragraphs)
    assert transcript.read_text(encoding="utf-8") == "Ana: Nóra del Mar ayudó a Nora Veyl."
    archive = manager.get_campaign_dir("Mesa") / "backups" / (response.json()["backup_id"] + ".assets")
    assert (archive / "output" / Path(docx).name).read_bytes() == original_docx


def test_delete_archives_session_exports_and_preserves_original_audio(journal):
    from src.exporters.md_exporter import export_session_md
    manager, client, temporary = journal
    state = manager.load_modular("Mesa")
    exported = Path(export_session_md(state["sessions"][1], "Mesa", state["roster"]))
    audio = manager.get_campaign_dir("Mesa") / "recordings" / "original.wav"
    audio.write_bytes(b"original audio")
    response = client.delete("/api/campaigns/Mesa/session/2")
    assert response.status_code == 200
    assert not exported.exists()
    archive = manager.get_campaign_dir("Mesa") / "backups" / (response.json()["backup_id"] + ".assets")
    assert (archive / "output" / exported.name).is_file()
    assert audio.read_bytes() == b"original audio"


def test_deleting_later_session_does_not_resurrect_previously_deleted_updates(tmp_path, monkeypatch):
    monkeypatch.setenv("WHISPER_OUTPUT_DIR", str(tmp_path / "output"))
    manager = CampaignManager(campaigns_dir=str(tmp_path / "campaigns"))
    for number, role in ((1, "Guía"), (2, "Capitana del puerto"), (3, "Almirante de la flota")):
        manager.record_session("Mesa", {"chronicle_text": "Nora participa."}, session_number=number,
            updated_npcs=[{"name": "Nora", "role": role, "notes": [f"Nota sin etiqueta {number}"]}], detected_npc_names=["Nora"])
    manager.delete_session("Mesa", 2)
    result = manager.delete_session("Mesa", 3)
    assert result["campaign_state"]["npcs"][0]["role"] == "Guía"
    assert result["campaign_state"]["npcs"][0]["notes"] == ["Nota sin etiqueta 1"]


def test_manually_corrected_npc_name_survives_future_old_spelling(tmp_path, monkeypatch):
    monkeypatch.setenv("WHISPER_OUTPUT_DIR", str(tmp_path / "output"))
    manager = CampaignManager(campaigns_dir=str(tmp_path / "campaigns"))
    manager.record_session("Mesa", {"chronicle_text": "Noralia participa."}, session_number=1,
        updated_npcs=[{"name": "Noralia", "role": "Guía"}], detected_npc_names=["Noralia"])
    manager.update_wiki_entity("Mesa", "npc", "Noralia", {"name": "Nora"})
    state = manager.record_session("Mesa", {"chronicle_text": "Noralia participa otra vez."}, session_number=2,
        updated_npcs=[{"name": "Noralia", "role": "Guía"}], detected_npc_names=["Noralia"])
    assert [npc["name"] for npc in state["npcs"]] == ["Nora"]


def test_editing_npc_does_not_mark_unrelated_places_as_manual(journal):
    _, client, _ = journal
    edit = client.put("/api/campaigns/Mesa/entities/npc", json={"original_name": "Nora", "name": "Nóra del Mar", "location_names": ["Puerto"]})
    assert edit.status_code == 200
    removed = client.delete("/api/campaigns/Mesa/session/2")
    assert removed.status_code == 200
    assert [place["name"] for place in removed.json()["campaign_state"]["locations"]] == ["Puerto"]
