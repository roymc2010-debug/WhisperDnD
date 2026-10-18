"""YouTube audio downloader using yt-dlp."""

import os
import re
import threading
from pathlib import Path
from typing import Callable, Optional

_yt_download_lock = threading.Lock()


def extract_youtube_video_id(url: str) -> Optional[str]:
    """Extract YouTube 11-char video ID from various URL formats, including /live/, music.youtube, and reordered query params."""
    if not url or not isinstance(url, str):
        return None
    patterns = [
        r"[?&]v=([\w-]{11})",
        r"(?:embed/|v/|youtu\.be/|shorts/|live/)([\w-]{11})",
        r"^([\w-]{11})$",
    ]
    for pattern in patterns:
        m = re.search(pattern, url.strip())
        if m:
            return m.group(1)
    return None


def is_valid_youtube_url(url: str) -> bool:
    """Check if the provided string looks like a valid YouTube video URL or ID."""
    if not url or not isinstance(url, str):
        return False
    trimmed = url.strip()
    pattern = re.compile(
        r"^(https?://)?(www\.|m\.|music\.)?(youtube\.com/(watch\?.*?v=|embed/|v/|shorts/|live/)|youtu\.be/)[\w-]+",
        re.IGNORECASE,
    )
    if bool(pattern.search(trimmed)):
        return True
    return bool(re.match(r"^[\w-]{11}$", trimmed))


