"""
Script de prueba controlada de captura aislada de Discord en WhisperDnD.
Graba 15 segundos en estéreo dual:
  - Canal 1 (Izquierdo): Micrófono interno Conexant.
  - Canal 2 (Derecho): Audio de Discord aislado (WASAPI Application Loopback).
La música externa (Spotify / YouTube en navegador) debe quedar excluida del Canal 2.
NO transcribe, NO llama a Groq ni Gemini, NO sube a Google Drive.
Guarda el archivo únicamente en outputs/discord-tests/.
"""
from __future__ import annotations

import datetime
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import soundfile as sf

from src.transcription.discord_audio_capture import (
    is_application_loopback_supported,
    find_discord_root_pid,
    DiscordAudioCapture,
)
from src.transcription.audio_recorder import (
    _resolve_microphone,
    DualChannelAudioRecorder,
)


def main():
    print("=" * 70)
    print(" WhisperDnD - Prueba Controlada de Captura Aislada de Discord")
    print("=" * 70)

    # 1. Verificar versión de Windows
    if not is_application_loopback_supported():
        print("[!] ERROR: Esta versión de Windows no admite Application Loopback.")
        print("    Se requiere Windows 10 build 20348 o superior (Windows 11).")
        sys.exit(1)

    print("[✓] Sistema operativo compatible con Application Loopback de Microsoft.")

    # 2. Verificar si Discord está abierto
    discord_pid = find_discord_root_pid()
    if not discord_pid:
        print("[!] AVISO: Discord no está ejecutándose en este momento.")
        print("    Abre la aplicación de escritorio de Discord y entra a un canal de voz")
        print("    para que la prueba pueda capturar su audio en el Canal 2.")
        print("    (Si continúas sin Discord, el Canal 2 registrará silencio digital sincronizado).")
    else:
        print(f"[✓] Discord detectado en el sistema (PID raíz: {discord_pid}).")

    # 3. Detectar micrófono interno recomendado
    mic = _resolve_microphone(None)
    mic_name = getattr(mic, "name", "Predeterminado")
    print(f"[✓] Canal 1 (Micrófono): {mic_name}")
    print("    (El micrófono interno Conexant preserva los audífonos Redmi Buds en estéreo A2DP).")
    print("[✓] Canal 2 (Audio remoto): Discord aislado (WASAPI Process Loopback).")
    print("    (Spotify, YouTube y reproductores fuera de Discord quedarán excluidos).")

    # 4. Carpeta aislada de pruebas
    test_dir = ROOT / "outputs" / "discord-tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_wav = test_dir / f"prueba_discord_{timestamp}.wav"

    print("\n" + "-" * 70)
    print(" INSTRUCCIONES DE LA PRUEBA (15 SEGUNDOS):")
    print("  1. Habla por tu micrófono durante unos segundos.")
    print("  2. Ten a alguien hablando en Discord (o reproduce un bot de audio en Discord).")
    print("  3. Reproduce música en Spotify o YouTube en tu navegador fuera de Discord.")
    print("-" * 70)
    print(f"Destino del archivo: {out_wav.relative_to(ROOT)}")
    print("\nIniciando captura en 3 segundos...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1... ¡Grabando!\n")

    recorder = DualChannelAudioRecorder(samplerate=16000, blocksize=1600)
    actual_path = recorder.start(output_path=str(out_wav), mode="roleplay")

    duration = 15
    for sec in range(duration, 0, -1):
        status = recorder.get_status()
        mic_rms = status.get("mic_rms", 0.0)
        spk_rms = status.get("speaker_rms", 0.0)
        d_status = status.get("discord_status", {})
        d_msg = d_status.get("status_message", "")
        print(
            f"  [Quedan {sec:02d}s] "
            f"Mic RMS: {mic_rms:.4f} | "
            f"Discord RMS: {spk_rms:.4f} | "
            f"{d_msg[:35]}",
            end="\r",
            flush=True,
        )
        time.sleep(1.0)

    print("\n\nFinalizando y guardando audio...")
    recorder.stop()

    if not out_wav.is_file():
        print(f"[!] Error: El archivo no se generó en {out_wav}")
        sys.exit(1)

    # 5. Análisis cuantitativo de canales
    data, sr = sf.read(str(out_wav), dtype="float32")
    ch1_mic = data[:, 0]
    ch2_discord = data[:, 1]

    mic_rms = float(np.sqrt(np.mean(ch1_mic ** 2)))
    mic_peak = float(np.max(np.abs(ch1_mic)))

    spk_rms = float(np.sqrt(np.mean(ch2_discord ** 2)))
    spk_peak = float(np.max(np.abs(ch2_discord)))

    print("\n" + "=" * 70)
    print(" ANÁLISIS DEL ARCHIVO DE PRUEBA GUARDADO")
    print("=" * 70)
    print(f"Archivo: {out_wav.name}")
    print(f"Ruta:    {out_wav.resolve()}")
    print(f"Formato: {sr} Hz, 2 canales (estéreo), {len(data)/sr:.1f} segundos")
    print("-" * 70)
    print(f"CANAL 1 (Izquierdo - Tu Micrófono):")
    print(f"  • Nivel RMS promedio: {mic_rms:.5f}")
    print(f"  • Nivel Pico:         {mic_peak:.5f}")
    print(f"  • Diagnóstico:        {'Audio detectado' if mic_rms > 0.001 else 'Silencio / muy bajo'}")
    print("-" * 70)
    print(f"CANAL 2 (Derecho - Discord Aislado):")
    print(f"  • Nivel RMS promedio: {spk_rms:.5f}")
    print(f"  • Nivel Pico:         {spk_peak:.5f}")
    print(f"  • Diagnóstico:        {'Audio de Discord capturado' if spk_rms > 0.001 else 'Sin audio de Discord / en espera'}")
    print("=" * 70)
    print("\nCÓMO VERIFICAR LOS CANALES:")
    print("  1. Abre el archivo en un reproductor estéreo o en Audacity.")
    print("  2. En el auricular IZQUIERDO solo debes escuchar tu voz.")
    print("  3. En el auricular DERECHO solo debe escucharse Discord.")
    print("  4. La música reproducida en Spotify/YouTube NO debe escucharse en el auricular derecho.\n")


if __name__ == "__main__":
    main()
