"""Only synthetic campaigns: no global cast, inferred identity or foreign aliases."""
import copy
import json
from pathlib import Path
from unittest.mock import Mock
from zipfile import ZipFile

import pytest

from src.api import server
from src.exporters.md_exporter import export_living_journal_md, export_session_md
from src.exporters.docx_exporter import export_session_docx, export_living_journal_docx
from src.storage.campaign_manager import CampaignManager, are_items_duplicate, are_locations_duplicate
from src.summarizer.gemini_client import GeminiTTRPGSummarizer
from src.summarizer.prompts import build_continuity_session_prompt
from src.transcription.roster_normalizer import normalize_transcript_roster


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    for key in ("INPUT", "OUTPUT", "CAMPAIGNS", "QUOTA"):
        monkeypatch.setenv(f"WHISPER_{key}_DIR", str(tmp_path / key.lower()))
    monkeypatch.setattr(server, "trigger_drive_sync_background", Mock())


@pytest.mark.parametrize("roster", [None, [], [{"character_name": "(DM)"}], [{"character_name": "Arin"}]])
def test_no_default_cast_or_phonetic_dictionary_without_matching_campaign(roster):
    text = "Marcos y Minipeco saludan a Seren y Belith. Ataúd de roble junto a la puerta."
    assert normalize_transcript_roster(text, roster) == text


def test_explicit_aliases_map_to_canonical_once_and_preserve_conflicts_and_objects():
    roster = [{"character_name": "Arin", "aliases": ["Aryn", "guardia"]},
              {"character_name": "Bryn", "aliases": ["Aryn"]},
              {"character_name": "Atou", "aliases": ["A tau", "ataúd"]}]
    assert normalize_transcript_roster("Aryn saluda. Ataúd de roble. A tau pregunta.", roster) == "Aryn saluda. Ataúd de roble. Atou pregunta."
    assert normalize_transcript_roster("Aryn abre la puerta.", roster[:1]) == "Arin abre la puerta."
    assert normalize_transcript_roster("El guardia abre la puerta.", roster[:1]) == "El guardia abre la puerta."


def test_player_name_is_not_replaced_by_an_npc_alias_even_for_the_dm():
    roster = [{"character_name": "(DM)", "player_name": "Beta"},
              {"character_name": "Mael", "aliases": ["Beta"]}]
    assert normalize_transcript_roster("[DM (Beta)]: Mael saluda.", roster) == "[DM (Beta)]: Mael saluda."


@pytest.mark.parametrize("youtube", [False, True])
def test_player_names_do_not_imply_a_character_species_or_class(youtube):
    manager = CampaignManager()
    pcs = [{"jugador": "Liam", "personaje": "Arin", "especie": "-", "clase": "-"},
           {"jugador": "Brennan", "personaje": "Lira", "especie": "Elfo", "clase": "Mago"},
           {"jugador": "Rodrigo", "personaje": "Doran", "especie": "Humano", "clase": "Guerrero"}]
    result = manager.record_session("Mesa", {"chronicle_text": "El grupo entra."}, detected_pcs=pcs, is_youtube=youtube)
    assert {p["personaje"] for p in result["universal_pcs"]} == {"Arin", "Lira", "Doran"}
    arin = next(p for p in result["universal_pcs"] if p["personaje"] == "Arin")
    assert arin["jugador"] == "Liam"
    assert arin["especie"] == "-"
    assert arin["clase"] == "-"
    if youtube:
        assert any(p["character_name"] == "Doran" for p in result["roster"])


def test_youtube_dm_is_taken_from_explicit_role_not_personal_name():
    result = CampaignManager().record_session("Video", {"chronicle_text": "Brennan es un mercader."},
        roster=[{"character_name": "(DM)", "player_name": "Liam", "role": "Dungeon Master"}],
        updated_npcs=[{"name": "Brennan", "role": "Mercader"}], is_youtube=True)
    assert result["roster"][0]["player_name"] == "Liam"
    assert not result["universal_pcs"]


@pytest.mark.parametrize("left,right", [
    ("Diario de la baronesa Alba", "Diario de la baronesa Luna"),
    ("Collar de Zun", "Collar de la Luna"),
    ("Estatuilla de Orcus de plata", "Estatuilla de Orcus de madera"),
])
def test_similar_item_type_is_not_evidence_of_same_identity(left, right):
    assert are_items_duplicate({"name": left}, {"name": right}) == (False, None)


