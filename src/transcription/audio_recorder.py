"""Dual-channel audio recorder capturing mic and system/Discord loopback audio."""

import datetime
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from src.transcription.discord_rpc import discord_tracker
except ImportError:
    from .discord_rpc import discord_tracker

_test_lock = threading.Lock()


def get_audio_devices() -> Dict[str, Any]:
    """
    List all physical input microphones and playback speaker devices on Windows.
    Returns:
        {
            "microphones": [{"id": str, "name": str}, ...],
            "speakers": [{"id": str, "name": str}, ...],
            "default_mic_id": Optional[str],
            "default_speaker_id": Optional[str],
        }
    """
    try:
        import soundcard as sc

        mics = [{"id": m.id, "name": m.name} for m in sc.all_microphones(include_loopback=False)]
        speakers = [{"id": s.id, "name": s.name} for s in sc.all_speakers()]

        default_mic = None
        try:
            default_mic = sc.default_microphone()
        except Exception:
            pass

        default_spk = None
        try:
            default_spk = sc.default_speaker()
        except Exception:
            pass

        return {
            "microphones": mics,
            "speakers": speakers,
            "default_mic_id": default_mic.id if default_mic else None,
            "default_speaker_id": default_spk.id if default_spk else None,
        }
    except Exception as exc:
        return {
            "microphones": [],
            "speakers": [],
            "default_mic_id": None,
            "default_speaker_id": None,
            "error": str(exc),
        }


def _resolve_microphone(mic_id: Optional[str] = None):
    """Acquire a specific physical microphone by ID or fallback to the system default."""
    import soundcard as sc

    if mic_id:
        try:
            return sc.get_microphone(id=mic_id)
        except Exception:
            pass
    try:
        return sc.default_microphone()
    except Exception:
        all_m = sc.all_microphones(include_loopback=False)
        return all_m[0] if all_m else None


def _resolve_speaker_loopback(speaker_id: Optional[str] = None):
    """
    Acquire the loopback recorder endpoint for a specific speaker / headphone by ID,
    falling back to the default speaker's loopback or any available loopback.
    """
    import soundcard as sc

    if speaker_id:
        try:
            return sc.get_microphone(id=speaker_id, include_loopback=True)
        except Exception:
            pass

    # Fallback to default speaker ID
    try:
        spk = sc.default_speaker()
        if spk and getattr(spk, "id", None):
            try:
                return sc.get_microphone(id=spk.id, include_loopback=True)
            except Exception:
                pass
        if spk and getattr(spk, "name", None):
            try:
                return sc.get_microphone(id=spk.name, include_loopback=True)
            except Exception:
                pass
    except Exception:
        pass

    # Fallback search for any loopback device
    try:
        for m in sc.all_microphones(include_loopback=True):
            if getattr(m, "isloopback", False):
                return m
    except Exception:
        pass

    return None


