"""Validate local-microphone recognitions against original, unamplified audio.

Volume is checked first. Long, sparse intervals also reuse the local engine's
bundled Silero voice detector. No audio is edited and Discord is never gated.
"""
import math

import numpy as np
import soundfile as sf


DEFAULT_MIC_MIN_RMS = 0.003  # approximately -50.5 dBFS


def _audible_interval(audio, start, end, min_rms):
    """Require 60 ms above threshold in 20 ms windows; ignore isolated clicks.

    Read bounded blocks, retaining the run across block boundaries. Long pauses
    do not dilute the RMS of a brief audible intervention.
    """
    start, end = float(start), float(end)
    if not math.isfinite(start) or not math.isfinite(end) or end <= start:
        raise ValueError("Invalid recognition interval")
    first = max(0, int(start * audio.samplerate))
    last = min(len(audio), math.ceil(end * audio.samplerate))
    if last <= first:
        raise ValueError("Recognition interval outside recording")
    window = max(1, round(audio.samplerate * 0.02))
    minimum_frames = math.ceil(audio.samplerate * 0.06)
    remaining = last - first
    audio.seek(first)
    run = 0
    has_audible_run = False
    active_frames = 0
    while remaining:
        data = audio.read(min(remaining, window * 256), dtype="float32",
                          always_2d=True)[:, 0]
        if not len(data) or not np.isfinite(data).all():
            raise ValueError("Unavailable microphone samples")
        remaining -= len(data)
        for offset in range(0, len(data), window):
            samples = data[offset:offset + window]
            rms = float(np.sqrt(np.mean(samples ** 2)))
            run = run + len(samples) if rms >= min_rms else 0
            if rms >= min_rms:
                active_frames += len(samples)
            if run >= minimum_frames:
                has_audible_run = True
    if not has_audible_run:
        return False, "mic_below_minimum_volume"
    # A short bump must not validate 30 seconds of invented speech. Preserve
    # genuine brief speech between long pauses using voice evidence, not a
    # mandatory speaking fraction or a blacklist of words.
    if end - start >= 5 and active_frames / (last - first) < 0.05:
        if not _has_detected_speech(audio, start, end):
            return False, "mic_no_detected_speech"
    return True, None


def _has_detected_speech(audio, start, end):
    """Reuse installed Silero assets; no model downloads or recognition calls.

    Bounded reads and a small context margin tolerate timestamp drift. Other
    sample rates use the existing PyAV decoding path in memory.
    """
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    options = VadOptions(min_speech_duration_ms=100, min_silence_duration_ms=200,
                         speech_pad_ms=0)
    rate = audio.samplerate
    first = max(0, int((float(start) - 0.2) * rate))
    last = min(len(audio), math.ceil((float(end) + 0.2) * rate))
    audio.seek(first)
    remaining = last - first
    while remaining:
        samples = audio.read(min(remaining, rate * 30), dtype="float32",
                             always_2d=True)[:, 0]
        if not len(samples):
            raise ValueError("Unavailable microphone samples for voice detection")
        remaining -= len(samples)
        if rate != 16000:
            import io
            from faster_whisper.audio import decode_audio
            stream = io.BytesIO()
            sf.write(stream, samples, rate, format="WAV", subtype="FLOAT")
            stream.seek(0)
            samples = decode_audio(stream, sampling_rate=16000)
        if get_speech_timestamps(samples, options, sampling_rate=16000):
            return True
    return False


def apply_mic_volume_gate(audio_path, result, min_rms=DEFAULT_MIC_MIN_RMS):
    """Exclude low-volume mic segments from usable text, retaining audit copies.

    Only stereo recordings with explicit local-mic labels qualify. The caller
    must supply the original audio, before normalization. Text is rebuilt only
    when something was excluded; raw_text and the input result remain intact.
    """
    if not math.isfinite(min_rms) or not 0 < min_rms <= 1:
        raise ValueError("Microphone minimum RMS must be between 0 and 1")
    segments = result.get("segments") or []
    kept, excluded = [], []
    try:
        with sf.SoundFile(str(audio_path)) as audio:
            if audio.channels != 2:
                return result
            for segment in segments:
                speaker = str(segment.get("speaker", ""))
                is_mic = speaker == "[Tu]" or speaker.startswith("[Tu / ")
                if is_mic:
                    audible, reason = _audible_interval(
                        audio, segment.get("start"), segment.get("end"), min_rms)
                    if not audible:
                        excluded.append({**segment, "reason": reason, "min_rms": min_rms})
                        continue
                kept.append(segment)
    except (OSError, RuntimeError, ValueError, TypeError, ImportError):
        return {**result, "mic_volume_gate": {"status": "unavailable",
                "message": "No se pudo comprobar el volumen del micrófono; no se excluyó texto."}}

    output = {**result, "mic_volume_gate": {"status": "checked", "min_rms": min_rms,
              "min_dbfs": round(20 * math.log10(min_rms), 1),
              "voice_check": "silero_for_long_sparse_segments",
              "excluded_count": len(excluded)}}
    if excluded:
        # Preserve every excluded recognition for inspection. Do not let a
        # fallback to raw_text reintroduce it into the usable transcript.
        output["excluded_segments"] = [*result.get("excluded_segments", []), *excluded]
        output["segments"] = kept
        output["text"] = " ".join(str(s.get("text", "")).strip() for s in kept).strip()
        output["formatted_transcript"] = "\n".join(
            s.get("formatted_line") or _formatted_line(s) for s in kept
        )
    return output


def _formatted_line(segment):
    from .groq_whisper import _format_hhmmss
    return (f"[{_format_hhmmss(segment['start'])} -> {_format_hhmmss(segment['end'])}] "
            f"{segment.get('speaker', '')}: {str(segment.get('text', '')).strip()}")