def download_youtube_audio(
    url: str,
    output_dir: str = "data/input",
    on_progress: Optional[Callable[[int, str], None]] = None,
) -> str:
    """
    Download audio from a YouTube URL and extract it as an MP3/M4A file.
    Reuses existing cached audio in output_dir if already downloaded.
    Thread-safe to prevent concurrent file-lock collisions.

    :param url: The YouTube video URL to download audio from.
    :param output_dir: Destination directory for the downloaded audio file.
    :param on_progress: Optional callback function receiving (percent: int, message: str).
    :return: Absolute file path of the downloaded audio.
    :raises ValueError: If the URL is invalid or the video is unavailable/private.
    :raises RuntimeError: If audio extraction or download fails.
    :raises ImportError: If yt-dlp is not installed.
    """
    if not is_valid_youtube_url(url):
        raise ValueError(
            f"Enlace de YouTube no reconocido o no soportado: '{url}'. "
            "Por favor proporciona un enlace válido de YouTube (ej: https://www.youtube.com/watch?v=... o https://youtu.be/...)."
        )

    dest_dir = Path(output_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fast cache check before acquiring lock or calling yt-dlp
    vid_id = extract_youtube_video_id(url)
    if vid_id:
        for ext in ["m4a", "webm", "opus", "mp3", "aac", "ogg"]:
            cand = dest_dir / f"{vid_id}.{ext}"
            if cand.is_file() and cand.stat().st_size > 10000:
                if on_progress:
                    on_progress(20, "Audio encontrado en caché local. Saltando descarga...")
                return str(cand.resolve())

    try:
        import yt_dlp
    except ImportError as exc:
        raise ImportError(
            "yt-dlp no está instalado en el servidor. "
            "Por favor instálalo ejecutando 'pip install yt-dlp'."
        ) from exc

    out_template = str(dest_dir / "%(id)s.%(ext)s")

    def ytdl_hook(d):
        if on_progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            downloaded = d.get("downloaded_bytes", 0)
            # Map 0.0% to 20.0% total progress (real progress by bytes)
            pct = round((downloaded / total) * 20.0, 1)
            pct_display = round((downloaded / total) * 100.0, 1)
            on_progress(pct, f"Descargando audio de YouTube... ({pct_display:.1f}%)")
        elif on_progress and d.get("status") == "finished":
            on_progress(20.0, "Descarga de YouTube completada (100.0%)")

    base_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": out_template,
        "restrictfilenames": True,  # Sanitizes filenames to ASCII safe chars
        "progress_hooks": [ytdl_hook],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
    }

    # Optional cookies support for cloud/Render deployments if provided
    cookies_env = os.environ.get("YOUTUBE_COOKIES_TXT", "").strip()
    cookies_file = dest_dir.parent / "cookies.txt"
    if cookies_env and not cookies_file.is_file():
        try:
            cookies_file.write_text(cookies_env, encoding="utf-8")
        except Exception:
            pass
    if cookies_file.is_file() and cookies_file.stat().st_size > 10:
        base_opts["cookiefile"] = str(cookies_file)

    strategies = [
        # Strategy 1: Native yt-dlp client negotiation without conflicting UA overrides
        {
            **base_opts,
            "extractor_args": {
                "youtube": {
                    "player_client": ["ios", "android", "mweb", "web"],
                }
            },
        },
        # Strategy 2: TV / Android VR embedded clients (often bypasses datacenter throttling)
        {
            **base_opts,
            "extractor_args": {
                "youtube": {
                    "player_client": ["tv", "android_vr", "ios", "mweb"],
                }
            },
        },
    ]

    def _resolve_downloaded_file(ydl, info) -> Optional[str]:
        if not info:
            return None
        # 1. Look for downloaded audio file in requested_downloads
        requested_downloads = info.get("requested_downloads")
        if requested_downloads and len(requested_downloads) > 0:
            final_path = requested_downloads[0].get("filepath")
            if final_path and Path(final_path).is_file():
                return str(Path(final_path).resolve())

        # 2. Check filename prepared by yt-dlp
        prepared = ydl.prepare_filename(info)
        if Path(prepared).is_file():
            return str(Path(prepared).resolve())

        # 3. Check for %(id)s.%(ext)s candidates
        extracted_id = info.get("id") or vid_id
        if extracted_id:
            for ext in ["m4a", "webm", "opus", "mp3", "aac", "ogg", "mp4"]:
                cand = dest_dir / f"{extracted_id}.{ext}"
                if cand.is_file():
                    return str(cand.resolve())

            for f in dest_dir.glob(f"*{extracted_id}*"):
                if f.is_file():
                    return str(f.resolve())

        # 4. Fallback: search in dest_dir for recent file matching title
        clean_title = re.sub(r"[^\w\-_\.]", "_", info.get("title", ""))
        for f in dest_dir.iterdir():
            if f.is_file() and ((clean_title and clean_title[:20] in f.name) or (extracted_id and extracted_id in f.name)):
                return str(f.resolve())
        return None

    try:
        with _yt_download_lock:
            # Re-check cache under lock in case another concurrent request just finished
            if vid_id:
                for ext in ["m4a", "webm", "opus", "mp3", "aac", "ogg"]:
                    cand = dest_dir / f"{vid_id}.{ext}"
                    if cand.is_file() and cand.stat().st_size > 10000:
                        if on_progress:
                            on_progress(20, "Audio descargado por proceso previo. Utilizando audio existente...")
                        return str(cand.resolve())

            last_dl_err = None
            for idx, ydl_opts in enumerate(strategies):
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        if not info:
                            raise RuntimeError("No se pudo extraer la información del enlace de YouTube.")

                        resolved_path = _resolve_downloaded_file(ydl, info)
                        if resolved_path:
                            return resolved_path

                        raise RuntimeError(
                            f"El archivo de audio se descargó pero no se pudo localizar en {dest_dir}."
                        )
                except yt_dlp.utils.DownloadError as dl_exc:
                    last_dl_err = dl_exc
                    err_str = str(dl_exc)
                    if "Video unavailable" in err_str or "Private video" in err_str:
                        raise
                    if idx + 1 < len(strategies):
                        continue
                    raise
            if last_dl_err:
                raise last_dl_err
            raise RuntimeError("No se pudo completar la descarga de YouTube.")

    except yt_dlp.utils.DownloadError as exc:
        err_msg = str(exc)
        if "Video unavailable" in err_msg or "Private video" in err_msg:
            raise ValueError(f"El video de YouTube no está disponible o es privado: {err_msg}") from exc
        if "Sign in to confirm you're not a bot" in err_msg or "bot" in err_msg.lower():
            raise RuntimeError(
                "YouTube ha solicitado verificación antibot para esta IP. "
                "Intenta nuevamente en unos minutos o descarga el audio manualmente y súbelo en la pestaña 'Archivo'."
            ) from exc
        if "ffprobe" in err_msg.lower() or "ffmpeg" in err_msg.lower():
            raise RuntimeError(
                "FFmpeg no está instalado o no se encuentra en el PATH del sistema. "
                "Descarga FFmpeg y añádelo al PATH de Windows para habilitar la extracción de audio."
            ) from exc
        raise RuntimeError(f"Error descargando audio de YouTube: {err_msg}") from exc
    except Exception as exc:
        if isinstance(exc, (ValueError, RuntimeError, ImportError)):
            raise
        raise RuntimeError(f"Error inesperado al descargar audio de YouTube: {exc}") from exc