class DualChannelAudioRecorder:
    """
    Captures dual-channel audio on Windows:
    - Channel 1 (Left): Selected / Default Microphone (Rodrigo / local player)
    - Channel 2 (Right): Selected / Default Speaker Loopback (Discord / other players / DM)
    Streams directly to disk in PCM_16 WAV format at 16,000 Hz to prevent RAM exhaustion.
    """

    def __init__(self, samplerate: int = 16000, blocksize: int = 1600):
        self.samplerate = samplerate
        self.blocksize = blocksize  # 0.1s at 16kHz
        self._is_recording = False
        self._mode = "roleplay"
        self._mic_id: Optional[str] = None
        self._speaker_id: Optional[str] = None
        self._latest_mic_rms = 0.0
        self._latest_spk_rms = 0.0
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_time = 0.0
        self._file_path: Optional[str] = None
        self._speaking_log: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    @property
    def speaking_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._speaking_log)

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def mic_id(self) -> Optional[str]:
        return self._mic_id

    @property
    def speaker_id(self) -> Optional[str]:
        return self._speaker_id

    @property
    def latest_mic_rms(self) -> float:
        return self._latest_mic_rms

    @property
    def latest_spk_rms(self) -> float:
        return self._latest_spk_rms

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            duration = round(time.time() - self._start_time, 1) if self._is_recording else 0.0
            return {
                "is_recording": self._is_recording,
                "mode": self._mode,
                "duration_seconds": duration,
                "file_path": self._file_path,
                "mic_id": self._mic_id,
                "speaker_id": self._speaker_id,
                "mic_rms": round(self._latest_mic_rms, 5),
                "speaker_rms": round(self._latest_spk_rms, 5),
            }

    def start(
        self,
        output_path: Optional[str] = None,
        mode: str = "roleplay",
        mic_id: Optional[str] = None,
        speaker_id: Optional[str] = None,
    ) -> str:
        """
        Start recording audio in a background thread.
        - mode='roleplay': Dual-channel (Mic Left + Speaker Loopback Right) for D&D/Discord.
        - mode='class': Single-channel (Microphone ONLY, Mono 16kHz) for in-person university lectures.

        :param output_path: Optional file path for the .wav output.
        :param mode: 'roleplay' or 'class'.
        :param mic_id: Optional physical microphone device ID.
        :param speaker_id: Optional playback speaker/headphone device ID for loopback.
        :return: The path to the WAV file being recorded.
        """
        with self._lock:
            if self._is_recording:
                raise RuntimeError("Recording is already in progress.")

            selected_mode = (mode or "roleplay").lower().strip()
            self._mode = "class" if selected_mode == "class" else "roleplay"
            self._mic_id = mic_id
            self._speaker_id = speaker_id
            self._latest_mic_rms = 0.0
            self._latest_spk_rms = 0.0

            if not output_path:
                project_root = Path(__file__).resolve().parent.parent.parent
                dest_dir = project_root / "data" / "input"
                dest_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                prefix = "lecture" if self._mode == "class" else "session"
                output_path = str((dest_dir / f"{prefix}_{timestamp}.wav").resolve())
            else:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                output_path = str(Path(output_path).resolve())

            self._file_path = output_path
            self._stop_event.clear()
            self._start_time = time.time()
            self._is_recording = True
            self._speaking_log = []

            if self._mode == "roleplay":
                try:
                    discord_tracker.start_session(self._start_time)
                except Exception as exc:
                    print(f"[AudioRecorder] Discord tracker start warning: {exc}")

            self._thread = threading.Thread(
                target=self._record_worker,
                args=(output_path, self._mode, self._mic_id, self._speaker_id),
                daemon=True,
                name="AudioRecorderThread",
            )
            self._thread.start()
            return output_path

    def stop(self) -> str:
        """
        Stop the recording, flush audio to disk, and return the completed file path.

        :return: The completed WAV file path.
        """
        with self._lock:
            if not self._is_recording:
                raise RuntimeError("No active recording to stop.")

            self._stop_event.set()

        # Stop Discord tracking session
        if self._mode == "roleplay":
            try:
                self._speaking_log = discord_tracker.stop_session()
            except Exception as exc:
                print(f"[AudioRecorder] Discord tracker stop warning: {exc}")
                self._speaking_log = []

        # Wait for the recording thread to flush and finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=6.0)

        with self._lock:
            self._is_recording = False
            self._latest_mic_rms = 0.0
            self._latest_spk_rms = 0.0
            final_path = self._file_path
            return final_path or ""

    def _record_worker(
        self,
        wav_path: str,
        mode: str = "roleplay",
        mic_id: Optional[str] = None,
        speaker_id: Optional[str] = None,
    ):
        """Worker thread that records audio directly to SoundFile."""
        try:
            import soundcard as sc
            import soundfile as sf
        except ImportError as exc:
            self._is_recording = False
            raise ImportError(
                "soundcard and soundfile are required for audio recording. "
                "Please run 'pip install soundcard soundfile'."
            ) from exc

        # 1. In-Person University Lecture Mode: Single-Channel Mono Microphone ONLY
        if mode == "class":
            try:
                mic = _resolve_microphone(mic_id)
                if not mic:
                    raise RuntimeError("No microphone device found.")
                with sf.SoundFile(
                    wav_path,
                    mode="w",
                    samplerate=self.samplerate,
                    channels=1,
                    subtype="PCM_16",
                ) as wav_file:
                    with mic.recorder(samplerate=self.samplerate, channels=1) as mic_rec:
                        while not self._stop_event.is_set():
                            data_mic = mic_rec.record(numframes=self.blocksize)
                            if len(data_mic) > 0:
                                # Mono 1-channel write
                                wav_file.write(data_mic[:, 0])
                                self._latest_mic_rms = float(np.sqrt(np.mean(data_mic[:, 0] ** 2)))
                                self._latest_spk_rms = 0.0
            except Exception as exc:
                print(f"[!] Error in university lecture audio recording worker: {exc}")
            finally:
                self._is_recording = False
            return

        # 2. D&D / Discord Roleplay Mode: Dual-Channel (Mic Left + Speaker Loopback Right)
        mic = _resolve_microphone(mic_id)
        loopback = _resolve_speaker_loopback(speaker_id)

        if loopback is None and mic is not None:
            loopback = mic

        if mic is None:
            print("[!] Error: No microphone device could be acquired for live recording.")
            self._is_recording = False
            return

        try:
            with sf.SoundFile(
                wav_path,
                mode="w",
                samplerate=self.samplerate,
                channels=2,
                subtype="PCM_16",
            ) as wav_file:
                with mic.recorder(samplerate=self.samplerate, channels=1) as mic_rec, \
                     loopback.recorder(samplerate=self.samplerate, channels=1) as spk_rec:
                    while not self._stop_event.is_set():
                        data_mic = mic_rec.record(numframes=self.blocksize)
                        data_spk = spk_rec.record(numframes=self.blocksize)

                        n_frames = min(len(data_mic), len(data_spk))
                        if n_frames > 0:
                            stereo_chunk = np.column_stack(
                                (data_mic[:n_frames, 0], data_spk[:n_frames, 0])
                            )
                            wav_file.write(stereo_chunk)
                            self._latest_mic_rms = float(np.sqrt(np.mean(data_mic[:n_frames, 0] ** 2)))
                            self._latest_spk_rms = float(np.sqrt(np.mean(data_spk[:n_frames, 0] ** 2)))
        except Exception as exc:
            print(f"[!] Error in roleplay audio recording worker: {exc}")
        finally:
            self._is_recording = False