def test_explicit_item_and_place_aliases_keep_existing_name_without_invented_canon():
    left = {"name": "Diario de Alba", "aliases": ["Journal of Alba"]}
    assert are_items_duplicate(left, {"name": "Journal of Alba"}) == (True, "Diario de Alba")
    place = {"name": "Mansión del Norte", "aliases": ["North Manor"]}
    assert are_locations_duplicate(place, {"name": "North Manor"}) == (True, "Mansión del Norte")
    assert not are_locations_duplicate({"name": "Mansión de Alba"}, {"name": "Mansión de Luna"})[0]


def test_campaign_deduplication_never_invents_zun_for_an_unrelated_necklace():
    manager = CampaignManager()
    state = manager.load_campaign("Mesa")
    state["items"] = [{"name": "Collar sagrado de la Aurora", "type": "reliquia"}]
    manager.save_campaign(state)
    manager.deduplicate_campaign_entities("Mesa")
    assert manager.load_campaign("Mesa")["items"][0]["name"] == "Collar sagrado de la Aurora"


@pytest.mark.parametrize("kind", ["md", "docx"])
@pytest.mark.parametrize("journal", [False, True])
def test_downloads_do_not_name_markus_for_unidentified_legacy_coaching(tmp_path, kind, journal):
    session = {"session_number": 1, "title": "La puerta", "chronicle_text": "Llegan.",
               "markus_coaching": "Reflexión sin identidad verificada."}
    destination = tmp_path / f"document.{kind}"
    if journal:
        state = {"campaign_name": "Mesa", "sessions": [session]}
        (export_living_journal_md if kind == "md" else export_living_journal_docx)(state, output_path=str(destination))
    else:
        (export_session_md if kind == "md" else export_session_docx)(session, campaign_name="Mesa", output_path=str(destination))
    if kind == "md":
        text = destination.read_text(encoding="utf8")
    else:
        with ZipFile(destination) as doc:
            text = doc.read("word/document.xml").decode()
    assert "Markus" not in text
    assert "Reflexión sin identidad verificada." in text


def test_whisper_vocabulary_includes_campaign_aliases_and_excludes_foreign_names():
    manager = CampaignManager()
    state = manager.load_campaign("Mesa")
    state["roster"] = [{"character_name": "Arin", "player_name": "Ana"}]
    state["universal_pcs"] = [{"personaje": "Arin", "aliases": ["Aryn"]}]
    state["npcs"] = [{"name": "Mael", "aliases": ["Mayel"]}]
    manager.save_campaign(state)
    result = server.build_whisper_prompt("Mesa", roster=state["roster"])
    assert "Aryn" in result and "Mayel" in result
    assert "Markus" not in result and "Minipeko" not in result
    assert "Aryn" not in (server.build_whisper_prompt(roster=[{"character_name": "Lira"}]) or "")


def test_gemini_receives_named_aliases_without_a_fixed_cast():
    result = build_continuity_session_prompt(
        roster_formatted=GeminiTTRPGSummarizer.format_roster([{"character_name": "Arin", "aliases": ["Aryn"]}]),
        existing_quests=[], known_npcs=[{"name": "Mael", "aliases": ["Mayel"]}],
        transcript_text="Aryn habla con Mayel.", session_number=1)
    history = result.split("</historical_campaign_context>")[0]
    assert "Aryn" in history and "Mayel" in history
    assert '"aliases": ["Alias1", "Apodo"]' not in result
    assert '"aliases": ["Variante Fonética 1", "Apodo"]' not in result
    assert "evolucionan con la campaña" in result


def test_transcription_normalizes_only_this_campaigns_npc_aliases(tmp_path, monkeypatch):
    manager = CampaignManager()
    state = manager.load_campaign("Mesa")
    state["npcs"] = [{"name": "Mael", "aliases": ["Mayel"]}]
    manager.save_campaign(state)
    audio = tmp_path / "synthetic.mp3"
    audio.write_bytes(b"not sent to any provider")
    output = {"text": "Mayel abre la puerta.", "segments": [{"start": 0, "end": 2, "text": "Mayel abre la puerta."}], "duration": 2}
    monkeypatch.setattr(server, "_transcribe_audio_pipeline", lambda *a, **kw: copy.deepcopy(output))
    assert server.transcribe_audio_pipeline(str(audio), campaign_name="Mesa")["text"] == "Mael abre la puerta."
    assert server.transcribe_audio_pipeline(str(audio))["text"] == "Mayel abre la puerta."


