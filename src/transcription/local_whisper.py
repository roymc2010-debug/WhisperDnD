"""Local Whisper transcription module using faster-whisper."""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.runtime_paths import resolve_runtime_paths, is_desktop_runtime

try:
    from dotenv import load_dotenv
    if not is_desktop_runtime():
        load_dotenv()
except ImportError:
    pass


class LocalWhisperTranscriber:
    """Clean, modular local audio transcription engine using faster-whisper."""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "int8",
        download_root: Optional[str] = None,
    ):
        """
        Initialize the LocalWhisperTranscriber.

        :param model_size: Size of Whisper model (tiny, base, small, medium, large-v3).
        :param device: Device to run inference on ('auto', 'cpu', 'cuda').
        :param compute_type: Computation type/quantization ('int8', 'float16', 'float32', 'default').
        :param download_root: Explicit model cache; installed default is the user's profile.
        """
        self.model_size = model_size if model_size != "base" else os.getenv("WHISPER_MODEL_SIZE", "base")
        self.device = device if device != "auto" else os.getenv("WHISPER_DEVICE", "auto")
        self.compute_type = compute_type if compute_type != "int8" else os.getenv("WHISPER_COMPUTE_TYPE", "int8")

        # CPU with CTranslate2 requires int8 or float32 (float16 not supported on x86 CPU)
        if self.device == "cpu" and self.compute_type in ("float16", "bfloat16"):
            self.compute_type = "int8"

        if download_root:
            self.download_root = download_root
        elif is_desktop_runtime():
            resources = Path(__file__).resolve().parent.parent.parent
            self.download_root = str(resolve_runtime_paths(resource_dir=resources).models_dir)
        else:
            # Preserve the existing development cache and environment semantics.
            self.download_root = os.getenv("WHISPER_DOWNLOAD_ROOT", "models")

        self._model = None

    def load_model(self) -> float:
        """Explicitly load the underlying WhisperModel and return load duration in seconds."""
        if self._model is None:
            import time
            start = time.time()
            _ = self.model
            return time.time() - start
        return 0.0

    @property
    def model(self):
        """Lazily initialize and cache the faster-whisper WhisperModel instance."""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise ImportError(
                    "faster-whisper is required for LocalWhisperTranscriber. "
                    "Install dependencies using 'pip install -r requirements.txt'."
                ) from exc

            os.makedirs(self.download_root, exist_ok=True)
            self._model = WhisperModel(
                model_size_or_path=self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root=self.download_root,
            )
        return self._model

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        on_info: Optional[Any] = None,
        on_segment: Optional[Any] = None,
        user_char_name: Optional[str] = None,
        speaking_log: Optional[List[Dict[str, Any]]] = None,
        roster: Optional[List[Dict[str, Any]]] = None,
        initial_prompt: Optional[str] = None,
        on_progress: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Transcribe an audio file using faster-whisper with Voice Activity Detection (VAD).

        :param audio_path: Path to the audio file to transcribe.
        :param language: Optional language code (e.g. 'es', 'en') to force transcription language.
        :param on_info: Optional callback invoked with info (language, duration).
        :param on_segment: Optional callback invoked for each transcribed segment in real-time.
        :param user_char_name: Optional user player character name for transcript tagging.
        :param speaking_log: Optional Discord speaking timeline events for cross-referencing.
        :param roster: Optional campaign roster for Discord User ID speaker mapping.
        :param initial_prompt: Optional vocabulary / glossary prompt to bias Whisper phonetic decoding.
        :param on_progress: Optional callback invoked with (percent, message) for pipeline progress.
        :return: Dictionary containing:
            - segments: list of objects containing start, end, and text.
            - text: full concatenated text string.
            - language: detected language code and probability.
            - duration: audio duration in seconds.
        :raises FileNotFoundError: If the specified audio file does not exist.
        """
        path = Path(audio_path)
        if not path.is_file():
            raise FileNotFoundError(f"Audio file does not exist: {path.resolve()}")

        if self._model is None and on_progress:
            on_progress(30.0, f"Cargando modelo local faster-whisper '{self.model_size}' (CPU int8)...")

        # Run transcription with Voice Activity Detection enabled and disable conditioning on previous text to stop hallucination loops
        transcribe_kwargs = {
            "vad_filter": True,
            "condition_on_previous_text": False,
        }
        if language:
            transcribe_kwargs["language"] = language
        if initial_prompt:
            transcribe_kwargs["initial_prompt"] = initial_prompt

        segments_generator, info = self.model.transcribe(
            str(path),
            **transcribe_kwargs,
        )

        if on_info is not None:
            on_info(info)

        audio_duration = float(info.duration) if (info and hasattr(info, "duration") and info.duration) else 0.0
        segments: List[Dict[str, Any]] = []
        text_chunks: List[str] = []

        from .groq_whisper import clean_whisper_hallucinations
        for segment in segments_generator:
            segment_text = clean_whisper_hallucinations(segment.text.strip(), roster=roster)
            seg_data = {
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment_text,
            }
            segments.append(seg_data)
            if segment_text:
                text_chunks.append(segment_text)
            if on_segment is not None:
                on_segment(seg_data)
            if on_progress is not None and audio_duration > 0:
                pct = min(74.0, round(35.0 + (segment.end / max(1.0, audio_duration)) * 39.0, 1))
                on_progress(pct, f"Transcribiendo con faster-whisper ({self.model_size}): {int(segment.end)}s / {int(audio_duration)}s")

        full_text = clean_whisper_hallucinations(" ".join(text_chunks), roster=roster).strip()
        raw_text = full_text
        formatted_transcript = ""

        # Automatic speaker channel tagging for 2-channel audio
        try:
            from .groq_whisper import tag_dual_channel_speakers, _format_hhmmss
            if segments:
                segments = tag_dual_channel_speakers(
                    str(path),
                    segments,
                    user_char_name=user_char_name,
                    speaking_log=speaking_log,
                    roster=roster,
                )
                formatted_lines = [
                    s.get(
                        "formatted_line",
                        f"[{_format_hhmmss(s['start'])} -> {_format_hhmmss(s['end'])}] {s.get('text', '').strip()}"
                    )
                    for s in segments
                ]
                formatted_transcript = "\n".join(formatted_lines)
        except Exception:
            pass

        return {
            "segments": segments,
            "text": full_text,
            "raw_text": raw_text,
            "formatted_transcript": formatted_transcript or full_text,
            "language": {
                "code": info.language,
                "probability": round(info.language_probability, 4),
            },
            "language_code": info.language,
            "language_probability": round(info.language_probability, 4),
            "duration": round(info.duration, 2),
        }