# Global singleton instance for the API server
active_recorder = DualChannelAudioRecorder()


def get_audio_levels(
    mic_id: Optional[str] = None,
    speaker_id: Optional[str] = None,
    sample_frames: int = 1600,
) -> Dict[str, Any]:
    """
    Sample audio levels from the selected microphone and speaker loopback.
    If recording is actively running, returns the live streaming RMS levels.
    If idle, captures a brief ~100ms sample to calculate current RMS levels.
    """
    if active_recorder.is_recording:
        return {
            "mic_rms": round(active_recorder.latest_mic_rms, 5),
            "speaker_rms": round(active_recorder.latest_spk_rms, 5),
            "is_recording": True,
        }

    mic_rms = 0.0
    spk_rms = 0.0

    # Non-blocking lock to prevent overlapping test-level polls from contending over the hardware
    if not _test_lock.acquire(blocking=False):
        return {"mic_rms": 0.0, "speaker_rms": 0.0, "is_recording": False}

    try:
        mic = _resolve_microphone(mic_id)
        loopback = _resolve_speaker_loopback(speaker_id)

        if mic and loopback and (getattr(mic, "id", None) != getattr(loopback, "id", None)):
            try:
                with mic.recorder(samplerate=16000, channels=1) as r1, \
                     loopback.recorder(samplerate=16000, channels=1) as r2:
                    d1 = r1.record(numframes=sample_frames)
                    d2 = r2.record(numframes=sample_frames)
                    if len(d1) > 0:
                        mic_rms = float(np.sqrt(np.mean(d1[:, 0] ** 2)))
                    if len(d2) > 0:
                        spk_rms = float(np.sqrt(np.mean(d2[:, 0] ** 2)))
            except Exception:
                # If simultaneous capture fails, measure individually
                if mic:
                    try:
                        with mic.recorder(samplerate=16000, channels=1) as r1:
                            d1 = r1.record(numframes=sample_frames)
                            if len(d1) > 0:
                                mic_rms = float(np.sqrt(np.mean(d1[:, 0] ** 2)))
                    except Exception:
                        pass
                if loopback:
                    try:
                        with loopback.recorder(samplerate=16000, channels=1) as r2:
                            d2 = r2.record(numframes=sample_frames)
                            if len(d2) > 0:
                                spk_rms = float(np.sqrt(np.mean(d2[:, 0] ** 2)))
                    except Exception:
                        pass
        elif mic:
            try:
                with mic.recorder(samplerate=16000, channels=1) as r1:
                    d1 = r1.record(numframes=sample_frames)
                    if len(d1) > 0:
                        mic_rms = float(np.sqrt(np.mean(d1[:, 0] ** 2)))
            except Exception:
                pass
    except Exception:
        pass
    finally:
        _test_lock.release()

    return {
        "mic_rms": round(mic_rms, 5),
        "speaker_rms": round(spk_rms, 5),
        "is_recording": False,
    }
