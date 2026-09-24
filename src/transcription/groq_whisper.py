"""Groq Whisper Cloud transcription module for ultra-fast audio transcription with native FFmpeg stream segmentation."""

import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def slice_audio_for_groq(input_audio_path: str, chunk_minutes: int = 15) -> List[str]:
    """
    Fast, stream-based audio segmentation using direct FFmpeg CLI.
    Never loads large audio files into Python memory.
    Preserves original native extension (.m4a, .webm, .mp3) using direct packet stream-copy ('-c copy')
    for instant slicing in ~1.5s with zero CPU re-encoding overhead.
    Falls back to '-c:a libmp3lame -b:a 64k' only if stream copy fails or for raw audio formats.
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    input_dir = Path(os.environ.get("WHISPER_INPUT_DIR", project_root / "data" / "input"))
    chunks_dir = input_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    # Clean any leftover chunks from previous runs
    for f in chunks_dir.glob("chunk_*"):
        try:
            f.unlink()
        except Exception:
            pass

    input_path = Path(input_audio_path)
    ext = input_path.suffix.lower() or ".mp3"
    segment_seconds = chunk_minutes * 60

    # Direct packet copy preserving native extension (.m4a, .webm, .mp3, etc.)
    output_pattern = str(chunks_dir / f"chunk_%03d{ext}").replace("\\", "/")
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-f", "segment", "-segment_time", str(segment_seconds),
        "-c", "copy",  # Direct packet copy (takes 1.5 seconds)
        output_pattern
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        chunk_files = sorted([str(p) for p in chunks_dir.glob(f"chunk_*{ext}")])
        if chunk_files:
            return chunk_files
    except Exception:
        # Fallback to re-encoding if stream copy fails
        pass

    # Fallback re-encode for WAV or non-streamable files
    fallback_pattern = str(chunks_dir / "chunk_%03d.mp3").replace("\\", "/")
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-f", "segment",
        "-segment_time", str(segment_seconds),
        "-c:a", "libmp3lame", "-b:a", "64k",
        fallback_pattern
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    chunk_files = sorted([str(p) for p in chunks_dir.glob("chunk_*.mp3")])
    return chunk_files


def clean_groq_chunks() -> None:
    """Delete temporary chunk files in data/input/chunks to keep disk clean."""
    project_root = Path(__file__).resolve().parent.parent.parent
    input_dir = Path(os.environ.get("WHISPER_INPUT_DIR", project_root / "data" / "input"))
    chunks_dir = input_dir / "chunks"
    if chunks_dir.exists():
        for f in chunks_dir.glob("chunk_*"):
            try:
                f.unlink()
            except Exception:
                pass


def _format_hhmmss(seconds: float) -> str:
    """Format floating point seconds into [HH:MM:SS]."""
    s = max(0, int(round(seconds)))
    hrs = s // 3600
    mins = (s % 3600) // 60
    secs = s % 60
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"


def tag_dual_channel_speakers(
    audio_path: str,
    segments: List[Dict[str, Any]],
    user_char_name: Optional[str] = None,
    speaking_log: Optional[List[Dict[str, Any]]] = None,
    roster: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Compare RMS volume between Channel 1 (Left = Mic) and Channel 2 (Right = Discord)
    for each segment timestamp slice [start, end].
    Tags segments with:
      - '[Tu / {user_char_name}]' (or '[Tu]') when mic_rms > (discord_rms * 1.5).
      - '[{character_name} ({player_name})]' when discord speaking user_id matches linked roster player.
      - '[{discord_user}]' when discord speaking event matches interval but is unlinked.
      - '[Discord]' otherwise.
    For single-channel mono audio, formats lines cleanly without speaker tags:
      - '[HH:MM:SS -> HH:MM:SS] Text...'
    Adds 'speaker', 'mic_rms', 'discord_rms', and 'formatted_line' to each segment dictionary.
    """
    p = Path(audio_path)
    if not p.is_file() or not segments:
        return segments

    try:
        from src.transcription.discord_rpc import DiscordRpcTracker
    except ImportError:
        try:
            from .discord_rpc import DiscordRpcTracker
        except ImportError:
            DiscordRpcTracker = None

    # Build mapping from discord_user_id to official roster label
    discord_id_to_speaker: Dict[str, str] = {}
    if roster and isinstance(roster, list):
        for item in roster:
            if isinstance(item, dict):
                uid = str(item.get("discord_user_id") or "").strip()
                if uid:
                    c_name = str(item.get("character_name") or item.get("personaje") or "").strip()
                    p_name = str(item.get("player_name") or item.get("jugador") or "").strip()
                    r_name = str(item.get("role") or "").strip()
                    if c_name in ("(DM)", "DM") or r_name == "Dungeon Master (DM)":
                        label = f"DM ({p_name})" if p_name else "DM"
                    elif c_name and c_name not in ("-", "(DM)", "DM") and p_name:
                        label = f"{c_name} ({p_name})"
                    elif c_name and c_name not in ("-", "(DM)", "DM"):
                        label = c_name
                    elif p_name:
                        label = p_name
                    else:
                        label = None
                    if label:
                        discord_id_to_speaker[uid] = label

    try:
        import soundfile as sf
        import numpy as np

        with sf.SoundFile(str(p)) as sf_file:
            if sf_file.channels < 2:
                # Single-channel mono audio (e.g. university lecture or single-channel): format without speaker tags
                for seg in segments:
                    start_sec = max(0.0, float(seg.get("start", 0.0)))
                    end_sec = max(start_sec, float(seg.get("end", start_sec)))
                    start_ts = _format_hhmmss(start_sec)
                    end_ts = _format_hhmmss(end_sec)
                    text_clean = str(seg.get("text", "")).strip()
                    seg["formatted_line"] = f"[{start_ts} -> {end_ts}] {text_clean}"
                return segments

            sr = sf_file.samplerate
            total_frames = len(sf_file)

            for seg in segments:
                start_sec = max(0.0, float(seg.get("start", 0.0)))
                end_sec = max(start_sec, float(seg.get("end", start_sec)))

                start_frame = int(start_sec * sr)
                end_frame = min(total_frames, int(end_sec * sr))
                n_frames = max(1, end_frame - start_frame)

                if start_frame < total_frames:
                    sf_file.seek(start_frame)
                    audio_slice = sf_file.read(frames=n_frames)
                    if len(audio_slice) > 0 and audio_slice.ndim == 2 and audio_slice.shape[1] >= 2:
                        mic_rms = float(np.sqrt(np.mean(audio_slice[:, 0] ** 2)))
                        discord_rms = float(np.sqrt(np.mean(audio_slice[:, 1] ** 2)))
                    else:
                        mic_rms = 0.0
                        discord_rms = 0.0
                else:
                    mic_rms = 0.0
                    discord_rms = 0.0

                if mic_rms > (discord_rms * 1.5):
                    char_name_clean = user_char_name.strip() if user_char_name else ""
                    speaker_tag = f"[Tu / {char_name_clean}]" if char_name_clean else "[Tu]"
                else:
                    matched_uid = None
                    matched_user = None
                    if DiscordRpcTracker:
                        if hasattr(DiscordRpcTracker, "match_user_id_in_interval"):
                            matched_uid = DiscordRpcTracker.match_user_id_in_interval(start_sec, end_sec, speaking_log)
                        matched_user = DiscordRpcTracker.match_speaker_in_interval(start_sec, end_sec, speaking_log)

                    if matched_uid and matched_uid in discord_id_to_speaker:
                        speaker_tag = f"[{discord_id_to_speaker[matched_uid]}]"
                    elif matched_user:
                        speaker_tag = f"[{matched_user}]"
                    else:
                        speaker_tag = "[Discord]"

                seg["speaker"] = speaker_tag
                seg["mic_rms"] = round(mic_rms, 5)
                seg["discord_rms"] = round(discord_rms, 5)

                start_ts = _format_hhmmss(start_sec)
                end_ts = _format_hhmmss(end_sec)
                text_clean = str(seg.get("text", "")).strip()
                seg["formatted_line"] = f"[{start_ts} -> {end_ts}] {speaker_tag}: {text_clean}"
    except Exception as exc:
        print(f"[!] Warning: Dual-channel speaker tagging skipped: {exc}")

    return segments


