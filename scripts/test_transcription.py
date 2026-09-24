#!/usr/bin/env python3
"""Test script for local audio transcription using WhisperEngine."""

import argparse
import json
import sys
import time
from pathlib import Path

# Add project root to sys.path so we can import from src
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.transcription.local_whisper import LocalWhisperTranscriber

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".webm", ".mp4"}


def find_audio_file(input_dir: Path) -> Path | None:
    """Find the first supported audio file in input_dir."""
    if not input_dir.exists():
        return None
    for file in sorted(input_dir.iterdir()):
        if file.suffix.lower() in AUDIO_EXTENSIONS:
            return file
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe an audio file using faster-whisper."
    )
    parser.add_argument(
        "audio",
        nargs="?",
        type=str,
        help="Path to the audio file. If omitted, searches data/input/.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Whisper model size (tiny, base, small, medium, large-v3).",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Device to use ('auto', 'cpu', 'cuda').",
    )
    parser.add_argument(
        "--compute-type",
        type=str,
        default=None,
        help="Compute type (e.g. 'int8', 'float16', 'default').",
    )
    parser.add_argument(
        "--language",
        type=str,
        default=None,
        help="Language code (e.g. 'es', 'en'). Defaults to auto-detect.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(project_root / "data" / "output"),
        help="Directory to save output transcripts (default: data/output).",
    )

    args = parser.parse_args()

    # Determine audio file
    if args.audio:
        audio_file = Path(args.audio)
    else:
        input_dir = project_root / "data" / "input"
        audio_file = find_audio_file(input_dir)
        if not audio_file:
            print(f"[!] No audio file specified and none found in {input_dir}")
            print(f"    Please place an audio file in 'data/input/' or provide the path as an argument.")
            print(f"    Example: python scripts/test_transcription.py data/input/audio.mp3")
            sys.exit(1)

    if not audio_file.is_file():
        print(f"[!] Audio file does not exist: {audio_file}")
        sys.exit(1)

    print("=" * 60)
    print(" WhisperDnD - Local Transcription Engine (MVP)")
    print("=" * 60)
    print(f"Audio file:   {audio_file.resolve()}")
    print(f"Model size:   {args.model or 'default (.env / base)'}")
    print(f"Device:       {args.device or 'default (.env / auto)'}")
    print(f"Compute type: {args.compute_type or 'default (.env / int8)'}")
    print(f"Language:     {args.language or 'auto-detect'}")
    print("-" * 60)

    try:
        print("[*] Loading Whisper model...")
        kwargs = {}
        if args.model:
            kwargs["model_size"] = args.model
        if args.device:
            kwargs["device"] = args.device
        if args.compute_type:
            kwargs["compute_type"] = args.compute_type

        transcriber = LocalWhisperTranscriber(**kwargs)

        start_time = time.time()
        print("[*] Starting transcription...")
        result = transcriber.transcribe(str(audio_file))
        elapsed_time = time.time() - start_time

        print("-" * 60)
        print(f"[+] Transcription finished in {elapsed_time:.2f}s")
        lang_code = result["language"]["code"]
        lang_prob = result["language"]["probability"]
        print(f"[+] Detected language: {lang_code} (p={lang_prob:.2f})")
        print(f"[+] Audio duration:    {result['duration']:.2f}s")
        print(f"[+] Total segments:    {len(result['segments'])}")
        print("-" * 60)

        # Print transcript preview
        preview = result["text"][:300] + ("..." if len(result["text"]) > 300 else "")
        print(f"Preview:\n{preview}\n")

        # Save outputs
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        base_name = audio_file.stem
        txt_path = output_dir / f"{base_name}.txt"
        json_path = output_dir / f"{base_name}.json"

        # Save plain text
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(result["text"])

        # Save detailed JSON with segments and timestamps
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"[+] Plain text saved to: {txt_path.relative_to(project_root)}")
        print(f"[+] JSON details saved to: {json_path.relative_to(project_root)}")
        print("=" * 60)

    except Exception as exc:
        print(f"[!] Error during transcription: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
