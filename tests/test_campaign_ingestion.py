"""Imports and retries must persist the same history in both storage formats."""
import io
import json
import os
from pathlib import Path
import zipfile
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api import server
from src.storage.campaign_manager import CampaignManager
from src.storage.drive_client import GoogleDriveStorage


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    for key in ("INPUT", "OUTPUT", "CAMPAIGNS", "QUOTA"):
        monkeypatch.setenv(f"WHISPER_{key}_DIR", str(tmp_path / key.lower()))
    monkeypatch.setattr(server, "trigger_drive_sync_background", lambda paths: None)
    monkeypatch.setattr(server, "GoogleDriveStorage", lambda: MagicMock(is_connected=lambda: False))
    return CampaignManager(), TestClient(server.app)


def payload(numbers):
    return {"campaign_name": "Mesa", "updated_at": "2099-01-01T00:00:00",
            "last_session": max(numbers, default=0),
            "sessions": [{"session_number": n, "title": f"Capítulo {n}",
                          "chronicle_text": f"Crónica {n}"} for n in numbers]}


def document(state, suffix):
    content = json.dumps(state).encode()
    if suffix == "zip":
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("campaign.json", content)
        return archive.getvalue()
    return content


@pytest.mark.parametrize("suffix", ["json", "zip"])
def test_api_import_replaces_modular_and_mirror_together(isolated, suffix):
    manager, client = isolated
    manager.save_campaign(payload([1, 2, 3]))
    mirror_before = manager.get_campaign_path("Mesa").read_bytes()
    response = client.post("/api/campaigns/import", files={"file": (
        f"mesa.{suffix}", document(payload([1, 2, 3, 4]), suffix))})
    assert response.status_code == 200, response.text
    state = manager.load_modular("Mesa")
    assert [s["session_number"] for s in state["sessions"]] == [1, 2, 3, 4]
    assert json.loads(manager.get_campaign_path("Mesa").read_text(encoding="utf-8"))["sessions"] == state["sessions"]
    backups = list((manager.get_campaign_dir("Mesa") / "backups").glob("import_*.json"))
    assert backups
    backup = json.loads(backups[0].read_text(encoding="utf-8"))
    assert backup["legacy_mirror_text"].encode() == mirror_before


def drive_for(state, suffix):
    base = Path(os.environ["WHISPER_CAMPAIGNS_DIR"]).parent
    storage = GoogleDriveStorage(str(base / "fake-credentials.json"), str(base / "fake-token.json"))
    storage.is_connected = lambda: True
    service = MagicMock()
    def listing(q=None, **kwargs):
        response = MagicMock()
        if "name = 'WhisperDnD'" in (q or ""):
            files = [{"id": "root", "name": "WhisperDnD"}]
        elif "'root' in parents" in (q or ""):
            files = [{"id": "remote", "name": f"mesa.{suffix}",
                      "mimeType": "application/json" if suffix == "json" else "application/zip"}]
        else:
            files = []
        response.execute.return_value = {"files": files}
        return response
    service.files.return_value.list.side_effect = listing
    storage._service = service
    storage.download_file_bytes = lambda file_id: document(state, suffix)
    storage.upload_file = MagicMock(return_value={"file_id": "uploaded"})
    return storage


@pytest.mark.parametrize("suffix", ["json", "zip"])
def test_drive_download_updates_existing_modular_history(isolated, suffix):
    manager, _ = isolated
    manager.save_campaign(payload([1, 2, 3]))
    storage = drive_for(payload([1, 2, 3, 4]), suffix)
    result = storage.sync_from_google_drive(manager.campaigns_dir, manager.output_dir)
    assert result["downloaded_campaigns"] == 1
    loaded = manager.load_campaign("Mesa")
    assert [s["session_number"] for s in loaded["sessions"]] == [1, 2, 3, 4]


