import json

import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.storage.campaign_manager import CampaignManager


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    monkeypatch.setenv("WHISPER_CAMPAIGNS_DIR", str(tmp_path / "campaigns"))
    monkeypatch.setenv("WHISPER_OUTPUT_DIR", str(tmp_path / "output"))
    manager = CampaignManager()
    state = {"campaign_name": "Mesa", "last_session": 2,
        "sessions": [{"session_number": 1, "raw_transcript": "original"},
                     {"session_number": 2, "raw_transcript": "duplicada",
                      "detected_pcs": [{"personaje": "Lia"}]}],
        "universal_pcs": [{"personaje": "Lia", "jugador": "Ana", "hitos_acumulados": ["Sesión #1: Llegó."]},
                          {"personaje": "Bruno", "jugador": "Luis"}],
        "roster": [{"character_name": "Lia", "player_name": "Ana"}],
        "npcs": [{"name": "Nora", "role": "Guía", "notes": ["Nota original"]}],
        "locations": [{"name": "Puerto", "associated_characters": ["Lia"], "description": "Muelle"},
                      {"name": "Bosque", "associated_characters": []}],
        "items": [{"name": "Llave", "holder": "Lia"}], "quests": [{"id": "q1", "title": "Viajar"}]}
    manager.save_campaign(state)
    return manager, TestClient(app)


def test_delete_one_session_keeps_shared_data_and_creates_backup(campaign):
    manager, client = campaign
    response = client.delete("/api/campaigns/Mesa/session/2")
    assert response.status_code == 200
    data = response.json()
    state = manager.load_modular("Mesa")
    assert [s["session_number"] for s in state["sessions"]] == [1]
    assert state["last_session"] == 1
    assert state["sessions_count"] == 1
    assert state["npcs"][0]["name"] == "Nora"
    assert state["quests"][0]["id"] == "q1"
    assert not (manager.get_modular_paths("Mesa")["sessions_dir"] / "session_2.json").exists()
    backup = json.loads((manager.get_campaign_dir("Mesa") / "backups" / data["backup_id"]).read_text(encoding="utf-8"))
    assert backup["campaign_state"]["sessions"][1]["raw_transcript"] == "duplicada"
    assert len(json.loads(manager.get_campaign_path("Mesa").read_text(encoding="utf-8"))["sessions"]) == 1


def test_missing_session_is_not_silently_replaced_by_previous_one(campaign):
    manager, client = campaign
    before = manager.get_campaign_path("Mesa").read_bytes()
    assert client.delete("/api/campaigns/Mesa/session/3").status_code == 404
    assert manager.get_campaign_path("Mesa").read_bytes() == before


def test_edit_pc_updates_details_and_linked_places_without_renaming(campaign):
    manager, client = campaign
    response = client.put("/api/campaigns/Mesa/entities/pc", json={
        "original_name": "Lia", "name": "Lia", "player_name": "Ana",
        "species": "Elfa", "location_names": ["Bosque"]})
    assert response.status_code == 200
    state = response.json()["campaign_state"]
    assert len(state["universal_pcs"]) == 2
    assert state["universal_pcs"][0]["personaje"] == "Lia"
    assert state["universal_pcs"][0]["hitos_acumulados"] == ["Sesión #1: Llegó."]
    assert state["roster"][0]["character_name"] == "Lia"
    assert state["roster"][0]["player_name"] == "Ana"
    assert state["items"][0]["holder"] == "Lia"
    assert state["locations"][0]["associated_characters"] == []
    assert state["locations"][1]["associated_characters"] == ["Lia"]
    assert state["locations"][1]["manual_associated_characters"] == ["Lia"]
    assert state["sessions"][1]["detected_pcs"][0]["personaje"] == "Lia"
    assert manager.load_modular("Mesa")["universal_pcs"][0]["especie"] == "Elfa"


@pytest.mark.parametrize("kind,original,updates,collection,expected", [
    ("npc", "Nora", {"name": "Nora / Guía", "role": "Exploradora", "location_names": ["Bosque"]}, "npcs", "Nora / Guía"),
    ("location", "Puerto", {"name": "Puerto Viejo", "description": "Muelle reparado", "associated_characters": ["Bruno"]}, "locations", "Puerto Viejo"),
])
def test_edit_npc_and_location_persist(campaign, kind, original, updates, collection, expected):
    manager, client = campaign
    response = client.put(f"/api/campaigns/Mesa/entities/{kind}", json={"original_name": original, **updates})
    assert response.status_code == 200
    assert manager.load_modular("Mesa")[collection][0]["name"] == expected


def test_name_collision_requires_explicit_merge_and_keeps_original(campaign):
    manager, client = campaign
    state = manager.load_modular("Mesa")
    state["npcs"].append({"name": "Luz", "role": "Herrera"})
    manager.save_campaign(state)
    before = manager.get_campaign_path("Mesa").read_bytes()
    response = client.put("/api/campaigns/Mesa/entities/npc", json={"original_name": "Nora", "name": "Luz"})
    assert response.status_code == 409
    assert manager.get_campaign_path("Mesa").read_bytes() == before


