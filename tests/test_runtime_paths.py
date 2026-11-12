"""Path contracts for future desktop packaging, using synthetic directories only."""
import sys

import pytest

from src.runtime_paths import resolve_runtime_paths


def test_development_retains_checkout_layout_and_existing_outputs(tmp_path):
    checkout = tmp_path / "WhisperDnD"
    (checkout / "outputs").mkdir(parents=True)
    paths = resolve_runtime_paths(resource_dir=checkout, installed=False, environ={})
    assert paths.campaigns_dir == checkout / "data" / "campaigns"
    assert paths.input_dir == checkout / "data" / "input"
    assert paths.output_dir == checkout / "outputs"
    assert paths.quota_dir == checkout / "data"
    assert paths.logs_dir == checkout / "outputs"


def test_development_without_outputs_uses_legacy_data_output(tmp_path):
    checkout = tmp_path / "checkout"
    paths = resolve_runtime_paths(resource_dir=checkout, installed=False, environ={})
    assert paths.output_dir == checkout / "data" / "output"
    assert not checkout.exists(), "resolving paths must not initialize or migrate data"


def test_installed_paths_keep_mutable_data_outside_program_resources(tmp_path):
    resources = tmp_path / "Program Files" / "WhisperDnD" / "_internal"
    profile = tmp_path / "Usuarios" / "María" / "AppData" / "Local"
    paths = resolve_runtime_paths(resource_dir=resources, installed=True,
                                  environ={"LOCALAPPDATA": str(profile)})
    assert paths.resource_dir == resources
    assert paths.data_dir == profile / "WhisperDnD"
    for field, folder in [("input_dir", "recordings"), ("campaigns_dir", "campaigns"),
                          ("output_dir", "exports"), ("quota_dir", "quota"),
                          ("models_dir", "models"), ("logs_dir", "logs"), ("config_dir", "config")]:
        actual = getattr(paths, field)
        assert actual == profile / "WhisperDnD" / folder
        assert not actual.is_relative_to(resources)
        assert not actual.exists()


@pytest.mark.parametrize("installed", [False, True])
def test_explicit_existing_overrides_take_precedence(tmp_path, installed):
    overrides = {
        "WHISPER_INPUT_DIR": str(tmp_path / "capture"),
        "WHISPER_OUTPUT_DIR": str(tmp_path / "exports"),
        "WHISPER_CAMPAIGNS_DIR": str(tmp_path / "campaigns"),
        "WHISPER_QUOTA_DIR": str(tmp_path / "ledger"),
        "WHISPER_DOWNLOAD_ROOT": str(tmp_path / "model-cache"),
        "LOCALAPPDATA": str(tmp_path / "profile"),
    }
    original = dict(overrides)
    paths = resolve_runtime_paths(resource_dir=tmp_path / "app", installed=installed, environ=overrides)
    assert [paths.input_dir, paths.output_dir, paths.campaigns_dir, paths.quota_dir, paths.models_dir] == [
        tmp_path / "capture", tmp_path / "exports", tmp_path / "campaigns", tmp_path / "ledger", tmp_path / "model-cache"]
    assert overrides == original


def test_user_profiles_do_not_share_config_or_campaigns(tmp_path):
    first = resolve_runtime_paths(resource_dir=tmp_path / "app", installed=True,
                                  environ={"LOCALAPPDATA": str(tmp_path / "first")})
    second = resolve_runtime_paths(resource_dir=tmp_path / "app", installed=True,
                                   environ={"LOCALAPPDATA": str(tmp_path / "second")})
    assert first.config_dir != second.config_dir
    assert first.campaigns_dir != second.campaigns_dir
    assert first.resource_dir == second.resource_dir


def test_installed_defaults_do_not_depend_on_working_directory(tmp_path, monkeypatch):
    resources = tmp_path / "app"
    environment = {"LOCALAPPDATA": str(tmp_path / "profile")}
    first = resolve_runtime_paths(resource_dir=resources, installed=True, environ=environment)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert resolve_runtime_paths(resource_dir=resources, installed=True, environ=environment) == first


def test_missing_installed_profile_never_falls_back_to_program_folder(tmp_path):
    with pytest.raises(ValueError, match="LOCALAPPDATA"):
        resolve_runtime_paths(resource_dir=tmp_path / "app", installed=True, environ={})


def test_frozen_runtime_discovers_resources_and_uses_user_data(tmp_path, monkeypatch):
    import src.runtime_paths as runtime_paths
    resources = tmp_path / "package" / "_internal"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime_paths, "__file__", str(resources / "src" / "runtime_paths.py"))
    paths = resolve_runtime_paths(environ={"LOCALAPPDATA": str(tmp_path / "profile")})
    assert paths.resource_dir == resources
    assert paths.campaigns_dir == tmp_path / "profile" / "WhisperDnD" / "campaigns"


def test_resolving_does_not_import_existing_campaign_or_create_config(tmp_path):
    resources = tmp_path / "app"
    legacy = resources / "data" / "campaigns"
    legacy.mkdir(parents=True)
    original = legacy / "synthetic.json"
    original.write_text('{"campaign_name": "Synthetic"}', encoding="utf8")
    paths = resolve_runtime_paths(resource_dir=resources, installed=True,
                                  environ={"LOCALAPPDATA": str(tmp_path / "profile")})
    assert original.read_text(encoding="utf8") == '{"campaign_name": "Synthetic"}'
    assert not paths.data_dir.exists()
    assert not paths.config_dir.exists()
