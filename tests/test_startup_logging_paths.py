"""Execute startup logging with synthetic resources and no server/browser launch."""
import importlib
import json
import logging
import os
from pathlib import Path
import runpy
import subprocess
import sys
import warnings
from unittest.mock import Mock

import dotenv
import pytest


PROJECT = Path(__file__).resolve().parent.parent


@pytest.fixture
def startup_copy(tmp_path, monkeypatch):
    root = tmp_path / "Program Files" / "WhisperDnD"
    root.mkdir(parents=True)
    entry = root / "main.py"
    entry.write_bytes((PROJECT / "main.py").read_bytes())
    python = root / ".venv" / "Scripts" / "pythonw.exe"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"synthetic executable, never run")
    python.with_name("python.exe").write_bytes(b"synthetic executable, never run")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Usuarios" / "María" / "Local"))
    monkeypatch.setenv("SHOW_CONSOLE", "1")
    monkeypatch.setenv("WHISPER_REEXEC", "1")
    monkeypatch.delenv("GOOGLE_CREDENTIALS_JSON", raising=False)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **kw: False)
    # This entry is evaluated without __main__, so uvicorn/main() cannot run.
    return root, entry, tmp_path / "Usuarios" / "María" / "Local" / "WhisperDnD"


def run_startup(entry, monkeypatch, inspect, *, silent=False):
    logger = logging.getLogger()
    handlers, level = list(logger.handlers), logger.level
    original_streams = (sys.stdout, sys.stderr)
    was_capturing = logging._warnings_showwarning is not None
    scope = None
    with monkeypatch.context() as state:
        state.setattr(sys, "path", list(sys.path))
        state.setattr(sys, "excepthook", sys.excepthook)
        state.setattr(warnings, "filters", list(warnings.filters))
        if silent:
            state.setattr(sys, "stdout", None)
            state.setattr(sys, "stderr", None)
        try:
            scope = runpy.run_path(str(entry), run_name="startup_logging_fixture")
            inspect(scope)
        finally:
            for handler in list(logger.handlers):
                if handler not in handlers:
                    logger.removeHandler(handler)
                    handler.close()
            if scope is not None:
                scope["file_handler"].close()
            for stream in (sys.stdout, sys.stderr):
                if stream is not None and stream not in original_streams:
                    stream.close()
            logger.setLevel(level)
            if not was_capturing:
                logging.captureWarnings(False)


def reject_resource_directories(root, monkeypatch):
    mkdir = Path.mkdir

    def outside_only(path, *args, **kwargs):
        assert not path.is_relative_to(root), "startup attempted to write inside program resources"
        return mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", outside_only)


def test_main_development_retains_outputs_log(startup_copy, monkeypatch):
    root, entry, _ = startup_copy
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    def inspect(scope):
        assert scope["log_file"] == root / "outputs" / "server.log"
        handler = scope["file_handler"]
        handler.emit(logging.LogRecord("synthetic", logging.INFO, "fixture", 1, "synthetic startup", (), None))
        handler.flush()
        assert "synthetic startup" in (root / "outputs" / "server.log").read_text(encoding="utf8")

    run_startup(entry, monkeypatch, inspect)


@pytest.mark.parametrize("silent", [False, True])
def test_packaged_main_logs_and_silent_streams_use_the_user_profile(startup_copy, monkeypatch, silent):
    root, entry, profile = startup_copy
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    reject_resource_directories(root, monkeypatch)

    def inspect(scope):
        expected = profile / "logs" / "server.log"
        assert scope["log_file"] == expected
        handler = scope["file_handler"]
        handler.emit(logging.LogRecord("synthetic", logging.INFO, "fixture", 1, "profile log", (), None))
        handler.flush()
        assert "profile log" in expected.read_text(encoding="utf8")
        if silent:
            assert Path(sys.stdout.name) == Path(sys.stderr.name) == expected
        assert not (root / "outputs").exists()

    run_startup(entry, monkeypatch, inspect, silent=silent)


def test_packaged_main_never_reexecutes_a_development_venv(startup_copy, monkeypatch):
    root, entry, _ = startup_copy
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("WHISPER_REEXEC", raising=False)
    reexec = Mock(side_effect=AssertionError("must not execute the synthetic interpreter"))
    monkeypatch.setattr(subprocess, "call", reexec)
    reject_resource_directories(root, monkeypatch)
    run_startup(entry, monkeypatch, lambda scope: None)
    reexec.assert_not_called()


