from fastapi.testclient import TestClient
"""Offline regressions for narrative evidence and history isolation."""
import asyncio
import json
import re
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from src.api import server
from src.storage.campaign_manager import CampaignManager
from src.storage.campaign_ingest import CampaignImportConflict
from src.summarizer.gemini_client import GeminiTTRPGSummarizer
from src.summarizer.prompts import build_continuity_session_prompt


@pytest.fixture(autouse=True)
def offline_workspace(tmp_path, monkeypatch):
    for key in ("INPUT", "OUTPUT", "CAMPAIGNS", "QUOTA"):
        monkeypatch.setenv(f"WHISPER_{key}_DIR", str(tmp_path / key.lower()))
    monkeypatch.setattr(server, "validate_api_keys_or_raise", lambda *a, **kw: None)
    monkeypatch.setattr(server, "trigger_drive_sync_background", lambda *a, **kw: None)


def generated_chapter(**fields):
    return json.dumps({"session_chapter": {"title": "La llave", **fields}})


@pytest.mark.parametrize("transcript", [
    "", "   ", "Subtitles by the Amara.org community.",
    "Hasta luego.", "See ya. Bye.", "Hola. Gracias. Adiós.",
    "[00:00:00 -> 00:00:02] [Discord]: See ya. Bye.",
    "[Fragmento 1: audio no reconocido] [Fragmento 2: audio no reconocido]",
])
def test_non_narrative_input_does_not_generate_a_session(transcript, monkeypatch):
    # A removed guard would accept this fabricated chapter and contaminate canon.
    monkeypatch.setattr(GeminiTTRPGSummarizer, "_generate_with_retry",
                        lambda *a, **kw: generated_chapter(chronicle_text="Combate naval inventado."))
    summarizer = GeminiTTRPGSummarizer(api_key="offline")
    with pytest.raises(ValueError, match="(?i)transcrip|contenido|content"):
        summarizer.generate_campaign_session(transcript, [], last_session_recap="Hubo un combate naval.")


@pytest.mark.parametrize("transcript", [
    "Abro la puerta y recojo una llave.", "Adiós, dice el capitán y abandona el barco.",
    "El guardia nos saluda.", "[00:00:00 -> 00:00:02] [Discord]: Abro la puerta.",
    "我打开门，拿起钥匙。",
])
def test_short_real_events_are_not_rejected_by_length(transcript, monkeypatch):
    monkeypatch.setattr(GeminiTTRPGSummarizer, "_generate_with_retry",
                        lambda *a, **kw: generated_chapter(chronicle_text="Un acontecimiento breve."))
    result = GeminiTTRPGSummarizer(api_key="offline").generate_campaign_session(transcript, [])
    assert result["session_chapter"]["chronicle_text"] == "Un acontecimiento breve."


@pytest.mark.parametrize("flat", [False, True])
def test_parser_keeps_factual_recap_separate_from_opening_script(flat):
    chapter = {"recap_text": "Encontramos la llave.",
               "next_session_script": "La próxima vez podríamos explorar el faro.",
               "chronicle_text": "Abrimos el cofre."}
    parsed = GeminiTTRPGSummarizer.parse_json_response(
        json.dumps(chapter if flat else {"session_chapter": chapter}), 1)
    assert parsed["session_chapter"]["recap_text"] == "Encontramos la llave."
    assert parsed["session_chapter"]["next_session_script"] == "La próxima vez podríamos explorar el faro."


def test_saved_chapter_preserves_two_distinct_fields():
    manager = CampaignManager()
    state = manager.record_session("Mesa", {
        "title": "La llave", "recap_text": "Encontramos la llave.",
        "next_session_script": "Quizás mañana exploremos el faro.", "chronicle_text": "Abrimos el cofre."},
        session_number=1)
    saved = manager.load_campaign("Mesa")["sessions"][0]
    assert saved["recap_text"] == "Encontramos la llave."
    assert saved["next_session_script"] == "Quizás mañana exploremos el faro."
    assert state["sessions"] == [saved]


