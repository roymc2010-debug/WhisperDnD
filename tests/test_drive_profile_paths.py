"""Desktop OAuth configuration and personal tokens remain in synthetic profiles."""
import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.storage import drive_client
from src.api import server  # Initialize the app before importing its routers.
from src.api.routers import drive as drive_router


DESKTOP_CLIENT = {"installed": {"client_id": "synthetic-client", "client_secret": "desktop-metadata",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}}


@pytest.fixture
def packaged(tmp_path, monkeypatch, request):
    resources = tmp_path / "Program Files" / "WhisperDnD"
    (resources / "oauth").mkdir(parents=True)
    # A distribution must not discover or restore personal files alongside its code.
    (resources / "credentials.json").write_text('{"web": {"client_id": "legacy-web"}}', encoding="utf8")
    (resources / "token.json").write_text('{"token":"bundle-owner"}', encoding="utf8")
    (resources / "token_backup.json").write_text('{"token":"bundle-owner-backup"}', encoding="utf8")
    if getattr(request, "param", True):
        (resources / "oauth" / "drive-desktop.json").write_text(json.dumps(DESKTOP_CLIENT), encoding="utf8")
    snapshot = {p.relative_to(resources): p.read_bytes() for p in resources.rglob("*") if p.is_file()}
    profile = tmp_path / "Usuarios" / "María" / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    monkeypatch.delenv("GOOGLE_CREDENTIALS_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_TOKEN_JSON", raising=False)
    monkeypatch.setenv("OAUTHLIB_INSECURE_TRANSPORT", "1")
    monkeypatch.setenv("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(drive_client, "__file__", str(resources / "src" / "storage" / "drive_client.py"))
    monkeypatch.setattr(drive_client, "_active_oauth_flow", None)
    monkeypatch.setattr(drive_client, "_active_oauth_flows", {})
    mkdir = Path.mkdir

    def outside_resources(path, *args, **kwargs):
        assert not path.is_relative_to(resources), "attempted OAuth write inside program resources"
        return mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", outside_resources)
    yield resources, profile / "WhisperDnD" / "config"
    assert {p.relative_to(resources): p.read_bytes() for p in resources.rglob("*") if p.is_file()} == snapshot


@pytest.mark.parametrize("packaged", [True, False], indirect=True)
def test_default_paths_never_use_bundle_owner_tokens(packaged):
    _, config = packaged
    storage = drive_client.GoogleDriveStorage()
    assert storage.credentials_path == config / "credentials.json"
    assert storage.token_path == config / "token.json"
    assert not storage.token_path.exists()
    assert not (config / "token_backup.json").exists()
    if storage.credentials_path.exists():
        assert json.loads(storage.credentials_path.read_text(encoding="utf8")) == DESKTOP_CLIENT


def test_second_profile_never_inherits_the_first_profiles_token(packaged, tmp_path, monkeypatch):
    first = drive_client.GoogleDriveStorage()
    first.token_path.parent.mkdir(parents=True, exist_ok=True)
    first.token_path.write_text('{"token":"first-user"}', encoding="utf8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "second-profile"))
    second = drive_client.GoogleDriveStorage()
    assert second.token_path != first.token_path
    assert not second.token_path.exists()
    assert json.loads(second.credentials_path.read_text(encoding="utf8")) == DESKTOP_CLIENT


def test_environment_bootstrap_writes_only_in_the_user_profile(packaged, monkeypatch):
    _, config = packaged
    monkeypatch.setenv("GOOGLE_CREDENTIALS_JSON", json.dumps(DESKTOP_CLIENT))
    monkeypatch.setenv("GOOGLE_TOKEN_JSON", '{"token":"own-environment-token"}')
    storage = drive_client.GoogleDriveStorage()
    assert storage.credentials_path == config / "credentials.json"
    assert json.loads(storage.credentials_path.read_text(encoding="utf8")) == DESKTOP_CLIENT
    assert json.loads(storage.token_path.read_text(encoding="utf8"))["token"] == "own-environment-token"


def test_web_client_is_rejected_in_packaged_configuration_without_exposing_its_values(packaged, monkeypatch):
    _, config = packaged
    monkeypatch.setenv("GOOGLE_CREDENTIALS_JSON", '{"web":{"client_id":"do-not-print"}}')
    with pytest.raises(ValueError) as error:
        drive_client.GoogleDriveStorage()
    assert "escritorio" in str(error.value).lower()
    assert "do-not-print" not in str(error.value)
    assert not (config / "credentials.json").exists()


def test_only_oauth_client_metadata_is_provisioned_from_the_environment(packaged, monkeypatch):
    payload = {"installed": {**DESKTOP_CLIENT["installed"], "refresh_token": "do-not-copy"}, "token": "do-not-copy"}
    monkeypatch.setenv("GOOGLE_CREDENTIALS_JSON", json.dumps(payload))
    storage = drive_client.GoogleDriveStorage()
    assert json.loads(storage.credentials_path.read_text(encoding="utf8")) == DESKTOP_CLIENT


def test_existing_user_oauth_configuration_is_validated_without_rewriting_it(packaged):
    _, config = packaged
    config.mkdir(parents=True)
    original = json.dumps(DESKTOP_CLIENT, indent=4)
    (config / "credentials.json").write_text(original, encoding="utf8")
    storage = drive_client.GoogleDriveStorage()
    assert storage.credentials_path.read_text(encoding="utf8") == original


def test_only_the_current_profiles_backup_can_restore_its_token(packaged):
    _, config = packaged
    config.mkdir(parents=True)
    (config / "token_backup.json").write_text('{"token":"own-backup"}', encoding="utf8")
    storage = drive_client.GoogleDriveStorage()
    assert storage.token_path == config / "token.json"
    assert json.loads(storage.token_path.read_text(encoding="utf8"))["token"] == "own-backup"


def test_explicit_constructor_paths_are_preserved(packaged, tmp_path):
    creds, token = tmp_path / "explicit-creds.json", tmp_path / "explicit-token.json"
    storage = drive_client.GoogleDriveStorage(credentials_path=str(creds), token_path=str(token))
    assert storage.credentials_path == creds
    assert storage.token_path == token
    assert not creds.exists() and not token.exists()


@pytest.mark.parametrize("operation", ["exchange", "restore", "disconnect"])
def test_packaged_token_operations_do_not_modify_a_global_container_token(packaged, tmp_path, monkeypatch, operation):
    _, config = packaged
    storage = drive_client.GoogleDriveStorage()
    container = tmp_path / "unrelated-container-token.json"
    container.write_text('{"token":"unrelated-owner"}', encoding="utf8")
    real_path = Path
    monkeypatch.setattr(drive_client, "Path", lambda value: container if str(value) == "/app/token.json" else real_path(value))
    monkeypatch.setattr(storage, "is_connected", lambda: True)
    if operation == "exchange":
        flow = Mock()
        flow.authorization_url.return_value = ("https://accounts.google.com/synthetic", "synthetic-state")
        flow.redirect_uri = "http://127.0.0.1:12345/callback"
        flow.credentials.to_json.return_value = '{"token":"own-new-token"}'
        monkeypatch.setattr(drive_client.InstalledAppFlow, "from_client_secrets_file", Mock(return_value=flow))
        storage.get_authorization_url(flow.redirect_uri)
        storage.exchange_code_for_token("synthetic-code", flow.redirect_uri, "synthetic-state")
    elif operation == "restore":
        assert storage.restore_from_client_token({"token": "own-new-token"})
    else:
        storage.token_path.parent.mkdir(parents=True, exist_ok=True)
        storage.token_path.write_text('{"token":"own-new-token"}', encoding="utf8")
        assert storage.disconnect()
        assert not storage.token_path.exists()
    assert json.loads(container.read_text(encoding="utf8"))["token"] == "unrelated-owner"
    if operation != "disconnect":
        assert storage.token_path == config / "token.json"
        assert json.loads(storage.token_path.read_text(encoding="utf8"))["token"] == "own-new-token"


def test_packaged_token_endpoint_does_not_fall_back_to_another_locations_token(packaged, tmp_path, monkeypatch):
    _, config = packaged
    container = tmp_path / "another-token.json"
    container.write_text('{"token":"unrelated-owner"}', encoding="utf8")
    storage = SimpleNamespace(token_path=config / "token.json", is_connected=lambda: False)
    monkeypatch.setattr(drive_router.server, "GoogleDriveStorage", lambda: storage)
    monkeypatch.setattr(drive_router, "Path", lambda value: container)
    result = asyncio.run(drive_router.get_drive_token_endpoint())
    assert result["status"] == "not_connected"
    assert result["token"] is None
