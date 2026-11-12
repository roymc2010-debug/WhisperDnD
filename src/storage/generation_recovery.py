"""Recover saved generation inputs without retranscribing audio or changing canon."""
import json
import re
import threading
from pathlib import Path
from contextlib import contextmanager

_LOCK = threading.RLock()
_RUNNING = set()
_INPUT_NAME = re.compile(r"[a-f0-9]{32}\.json")


class GenerationRecoveryConflict(ValueError):
    pass


@contextmanager
def active_input(job_id):
    """Do not offer recovery while the original local pipeline is still running."""
    with _LOCK:
        _RUNNING.add(job_id)
    try:
        yield
    finally:
        with _LOCK:
            _RUNNING.discard(job_id)


def input_path(output_dir, job_id):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise FileNotFoundError("Entrada no encontrada.")
    return Path(output_dir) / "generation-inputs" / (job_id + ".json")


def read_input(output_dir, job_id):
    data = json.loads(input_path(output_dir, job_id).read_text(encoding="utf8"))
    if not isinstance(data, dict) or not isinstance(data.get("raw_transcript"), str) or not data.get("campaign_name"):
        raise ValueError("La entrada guardada no tiene una transcripción de campaña válida.")
    return data


def _read(path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except json.JSONDecodeError:
        # An unfinished metadata write is an unknown outcome, never permission to resend.
        return default


def _write(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")
    temp.replace(path)


def _latest_attempt_path(output_dir, job_id):
    original = input_path(output_dir, job_id)
    children = [p for p in original.parent.glob("*.json")
                if _INPUT_NAME.fullmatch(p.name) and _read(p, {}).get("retry_of") == job_id]
    return max(children, key=lambda p: p.stat().st_mtime_ns) if children else original


def _review_for_input(output_dir, artifact):
    for path in (Path(output_dir) / "session-reviews").glob("*.json"):
        review = _read(path, {})
        metadata = review.get("chapter", {}).get("generation_metadata", {})
        if metadata.get("input_artifact") == artifact:
            return review.get("id")
    return None


def input_status(output_dir, job_id):
    data = read_input(output_dir, job_id)
    latest = _latest_attempt_path(output_dir, job_id)
    attempt_id = latest.stem
    attempts = _read(latest.with_name(attempt_id + "-attempts.json"), [])
    response = latest.with_name(attempt_id + "-response.json")
    recovered = _read(input_path(output_dir, job_id).with_name(job_id + "-recovery.json"), {})
    last = attempts[-1] if attempts else {}
    from src.summarizer.generation_diagnostics import public_generation_status
    generation = public_generation_status(_read(latest.with_name(attempt_id + "-diagnostics.json"), {}))
    review_id = recovered.get("review_id") or _review_for_input(output_dir, latest.name)
    with _LOCK:
        can_retry = job_id not in _RUNNING and attempt_id not in _RUNNING and (response.is_file() or last.get("status") == "failed")
    return {"generation": generation, "id": job_id, "campaign_name": data["campaign_name"], "session_number": data.get("session_number"),
            "transcript_characters": len(data["raw_transcript"]), "response_saved": response.is_file(),
            "model": last.get("model"), "error_type": last.get("error_type"), "seconds": last.get("seconds"),
            "can_retry": can_retry, "review_id": review_id, "retry_of": data.get("retry_of")}


def list_inputs(output_dir):
    result = []
    for path in (Path(output_dir) / "generation-inputs").glob("*.json"):
        if not _INPUT_NAME.fullmatch(path.name):
            continue
        data = _read(path, {})
        if not data or data.get("retry_of"):
            continue
        row = input_status(output_dir, path.stem)
        if not row["review_id"]:
            row.pop("retry_of", None)
            result.append(row)
    return result


def retry_input(output_dir, job_id, processor):
    path = input_path(output_dir, job_id)
    with _LOCK:
        saved = read_input(output_dir, job_id)
        status = input_status(output_dir, job_id)
        if status["review_id"]:
            return {"status": "review_ready", "review_id": status["review_id"]}
        if job_id in _RUNNING:
            raise GenerationRecoveryConflict("Ya se está generando la crónica de esta transcripción. Espera a que termine.")
        if not status["can_retry"]:
            raise GenerationRecoveryConflict("No se puede confirmar que el intento anterior haya terminado. Se conserva su entrada; no se duplicó la generación.")
        latest = _latest_attempt_path(output_dir, job_id)
        _RUNNING.add(job_id)
    try:
        response_path = latest.with_name(latest.stem + "-response.json")
        raw = response_path.read_text(encoding="utf8") if response_path.is_file() else None
        attempts = _read(latest.with_name(latest.stem + "-attempts.json"), [])
        result = processor(saved, raw, attempts)
        review_id = result.get("session_chapter", {}).get("review_id")
        if not review_id:
            raise ValueError("La recuperación no devolvió un borrador revisable.")
        with _LOCK:
            _write(path.with_name(job_id + "-recovery.json"), {"review_id": review_id})
        return {"status": "review_ready", "review_id": review_id, "reused_response": raw is not None}
    finally:
        with _LOCK:
            _RUNNING.discard(job_id)