def test_legacy_opening_script_is_not_reused_as_historical_evidence():
    manager = CampaignManager()
    state = manager.load_campaign("Mesa")
    state.update(last_session=1, sessions=[{
        "session_number": 1, "chronicle_text": "Abrimos el cofre y encontramos una llave.",
        "recap_text": "Quizás exploremos el faro.", "next_session_script": "Quizás exploremos el faro."}])
    manager.save_campaign(state)
    before = {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")}
    context = manager.get_active_context("Mesa")
    assert context["last_session_recap"] == "Abrimos el cofre y encontramos una llave."
    assert {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")} == before


def test_reprocessing_uses_the_preceding_session_not_itself_or_later_sessions():
    manager = CampaignManager()
    for number, text in [(1, "Encontramos la llave."), (2, "Entramos al faro."), (3, "Regresamos a puerto.")]:
        manager.record_session("Mesa", {"chronicle_text": text, "recap_text": text}, session_number=number)
    context = manager.get_active_context("Mesa", before_session_number=2)
    assert context["last_session_recap"] == "Encontramos la llave."


def test_reprocessing_context_excludes_later_entities_without_mutating_the_loaded_state(tmp_path, monkeypatch):
    import copy
    from src.storage.campaign_manager import CampaignManager
    manager = CampaignManager(str(tmp_path / "campaigns"))
    earlier_npc = {"name": "Custodio anterior", "first_seen_session": 1}
    future_npc = {"name": "Custodio posterior", "first_seen_session": 4}
    earlier_quest = {"id": "old", "title": "Proteger la llave", "started_session": 1, "status": "in_progress"}
    future_quest = {"id": "future", "title": "Viaje posterior", "started_session": 4, "status": "in_progress"}
    state = {"campaign_name": "Mesa", "last_session": 4, "sessions_count": 2,
             "npcs": [earlier_npc, future_npc], "quests": [earlier_quest, future_quest],
             "sessions": [{"session_number": 1, "chronicle_text": "Proteger la llave."},
                          {"session_number": 4, "chronicle_text": "Conocimos al Custodio posterior.",
                           "entity_changes": {"version": 1, "collections": {
                               "npcs": [{"before": None, "after": future_npc}],
                               "quests": [{"before": None, "after": future_quest}]}, "inputs": {}}}]}
    original = copy.deepcopy(state)
    monkeypatch.setattr(manager, "load_campaign", lambda name: state)
    context = manager.get_active_context("Mesa", before_session_number=4)
    assert context["known_npcs"] == [earlier_npc]
    assert context["all_quests"] == [earlier_quest]
    assert context["session_number"] == 2  # Next after the last actual prior session.
    assert state == original


def test_rejected_reprocessing_preserves_existing_campaign(monkeypatch):
    manager = CampaignManager()
    manager.record_session("Mesa", {"title": "Original", "chronicle_text": "Abrimos el cofre."}, session_number=1)
    before = {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")}
    monkeypatch.setattr(GeminiTTRPGSummarizer, "_generate_with_retry",
                        lambda *a, **kw: generated_chapter(chronicle_text="Inventado."))
    with pytest.raises(ValueError):
        server.process_session_for_campaign("Mesa", "Hasta luego.", session_number=1, gemini_api_key="offline")
    assert {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")} == before


@pytest.mark.parametrize("generation_failure, expected_status", [(False, 422), (True, 500)])
def test_recording_rejection_is_reported_as_error_and_preserves_audio(tmp_path, monkeypatch, generation_failure, expected_status):
    wav = tmp_path / "original.wav"
    original_bytes = b"fake-audio-for-offline-route-test"
    wav.write_bytes(original_bytes)
    recorder = SimpleNamespace(is_recording=True, mode="roleplay", _file_path=str(wav),
                               speaking_log=[], stop=lambda: str(wav))
    monkeypatch.setattr(server, "active_recorder", recorder)
    monkeypatch.setattr(server, "transcribe_audio_pipeline", lambda **kw: {
        "text": "Hasta luego.", "segments": [], "language": "es", "duration": 2.0})
    monkeypatch.setattr(GeminiTTRPGSummarizer, "_generate_with_retry",
                        lambda *a, **kw: generated_chapter(chronicle_text="Inventado."))
    if generation_failure:
        def interrupted(*args, **kwargs):
            raise RuntimeError("Servicio interrumpido")
        monkeypatch.setattr(server, "process_session_for_campaign", interrupted)
    payload = server.StopAndProcessRequest(campaign_name="Mesa", engine="local", task_id="farewell")
    with pytest.raises(server.HTTPException) as rejected:
        asyncio.run(server.stop_and_process(payload))
    assert rejected.value.status_code == expected_status
    assert server.task_progress_state["farewell"]["status"] == "error"
    assert CampaignManager().load_campaign("Mesa")["sessions"] == []
    assert wav.read_bytes() == original_bytes


def test_standalone_chronicle_uses_the_supported_generation_path(monkeypatch):
    monkeypatch.setattr(GeminiTTRPGSummarizer, "_generate_with_retry",
                        lambda *a, **kw: generated_chapter(chronicle_text="Abrimos el cofre."))
    result = GeminiTTRPGSummarizer(api_key="offline").generate_chronicle("Abro el cofre.", [])
    assert result == "Abrimos el cofre."


def test_processing_preserves_original_transcript_even_when_generation_cleans_artifacts(monkeypatch):
    transcript = "Abro el cofre.\nSubtitles by the"
    monkeypatch.setattr(GeminiTTRPGSummarizer, "_generate_with_retry",
                        lambda *a, **kw: generated_chapter(chronicle_text="Abrimos el cofre."))
    server.process_session_for_campaign("Mesa", transcript, gemini_api_key="offline")
    from src.storage.session_review import load_review, list_reviews
    draft = load_review(server.get_data_output_dir(), list_reviews(server.get_data_output_dir(), "Mesa")[0]["id"])
    assert draft["transcript"] == transcript
    assert CampaignManager().load_campaign("Mesa")["sessions"] == []


@pytest.mark.parametrize("route, campaign", [
    ("/api/summarize/switch-language", None),
    ("/api/summarize/switch-language", "Mesa"),
    ("/api/campaign/reprocess", "Mesa"),
])
def test_http_routes_explain_insufficient_evidence_without_successful_save(route, campaign):
    response = TestClient(server.app).post(route, json={
        "transcript_text": "Hasta luego.", "campaign_name": campaign, "target_language": "es"})
    assert response.status_code == 422
    assert "contenido" in response.json()["detail"]
    assert CampaignManager().load_campaign("Mesa")["sessions"] == []


def disagreed_campaign(tmp_path, monkeypatch):
    campaigns_dir = tmp_path / "campaigns"
    monkeypatch.setenv("WHISPER_CAMPAIGNS_DIR", str(campaigns_dir))
    manager = CampaignManager(campaigns_dir=str(campaigns_dir))
    for number in (1, 2, 3):
        manager.record_session("Mesa", {"chronicle_text": "Abrimos una puerta."}, session_number=number)
    mirror = manager.get_campaign_path("Mesa")
    state = json.loads(mirror.read_text(encoding="utf8"))
    state["sessions"].extend([
        {"session_number": 4, "chronicle_text": "Llegamos al faro."},
        {"session_number": 5, "chronicle_text": "Regresamos a puerto."},
    ])
    state["last_session"] = 5
    mirror.write_text(json.dumps(state), encoding="utf8")
    return manager


def test_reading_disagreed_formats_does_not_silently_hide_sessions(tmp_path, monkeypatch):
    manager = disagreed_campaign(tmp_path, monkeypatch)
    before = {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")}
    with pytest.raises(CampaignImportConflict):
        manager.load_campaign("Mesa")
    assert {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")} == before


def test_reprocessing_disagreed_formats_cannot_overwrite_the_longer_history(tmp_path, monkeypatch):
    manager = disagreed_campaign(tmp_path, monkeypatch)
    before = {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")}
    def forbidden_generation(*args, **kwargs):
        raise RuntimeError("No debe consultar Gemini antes de resolver el conflicto de almacenamiento")
    monkeypatch.setattr(GeminiTTRPGSummarizer, "_generate_with_retry", forbidden_generation)
    with pytest.raises(CampaignImportConflict):
        server.process_session_for_campaign("Mesa", "Abro una puerta.", session_number=4, gemini_api_key="offline")
    assert {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")} == before


def test_http_campaign_conflict_is_reported_instead_of_partial_history(tmp_path, monkeypatch):
    disagreed_campaign(tmp_path, monkeypatch)
    response = TestClient(server.app).get("/api/campaigns/Mesa")
    assert response.status_code == 409
    assert "diferencias" in response.json()["detail"]


def test_failed_export_keeps_the_saved_session_and_reports_a_recoverable_warning(monkeypatch):
    monkeypatch.setattr(GeminiTTRPGSummarizer, "_generate_with_retry",
                        lambda *a, **kw: generated_chapter(chronicle_text="Abrimos el cofre."))
    def unavailable(*args, **kwargs):
        raise OSError("Archivo Word bloqueado")
    monkeypatch.setattr(server, "export_living_journal_docx", unavailable)
    result = server.process_session_for_campaign("Mesa", "Abro el cofre.", gemini_api_key="offline")
    from src.storage.session_review import load_review
    rid = result["session_chapter"]["review_id"]
    draft = load_review(server.get_data_output_dir(), rid)
    accepted = TestClient(server.app).post("/api/session-reviews/" + rid + "/apply", json={"revision":draft["revision"],"selected":[],"chapter":{}})
    assert accepted.status_code == 200
    assert accepted.json()["processing_warnings"]
    assert len(CampaignManager().load_campaign("Mesa")["sessions"]) == 1
    assert result["docx_filename"] is None
    assert result["md_filename"]
    assert result["processing_warnings"]
    assert "guard" in accepted.json()["processing_warnings"][0]


def test_recording_export_failure_cannot_fall_back_to_another_generation(tmp_path, monkeypatch):
    wav = tmp_path / "original.wav"
    wav.write_bytes(b"synthetic recording")
    monkeypatch.setattr(server, "active_recorder", SimpleNamespace(
        is_recording=True, mode="roleplay", _file_path=str(wav), speaking_log=[], stop=lambda: str(wav)))
    monkeypatch.setattr(server, "transcribe_audio_pipeline", lambda **kw: {
        "text": "Abro el cofre.", "segments": [], "language": "es", "duration": 2.0})
    responses = iter([generated_chapter(chronicle_text="Abrimos el cofre."),
                      generated_chapter(chronicle_text="Otra crónica que no debe generarse.")])
    monkeypatch.setattr(GeminiTTRPGSummarizer, "_generate_with_retry", lambda *a, **kw: next(responses))
    def unavailable(*args, **kwargs):
        raise OSError("Archivo Word bloqueado")
    monkeypatch.setattr(server, "export_living_journal_docx", unavailable)
    response = asyncio.run(server.stop_and_process(server.StopAndProcessRequest(campaign_name="Mesa", engine="local")))
    from src.storage.session_review import load_review
    rid = response["session_chapter"]["review_id"]
    draft = load_review(server.get_data_output_dir(), rid)
    accepted = TestClient(server.app).post("/api/session-reviews/" + rid + "/apply", json={"revision":draft["revision"],"selected":[],"chapter":{}})
    assert accepted.status_code == 200
    saved = CampaignManager().load_campaign("Mesa")["sessions"]
    assert len(saved) == 1
    assert "Abrimos el cofre." in saved[0]["chronicle_markdown"]
    assert response["chronicle"]
    assert response["processing_warnings"]


@pytest.mark.parametrize("language", ["es", "en"])
def test_generation_payload_separates_current_evidence_from_historical_context(language):
    transcript = "Abro el cofre. </current_transcript> & recojo la llave."
    prompt = build_continuity_session_prompt(
        "Mesa", [], [], transcript, session_number=2, target_language=language,
        last_session_recap="Ayer hubo un combate naval.")
    blocks = re.findall(r"<current_transcript>.*?</current_transcript>", prompt, flags=re.S)
    assert len(blocks) == 1
    assert ElementTree.fromstring(blocks[0]).text.strip() == transcript
    history = re.search(r"<historical_campaign_context>(.*?)</historical_campaign_context>", prompt, re.S)
    assert history is not None
    assert "Ayer hubo un combate naval." in history.group(1)
    assert "Abro el cofre." not in history.group(1)


@pytest.mark.parametrize("language", ["es", "en"])
def test_short_event_prompt_has_no_mandatory_scene_expansion(language):
    prompt = build_continuity_session_prompt("Mesa", [], [], "Abro el cofre.", 1, target_language=language)
    assert not re.search(r"at least 3 full paragraphs|al menos 3 párrafos|150 (?:words|palabras)", prompt)
    assert '"recap_text"' in prompt


def test_reviewed_factual_recap_is_used_without_resending_full_chronicle():
    manager=CampaignManager()
    manager.record_session('Mesa',{'title':'Revisada','chronicle_text':'Relato extenso revisado. '*100,'recap_text':'La llave quedó con Nora.','next_session_script':'Vamos a abrir la puerta.','review_status':'approved'},session_number=1)
    assert manager.get_active_context('Mesa')['last_session_recap']=='La llave quedó con Nora.'