def test_failed_regeneration_keeps_previous_session_in_both_formats(isolated, monkeypatch):
    manager, _ = isolated
    manager.save_campaign(payload([1, 2, 3, 4]))
    before = {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")}
    summarizer = MagicMock()
    summarizer.model_name = "offline-model"
    summarizer.generate_campaign_session.side_effect = RuntimeError("Gemini no disponible")
    monkeypatch.setattr(server, "GeminiTTRPGSummarizer", lambda **kwargs: summarizer)
    with pytest.raises(RuntimeError, match="Gemini no disponible"):
        server.process_session_for_campaign("Mesa", "Transcripción válida", session_number=4)
    assert {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")} == before


def test_conflicting_formats_are_not_overwritten_by_an_import(isolated):
    manager, client = isolated
    manager.save_campaign(payload([1, 2, 3]))
    mirror = manager.get_campaign_path("Mesa")
    mirror.write_text(json.dumps(payload([1, 2, 3, 4, 5])), encoding="utf-8")
    before = {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")}
    response = client.post("/api/campaigns/import", files={"file": (
        "mesa.json", document(payload([1, 2, 3, 4]), "json"))})
    assert response.status_code == 409, response.text
    assert {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")} == before


def test_normal_save_cannot_erase_sessions_hidden_in_the_other_format(isolated):
    manager, _ = isolated
    manager.save_campaign(payload([1, 2, 3]))
    manager.get_campaign_path("Mesa").write_text(json.dumps(payload([1, 2, 3, 4, 5])), encoding="utf-8")
    before = {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")}
    with pytest.raises(ValueError, match="diferencias"):
        manager.save_campaign(payload([1, 2, 3, 4]))
    assert {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")} == before


def test_failed_mirror_write_rolls_back_the_modular_update(isolated, monkeypatch):
    from pathlib import Path
    manager, _ = isolated
    manager.save_campaign(payload([1, 2, 3]))
    before = {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")}
    write_text = Path.write_text
    def failing_write(path, *args, **kwargs):
        if path == manager.get_campaign_path("Mesa"):
            raise OSError("Disco no disponible")
        return write_text(path, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", failing_write)
    with pytest.raises(OSError, match="Disco no disponible"):
        manager.save_campaign(payload([1, 2, 3, 4]))
    assert {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")} == before


def test_upload_returns_the_session_identity_used_for_regeneration(isolated, monkeypatch):
    manager, client = isolated
    state = payload([1, 2, 3, 4])
    monkeypatch.setattr(server, "validate_api_keys_or_raise", lambda *args, **kwargs: None)
    monkeypatch.setattr(server, "transcribe_audio_pipeline", lambda **kwargs: {
        "text": "Transcripción de la sesión cuatro", "segments": [],
        "language": {"code": "es"}, "duration": 30, "engine_used": "local-base"})
    monkeypatch.setattr(server, "process_session_for_campaign", lambda **kwargs: {
        "campaign_state": state, "campaign_name": "Mesa", "session_number": 4,
        "session_chapter": {"title": "Cuatro"}, "chronicle": "Crónica cuatro",
        "file_path": str(manager.output_dir / "cuatro.docx")})
    response = client.post("/api/transcribe/file", files={"file": ("audio.wav", b"fake audio")},
                           data={"campaign_name": "Mesa", "engine": "local"})
    assert response.status_code == 200, response.text
    assert response.json()["campaign_name"] == "Mesa"
    assert response.json()["session_number"] == 4


@pytest.mark.parametrize("suffix", ["json", "zip"])
def test_drive_reports_local_conflicts_without_uploading_either_version(isolated, suffix):
    manager, _ = isolated
    manager.save_campaign(payload([1, 2, 3]))
    manager.get_campaign_path("Mesa").write_text(json.dumps(payload([1, 2, 3, 4, 5])), encoding="utf-8")
    before = {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")}
    remote = payload([1, 2, 3, 4, 5, 6])
    remote["updated_at"] = "2199-01-01T00:00:00"
    storage = drive_for(remote, suffix)
    result = storage.sync_from_google_drive(manager.campaigns_dir, manager.output_dir)
    assert result["status"] == "partial"
    assert result["campaign_errors"]
    assert result["downloaded_campaigns"] == 0
    assert {p: p.read_bytes() for p in manager.campaigns_dir.rglob("*.json")} == before
    storage.upload_file.assert_not_called()


def test_modular_history_with_a_deleted_middle_session_is_still_loadable(isolated):
    manager, _ = isolated
    manager.save_campaign(payload([1, 3]))
    state = manager.load_modular("Mesa")
    assert state is not None
    assert [s["session_number"] for s in state["sessions"]] == [1, 3]


def test_successful_rerecord_keeps_number_and_backs_up_the_previous_chapter(isolated):
    manager, _ = isolated
    manager.save_campaign(payload([1, 2, 3, 4]))
    state = manager.record_session("Mesa", {"title": "Cuatro corregida", "chronicle_text": "Nueva crónica"},
                                   session_number=4, raw_transcript="Audio completo transcrito")
    assert [s["session_number"] for s in state["sessions"]] == [1, 2, 3, 4]
    assert state["sessions"][-1]["title"] == "Cuatro corregida"
    mirror = json.loads(manager.get_campaign_path("Mesa").read_text(encoding="utf-8"))
    assert mirror["sessions"] == manager.load_modular("Mesa")["sessions"]
    backups = list((manager.get_campaign_dir("Mesa") / "backups").glob("rerecord_4_*.json"))
    assert backups
    backup = json.loads(backups[0].read_text(encoding="utf-8"))
    assert backup["campaign_state"]["sessions"][-1]["title"] == "Capítulo 4"


@pytest.mark.parametrize("suffix", ["json", "zip"])
def test_older_drive_backup_cannot_restore_an_obsolete_history(isolated, suffix):
    manager, _ = isolated
    manager.save_campaign(payload([1, 2, 3, 4]))
    remote = payload([1, 2, 3])
    remote["updated_at"] = "2000-01-01T00:00:00"
    storage = drive_for(remote, suffix)
    result = storage.sync_from_google_drive(manager.campaigns_dir, manager.output_dir)
    assert result["downloaded_campaigns"] == 0
    assert [s["session_number"] for s in manager.load_modular("Mesa")["sessions"]] == [1, 2, 3, 4]


def test_regenerating_four_while_five_exists_preserves_five(isolated, monkeypatch):
    manager, _ = isolated
    original = payload([1, 2, 3, 4, 5])
    manager.save_campaign(original)
    summarizer = MagicMock()
    summarizer.model_name = "offline-model"
    summarizer.generate_campaign_session.return_value = {
        "session_chapter": {"title": "Cuatro corregida", "chronicle_text": "Crónica completa corregida"},
        "updated_quests": [], "updated_npcs": [], "detected_pcs": [], "detected_party": [],
        "detected_npc_names": [], "locations": [], "items": []}
    monkeypatch.setattr(server, "GeminiTTRPGSummarizer", lambda **kwargs: summarizer)
    result = server.process_session_for_campaign("Mesa", "Transcripción completa de la sesión cuatro", session_number=4)
    assert result["session_number"] == 4
    from src.storage.session_review import load_review, apply_review
    rid = result["session_chapter"]["review_id"]
    draft = load_review(server.get_data_output_dir(), rid)
    apply_review(manager, server.get_data_output_dir(), rid, draft["revision"], [], {})
    loaded = manager.load_modular("Mesa")
    assert [s["session_number"] for s in loaded["sessions"]] == [1, 2, 3, 4, 5]
    assert loaded["sessions"][-1] == original["sessions"][-1]
    assert loaded["sessions"][3]["title"] == "Cuatro corregida"
    assert loaded["last_session"] == 5
    mirror = json.loads(manager.get_campaign_path("Mesa").read_text(encoding="utf-8"))
    assert mirror["sessions"] == loaded["sessions"]
