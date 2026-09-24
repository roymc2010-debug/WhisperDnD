#!/usr/bin/env python3
"""CLI test script for local audio transcription using LocalWhisperTranscriber."""

import sys
import time
from pathlib import Path

# Add project root to sys.path so we can import src modules
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.transcription.local_whisper import LocalWhisperTranscriber


def format_timestamp(seconds: float) -> str:
    """Format seconds into MM:SS.cc (e.g. 00:00.00 -> 00:05.00)."""
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    return f"{minutes:02d}:{remaining_seconds:05.2f}"


def print_usage_and_exit():
    """Print clear usage instructions and exit."""
    print("=" * 60)
    print(" WhisperDnD - Local Transcription Test")
    print("=" * 60)
    print("Usage:")
    print("  python test_transcribe.py <path/to/audio_file>")
    print()
    print("Default fallback:")
    print("  If no argument is provided, the script looks for 'data/input/sample.mp3'.")
    print()
    print("Error:")
    print("  No audio argument provided and 'data/input/sample.mp3' was not found.")
    print("  Please provide a path to an audio file or place 'sample.mp3' in 'data/input/'.")
    print("=" * 60)
    sys.exit(1)


def main():
    # 1. Check command line arguments or default sample
    if len(sys.argv) > 1:
        audio_path = Path(sys.argv[1])
        if not audio_path.is_file():
            print(f"[!] Error: Specified audio file does not exist: {audio_path}")
            sys.exit(1)
    else:
        default_sample = project_root / "data" / "input" / "sample.mp3"
        if default_sample.is_file():
            audio_path = default_sample
        else:
            print_usage_and_exit()

    print("=" * 60)
    print(" WhisperDnD - Audio Transcription Stream")
    print("=" * 60)
    print(f"Audio file: {audio_path.resolve()}")
    print("-" * 60)

    # 2. Instantiate transcriber and measure model load time
    print("[*] Loading Whisper model...")
    load_start = time.time()
    transcriber = LocalWhisperTranscriber()
    # Trigger model loading to measure exact load time
    _ = transcriber.model
    model_load_time = time.time() - load_start
    print(
        f"[+] Model loaded in {model_load_time:.2f}s "
        f"(size: {transcriber.model_size}, device: {transcriber.device}, compute: {transcriber.compute_type})"
    )
    print("-" * 60)

    # 3. Callbacks for info and real-time streaming
    def on_info(info):
        lang_prob_str = (
            f" (probability: {info.language_probability:.2%})"
            if hasattr(info, "language_probability")
            else ""
        )
        print(f"[+] Detected language: {info.language}{lang_prob_str}")
        print(f"[+] Audio duration:    {info.duration:.2f}s")
        print("-" * 60)
        print("Transcription Stream:")

    def on_segment(seg):
        start_fmt = format_timestamp(seg["start"])
        end_fmt = format_timestamp(seg["end"])
        print(f"[{start_fmt} -> {end_fmt}] {seg['text']}")

    # 4. Transcribe and measure elapsed transcription time
    transcribe_start = time.time()
    try:
        result = transcriber.transcribe(
            str(audio_path),
            on_info=on_info,
            on_segment=on_segment,
        )
    except Exception as exc:
        print(f"\n[!] Error during transcription: {exc}", file=sys.stderr)
        sys.exit(1)

    total_elapsed_time = time.time() - transcribe_start

    print("-" * 60)
    print(f"[+] Total elapsed transcription time: {total_elapsed_time:.2f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
