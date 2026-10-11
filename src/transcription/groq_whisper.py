"""Groq Whisper Cloud transcription module for ultra-fast audio transcription with native FFmpeg stream segmentation."""

import os
import re
import sys
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
    env_input = os.environ.get("WHISPER_INPUT_DIR")
    if env_input:
        input_dir = Path(env_input).resolve()
    elif os.path.exists("/tmp") and os.path.isdir("/tmp") and sys.platform != "win32":
        input_dir = Path("/tmp/whisper_input").resolve()
    else:
        project_root = Path(__file__).resolve().parent.parent.parent
        input_dir = (project_root / "data" / "input").resolve()
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

    # For compressed streamable files (not raw uncompressed WAV), try instant packet copy first
    if ext in (".mp3", ".m4a", ".aac", ".webm", ".ogg"):
        output_pattern = str(chunks_dir / f"chunk_%03d{ext}").replace("\\", "/")
        cmd = [
            "ffmpeg", "-y", "-threads", "0", "-i", str(input_path),
            "-f", "segment", "-segment_time", str(segment_seconds),
            "-c", "copy",
            output_pattern
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            chunk_files = sorted([str(p) for p in chunks_dir.glob(f"chunk_*{ext}")])
            if chunk_files and all(Path(p).stat().st_size <= 24 * 1024 * 1024 for p in chunk_files):
                return chunk_files
        except Exception:
            pass

    # For WAV or any audio whose chunks would exceed 24 MB, encode to compact MP3 at 64k
    # 15 minutes of speech at 64kbps = ~7 MB, well below Groq's 25 MB hard limit
    fallback_pattern = str(chunks_dir / "chunk_%03d.mp3").replace("\\", "/")
    cmd = [
        "ffmpeg", "-y", "-threads", "0", "-i", str(input_path),
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
    env_input = os.environ.get("WHISPER_INPUT_DIR")
    if env_input:
        input_dir = Path(env_input).resolve()
    elif os.path.exists("/tmp") and os.path.isdir("/tmp") and sys.platform != "win32":
        input_dir = Path("/tmp/whisper_input").resolve()
    else:
        project_root = Path(__file__).resolve().parent.parent.parent
        input_dir = (project_root / "data" / "input").resolve()
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


def clean_whisper_hallucinations(text: str) -> str:
    """
    Remove repetitive artifact hallucination patterns from Whisper output,
    such as edition tags (5e, 6e, 7e, 5e., 6e-, etc.), leading edition prefixes,
    and repetitive stutter loops (e.g. 'o o o o', 'la la la la').
    """
    if not text:
        return ""
    # Strip edition artifacts like "5e", "6e", "7e", "6e-", "7e-", "5e.", "5e,"
    cleaned = re.sub(r'(?i)(?:^|(?<=[\s.,;:!?¿¡]))[5-9]e[-.:,]?(?=[\s.,;:!?¿¡]|$)', '', text)
    cleaned = re.sub(r'^\s*(?:[5-9]e[-.:,]?\s*)+', '', cleaned, flags=re.IGNORECASE)
    # Clean repetitive single letters or short syllables (e.g., 'o o o o', 'ah ah ah ah')
    cleaned = re.sub(r'(?i)\b([a-zñáéíóú])(?:\s+\1\b){3,}', '', cleaned)
    cleaned = re.sub(r'(?i)\b([a-zñáéíóú]{1,3})(?:\s+\1\b){4,}', '', cleaned)
    # Clean empty punctuation pairs left behind by hallucinations like "¿?" or "¡!"
    cleaned = re.sub(r'¿\s*\?', '', cleaned)
    cleaned = re.sub(r'¡\s*!', '', cleaned)
    cleaned = re.sub(r'([?¡!])\s*\.', r'\1', cleaned)
    cleaned = re.sub(r'\s+([.,;:!?])', r'\1', cleaned)
    cleaned = re.sub(r'^\s*[-.,;:!?]+\s*', '', cleaned)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
    return cleaned


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
                    text_clean = clean_whisper_hallucinations(str(seg.get("text", "")).strip())
                    seg["text"] = text_clean
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
                text_clean = clean_whisper_hallucinations(str(seg.get("text", "")).strip())
                seg["text"] = text_clean
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
        language: Optional[str] = None,
        on_progress: Optional[Callable[[int, str], None]] = None,
        source: str = "local",
        user_char_name: Optional[str] = None,
        speaking_log: Optional[List[Dict[str, Any]]] = None,
        roster: Optional[List[Dict[str, Any]]] = None,
        prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Transcribe audio file using Groq Whisper Cloud API.
        If file exceeds 24 MB, automatically slices into 15-minute chunks with FFmpeg and transcribes sequentially.
        If file is a dual-channel recording (Left=Mic, Right=Discord), tags segments by comparing channel RMS energy.

        :param audio_path: Path to the audio file (.wav, .mp3, .m4a, etc.).
        :param language: Optional language code (default None = auto-detect spoken language).
        :param on_progress: Optional callback function receiving (percent: int, message: str).
        :param source: Source type ('youtube', 'local', or 'live').
        :param user_char_name: Optional user player character name for transcript tagging.
        :param speaking_log: Optional Discord speaking timeline events for cross-referencing.
        :param roster: Optional campaign roster for Discord User ID speaker mapping.
        :param prompt: Optional vocabulary / glossary prompt to bias Whisper phonetic decoding.
        :return: Dict containing segments, text, language, and duration.
        """
        path = Path(audio_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Archivo de audio no encontrado: {path}")

        effective_lang = language if (language and str(language).strip().lower() != "auto") else None

        file_size = path.stat().st_size
        if file_size <= self.MAX_FILE_SIZE_BYTES:
            min_pct = 30.0
            max_pct = 80.0
            single_kwargs = {"language": effective_lang, "timeout": 60.0}
            if prompt is not None:
                single_kwargs["prompt"] = prompt
            res = self._transcribe_single_file(str(path), **single_kwargs)
            if on_progress:
                on_progress(max_pct, "Transcribiendo audio (Fragmento 1 de 1 - 80.0%)")
        else:
            # File is > 24 MB: slice using fast FFmpeg CLI
            res = self._transcribe_chunked(
                str(path),
                language=effective_lang,
                on_progress=on_progress,
                source=source,
                prompt=prompt,
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
            res["text"] = clean_whisper_hallucinations(res.get("text", "")).strip()
            res["raw_text"] = res["text"]
            res["formatted_transcript"] = formatted_text

        return res

    def _transcribe_single_file(
        self,
        file_path: str,
        language: Optional[str] = None,
        time_offset: float = 0.0,
        timeout: float = 60.0,
        prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a single audio file to Groq Whisper API and parse verbose_json response."""
        p = Path(file_path)
        with open(p, "rb") as f:
            kwargs = {
                "model": self.model,
                "file": f,
                "response_format": "verbose_json",
                "timeout": timeout,
            }
            if language and str(language).strip().lower() != "auto":
                kwargs["language"] = str(language).strip()
            if prompt:
                kwargs["prompt"] = prompt
            response = self.client.audio.transcriptions.create(**kwargs)

        return self._parse_groq_response(response, time_offset=time_offset)

    def _parse_groq_response(self, response: Any, time_offset: float = 0.0) -> Dict[str, Any]:
        """Parse Groq transcription response object or dict with robust hallucination filtering."""
        raw_text = clean_whisper_hallucinations(getattr(response, "text", "") or "")
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
        last_clean_text = ""
        for s in raw_segments:
            s_start = s.get("start", 0.0) if isinstance(s, dict) else getattr(s, "start", 0.0)
            s_end = s.get("end", 0.0) if isinstance(s, dict) else getattr(s, "end", 0.0)
            s_text = s.get("text", "") if isinstance(s, dict) else getattr(s, "text", "")
            s_no_speech = s.get("no_speech_prob", 0.0) if isinstance(s, dict) else getattr(s, "no_speech_prob", 0.0)
            s_avg_logprob = s.get("avg_logprob", 0.0) if isinstance(s, dict) else getattr(s, "avg_logprob", 0.0)
            s_compression = s.get("compression_ratio", 1.0) if isinstance(s, dict) else getattr(s, "compression_ratio", 1.0)

            # 1. Skip high probability non-speech / silence
            if s_no_speech and float(s_no_speech) > 0.8 and float(s_avg_logprob) < -0.8:
                continue

            # 2. Skip extreme repetitive loops (high compression ratio)
            if s_compression and float(s_compression) > 2.4:
                continue

            s_text_clean = clean_whisper_hallucinations(s_text.strip())
            if not s_text_clean or len(s_text_clean) < 2:
                continue

            # 3. Discard consecutive duplicate loops (e.g. repeated "o", "gracias", etc.)
            if s_text_clean.lower() == last_clean_text.lower():
                continue

            # 4. If detected language is Latin-based, discard completely out-of-alphabet hallucinations (Cyrillic, Arabic, CJK)
            if detected_lang in ("es", "en", "pt", "fr", "it", "de", "ca"):
                has_non_latin = bool(re.search(r'[\u0400-\u04FF\u0600-\u06FF\u4E00-\u9FFF\u3040-\u30FF]', s_text_clean))
                if has_non_latin:
                    continue

            last_clean_text = s_text_clean
            segments.append({
                "start": round(float(s_start) + time_offset, 2),
                "end": round(float(s_end) + time_offset, 2),
                "text": s_text_clean,
            })

        if not segments and raw_text:
            segments.append({
                "start": round(time_offset, 2),
                "end": round(time_offset + float(duration), 2),
                "text": raw_text.strip(),
            })

        parsed_text = " ".join([seg["text"] for seg in segments]).strip() if segments else raw_text.strip()

        return {
            "segments": segments,
            "text": parsed_text,
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
        language: Optional[str] = None,
        on_progress: Optional[Callable[[int, str], None]] = None,
        source: str = "local",
        prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Slice audio file into 15-minute chunks with FFmpeg and transcribe each sequentially.
        If language is not specified, auto-detects on chunk 1 and pins that language for all remaining chunks.
        """
        # Progress range calibration
        # If source is YouTube: maps from 35% to 80%
        # Fase 3: Transcripción con Whisper en Groq (30.0% a 80.0%)
        min_pct = 30.0
        max_pct = 80.0

        if on_progress:
            if source == "youtube":
                on_progress(25.0, "Segmentando audio de YouTube...")
            else:
                on_progress(25.0, "Segmentando archivo en el servidor...")

        chunks_list = self._slice_audio(audio_path, chunk_minutes=self.DEFAULT_CHUNK_MINUTES)
        num_chunks = len(chunks_list)

        if num_chunks == 0:
            raise RuntimeError(f"FFmpeg no generó fragmentos de audio para: {audio_path}")

        all_segments: List[Dict[str, Any]] = []
        text_parts: List[str] = []
        total_duration = 0.0
        current_time_offset = 0.0
        detected_lang = language if (language and str(language).strip().lower() != "auto") else None

        try:
            for idx, chunk_item in enumerate(chunks_list):
                chunk_path = chunk_item[0] if isinstance(chunk_item, (tuple, list)) else chunk_item

                # Default fallback duration if chunk tuple has it
                estimated_chunk_dur = 0.0
                if isinstance(chunk_item, (tuple, list)) and len(chunk_item) >= 3:
                    try:
                        estimated_chunk_dur = float(chunk_item[2])
                    except (ValueError, TypeError):
                        estimated_chunk_dur = 0.0

                try:
                    # Enviar chunk a Groq con timeout de 60s
                    # Si detected_lang ya fue determinado (por fragmento 1 o usuario), fijar en todos los fragmentos
                    kwargs = {
                        "language": detected_lang,
                        "time_offset": current_time_offset,
                        "timeout": 60.0,
                    }
                    if prompt is not None:
                        kwargs["prompt"] = prompt
                    chunk_res = self._transcribe_single_file(
                        chunk_path,
                        **kwargs,
                    )

                    all_segments.extend(chunk_res.get("segments", []))
                    if chunk_res.get("text"):
                        text_parts.append(chunk_res["text"])
                    if not detected_lang and chunk_res.get("language_code"):
                        detected_lang = chunk_res["language_code"]
                        print(f"[groq_whisper] Idioma de audio detectado en fragmento 1: '{detected_lang}'. Fijando para todos los fragmentos restantes.")

                    chunk_dur = chunk_res.get("duration", 0.0) or estimated_chunk_dur
                except Exception as e:
                    print(f"[Error en chunk {idx + 1}/{num_chunks}]: {e}")
                    # Si un chunk falla por silencio o red, registrar el fallo y continuar con el siguiente
                    fallback_text = f"[Fragmento {idx + 1}: audio no reconocido]"
                    text_parts.append(fallback_text)
                    chunk_dur = estimated_chunk_dur or (self.DEFAULT_CHUNK_MINUTES * 60.0)
                    all_segments.append({
                        "start": round(current_time_offset, 2),
                        "end": round(current_time_offset + chunk_dur, 2),
                        "text": fallback_text,
                    })

                current_time_offset += chunk_dur
                total_duration += chunk_dur

                # Emitir progreso real (Fase 3: 30.0% + ((idx + 1) / len(chunks)) * 50.0)
                chunk_pct = round(min_pct + (((idx + 1) / max(1, num_chunks)) * (max_pct - min_pct)), 1)
                if on_progress:
                    on_progress(
                        chunk_pct,
                        f"Transcribiendo audio (Fragmento {idx + 1} de {num_chunks} - {chunk_pct:.1f}%)",
                    )
        finally:
            # Chunk Cleanup: Immediately after all chunks are transcribed, delete the chunks directory contents
            clean_groq_chunks()

        return {
            "segments": all_segments,
            "text": clean_whisper_hallucinations(" ".join(text_parts)).strip(),
            "language": {
                "code": detected_lang,
                "probability": 1.0,
            },
            "language_code": detected_lang,
            "language_probability": 1.0,
            "duration": round(total_duration, 2),
        }
