"""
System API Quota and Token Usage Tracker.
Tracks daily token consumption for Gemini and audio duration seconds for Groq Whisper.
Provides percentage remaining and safety thresholds to prevent half-completed sessions.
"""

import json
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


def get_quota_status() -> Dict[str, Any]:
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
        "requests_today": int(data.get("requests_today", 0)),
        "date": data.get("date", _get_current_quota_date()),
        "can_process_safe": can_process,
        "warning": is_warning,
        "danger": is_danger,
        "last_updated": data.get("last_updated"),
    }