class GroqWhisperTranscriber:
    """
    Ultra-fast audio transcription engine using Groq Cloud API (whisper-large-v3).
    Supports automatic stream-based audio chunking using FFmpeg for files exceeding the 25 MB limit.
    """

    MAX_FILE_SIZE_BYTES = 24 * 1024 * 1024  # 24 MB safe threshold (Groq limit is 25 MB)
    DEFAULT_CHUNK_MINUTES = 15

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "whisper-large-v3",
    ):
        """
        Initialize GroqWhisperTranscriber.

        :param api_key: Optional Groq API key. Defaults to GROQ_API_KEY env var.
        :param model: Whisper model to use ('whisper-large-v3' or 'whisper-large-v3-turbo').
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "").strip()
        self.model = model
        self._client = None

    @property
    def client(self):
        """Lazily initialize the Groq client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "GROQ_API_KEY no está configurada. "
                    "Por favor añade tu clave de API en el archivo .env."
                )
            try:
                import groq
            except ImportError as exc:
                raise ImportError(
                    "groq no está instalado. Ejecuta 'pip install groq'."
                ) from exc
            self._client = groq.Client(api_key=self.api_key)
        return self._client

    def transcribe(
        self,
        audio_path: str,
        language: str = "es",
        on_progress: Optional[Callable[[int, str], None]] = None,
        source: str = "local",
        user_char_name: Optional[str] = None,
        speaking_log: Optional[List[Dict[str, Any]]] = None,
        roster: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Transcribe audio file using Groq Whisper Cloud API.
        If file exceeds 24 MB, automatically slices into 15-minute chunks with FFmpeg and transcribes sequentially.
        If file is a dual-channel recording (Left=Mic, Right=Discord), tags segments by comparing channel RMS energy.

        :param audio_path: Path to the audio file (.wav, .mp3, .m4a, etc.).
        :param language: Language code (ISO-639-1, default 'es').
        :param on_progress: Optional callback function receiving (percent: int, message: str).
        :param source: Source type ('youtube', 'local', or 'live').
        :param user_char_name: Optional user player character name for transcript tagging.
        :param speaking_log: Optional Discord speaking timeline events for cross-referencing.
        :param roster: Optional campaign roster for Discord User ID speaker mapping.
        :return: Dict containing segments, text, language, and duration.
        """
        path = Path(audio_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Archivo de audio no encontrado: {path}")

        file_size = path.stat().st_size
        if file_size <= self.MAX_FILE_SIZE_BYTES:
            min_pct = 35 if source == "youtube" else 0
            max_pct = 80 if source == "youtube" else 75
            if on_progress:
                on_progress(min_pct, "Enviando audio a Groq Cloud (whisper-large-v3)...")
            res = self._transcribe_single_file(str(path), language=language)
            if on_progress:
                on_progress(max_pct, f"Transcripción de Groq completada ({max_pct}%).")
        else:
            # File is > 24 MB: slice using fast FFmpeg CLI
            res = self._transcribe_chunked(
                str(path),
                language=language,
                on_progress=on_progress,
                source=source,
            )

        # Automatic speaker channel tagging for 2-channel audio (Left=Mic, Right=Discord)
        if res.get("segments"):
            res["segments"] = tag_dual_channel_speakers(
                str(path),
                res["segments"],
                user_char_name=user_char_name,
                speaking_log=speaking_log,
                roster=roster,
            )
            formatted_lines = [
                s.get(
                    "formatted_line",
                    f"[{_format_hhmmss(s['start'])} -> {_format_hhmmss(s['end'])}] {s.get('text', '').strip()}"
                )
                for s in res["segments"]
            ]
            formatted_text = "\n".join(formatted_lines)
            res["raw_text"] = res.get("text", "")
            res["formatted_transcript"] = formatted_text

        return res

    def _transcribe_single_file(
        self,
        file_path: str,
        language: str = "es",
        time_offset: float = 0.0,
    ) -> Dict[str, Any]:
        """Send a single audio file to Groq Whisper API and parse verbose_json response."""
        p = Path(file_path)
        with open(p, "rb") as f:
            response = self.client.audio.transcriptions.create(
                model=self.model,
                file=f,
                language=language,
                response_format="verbose_json",
            )

        return self._parse_groq_response(response, time_offset=time_offset)

    def _parse_groq_response(self, response: Any, time_offset: float = 0.0) -> Dict[str, Any]:
        """Parse Groq transcription response object or dict."""
        raw_text = getattr(response, "text", "") or ""
        raw_segments = (
            getattr(response, "segments", None)
            or (response.model_extra.get("segments") if hasattr(response, "model_extra") and response.model_extra else None)
            or (response.get("segments") if isinstance(response, dict) else [])
            or []
        )
        detected_lang = (
            getattr(response, "language", None)
            or (response.model_extra.get("language") if hasattr(response, "model_extra") and response.model_extra else "es")
            or (response.get("language") if isinstance(response, dict) else "es")
            or "es"
        )
        lang_str = str(detected_lang).strip().lower()
        lang_map = {
            "spanish": "es",
            "español": "es",
            "english": "en",
            "french": "fr",
            "german": "de",
            "italian": "it",
            "portuguese": "pt",
        }
        detected_lang = lang_map.get(lang_str, lang_str[:2] if len(lang_str) >= 2 else "es")
        duration = (
            getattr(response, "duration", None)
            or (response.model_extra.get("duration") if hasattr(response, "model_extra") and response.model_extra else 0.0)
            or (response.get("duration") if isinstance(response, dict) else 0.0)
            or 0.0
        )

        segments = []
        for s in raw_segments:
            s_start = s.get("start", 0.0) if isinstance(s, dict) else getattr(s, "start", 0.0)
            s_end = s.get("end", 0.0) if isinstance(s, dict) else getattr(s, "end", 0.0)
            s_text = s.get("text", "") if isinstance(s, dict) else getattr(s, "text", "")
            segments.append({
                "start": round(float(s_start) + time_offset, 2),
                "end": round(float(s_end) + time_offset, 2),
                "text": s_text.strip(),
            })

        if not segments and raw_text:
            segments.append({
                "start": round(time_offset, 2),
                "end": round(time_offset + float(duration), 2),
                "text": raw_text.strip(),
            })

        return {
            "segments": segments,
            "text": raw_text.strip(),
            "language": {
                "code": detected_lang,
                "probability": 1.0,
            },
            "language_code": detected_lang,
            "language_probability": 1.0,
            "duration": round(float(duration), 2),
        }

    def _slice_audio(
        self,
        audio_path: str,
        chunk_minutes: int = 15,
    ) -> List[Any]:
        """Wrapper method for fast FFmpeg slicing."""
        return slice_audio_for_groq(audio_path, chunk_minutes=chunk_minutes)

    def _transcribe_chunked(
        self,
        audio_path: str,
        language: str = "es",
        on_progress: Optional[Callable[[int, str], None]] = None,
        source: str = "local",
    ) -> Dict[str, Any]:
        """
        Slice audio file into 15-minute chunks with FFmpeg and transcribe each sequentially.
        """
        # Progress range calibration
        # If source is YouTube: maps from 35% to 80%
        # If source is Local / Live Discord: maps from 0% to 75%
        if source == "youtube":
            min_pct = 35
            max_pct = 80
        else:
            min_pct = 0
            max_pct = 75

        if on_progress:
            on_progress(
                min_pct,
                f"Archivo extenso detectado (>24 MB). Dividiendo en fragmentos de {self.DEFAULT_CHUNK_MINUTES} minutos con FFmpeg...",
            )

        chunks_list = self._slice_audio(audio_path, chunk_minutes=self.DEFAULT_CHUNK_MINUTES)
        num_chunks = len(chunks_list)

        if num_chunks == 0:
            raise RuntimeError(f"FFmpeg no generó fragmentos de audio para: {audio_path}")

        all_segments: List[Dict[str, Any]] = []
        text_parts: List[str] = []
        total_duration = 0.0
        current_time_offset = 0.0
        detected_lang = language

        try:
            for idx, chunk_item in enumerate(chunks_list):
                chunk_path = chunk_item[0] if isinstance(chunk_item, (tuple, list)) else chunk_item

                # Transcribe chunk using Groq Whisper
                chunk_res = self._transcribe_single_file(
                    chunk_path,
                    language=language,
                    time_offset=current_time_offset,
                )

                all_segments.extend(chunk_res.get("segments", []))
                if chunk_res.get("text"):
                    text_parts.append(chunk_res["text"])
                if chunk_res.get("language_code"):
                    detected_lang = chunk_res["language_code"]

                # Duration adjustment
                chunk_dur = chunk_res.get("duration", 0.0)
                if isinstance(chunk_item, (tuple, list)) and len(chunk_item) >= 3:
                    chunk_dur = chunk_item[2]

                current_time_offset += chunk_dur
                total_duration += chunk_dur

                # Update progress after completed chunk
                chunk_pct = min_pct + int(((idx + 1) / max(1, num_chunks)) * (max_pct - min_pct))
                if on_progress:
                    on_progress(
                        chunk_pct,
                        f"Transcribiendo fragmento {idx + 1} de {num_chunks} con Groq (Large-v3)...",
                    )
        finally:
            # Chunk Cleanup: Immediately after all chunks are transcribed, delete the chunks directory contents
            clean_groq_chunks()

        return {
            "segments": all_segments,
            "text": " ".join(text_parts).strip(),
            "language": {
                "code": detected_lang,
                "probability": 1.0,
            },
            "language_code": detected_lang,
            "language_probability": 1.0,
            "duration": round(total_duration, 2),
        }