def extract_youtube_captions_fallback(
    url: str,
    preferred_lang: Optional[str] = "es",
) -> Optional[dict]:
    """
    Fallback extractor that retrieves timestamped subtitles or automatic captions from YouTube
    without downloading the media stream (useful when cloud datacenter IPs block audio stream downloads).
    Returns a dict compatible with transcribe_audio_pipeline output if captions are found, else None.
    """
    try:
        import json as _json
        import urllib.request
        import yt_dlp
    except ImportError:
        return None

    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None

            subtitles = info.get("subtitles") or {}
            auto_captions = info.get("automatic_captions") or {}
            lang_Order = []
            if preferred_lang:
                lang_Order.extend([preferred_lang, f"{preferred_lang}-419", f"{preferred_lang}-ES", f"{preferred_lang}-MX"])
            lang_Order.extend(["es", "es-419", "es-ES", "en", "en-US"])

            chosen_tracks = None
            chosen_lang = preferred_lang or "es"

            for lang in lang_Order:
                if lang in subtitles and subtitles[lang]:
                    chosen_tracks = subtitles[lang]
                    chosen_lang = lang
                    break
            if not chosen_tracks:
                for lang in lang_Order:
                    if lang in auto_captions and auto_captions[lang]:
                        chosen_tracks = auto_captions[lang]
                        chosen_lang = lang
                        break
            if not chosen_tracks:
                # Pick first available subtitle or auto_caption language
                for lang, tracks in list(subtitles.items()) + list(auto_captions.items()):
                    if tracks:
                        chosen_tracks = tracks
                        chosen_lang = lang
                        break

            if not chosen_tracks:
                return None

            # Prefer json3 format for clean timestamped segments
            json3_url = None
            for track in chosen_tracks:
                if track.get("ext") == "json3" and track.get("url"):
                    json3_url = track["url"]
                    break

            if not json3_url:
                return None

            req = urllib.request.Request(
                json3_url,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw_data = _json.loads(resp.read().decode("utf-8", errors="replace"))

            events = raw_data.get("events") or []
            segments = []
            lines = []
            for ev in events:
                segs = ev.get("segs")
                if not segs:
                    continue
                text_piece = "".join(s.get("utf8", "") for s in segs).replace("\n", " ").strip()
                if not text_piece:
                    continue
                start_s = float(ev.get("tStartMs", 0)) / 1000.0
                dur_s = float(ev.get("dDurationMs", 2000)) / 1000.0
                end_s = start_s + dur_s
                mins = int(start_s // 60)
                secs = int(start_s % 60)
                segments.append({
                    "start": round(start_s, 2),
                    "end": round(end_s, 2),
                    "text": text_piece,
                })
                lines.append(f"[{mins:02d}:{secs:02d}] {text_piece}")

            if not lines:
                return None

            full_text = " ".join(s["text"] for s in segments)
            formatted_text = "\n".join(lines)
            return {
                "text": full_text,
                "formatted_transcript": formatted_text,
                "segments": segments,
                "language": {"code": chosen_lang[:2], "probability": 1.0},
                "language_code": chosen_lang[:2],
                "title": info.get("title") or "Video de YouTube",
            }
    except Exception as exc:
        print(f"[extract_youtube_captions_fallback] Fallback caption extraction failed: {exc}")
        return None

