"""Server/storage path integration without using real profiles or campaigns."""
import asyncio
from pathlib import Path
import sys

import pytest

from src.api import server
from src.storage import campaign_manager


PATH_OVERRIDES = ("WHISPER_INPUT_DIR", "WHISPER_OUTPUT_DIR", "WHISPER_CAMPAIGNS_DIR")


def point_at_resources(monkeypatch, resources):
    monkeypatch.setattr(server, "project_root", resources)
    monkeypatch.setattr(campaign_manager, "__file__", str(resources / "src" / "storage" / "campaign_manager.py"))


@pytest.fixture
def packaged_profile(tmp_path, monkeypatch):
    resources = tmp_path / "Program Files" / "WhisperDnD" / "_internal"
    (resources / "data" / "campaigns").mkdir(parents=True)
    (resources / "outputs").mkdir()
    (resources / "static").mkdir()
    legacy = resources / "data" / "campaigns" / "old.json"
    legacy.write_text('{"campaign_name":"Legacy synthetic"}', encoding="utf8")
    (resources / "static" / "index.html").write_text("<h1>Synthetic resource</h1>", encoding="utf8")
    before = {p.relative_to(resources): p.read_bytes() for p in resources.rglob("*") if p.is_file()}
    local = tmp_path / "Usuarios" / "María" / "AppData" / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    for name in PATH_OVERRIDES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    point_at_resources(monkeypatch, resources)
    original_mkdir = Path.mkdir

    def writable_only_outside_resources(path, *args, **kwargs):
        assert not path.is_relative_to(resources), "attempted write in read-only program resources"
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", writable_only_outside_resources)
    yield resources, local / "WhisperDnD"
    assert {p.relative_to(resources): p.read_bytes() for p in resources.rglob("*") if p.is_file()} == before


def test_packaged_server_and_manager_agree_on_user_storage(packaged_profile, tmp_path, monkeypatch):
    resources, data = packaged_profile
    elsewhere = tmp_path / "another working directory"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert server.get_data_input_dir() == data / "recordings"
    assert server.get_data_output_dir() == data / "exports"
    assert server.get_data_campaigns_dir() == data / "campaigns"
    manager = campaign_manager.CampaignManager()
    assert manager.campaigns_dir == data / "campaigns"
    assert manager.output_dir == data / "exports"
    assert manager.list_campaigns() == [], "packaging must not auto-import legacy campaigns"
    assert (resources / "data" / "campaigns" / "old.json").is_file()


def test_packaged_campaign_save_uses_only_the_synthetic_user_profile(packaged_profile):
    resources, data = packaged_profile
    manager = campaign_manager.CampaignManager()
    state = manager.load_campaign("Mesa sintética")
    saved = manager.save_campaign(state)
    assert saved == data / "campaigns" / "mesa_sintética.json"
    assert saved.is_file()
    assert (data / "campaigns" / "mesa_sintética" / "campaign.json").is_file()
    assert manager.load_campaign("Mesa sintética")["campaign_name"] == "Mesa sintética"
    assert not (resources / "data" / "campaigns" / "mesa_sintética.json").exists()


def test_packaged_frontend_is_read_from_resources_not_the_user_profile(packaged_profile):
    _, data = packaged_profile
    response = asyncio.run(server.serve_index())
    assert response.body == b"<h1>Synthetic resource</h1>"
    assert not (data / "static").exists()


def test_existing_overrides_remain_authoritative_in_packaged_mode(packaged_profile, tmp_path, monkeypatch):
    paths = [tmp_path / name for name in ("test inputs", "test exports", "test campaigns")]
    for name, path in zip(PATH_OVERRIDES, paths):
        monkeypatch.setenv(name, str(path))
    assert [server.get_data_input_dir(), server.get_data_output_dir(), server.get_data_campaigns_dir()] == paths
    manager = campaign_manager.CampaignManager()
    assert manager.campaigns_dir == paths[2]
    assert manager.output_dir == paths[1]
    explicit = tmp_path / "constructor override"
    assert campaign_manager.CampaignManager(campaigns_dir=str(explicit)).campaigns_dir == explicit
    new_exports = tmp_path / "changed exports"
    monkeypatch.setenv("WHISPER_OUTPUT_DIR", str(new_exports))
    assert server.get_data_output_dir() == manager.output_dir == new_exports


@pytest.mark.parametrize("outputs_exist", [True, False])
def test_development_campaign_and_export_defaults_remain_unchanged(tmp_path, monkeypatch, outputs_exist):
    resources = tmp_path / "checkout"
    resources.mkdir()
    if outputs_exist:
        (resources / "outputs").mkdir()
    point_at_resources(monkeypatch, resources)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    for name in PATH_OVERRIDES:
        monkeypatch.delenv(name, raising=False)
    expected_output = resources / "outputs" if outputs_exist else resources / "data" / "output"
    manager = campaign_manager.CampaignManager()
    assert server.get_data_campaigns_dir() == manager.campaigns_dir == resources / "data" / "campaigns"
    assert server.get_data_output_dir() == manager.output_dir == expected_output


def test_development_windows_recording_default_is_preserved(tmp_path, monkeypatch):
    point_at_resources(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("WHISPER_INPUT_DIR", raising=False)
    assert server.get_data_input_dir() == tmp_path / "data" / "input"


def test_linux_development_keeps_the_existing_temporary_recording_directory(tmp_path, monkeypatch):
    point_at_resources(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("WHISPER_INPUT_DIR", raising=False)
    original_exists, original_isdir, original_mkdir = server.os.path.exists, server.os.path.isdir, Path.mkdir
    monkeypatch.setattr(server.os.path, "exists", lambda p: True if p == "/tmp" else original_exists(p))
    monkeypatch.setattr(server.os.path, "isdir", lambda p: True if p == "/tmp" else original_isdir(p))
    expected = Path("/tmp/whisper_input").resolve()

    def mkdir_without_touching_global_tmp(path, *args, **kwargs):
        if path != expected:
            return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", mkdir_without_touching_global_tmp)
    assert server.get_data_input_dir() == expected