def test_unknown_place_does_not_overwrite_character(campaign):
    manager, client = campaign
    before = manager.get_campaign_path("Mesa").read_bytes()
    response = client.put("/api/campaigns/Mesa/entities/pc", json={"original_name": "Lia", "location_names": ["Inexistente"]})
    assert response.status_code == 422
    assert manager.get_campaign_path("Mesa").read_bytes() == before


def test_deleting_a_session_does_not_block_recording_that_number_later(campaign):
    manager, client = campaign
    assert client.delete("/api/campaigns/Mesa/session/2").status_code == 200
    manager.record_session("Mesa", session_number=2, session_chapter={"title": "Sesión corregida"})
    state = manager.load_modular("Mesa")
    assert [s["session_number"] for s in state["sessions"]] == [1, 2]


def test_corrupt_session_prevents_an_edit_instead_of_silently_dropping_it(campaign):
    manager, client = campaign
    before = manager.get_campaign_path("Mesa").read_bytes()
    (manager.get_modular_paths("Mesa")["sessions_dir"] / "session_2.json").write_text("{broken", encoding="utf-8")
    response = client.put("/api/campaigns/Mesa/entities/pc", json={"original_name": "Lia", "species": "Elfa"})
    assert response.status_code == 422
    assert manager.get_campaign_path("Mesa").read_bytes() == before


def test_edit_preserves_numeric_session_order(campaign):
    manager, client = campaign
    state = manager.load_modular("Mesa")
    state["sessions"].append({"session_number": 10, "title": "Décima sesión"})
    manager.save_campaign(state)
    response = client.put("/api/campaigns/Mesa/entities/pc", json={"original_name": "Lia", "species": "Elfa"})
    assert response.status_code == 200
    assert [s["session_number"] for s in response.json()["campaign_state"]["sessions"]] == [1, 2, 10]


@pytest.mark.parametrize("accepted", [["Nori", "Guía nueva"], []])
def test_api_can_replace_or_clear_npc_aliases_and_rejections_persist(campaign, accepted):
    manager, client = campaign
    state = manager.load_campaign("Mesa")
    state["npcs"][0]["aliases"] = ["Erróneo", "Nori"]
    manager.save_campaign(state)
    response = client.put("/api/campaigns/Mesa/entities/npc", json={"original_name":"Nora", "aliases":accepted})
    assert response.status_code == 200
    result = response.json()
    assert result["entity"]["aliases"] == accepted
    assert "Erróneo" in result["entity"]["_rejected_aliases"]
    assert manager.load_modular("Mesa")["npcs"][0]["aliases"] == accepted
    assert json.loads(manager.get_campaign_path("Mesa").read_text(encoding="utf8"))["npcs"][0]["aliases"] == accepted
    assert (manager.get_campaign_dir("Mesa")/"backups"/result["backup_id"]).is_file()
    manager.record_session("Mesa", {"title":"Siguiente"}, session_number=3,
                           updated_npcs=[{"name":"Nora","aliases":["Erróneo", "Otra variante"]}])
    npc = next(n for n in manager.load_modular("Mesa")["npcs"] if n["name"] == "Nora")
    assert "Erróneo" not in npc["aliases"]
    assert "Otra variante" in npc["aliases"]
    assert set(accepted).issubset(npc["aliases"])


def test_alias_edit_rejects_invalid_values_without_changing_campaign(campaign):
    manager, client = campaign
    before=manager.get_campaign_path("Mesa").read_bytes()
    response=client.put("/api/campaigns/Mesa/entities/npc",json={"original_name":"Nora","aliases":[{}]})
    assert response.status_code==422
    assert manager.get_campaign_path("Mesa").read_bytes()==before


@pytest.mark.parametrize("kind, original", [("pc", "Lia"), ("location", "Puerto")])
def test_alias_editor_is_limited_to_npcs(campaign, kind, original):
    manager, client = campaign
    before = manager.get_campaign_path("Mesa").read_bytes()
    response = client.put(f"/api/campaigns/Mesa/entities/{kind}", json={"original_name":original, "aliases":["Variante"]})
    assert response.status_code == 422
    assert manager.get_campaign_path("Mesa").read_bytes() == before


def test_npc_nickname_and_phonetic_alias_are_independent(campaign):
    manager,client=campaign
    response=client.put('/api/campaigns/Mesa/entities/npc',json={'original_name':'Nora','aliases':['Nori'],'nicknames':['La Vigía']})
    assert response.status_code==200
    npc=manager.load_modular('Mesa')['npcs'][0]
    assert npc['nicknames']==['La Vigía'] and npc['aliases']==['Nori']
    response=client.put('/api/campaigns/Mesa/entities/npc',json={'original_name':'Nora','nicknames':[]})
    assert response.status_code==200
    npc=manager.load_modular('Mesa')['npcs'][0]
    assert npc['nicknames']==[] and npc['aliases']==['Nori']
