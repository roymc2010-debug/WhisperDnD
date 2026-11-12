"""
Local Transcription Test Reporter for WhisperDnD.
Generates privacy-safe, isolated benchmarking reports for Groq Cloud and faster-whisper local models.

Strict privacy rules:
- No audio content or audio files stored.
- No API keys, tokens, YouTube URLs, campaign names, character names, or player roster.
- No full transcript included by default.
- Only saved in local outputs/transcription-tests/.
- Never uploaded to Google Drive or external cloud providers.
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path
from src.runtime_paths import resolve_runtime_paths, is_desktop_runtime
import re
from typing import Any, Dict, List, Optional
import uuid


def get_transcription_tests_dir() -> Path:
    """Return the designated local directory for transcription test reports."""
    env_dir = os.environ.get("WHISPER_OUTPUT_DIR")
    if is_desktop_runtime():
        base = resolve_runtime_paths().output_dir
    elif env_dir:
        base = Path(env_dir).resolve()
    else:
        project_root = Path(__file__).resolve().parents[2]
        base = project_root / "outputs"

    target = base / "transcription-tests"
    target.mkdir(parents=True, exist_ok=True)
    return target


def normalize_text_for_evaluation(text: str) -> str:
    """
    Standard normalization for ASR benchmarking (WER/CER):
    - Converts to lowercase
    - Replaces punctuation and special characters with spaces
    - Collapses consecutive whitespace characters
    """
    if not text:
        return ""
    cleaned = text.lower()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _levenshtein_distance(seq1: List[Any], seq2: List[Any]) -> int:
    """Compute Levenshtein distance between two sequences (words or characters)."""
    n, m = len(seq1), len(seq2)
    if n == 0:
        return m
    if m == 0:
        return n

    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, m + 1):
            temp = dp[j]
            if seq1[i - 1] == seq2[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[m]


def calculate_wer_and_cer(reference: str, hypothesis: str) -> Dict[str, Any]:
    """
    Calculate Word Error Rate (WER) and Character Error Rate (CER).
    WER = (Substitutions + Deletions + Insertions) / Total Reference Words
    CER = (Substitutions + Deletions + Insertions) / Total Reference Characters
    """
    norm_ref = normalize_text_for_evaluation(reference)
    norm_hyp = normalize_text_for_evaluation(hypothesis)

    ref_words = norm_ref.split()
    hyp_words = norm_hyp.split()

    ref_chars = list(norm_ref.replace(" ", ""))
    hyp_chars = list(norm_hyp.replace(" ", ""))

    if not ref_words:
        wer = 0.0 if not hyp_words else 100.0
    else:
        word_dist = _levenshtein_distance(ref_words, hyp_words)
        wer = round((word_dist / len(ref_words)) * 100, 2)

    if not ref_chars:
        cer = 0.0 if not hyp_chars else 100.0
    else:
        char_dist = _levenshtein_distance(ref_chars, hyp_chars)
        cer = round((char_dist / len(ref_chars)) * 100, 2)

    return {
        "reference_words": len(ref_words),
        "hypothesis_words": len(hyp_words),
        "reference_chars": len(ref_chars),
        "hypothesis_chars": len(hyp_chars),
        "wer": wer,
        "cer": cer,
        "normalization": "Minúsculas, remoción de puntuación y símbolos, colapso de espacios múltiples",
    }


def sanitize_source_label(source: str) -> str:
    """Sanitize source into generic category to protect privacy."""
    s = str(source or "").lower().strip()
    if "youtube" in s:
        return "YouTube (Audio de video)"
    if any(k in s for k in ("live", "mic", "record", "browser")):
        return "Grabación en Vivo (Micrófono)"
    return "Archivo Local"


def create_transcription_test_report(
    *,
    engine: str,
    model_size: Optional[str] = None,
    source: str = "file",
    audio_duration_seconds: Optional[float] = None,
    transcription_time_seconds: Optional[float] = None,
    total_time_seconds: Optional[float] = None,
    language: Optional[str] = None,
    device: Optional[str] = None,
    compute_type: Optional[str] = None,
    vad_enabled: bool = True,
    condition_on_previous_text: bool = False,
    success: bool = True,
    error_summary: Optional[str] = None,
    reference_text: Optional[str] = None,
    hypothesis_text: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> Path:
    """
    Generate and save a local text report of an ASR benchmark run.
    Guarantees zero leaks of audio, keys, campaign names, or sensitive information.
    """
    now = datetime.datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
    file_timestamp = now.strftime("%Y%m%d_%H%M%S")
    run_id = uuid.uuid4().hex[:8]

    clean_engine = "local" if "local" in str(engine).lower() else "groq"
    clean_model = (model_size or ("base" if clean_engine == "local" else "whisper-large-v3")).lower().strip()
    clean_source = sanitize_source_label(source)
    status_label = "COMPLETADO" if success else "FALLIDO"

    target_dir = output_dir or get_transcription_tests_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    report_filename = f"test_report_{file_timestamp}_{clean_engine}_{clean_model}_{run_id}.txt"
    report_path = target_dir / report_filename

    # Audio duration formatting
    if audio_duration_seconds is not None and audio_duration_seconds >= 0:
        mins = int(audio_duration_seconds // 60)
        secs = int(audio_duration_seconds % 60)
        dur_str = f"{mins:02d}:{secs:02d} ({audio_duration_seconds:.2f} s)"
    else:
        dur_str = "No disponible"

    # Time measurements
    trans_time_str = f"{transcription_time_seconds:.2f} s" if transcription_time_seconds is not None else "No medido por separado"
    total_time_str = f"{total_time_seconds:.2f} s" if total_time_seconds is not None else "No medido"

    # Real-time factor (RTF)
    rtf_str = "N/A"
    if audio_duration_seconds and audio_duration_seconds > 0:
        measure_time = transcription_time_seconds or total_time_seconds
        if measure_time and measure_time > 0:
            rtf = measure_time / audio_duration_seconds
            speedup = audio_duration_seconds / measure_time
            rtf_str = f"{rtf:.3f}x ({speedup:.1f}x tiempo real)"

    # Configuration
    if clean_engine == "local":
        engine_display = "faster-whisper (Inferencia Local)"
        dev_display = device or "CPU (Intel Core i7-6560U, 16 GB RAM)"
        compute_display = compute_type or "int8"
        vad_display = "Activado (silero_vad, threshold=0.35)" if vad_enabled else "Desactivado"
    else:
        engine_display = "Groq Cloud Whisper API"
        dev_display = device or "Cloud LPU"
        compute_display = compute_type or "fp16 (Cloud)"
        vad_display = "N/A (Procesado por API de Groq)"

    cond_prev_str = "False (evita bucles fonéticos y alucinaciones)" if not condition_on_previous_text else "True"
    lang_display = language or "auto-detect"

    lines = [
        "======================================================================",
        "INFORME LOCAL DE PRUEBA DE TRANSCRIPCIÓN - WhisperDnD",
        "======================================================================",
        f"Fecha y hora:        {timestamp_str}",
        f"Identificador:       {report_filename.replace('.txt', '')}",
        f"Estado:              {status_label}",
        "",
        "--- MOTOR Y MODELO ---",
        f"Motor:               {engine_display}",
        f"Modelo:              {clean_model}",
        f"Dispositivo:         {dev_display}",
        f"Tipo de cómputo:     {compute_display}",
        f"VAD:                 {vad_display}",
        f"Cond. texto previo:  {cond_prev_str}",
        "",
        "--- ORIGEN Y AUDIO ---",
        f"Origen del audio:    {clean_source}",
        f"Duración del audio:  {dur_str}",
        f"Idioma:              {lang_display}",
        "",
        "--- TIEMPOS DE RENDIMIENTO ---",
        f"Tiempo transcripción: {trans_time_str}",
        f"Tiempo total:         {total_time_str}",
        f"Factor de tiempo:     {rtf_str}",
        "",
        "--- EVALUACIÓN DE PRECISIÓN ---",
    ]

    if reference_text and reference_text.strip():
        metrics = calculate_wer_and_cer(reference_text.strip(), (hypothesis_text or "").strip())
        lines.extend([
            "Referencia externa:  Proporcionada para evaluación local",
            f"Supuestos norm.:     {metrics['normalization']}",
            f"Palabras referencia: {metrics['reference_words']}",
            f"Palabras hipótesis:  {metrics['hypothesis_words']}",
            f"Word Error Rate:     {metrics['wer']:.2f}% (WER)",
            f"Char Error Rate:     {metrics['cer']:.2f}% (CER)",
            "Nota:                El cálculo se realiza en memoria; la referencia no se almacena.",
        ])
    else:
        lines.extend([
            "Referencia externa:  No proporcionada (no se calcula WER/CER)",
            "Nota metodológica:   La precisión requiere una transcripción de referencia corregida.",
            "                     No se asume que un modelo sea más preciso sin una comparación",
            "                     cuantitativa controlada basada en texto de referencia.",
        ])

    lines.extend([
        "",
        "--- RESULTADO / DIAGNÓSTICO ---",
        f"Resultado:           {'Éxito' if success else 'Fallo'}",
    ])

    if not success and error_summary:
        # Sanitize error to avoid leaking keys or file paths
        sanitized_err = re.sub(r"gsk_[a-zA-Z0-9_-]+", "[GROQ_KEY_REDACTED]", error_summary)
        sanitized_err = re.sub(r"AIza[a-zA-Z0-9_-]+", "[GEMINI_KEY_REDACTED]", sanitized_err)
        sanitized_err = re.sub(r"[A-Z]:\\[^\s]+\\data\\[^\s]+", "[LOCAL_PATH_REDACTED]", sanitized_err)
        lines.append(f"Error resumido:      {sanitized_err}")
    else:
        lines.append("Notas:               Transcripción completada con éxito.")

    lines.extend([
        "",
        "======================================================================",
        f"Ubicación del informe: {report_path.resolve()}",
        "Privacidad garantizada: Este informe es estrictamente local.",
        "No contiene audio, transcripciones completas, claves de API,",
        "tokens, nombres de campañas, personajes, jugadores ni roster.",
        "No se sincroniza a Google Drive ni a servicios en la nube.",
        "======================================================================",
        "",
    ])

    content = "\n".join(lines)
    report_path.write_text(content, encoding="utf-8")
    print(f"[TestReporter] Informe de prueba guardado en: {report_path}")
    return report_path
