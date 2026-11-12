"""Capture identity and dates, independent of filesystem modification times."""
import datetime as dt
import json
import re
import threading
import uuid
from pathlib import Path

_naming_lock = threading.Lock()


def get_recorded_at(audio_path):
    path = Path(audio_path)
    try:
        value = json.loads(path.with_suffix(".recording.json").read_text(encoding="utf-8"))["recorded_at"]
        return dt.datetime.fromisoformat(value).isoformat()
    except (OSError, ValueError, KeyError, TypeError):
        pass
    match = re.fullmatch(r"(?:session|lecture)_(\d{8}_\d{6})", path.stem)
    if match:
        try:
            return dt.datetime.strptime(match[1], "%Y%m%d_%H%M%S").isoformat()
        except ValueError:
            pass
    return None


def create_recording_path(folder, campaign_name, session_number, recorded_at, mirror_folder=None, audio_suffix=".wav"):
    """Reserve a new WAV exclusively; promote only recordings owned by this scheme.

    Renames include matching sidecars and verified mirrors. If an I/O operation fails,
    restore previous names/metadata. No historical/unmanaged recording is renamed.
    """
    if not isinstance(session_number, int) or session_number < 1:
        raise ValueError("Selecciona un número de sesión positivo antes de grabar.")
    clean = re.sub(r'[\\/*?:"<>|\x00-\x1f]', "", campaign_name.strip())
    clean = re.sub(r"\s+", "_", clean).strip(". ")[:100] or "Campana"
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    base = f"{clean}_Sesion_{session_number:02d}_{recorded_at:%d-%m-%y}"
    with _naming_lock:
        previous = []
        for sidecar in folder.glob("*.recording.json"):
            try:
                meta = json.loads(sidecar.read_text(encoding="utf-8"))
                audio_name = meta.get("audio_file") or sidecar.name.removesuffix(".recording.json") + ".wav"
                audio = sidecar.with_name(Path(audio_name).name)
                if (meta.get("schema_version") == 1 and meta.get("campaign_name") == campaign_name
                        and meta.get("session_number") == session_number and audio.is_file()):
                    previous.append((audio, meta))
            except (OSError, ValueError, TypeError):
                continue
        index = max((m.get("part_index", 1) for _, m in previous), default=0) + 1
        target = folder / (base + (f"_Parte_{index:02d}" if index > 1 else "") + audio_suffix)
        promotions = []
        for audio, meta in previous:
            if meta.get("part_index") == 1 and not audio.stem.endswith("_Parte_01"):
                promotions.append((audio, audio.with_stem(audio.stem + "_Parte_01"), meta))
                if mirror_folder:
                    mirror = Path(mirror_folder) / audio.name
                    try:
                        mirrored = json.loads(mirror.with_suffix(".recording.json").read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        mirrored = {}
                    if mirror != audio and mirror.exists():
                        if mirrored.get("recording_id") != meta.get("recording_id"):
                            raise FileExistsError(f"La copia de {audio.name} tiene otra identidad; no se renombró.")
                        promotions.append((mirror, mirror.with_stem(mirror.stem + "_Parte_01"), mirrored))
        moves = []
        for old, new, meta in promotions:
            for suffix in (old.suffix, ".timeline.json", ".recording.json"):
                src, dst = old.with_suffix(suffix), new.with_suffix(suffix)
                if dst.exists():
                    raise FileExistsError(f"Ya existe {dst.name}; no se sobrescribirá.")
                if src.exists():
                    moves.append((src, dst))
        reserved = False
        moved, changed = [], []
        try:
            with target.open("xb"):
                pass
            reserved = True
            for src, dst in moves:
                src.rename(dst)
                moved.append((src, dst))
            for old, new, meta in promotions:
                for suffix in (".timeline.json", ".recording.json"):
                    p = new.with_suffix(suffix)
                    if p.is_file():
                        original = p.read_bytes()
                        data = json.loads(original)
                        data["audio_file"] = new.name
                        changed.append((p, original))
                        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            metadata = {"schema_version": 1, "recording_id": uuid.uuid4().hex,
                        "audio_file": target.name, "campaign_name": campaign_name,
                        "session_number": session_number, "part_index": index,
                        "recorded_at": recorded_at.isoformat()}
            with target.with_suffix(".recording.json").open("x", encoding="utf-8") as out:
                json.dump(metadata, out, ensure_ascii=False, indent=2)
            return target
        except Exception:
            for p, original in reversed(changed):
                p.write_bytes(original)
            for src, dst in reversed(moved):
                dst.rename(src)
            if reserved:
                target.unlink()
            raise


def combine_transcriptions(results):
    """Join ordered results without another ASR engine or an in-memory audio merge."""
    from .groq_whisper import _format_hhmmss
    offset, segments, lines, texts = 0.0, [], [], []
    for part, result in enumerate(results, 1):
        duration = float(result.get("duration") or 0)
        if duration <= 0:
            raise ValueError(f"No se pudo determinar la duración de la parte {part}.")
        text = (result.get("formatted_transcript") or result.get("text") or "").strip()
        texts.append(result.get("text") or "")
        part_lines = []
        for raw in result.get("segments", []):
            seg = dict(raw, start=float(raw["start"]) + offset, end=float(raw["end"]) + offset, part_index=part)
            # Keep the original speaker label, but rebuild absolute timestamps.
            original = raw.get("formatted_line", "")
            body = re.sub(r"^\[[^\]]*\]\s*", "", original) if original else raw.get("text", "")
            if not original and raw.get("speaker"):
                body = f"{raw['speaker']}: {body}"
            seg["formatted_line"] = f"[{_format_hhmmss(seg['start'])} -> {_format_hhmmss(seg['end'])}] {body}"
            segments.append(seg)
            part_lines.append(seg["formatted_line"])
        lines.append(f"--- Parte {part} ---\n" + ("\n".join(part_lines) if part_lines else text))
        offset += duration
    return dict(results[0], text="\n".join(texts), formatted_transcript="\n\n".join(lines), segments=segments, duration=round(offset, 2))
