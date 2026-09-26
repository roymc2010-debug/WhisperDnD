"""YouTube audio downloader using yt-dlp."""

import os
import re
from pathlib import Path
from typing import Callable, Optional


def is_valid_youtube_url(url: str) -> bool:
    """Check if the provided string looks like a valid YouTube video URL."""
    if not url or not isinstance(url, str):
        return False
    trimmed = url.strip()
    youtube_pattern = re.compile(
        r"^(https?://)?(www\.|m\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w-]+",
        re.IGNORECASE,
    )
    return bool(youtube_pattern.search(trimmed))


def download_youtube_audio(
    url: str,
    output_dir: str = "data/input",
    on_progress: Optional[Callable[[int, str], None]] = None,
) -> str:
    """
    Download audio from a YouTube URL and extract it as an MP3 file.

    :param url: The YouTube video URL to download audio from.
    :param output_dir: Destination directory for the downloaded audio file.
    :param on_progress: Optional callback function receiving (percent: int, message: str).
    :return: Absolute file path of the downloaded MP3.
    :raises ValueError: If the URL is invalid or the video is unavailable/private.
    :raises RuntimeError: If audio extraction or download fails.
    :raises ImportError: If yt-dlp is not installed.
    """
    if not is_valid_youtube_url(url):
        raise ValueError(f"Invalid or unsupported YouTube URL: '{url}'. Please provide a valid YouTube link.")

    try:
        import yt_dlp
    except ImportError as exc:
        raise ImportError(
            "yt-dlp is required to download YouTube audio. "
            "Please install it using 'pip install yt-dlp'."
        ) from exc

    dest_dir = Path(output_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    out_template = str(dest_dir / "%(id)s.%(ext)s")

    def ytdl_hook(d):
        if on_progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            downloaded = d.get("downloaded_bytes", 0)
            # Map 0.0% to 20.0% total progress
            pct = round((downloaded / total) * 20.0, 1)
            pct_display = round((downloaded / total) * 100.0, 1)
            on_progress(pct, f"Descargando audio de YouTube... ({pct_display:.1f}%)")
        elif on_progress and d.get("status") == "finished":
            on_progress(20.0, "Descargando audio de YouTube... (100.0%)")

    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": out_template,
        "restrictfilenames": True,  # Sanitizes filenames to ASCII safe chars
        "progress_hooks": [ytdl_hook],
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError("Failed to extract information from YouTube URL.")

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
            vid_id = info.get("id")
            if vid_id:
                for ext in ["m4a", "webm", "opus", "mp3", "aac", "ogg"]:
                    cand = dest_dir / f"{vid_id}.{ext}"
                    if cand.is_file():
                        return str(cand.resolve())

                for f in dest_dir.glob(f"*{vid_id}*"):
                    if f.is_file():
                        return str(f.resolve())

            # 4. Fallback: search in dest_dir for recent file matching title
            clean_title = re.sub(r"[^\w\-_\.]", "_", info.get("title", ""))
            for f in dest_dir.iterdir():
                if f.is_file() and (clean_title[:20] in f.name or (vid_id and vid_id in f.name)):
                    return str(f.resolve())

            raise RuntimeError(
                f"Audio file was downloaded but could not be located in {dest_dir}."
            )

    except yt_dlp.utils.DownloadError as exc:
        err_msg = str(exc)
        if "Video unavailable" in err_msg or "Private video" in err_msg:
            raise ValueError(f"The YouTube video is unavailable or private: {err_msg}") from exc
        raise RuntimeError(f"Download failed: {err_msg}") from exc
    except Exception as exc:
        if isinstance(exc, (ValueError, RuntimeError, ImportError)):
            raise
        raise RuntimeError(f"Unexpected error while downloading YouTube audio: {exc}") from exc