def test_aliases_evolve_across_sessions_and_manual_rejections_stay_rejected():
    manager = CampaignManager()
    manager.record_session("Mesa", {"title": "Uno"}, session_number=1,
                           updated_npcs=[{"name": "Mael", "aliases": ["Mayel"]}])
    manager.record_session("Mesa", {"title": "Dos"}, session_number=2,
                           updated_npcs=[{"name": "Mael", "aliases": ["Mahel"]}])
    assert set(manager.load_campaign("Mesa")["npcs"][0]["aliases"]) == {"Mayel", "Mahel"}
    manager.update_wiki_entity("Mesa", "npc", "Mael", {"aliases": ["Mahel"]})
    manager.record_session("Mesa", {"title": "Tres"}, session_number=3,
                           updated_npcs=[{"name": "Mael", "aliases": ["Mayel", "Mayell"]}])
    npc = manager.load_campaign("Mesa")["npcs"][0]
    assert set(npc["aliases"]) == {"Mahel", "Mayell"}
    assert "Mayel" not in (server.build_whisper_prompt("Mesa") or "").split(", ")
    assert "Mayell" in server.build_whisper_prompt("Mesa")
    # Persisted in both active representations, not a process-global cache.
    modular = json.loads(manager.get_modular_paths("Mesa")["npcs"].read_text(encoding="utf8"))
    assert modular[0]["aliases"] == npc["aliases"]


def test_new_canonical_name_preserves_old_name_for_future_recognition():
    manager = CampaignManager()
    manager.record_session("Mesa", {"title": "Uno"}, updated_npcs=[{"name": "Mael", "aliases": ["Mayel"]}])
    manager.update_wiki_entity("Mesa", "npc", "Mael", {"name": "Mael del Norte"})
    prompt = server.build_whisper_prompt("Mesa")
    assert "Mael del Norte" in prompt and "Mayel" in prompt
    assert "Mael" in manager.load_campaign("Mesa")["npcs"][0]["aliases"]
    # A known spelling variant must not become the canonical name by being longer.
    manager.record_session("Mesa", {"title": "Dos"}, updated_npcs=[{"name": "Mayel", "aliases": []}])
    assert manager.load_campaign("Mesa")["npcs"][0]["name"] == "Mael del Norte"


def test_removed_alias_cannot_fuzzy_merge_another_character_into_the_old_one():
    manager = CampaignManager()
    manager.record_session("Mesa", {"title": "Uno"}, updated_npcs=[{"name": "Mael", "aliases": ["Mayel"]}])
    manager.update_wiki_entity("Mesa", "npc", "Mael", {"aliases": []})
    manager.record_session("Mesa", {"title": "Dos"}, updated_npcs=[{"name": "Mayel", "role": "Otro guardia"}])
    assert {n["name"] for n in manager.load_campaign("Mesa")["npcs"]} == {"Mael", "Mayel"}


def test_deduplication_retains_confirmed_item_aliases_for_future_sessions():
    manager = CampaignManager()
    state = manager.load_campaign("Mesa")
    state["items"] = [{"name": "Llave del Norte", "aliases": ["North Key"]},
                      {"name": "North Key", "aliases": ["Llave azul"]}]
    manager.save_campaign(state)
    manager.deduplicate_campaign_entities("Mesa")
    item = manager.load_campaign("Mesa")["items"][0]
    assert set(item["aliases"]) == {"North Key", "Llave azul"}


@pytest.mark.parametrize("kind", ["items", "locations"])
def test_recording_a_new_entity_does_not_drop_its_aliases(kind):
    state = CampaignManager().record_session("Mesa", {"title": "Uno"},
        **{kind: [{"name": "Lugar u objeto del Norte", "aliases": ["North Landmark"]}]})
    assert state[kind][0]["aliases"] == ["North Landmark"]
