"""Local Audio Transcription Engine using faster-whisper."""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class WhisperEngine:
    """Wrapper around faster-whisper WhisperModel for local audio transcription."""

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        download_root: Optional[str] = None,
    ):
        """
        Initialize the WhisperModel engine.

        :param model_size: Size of the model (e.g. 'tiny', 'base', 'small', 'medium', 'large-v3').
        :param device: Device to run on ('cpu', 'cuda', 'auto').
        :param compute_type: Quantization type (e.g. 'int8', 'float16', 'float32', 'default').
        :param download_root: Path where model weights should be cached.
        """
        self.model_size = model_size or os.getenv("WHISPER_MODEL_SIZE", "base")
        self.device = device or os.getenv("WHISPER_DEVICE", "auto")
        self.compute_type = compute_type or os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        self.download_root = download_root or os.getenv("WHISPER_DOWNLOAD_ROOT", "models")

        # Lazy loading or eager initialization
        self._model = None

    @property
    def model(self):
        """Lazily initialize and return the underlying WhisperModel."""
        if self._model is None:
            # Import inside property so module can be imported even if faster-whisper is not yet installed
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise ImportError(
                    "faster-whisper is not installed. Please run 'pip install -r requirements.txt'."
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
        audio_path: str | Path,
        language: Optional[str] = None,
        beam_size: int = 5,
        vad_filter: bool = True,
    ) -> Dict[str, Any]:
        """
        Transcribe an audio file.

        :param audio_path: Path to the audio file.
        :param language: Language code (e.g. 'es', 'en') or None for auto-detection.
        :param beam_size: Beam size for decoding.
        :param vad_filter: Whether to enable Silero Voice Activity Detection.
        :return: Dictionary with transcription text, language info, and segments.
        """
        file_path = Path(audio_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"Audio file not found: {file_path.resolve()}")

        segments_raw, info = self.model.transcribe(
            str(file_path),
            beam_size=beam_size,
            language=language,
            vad_filter=vad_filter,
        )

        segments: List[Dict[str, Any]] = []
        full_text_parts: List[str] = []

        for seg in segments_raw:
            text = seg.text.strip()
            segments.append(
                {
                    "id": seg.id,
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": text,
                }
            )
            if text:
                full_text_parts.append(text)

        full_text = " ".join(full_text_parts)

        return {
            "file": str(file_path.name),
            "language": info.language,
            "language_probability": round(info.language_probability, 4),
            "duration": round(info.duration, 2),
            "text": full_text,
            "segments": segments,
        }