def test_missing_packaged_profile_never_falls_back_to_program_logs(startup_copy, monkeypatch):
    root, entry, _ = startup_copy
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("LOCALAPPDATA")
    reject_resource_directories(root, monkeypatch)
    with pytest.raises(ValueError, match="LOCALAPPDATA"):
        run_startup(entry, monkeypatch, lambda scope: None)


def test_packaged_main_bootstraps_oauth_configuration_only_in_the_user_profile(startup_copy, monkeypatch):
    root, entry, profile = startup_copy
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    client = {"installed": {"client_id": "synthetic", "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token"}}
    monkeypatch.setenv("GOOGLE_CREDENTIALS_JSON", json.dumps(client))
    reject_resource_directories(root, monkeypatch)

    def inspect(scope):
        assert Path(scope["credentials_path"]) == profile / "config" / "credentials.json"
        assert json.loads(Path(scope["credentials_path"]).read_text(encoding="utf8")) == client
        assert not (root / "credentials.json").exists()

    run_startup(entry, monkeypatch, inspect)


def test_invalid_optional_drive_configuration_does_not_abort_packaged_startup(startup_copy, monkeypatch):
    root, entry, profile = startup_copy
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("GOOGLE_CREDENTIALS_JSON", '{"web":{"client_id":"do-not-print"}}')
    reject_resource_directories(root, monkeypatch)

    def inspect(scope):
        assert Path(scope["credentials_path"]) == profile / "config" / "credentials.json"
        assert not Path(scope["credentials_path"]).exists()
        assert not (root / "credentials.json").exists()

    run_startup(entry, monkeypatch, inspect)


@pytest.mark.parametrize("ready", [True, False])
def test_launcher_uses_the_same_packaged_log_and_reports_its_path(startup_copy, monkeypatch, ready):
    root, _, profile = startup_copy
    mod = importlib.import_module("scripts.launch_desktop")
    monkeypatch.setattr(mod, "ROOT", root)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    reject_resource_directories(root, monkeypatch)
    monkeypatch.setattr(mod, "is_server_ready", lambda *a, **kw: False)
    monkeypatch.setattr(mod, "wait_for_server", lambda *a, **kw: ready)
    window = Mock()
    monkeypatch.setattr(mod, "open_app_window", window)
    captured = []

    def spawn(args, **kwargs):
        captured.append(Path(kwargs["stdout"].name))
        assert kwargs["stderr"] is kwargs["stdout"]
        assert kwargs["env"]["NO_BROWSER"] == "1"
        return Mock(poll=lambda: None)

    monkeypatch.setattr(mod.subprocess, "Popen", spawn)
    if ready:
        mod.launch()
        window.assert_called_once_with("http://localhost:8080")
    else:
        with pytest.raises(RuntimeError) as error:
            mod.launch()
        assert str(profile / "logs" / "server.log") in str(error.value)
        window.assert_not_called()
    assert captured == [profile / "logs" / "server.log"]
    assert not (root / "outputs").exists()


def test_launcher_script_can_find_its_internal_module_from_another_working_directory(startup_copy, tmp_path):
    root, _, _ = startup_copy
    (root / "scripts").mkdir()
    (root / "src").mkdir()
    script = root / "scripts" / "launch_desktop.py"
    script.write_bytes((PROJECT / "scripts" / "launch_desktop.py").read_bytes())
    (root / "src" / "__init__.py").write_text("", encoding="utf8")
    (root / "src" / "runtime_paths.py").write_bytes((PROJECT / "src" / "runtime_paths.py").read_bytes())
    elsewhere = tmp_path / "unrelated working directory"
    elsewhere.mkdir()
    # Only this short-lived test interpreter runs. Its server and browser are doubles.
    code = """
import runpy, sys
from types import SimpleNamespace
scope = runpy.run_path(sys.argv[1], run_name='standalone_launcher_fixture')
globals_ = scope['launch'].__globals__
globals_['is_server_ready'] = lambda *a, **kw: False
globals_['wait_for_server'] = lambda *a, **kw: True
globals_['open_app_window'] = lambda url: None
def spawn(args, **kwargs):
    print(kwargs['stdout'].name)
    return SimpleNamespace(poll=lambda: None)
globals_['subprocess'].Popen = spawn
scope['launch']()
"""
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run([sys.executable, "-c", code, str(script)], cwd=elsewhere,
                            env=environment, capture_output=True, text=True, encoding="utf8",
                            timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == root / "outputs" / "server.log"
