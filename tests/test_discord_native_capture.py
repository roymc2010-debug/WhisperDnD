"""Exercise the native callback boundary without recording microphone audio."""

import ctypes
import os
import subprocess
import sys
import time
import uuid
import wave
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.transcription import discord_audio_capture as discord
from src.transcription import audio_recorder


def test_audio_format_exposes_float_guid_at_the_windows_abi_offset():
    audio_format = discord.WAVEFORMATEXTENSIBLE()
    audio_format.Format.wFormatTag = 0xFFFE
    audio_format.SubFormat = discord._make_guid("00000003-0000-0010-8000-00aa00389b71")
    native_bytes = ctypes.string_at(ctypes.byref(audio_format), 40)
    assert native_bytes[24:40] == uuid.UUID("00000003-0000-0010-8000-00aa00389b71").bytes_le


@pytest.mark.parametrize("iid", [discord.IID_IUnknown, discord.IID_IAgileObject,
                                  discord.IID_IActivateAudioInterfaceCompletionHandler])
def test_activation_callback_accepts_binary_interface_ids(iid):
    capture = discord.DiscordAudioCapture()
    kernel = MagicMock()
    kernel.CreateEventW.return_value = 1
    mmdevapi = MagicMock()
    result = []

    def activate(device, requested_iid, params, handler_pointer, operation):
        handler = ctypes.cast(handler_pointer, ctypes.POINTER(discord.IActivateAudioInterfaceCompletionHandler))
        callback = handler.contents.lpVtbl.contents.QueryInterface
        # Call through the ABI Windows uses: REFIID is a pointer to 16 binary bytes.
        native_query = ctypes.WINFUNCTYPE(discord.HRESULT, ctypes.c_void_p,
                                         ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(
            ctypes.cast(callback, ctypes.c_void_p).value)
        iid_buffer = ctypes.create_string_buffer(iid)
        output = ctypes.c_void_p()
        hr = native_query(handler_pointer, ctypes.byref(iid_buffer), ctypes.byref(output))
        result.append((hr, output.value))
        capture._stop_event.set()
        return -2147467259

    mmdevapi.ActivateAudioInterfaceAsync.side_effect = activate
    with patch.object(discord, "is_application_loopback_supported", return_value=True), \
         patch.object(discord, "find_discord_root_pid", return_value=123), \
         patch.object(discord.ctypes, "WinDLL", side_effect=lambda name, **kw: kernel if name.lower().startswith("kernel32") else mmdevapi), \
         patch.object(discord.ctypes.oledll, "ole32", MagicMock()), \
         patch.object(discord.time, "sleep"):
        capture._worker()

    assert result[0][0] == 0
    assert result[0][1] is not None


def test_idle_meter_reports_audio_from_isolated_discord_capture():
    capture = MagicMock()
    capture.get_audio_chunk.return_value = np.full((1600, 1), 0.25, dtype=np.float32)
    capture.get_status.return_value = {"discord_detected": True, "target_pid": 123,
        "is_capturing": True, "status_message": "Captura aislada activa", "latest_rms": 0.25}
    with patch.object(audio_recorder, "_resolve_microphone", return_value=None), \
         patch.object(audio_recorder, "find_discord_root_pid", return_value=123), \
         patch.object(audio_recorder, "DiscordAudioCapture", return_value=capture):
        levels = audio_recorder.get_audio_levels()

    assert levels["speaker_rms"] == 0.25
    assert levels["discord_status"]["is_capturing"] is True


def test_busy_meter_is_distinguished_from_a_silent_audio_sample():
    lock = MagicMock()
    lock.acquire.return_value = False
    with patch.object(audio_recorder, "_test_lock", lock):
        levels = audio_recorder.get_audio_levels()
    assert levels.get("meter_busy") is True
    lock.release.assert_not_called()


def test_activation_error_is_not_reported_as_waiting_for_voice():
    capture = discord.DiscordAudioCapture()
    kernel = MagicMock()
    kernel.CreateEventW.return_value = 1
    mmdevapi = MagicMock()

    def fail_activation(*args):
        capture._stop_event.set()
        return -2147467262  # E_NOINTERFACE

    mmdevapi.ActivateAudioInterfaceAsync.side_effect = fail_activation
    with patch.object(discord, "is_application_loopback_supported", return_value=True), \
         patch.object(discord, "find_discord_root_pid", return_value=123), \
         patch.object(discord.ctypes, "WinDLL", side_effect=lambda name, **kw: kernel if name.lower().startswith("kernel32") else mmdevapi), \
         patch.object(discord.ctypes.oledll, "ole32", MagicMock()), \
         patch.object(discord.time, "sleep"):
        capture._worker()

    status = capture.get_status()
    assert not status["is_capturing"]
    assert "0x80004002" in status["status_message"]


@pytest.mark.skipif(os.environ.get("WHISPER_NATIVE_AUDIO_TEST") != "1",
                    reason="Explicit local WASAPI integration check")
def test_real_windows_process_loopback_activates_and_stops():
    capture = discord.DiscordAudioCapture()
    with patch.object(discord, "find_discord_root_pid", return_value=os.getpid()):
        try:
            capture.start()
            deadline = time.monotonic() + 2
            while not capture.is_connected and time.monotonic() < deadline:
                time.sleep(0.05)
            assert capture.is_connected, capture.get_status()
        finally:
            capture.stop()
    assert not capture._thread.is_alive()


@pytest.mark.skipif(os.environ.get("WHISPER_NATIVE_AUDIO_TEST") != "1",
                    reason="Explicit synthetic-tone WASAPI integration check")
def test_real_loopback_captures_target_tone_and_excludes_other_process(tmp_path):
    players = []
    capture = discord.DiscordAudioCapture()
    player_code = (
        "import sys,winsound; print('ready',flush=True); "
        "\nfor command in sys.stdin:"
        "\n if command.strip()=='quit': break"
        "\n winsound.PlaySound(sys.argv[1] if command.strip()=='play' else None, "
        "winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_LOOP)"
    )

    def command(player, text):
        player.stdin.write(text + "\n")
        player.stdin.flush()

    try:
        for frequency in (440, 880):
            audio_path = tmp_path / f"tone_{frequency}.wav"
            tone = (700 * np.sin(2 * np.pi * frequency * np.arange(48000) / 48000)).astype("<i2")
            with wave.open(str(audio_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(48000)
                wav.writeframes(tone.tobytes())
            player = subprocess.Popen([sys.executable, "-c", player_code, str(audio_path)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            players.append(player)
            assert player.stdout.readline().strip() == "ready"

        # Sibling processes: the second tone is outside the selected process tree.
        with patch.object(discord, "find_discord_root_pid", return_value=players[0].pid):
            capture.start()
            deadline = time.monotonic() + 2
            while not capture.is_connected and time.monotonic() < deadline:
                time.sleep(0.05)
            assert capture.is_connected, capture.get_status()
            for player in players:
                command(player, "play")
            chunks = [capture.get_audio_chunk(timeout=0.3)[:, 0] for _ in range(15)]
            signal = np.concatenate(chunks)
            spectrum = np.abs(np.fft.rfft(signal)) / len(signal)
            frequencies = np.fft.rfftfreq(len(signal), 1 / 16000)
            target = float(spectrum[np.abs(frequencies - 440) < 5].max())
            unrelated = float(spectrum[np.abs(frequencies - 880) < 5].max())
            print(f"Synthetic-tone amplitudes: target={target:.6f}, unrelated={unrelated:.6f}")
            assert target > 0.001
            assert unrelated < target * 0.05

            command(players[0], "stop")
            for _ in range(5):
                capture.get_audio_chunk(timeout=0.3)
            other_only = np.concatenate([capture.get_audio_chunk(timeout=0.3)[:, 0] for _ in range(5)])
            assert float(np.max(np.abs(other_only))) < 0.0001
    finally:
        capture.stop()
        for player in players:
            try:
                command(player, "quit")
                player.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                player.kill()
                player.wait(timeout=3)
            for stream in (player.stdin, player.stdout, player.stderr):
                stream.close()
