"""Resolve desktop paths without creating directories, importing data or changing env.

The API directory providers and campaign manager use this contract. Development
keeps its checkout layout; a packaged Windows runtime uses per-user storage.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Mapping, Optional


def is_desktop_runtime(environ: Optional[Mapping[str, str]] = None) -> bool:
    """The manual pre-EXE entry uses the same paths without pretending to be frozen."""
    environment = os.environ if environ is None else environ
    return bool(getattr(sys, "frozen", False)) or environment.get("WHISPER_DESKTOP_MODE") == "1"


@dataclass(frozen=True)
class RuntimePaths:
    resource_dir: Path
    data_dir: Path
    input_dir: Path
    output_dir: Path
    campaigns_dir: Path
    quota_dir: Path
    models_dir: Path
    logs_dir: Path
    config_dir: Path


def resolve_runtime_paths(
    *,
    resource_dir: Optional[Path] = None,
    installed: Optional[bool] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> RuntimePaths:
    """Select paths for the current Windows distribution or development checkout.

    Explicit existing WHISPER_* directory overrides win in either mode. Missing
    LOCALAPPDATA in installed mode is an error: program resources must never be
    used silently as a writable fallback. Callers own initialization and errors.
    """
    environment = os.environ if environ is None else environ
    packaged = is_desktop_runtime(environment) if installed is None else installed
    resources = Path(resource_dir).resolve() if resource_dir is not None else Path(__file__).resolve().parent.parent

    if packaged:
        custom_root = environment.get("WHISPER_DESKTOP_DATA_ROOT", "").strip()
        profile = environment.get("LOCALAPPDATA", "").strip()
        if custom_root:
            if not Path(custom_root).is_absolute():
                raise ValueError("WHISPER_DESKTOP_DATA_ROOT debe indicar una carpeta absoluta.")
            data = Path(custom_root).resolve()
        elif not profile or not Path(profile).is_absolute():
            raise ValueError("LOCALAPPDATA debe indicar una carpeta absoluta de datos del usuario.")
        else:
            data = Path(profile).resolve() / "WhisperDnD"
        inputs = data / "recordings"
        outputs = data / "exports"
        quota = data / "quota"
        logs = data / "logs"
        config = data / "config"
        models = data / "models"
    else:
        data = resources / "data"
        inputs = data / "input"
        outputs = resources / "outputs" if (resources / "outputs").is_dir() else data / "output"
        quota = data
        logs = resources / "outputs"
        config = resources
        models = resources / "models"

    def override(name: str, default: Path) -> Path:
        value = environment.get(name)
        return Path(value).resolve() if value else default

    return RuntimePaths(
        resource_dir=resources,
        data_dir=data,
        input_dir=override("WHISPER_INPUT_DIR", inputs),
        output_dir=override("WHISPER_OUTPUT_DIR", outputs),
        campaigns_dir=override("WHISPER_CAMPAIGNS_DIR", data / "campaigns"),
        quota_dir=override("WHISPER_QUOTA_DIR", quota),
        models_dir=override("WHISPER_DOWNLOAD_ROOT", models),
        logs_dir=logs,
        config_dir=config,
    )
