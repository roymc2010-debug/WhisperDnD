"""
System API Quota and Token Usage Tracker.
Tracks daily token consumption for Gemini and audio duration seconds for Groq Whisper.
Provides percentage remaining and safety thresholds to prevent half-completed sessions.
"""

import json
import math
import time
from contextlib import contextmanager
import os
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional


_LOCK = threading.Lock()
_LEDGER_FILENAME = "system_quota.json"

DEFAULT_GEMINI_DAILY_TOKEN_LIMIT = int(os.getenv("GEMINI_DAILY_TOKEN_LIMIT", "1000000"))
DEFAULT_GROQ_DAILY_SECONDS_LIMIT = float(os.getenv("GROQ_DAILY_SECONDS_LIMIT", "86400.0"))  # 24 hours


def _get_current_quota_date() -> str:
    """Return current date in UTC to align with Google Gemini and Groq API 00:00 UTC quota resets."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _get_seconds_until_utc_midnight() -> tuple[int, str]:
    """Calculate remaining seconds and human string until next 00:00 UTC quota rollover."""
    now_utc = datetime.now(timezone.utc)
    next_midnight = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    diff = max(0, int((next_midnight - now_utc).total_seconds()))
    hours = diff // 3600
    mins = (diff % 3600) // 60
    return diff, f"{hours}h {mins}m"


def _get_ledger_path() -> Path:
    project_root = Path(__file__).resolve().parent.parent.parent
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / _LEDGER_FILENAME


def _load_ledger() -> Dict[str, Any]:
    path = _get_ledger_path()
    today_str = _get_current_quota_date()
    default_data = {
        "date": today_str,
        "gemini_tokens_used": 0,
        "gemini_daily_limit": DEFAULT_GEMINI_DAILY_TOKEN_LIMIT,
        "groq_seconds_used": 0.0,
        "groq_daily_limit": DEFAULT_GROQ_DAILY_SECONDS_LIMIT,
        "requests_today": 0,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    if not path.is_file():
        return default_data

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default_data

        # Daily rollover check (automatically resets at 00:00 UTC when API providers replenish)
        if data.get("date") != today_str:
            data["date"] = today_str
            data["gemini_tokens_used"] = 0
            data["groq_seconds_used"] = 0.0
            data["requests_today"] = 0
            data["last_updated"] = datetime.now(timezone.utc).isoformat()
            # Preserve or update configured limits
            data["gemini_daily_limit"] = int(os.getenv("GEMINI_DAILY_TOKEN_LIMIT", str(data.get("gemini_daily_limit", DEFAULT_GEMINI_DAILY_TOKEN_LIMIT))))
            data["groq_daily_limit"] = float(os.getenv("GROQ_DAILY_SECONDS_LIMIT", str(data.get("groq_daily_limit", DEFAULT_GROQ_DAILY_SECONDS_LIMIT))))
            _save_ledger(data)

        return data
    except Exception as exc:
        print(f"[QuotaTracker] Error reading ledger: {exc}")
        return default_data


def _save_ledger(data: Dict[str, Any]) -> None:
    path = _get_ledger_path()
    try:
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(path)
    except Exception as exc:
        print(f"[QuotaTracker] Error writing ledger: {exc}")


def record_gemini_tokens(tokens: Any) -> None:
    """Record consumed Gemini tokens."""
    try:
        t_int = int(tokens)
    except (ValueError, TypeError):
        return
    if t_int <= 0:
        return
    with _LOCK:
        data = _load_ledger()
        data["gemini_tokens_used"] = int(data.get("gemini_tokens_used", 0)) + t_int
        data["requests_today"] = int(data.get("requests_today", 0)) + 1
        data["last_updated"] = datetime.now().isoformat()
        _save_ledger(data)


def record_groq_audio_seconds(seconds: Any) -> None:
    """Record processed Groq Whisper audio duration in seconds."""
    try:
        s_float = float(seconds)
    except (ValueError, TypeError):
        return
    if s_float <= 0:
        return
    with _LOCK:
        data = _load_ledger()
        data["groq_seconds_used"] = round(float(data.get("groq_seconds_used", 0.0)) + s_float, 2)
        data["requests_today"] = int(data.get("requests_today", 0)) + 1
        data["last_updated"] = datetime.now().isoformat()
        _save_ledger(data)


def record_audio_sample(
    duration_seconds: Any, tokens_used: Any, *, source: str = "unknown",
    workspace: str = "unknown", document_format: Optional[str] = None,
    status: str = "completed", usage_estimated: bool = False, generation_seconds: float = 0,
) -> None:
    """Store bounded local usage metadata; never audio, text, URLs, keys or error messages."""
    if not isinstance(duration_seconds, (int, float)) or not isinstance(tokens_used, (int, float)):
        return
    if isinstance(duration_seconds, bool) or isinstance(tokens_used, bool):
        return
    duration, tokens = float(duration_seconds), float(tokens_used)
    if not math.isfinite(duration) or not math.isfinite(tokens) or duration <= 0 or tokens < 0:
        return
    source = source if source in {"recording", "youtube", "file"} else "unknown"
    workspace = workspace if workspace in {"dnd", "work_and_study"} else "unknown"
    document_format = document_format if workspace == "work_and_study" and document_format in {"academic", "executive"} else None
    elapsed = generation_seconds if isinstance(generation_seconds, (int, float)) and math.isfinite(generation_seconds) and generation_seconds >= 0 else 0
    sample = {
        "duration_seconds": duration, "tokens_used": tokens, "source": source,
        "workspace": workspace, "document_format": document_format,
        "status": "failed" if status == "failed" else "completed",
        "usage_estimated": bool(usage_estimated), "generation_seconds": round(elapsed, 3),
        "timestamp": datetime.now(timezone.utc).isoformat(), "stage": "generation",
    }
    with _LOCK:
        data = _load_ledger()
        samples = data.get("audio_samples", [])
        if not isinstance(samples, list):
            samples = []
        data["audio_samples"] = (samples + [sample])[-500:]
        _save_ledger(data)


@contextmanager
def track_audio_processing(summarizer: Any, duration_seconds: Any, **profile):
    """Observe generation without changing its return value or swallowing failures."""
    def count():
        value = getattr(summarizer, "_quota_tokens_used", 0)
        return value if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 else 0
    before, started, status = count(), time.perf_counter(), "failed"
    try:
        yield
        status = "completed"
    finally:
        try:
            used = max(0, count() - before)
            record_audio_sample(
                duration_seconds, used, **profile, status=status,
                usage_estimated=status != "completed" or used <= 0 or getattr(summarizer, "_quota_usage_estimated", True) is not False,
                generation_seconds=time.perf_counter() - started,
            )
        except Exception:
            # Collection must never turn a successful document into an error.
            print("[QuotaTracker] Could not record local processing metadata.")


def get_processing_usage() -> Dict[str, Any]:
    """Read local history and aggregates; only explicit metadata fields are returned."""
    with _LOCK:
        data = _load_ledger()
    allowed = {"duration_seconds", "tokens_used", "source", "workspace", "document_format", "status", "usage_estimated", "generation_seconds", "timestamp", "stage"}
    stored = data.get("audio_samples", [])
    if not isinstance(stored, list):
        stored = []
    rows = [{key: value for key, value in row.items() if key in allowed}
            for row in stored if isinstance(row, dict)]
    groups = {}
    for row in rows:
        key = (row.get("source", "unknown"), row.get("workspace", "unknown"), row.get("document_format"))
        group = groups.setdefault(key, {"source": key[0], "workspace": key[1], "document_format": key[2], "completed": 0, "failed": 0, "tokens_used": 0, "audio_seconds_observed": 0})
        group["failed" if row.get("status") == "failed" else "completed"] += 1
        for field, target in (("tokens_used", "tokens_used"), ("duration_seconds", "audio_seconds_observed")):
            value = row.get(field, 0)
            if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0:
                group[target] += value
    return {"storage": "local", "records": len(rows), "retention_limit": 500, "groups": list(groups.values()), "recent": rows[-50:]}


def _audio_capacity(data: Dict[str, Any], tokens_remaining: int, percent_remaining: float, audio_remaining: float, source: Optional[str] = None, workspace: Optional[str] = None, document_format: Optional[str] = None) -> Dict[str, Any]:
    rates = []
    samples = data.get("audio_samples", [])
    for sample in samples if isinstance(samples, list) else []:
        if not isinstance(sample, dict):
            continue
        if sample.get("status", "completed") != "completed" or sample.get("usage_estimated") is True:
            continue
        if source and sample.get("source") != source:
            continue
        if workspace and sample.get("workspace") != workspace:
            continue
        if document_format and sample.get("document_format") != document_format:
            continue
        try:
            duration, tokens = float(sample["duration_seconds"]), float(sample["tokens_used"])
            if math.isfinite(duration) and math.isfinite(tokens) and duration >= 60 and tokens > 0:
                rate = tokens / duration
                if math.isfinite(rate) and rate > 0:
                    rates.append(rate)
        except (KeyError, TypeError, ValueError):
            continue
    rates = rates[-20:]
    result = {"seconds": None, "safety_margin_percent": 5, "samples": len(rates)}
    if percent_remaining > 20:
        return result
    if tokens_remaining <= 0 or audio_remaining <= 0:
        result["seconds"] = 0
    elif len(rates) >= 3:
        # Use the most expensive recent sample, respect both stages, then discount 5%.
        result["seconds"] = math.floor(min(tokens_remaining / max(rates), audio_remaining) * 0.95)
    return result


def get_quota_status(source: Optional[str] = None, workspace: Optional[str] = None, document_format: Optional[str] = None) -> Dict[str, Any]:
    """Calculate and return full API token and quota status with percentages."""
    with _LOCK:
        data = _load_ledger()

    gemini_used = int(data.get("gemini_tokens_used", 0))
    gemini_limit = int(data.get("gemini_daily_limit", DEFAULT_GEMINI_DAILY_TOKEN_LIMIT))
    gemini_rem = max(0, gemini_limit - gemini_used)
    gemini_pct_used = max(0.0, min(100.0, (gemini_used / gemini_limit) * 100.0)) if gemini_limit > 0 else 0.0
    gemini_pct_rem = max(0.0, min(100.0, (gemini_rem / gemini_limit) * 100.0)) if gemini_limit > 0 else 100.0

    groq_used = float(data.get("groq_seconds_used", 0.0))
    groq_limit = float(data.get("groq_daily_limit", DEFAULT_GROQ_DAILY_SECONDS_LIMIT))
    groq_rem = max(0.0, groq_limit - groq_used)
    groq_pct_used = max(0.0, min(100.0, (groq_used / groq_limit) * 100.0)) if groq_limit > 0 else 0.0
    groq_pct_rem = max(0.0, min(100.0, (groq_rem / groq_limit) * 100.0)) if groq_limit > 0 else 100.0

    # Danger/Critical alarm is ONLY active when tokens used exceeds 95% of the daily limit
    is_danger = bool(gemini_limit > 0 and gemini_pct_used >= 95.0)
    is_warning = bool(gemini_limit > 0 and gemini_pct_used >= 80.0)
    can_process = bool(not is_danger)

    _, resets_in_str = _get_seconds_until_utc_midnight()

    return {
        "percent_used": round(gemini_pct_used, 1),
        "percent_remaining": round(gemini_pct_rem, 1),
        "resets_in": resets_in_str,
        "resets_at_utc": "00:00 UTC",
        "gemini": {
            "tokens_used": gemini_used,
            "tokens_limit": gemini_limit,
            "tokens_remaining": gemini_rem,
            "percent_used": round(gemini_pct_used, 1),
            "percent_remaining": round(gemini_pct_rem, 1),
        },
        "groq": {
            "seconds_used": round(groq_used, 1),
            "seconds_limit": round(groq_limit, 1),
            "seconds_remaining": round(groq_rem, 1),
            "percent_used": round(groq_pct_used, 1),
            "percent_remaining": round(groq_pct_rem, 1),
        },
        "audio_capacity": _audio_capacity(data, gemini_rem, gemini_pct_rem, groq_rem, source, workspace, document_format),
        "requests_today": int(data.get("requests_today", 0)),
        "date": data.get("date", _get_current_quota_date()),
        "can_process_safe": can_process,
        "warning": is_warning,
        "danger": is_danger,
        "last_updated": data.get("last_updated"),
    }
