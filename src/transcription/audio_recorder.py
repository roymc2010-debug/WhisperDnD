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


def _is_headphone_name(name: str) -> bool:
    """Check if device name suggests headphones, headsets, or earbuds."""
    lower = (name or "").lower()
    return any(
        kw in lower
        for kw in (
            "auricular",
            "headphone",
            "headset",
            "casco",
            "airpod",
            "buds",
            "earphone",
            "wireless",
            "bluetooth",
        )
    )


def get_audio_devices() -> Dict[str, Any]:
    """
    List all physical input microphones and playback speaker devices on Windows.
    Categorizes headphone vs speaker devices and recommends the best speaker endpoint.
    Returns:
        {
            "microphones": [{"id": str, "name": str}, ...],
            "speakers": [{"id": str, "name": str, "is_headphone": bool}, ...],
            "default_mic_id": Optional[str],
            "default_speaker_id": Optional[str],
            "suggested_speaker_id": Optional[str],
        }
    """
    try:
        import soundcard as sc

        mics = [{"id": m.id, "name": m.name} for m in sc.all_microphones(include_loopback=False)]
        speakers = [
            {
                "id": s.id,
                "name": s.name,
                "is_headphone": _is_headphone_name(s.name),
            }
            for s in sc.all_speakers()
        ]

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

        # Intelligent suggestion: prioritize headphones over built-in laptop speakers
        suggested_spk_id = default_spk.id if default_spk else None
        if default_spk and not _is_headphone_name(default_spk.name):
            headphone_candidate = next((s for s in speakers if s["is_headphone"]), None)
            if headphone_candidate:
                suggested_spk_id = headphone_candidate["id"]

        return {
            "microphones": mics,
            "speakers": speakers,
            "default_mic_id": default_mic.id if default_mic else None,
            "default_speaker_id": default_spk.id if default_spk else None,
            "suggested_speaker_id": suggested_spk_id,
        }
    except Exception as exc:
        return {
            "microphones": [],
            "speakers": [],
            "default_mic_id": None,
            "default_speaker_id": None,
            "suggested_speaker_id": None,
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
    NEVER falls back to microphone to prevent duplicate voice audio on Channel 2.
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

    # Fallback search for any true loopback device
    try:
        for m in sc.all_microphones(include_loopback=True):
            if getattr(m, "isloopback", False):
                return m
    except Exception:
        pass

    return None


def normalize_dual_channel_audio(audio_path: str, target_rms: float = 0.12) -> str:
    """
    Post-processing auto-leveling for dual-channel audio before Whisper transcription & diarization.
    Analyzes active speech RMS on both channels (Mic vs Speaker Loopback).
    If Channel 1 (Discord) is quieter than Channel 0 (Mic), applies linear gain to
    Channel 1 to equalize perceived loudness without digital clipping (np.clip to -0.98, 0.98).
    Also ensures Channel 0 (Mic) is comfortably normalized within headroom.
    Overwrites the WAV file safely and returns the audio path.
    """
    if not audio_path:
        return ""

    p = Path(audio_path)
    if not p.is_file() or p.suffix.lower() != ".wav":
        return str(audio_path)

    try:
        import soundfile as sf
        data, sr = sf.read(str(p), dtype="float32")

        if data.ndim != 2 or data.shape[1] < 2 or data.shape[0] < 160:
            # Single channel or empty file, skip dual-channel normalization
            return str(audio_path)

        gate = 0.005  # Noise gate threshold for active speech detection
        mask_mic = np.abs(data[:, 0]) > gate
        mask_spk = np.abs(data[:, 1]) > gate

        active_mic = data[mask_mic, 0]
        active_spk = data[mask_spk, 1]

        rms_mic = float(np.sqrt(np.mean(active_mic ** 2))) if len(active_mic) > 100 else 0.0
        rms_spk = float(np.sqrt(np.mean(active_spk ** 2))) if len(active_spk) > 100 else 0.0

        modified = False

        # If both have active speech detected
        if rms_spk > 0.001 and rms_mic > 0.001:
            if rms_spk < rms_mic:
                # Discord is quieter than mic -> boost Discord up to 6.0x
                ratio = min(6.0, rms_mic / rms_spk)
                if ratio > 1.05:
                    data[:, 1] = np.clip(data[:, 1] * ratio, -0.98, 0.98)
                    modified = True
                    print(
                        f"[AudioRecorder] Normalization: Boosted Discord channel by {ratio:.2f}x "
                        f"(RMS: {rms_spk:.4f} -> {rms_spk * ratio:.4f}, Mic RMS: {rms_mic:.4f})"
                    )
            elif rms_mic < (rms_spk * 0.5):
                # Mic is exceptionally quieter than Discord -> boost Mic up to 3.0x
                ratio = min(3.0, (rms_spk * 0.8) / rms_mic)
                if ratio > 1.05:
                    data[:, 0] = np.clip(data[:, 0] * ratio, -0.98, 0.98)
                    modified = True
                    print(
                        f"[AudioRecorder] Normalization: Boosted Mic channel by {ratio:.2f}x "
                        f"(RMS: {rms_mic:.4f} -> {rms_mic * ratio:.4f}, Discord RMS: {rms_spk:.4f})"
                    )
        elif rms_spk > 0.001 and rms_mic <= 0.001:
            # Discord had audio but mic was essentially silent; normalize Discord to target RMS if quiet
            if rms_spk < target_rms:
                ratio = min(4.0, target_rms / rms_spk)
                if ratio > 1.05:
                    data[:, 1] = np.clip(data[:, 1] * ratio, -0.98, 0.98)
                    modified = True

        # Safety: clip any excessive peaks to -0.98, 0.98
        max_peak = float(np.max(np.abs(data)))
        if max_peak > 0.98:
            data = np.clip(data, -0.98, 0.98)
            modified = True

        if modified:
            # Atomic rewrite
            tmp_path = str(p.with_suffix(".norm_tmp.wav"))
            sf.write(tmp_path, data, sr, subtype="PCM_16")
            os.replace(tmp_path, str(p))

    except Exception as exc:
        print(f"[AudioRecorder] Normalization warning on '{audio_path}': {exc}")

    return str(audio_path)


class DualChannelAudioRecorder:
    """
    Captures dual-channel audio on Windows using independent reader threads (producer-consumer):
    - Channel 1 (Left): Selected / Default Microphone (local player)
    - Channel 2 (Right): Selected / Default Speaker Loopback (Discord / other players / DM)
    Streams directly to disk in PCM_16 WAV format at 16,000 Hz with queue buffering
    and automatic reconnection against transient WASAPI/hardware glitches.
    """

    def __init__(self, samplerate: int = 16000, blocksize: int = 1600):
        self.samplerate = samplerate
        self.blocksize = blocksize  # 0.1s at 16kHz
        self._is_recording = False
        self._mode = "roleplay"
        self._mic_id: Optional[str] = None
        self._speaker_id: Optional[str] = None
        self._gain_mic: float = 1.0
        self._gain_spk: float = 1.0
        self._latest_mic_rms = 0.0
        self._latest_spk_rms = 0.0
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_time = 0.0
        self._frames_written = 0
        self._file_path: Optional[str] = None
        self._speaking_log: List[Dict[str, Any]] = []
        self._loopback_active = False
        self._last_error: Optional[str] = None
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
    def gain_mic(self) -> float:
        return self._gain_mic

    @property
    def gain_spk(self) -> float:
        return self._gain_spk

    @property
    def latest_mic_rms(self) -> float:
        return self._latest_mic_rms

    @property
    def latest_spk_rms(self) -> float:
        return self._latest_spk_rms

    @property
    def loopback_active(self) -> bool:
        return self._loopback_active

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def duration_seconds(self) -> float:
        with self._lock:
            if not self._is_recording:
                return 0.0
            if self._frames_written > 0:
                return round(self._frames_written / self.samplerate, 1)
            return round(time.time() - self._start_time, 1)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            duration = (
                round(self._frames_written / self.samplerate, 1)
                if (self._is_recording and self._frames_written > 0)
                else (round(time.time() - self._start_time, 1) if self._is_recording else 0.0)
            )
            return {
                "is_recording": self._is_recording,
                "mode": self._mode,
                "duration_seconds": duration,
                "file_path": self._file_path,
                "mic_id": self._mic_id,
                "speaker_id": self._speaker_id,
                "gain_mic": round(self._gain_mic, 2),
                "gain_spk": round(self._gain_spk, 2),
                "mic_rms": round(self._latest_mic_rms, 5),
                "speaker_rms": round(self._latest_spk_rms, 5),
                "loopback_active": self._loopback_active,
                "error": self._last_error,
            }

    def start(
        self,
        output_path: Optional[str] = None,
        mode: str = "roleplay",
        mic_id: Optional[str] = None,
        speaker_id: Optional[str] = None,
        gain_mic: float = 1.0,
        gain_spk: float = 1.0,
    ) -> str:
        """
        Start recording audio in a background thread.
        - mode='roleplay': Dual-channel (Mic Left + Speaker Loopback Right) for D&D/Discord.
        - mode='class': Single-channel (Microphone ONLY, Mono 16kHz) for in-person university lectures.

        :param output_path: Optional file path for the .wav output.
        :param mode: 'roleplay' or 'class'.
        :param mic_id: Optional physical microphone device ID.
        :param speaker_id: Optional playback speaker/headphone device ID for loopback.
        :param gain_mic: Software volume multiplier for microphone (0.1 to 5.0).
        :param gain_spk: Software volume multiplier for loopback/Discord (0.1 to 10.0).
        :return: The path to the WAV file being recorded.
        """
        with self._lock:
            if self._is_recording:
                raise RuntimeError("Recording is already in progress.")

            selected_mode = (mode or "roleplay").lower().strip()
            self._mode = "class" if selected_mode == "class" else "roleplay"
            self._mic_id = mic_id
            self._speaker_id = speaker_id
            self._gain_mic = max(0.1, min(5.0, float(gain_mic if gain_mic is not None else 1.0)))
            self._gain_spk = max(0.1, min(10.0, float(gain_spk if gain_spk is not None else 1.0)))
            self._latest_mic_rms = 0.0
            self._latest_spk_rms = 0.0
            self._frames_written = 0
            self._loopback_active = False
            self._last_error = None

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
        """
        Multi-threaded producer-consumer audio worker.
        Runs separate capture threads for microphone and speaker loopback into queues,
        preventing WASAPI buffer underruns, choppiness, and silent session aborts.
        """
        import queue
        import warnings

        try:
            import soundcard as sc
            import soundfile as sf
        except ImportError as exc:
            self._is_recording = False
            self._last_error = "soundcard/soundfile not installed"
            raise ImportError(
                "soundcard and soundfile are required for audio recording. "
                "Please run 'pip install soundcard soundfile'."
            ) from exc

        # Suppress benign SoundcardRuntimeWarning (discontinuity warnings handled by queues)
        warnings.filterwarnings("ignore", category=UserWarning)

        mic = _resolve_microphone(mic_id)
        if mic is None:
            err = "No microphone device could be acquired for recording."
            print(f"[AudioRecorder] {err}")
            self._last_error = err
            self._is_recording = False
            return

        # -------------------------------------------------------------
        # Mode 1: Class (Mono microphone only)
        # -------------------------------------------------------------
        if mode == "class":
            mic_q: queue.Queue = queue.Queue(maxsize=150)

            def _class_mic_reader():
                retries = 0
                while not self._stop_event.is_set():
                    try:
                        cur_mic = mic
                        with cur_mic.recorder(samplerate=self.samplerate, channels=1) as m_rec:
                            while not self._stop_event.is_set():
                                chunk = m_rec.record(numframes=self.blocksize)
                                if len(chunk) > 0:
                                    if self._gain_mic != 1.0:
                                        chunk = np.clip(chunk * self._gain_mic, -1.0, 1.0)
                                    try:
                                        mic_q.put_nowait(chunk)
                                    except queue.Full:
                                        try:
                                            mic_q.get_nowait()
                                        except queue.Empty:
                                            pass
                                        mic_q.put_nowait(chunk)
                                    rms = float(np.sqrt(np.mean(chunk[:, 0] ** 2)))
                                    self._latest_mic_rms = rms
                    except Exception as exc:
                        if self._stop_event.is_set():
                            break
                        retries += 1
                        time.sleep(0.1)
                        if retries > 10:
                            print(f"[AudioRecorder] Mic reader persistent failure: {exc}")
                            break

            reader_thread = threading.Thread(target=_class_mic_reader, daemon=True, name="ClassMicReader")
            reader_thread.start()

            try:
                with sf.SoundFile(
                    wav_path,
                    mode="w",
                    samplerate=self.samplerate,
                    channels=1,
                    subtype="PCM_16",
                ) as wav_file:
                    while not (self._stop_event.is_set() and mic_q.empty()):
                        try:
                            chunk = mic_q.get(timeout=0.15)
                            wav_file.write(chunk[:, 0])
                            with self._lock:
                                self._frames_written += len(chunk)
                        except queue.Empty:
                            if self._stop_event.is_set():
                                break
                            continue
            except Exception as exc:
                self._last_error = str(exc)
                print(f"[AudioRecorder] Error in class audio recording worker: {exc}")
            finally:
                reader_thread.join(timeout=1.5)
                self._is_recording = False
            return

        # -------------------------------------------------------------
        # Mode 2: Roleplay (Dual-channel: Mic Left + Loopback Right)
        # -------------------------------------------------------------
        loopback = _resolve_speaker_loopback(speaker_id)
        self._loopback_active = loopback is not None

        if not self._loopback_active:
            print("[AudioRecorder] Warning: No speaker loopback device found. Channel 2 will record digital silence.")

        mic_queue: queue.Queue = queue.Queue(maxsize=150)
        spk_queue: queue.Queue = queue.Queue(maxsize=150)

        # Producer 1: Microphone reader thread
        def _roleplay_mic_reader():
            retries = 0
            while not self._stop_event.is_set():
                try:
                    cur_mic = mic
                    with cur_mic.recorder(samplerate=self.samplerate, channels=1) as m_rec:
                        while not self._stop_event.is_set():
                            data = m_rec.record(numframes=self.blocksize)
                            if len(data) > 0:
                                if self._gain_mic != 1.0:
                                    data = np.clip(data * self._gain_mic, -1.0, 1.0)
                                try:
                                    mic_queue.put_nowait(data)
                                except queue.Full:
                                    try:
                                        mic_queue.get_nowait()
                                    except queue.Empty:
                                        pass
                                    mic_queue.put_nowait(data)
                                rms = float(np.sqrt(np.mean(data[:, 0] ** 2)))
                                self._latest_mic_rms = rms
                except Exception as exc:
                    if self._stop_event.is_set():
                        break
                    retries += 1
                    time.sleep(0.1)
                    if retries > 10:
                        print(f"[AudioRecorder] Mic capture failed after retries: {exc}")
                        break

        # Producer 2: Speaker loopback reader thread
        def _roleplay_spk_reader():
            retries = 0
            while not self._stop_event.is_set():
                if loopback is None:
                    # Synthesize periodic silence chunks if no loopback device exists
                    time.sleep(self.blocksize / self.samplerate)
                    silence = np.zeros((self.blocksize, 1), dtype=np.float32)
                    try:
                        spk_queue.put_nowait(silence)
                    except queue.Full:
                        pass
                    continue

                try:
                    cur_loop = loopback
                    with cur_loop.recorder(samplerate=self.samplerate, channels=1) as s_rec:
                        while not self._stop_event.is_set():
                            data = s_rec.record(numframes=self.blocksize)
                            if len(data) > 0:
                                if self._gain_spk != 1.0:
                                    data = np.clip(data * self._gain_spk, -1.0, 1.0)
                                try:
                                    spk_queue.put_nowait(data)
                                except queue.Full:
                                    try:
                                        spk_queue.get_nowait()
                                    except queue.Empty:
                                        pass
                                    spk_queue.put_nowait(data)
                                rms = float(np.sqrt(np.mean(data[:, 0] ** 2)))
                                self._latest_spk_rms = rms
                except Exception as exc:
                    if self._stop_event.is_set():
                        break
                    retries += 1
                    time.sleep(0.1)
                    if retries > 10:
                        print(f"[AudioRecorder] Speaker loopback capture failed after retries: {exc}")
                        # Fallback to silence chunks
                        while not self._stop_event.is_set():
                            time.sleep(self.blocksize / self.samplerate)
                            silence = np.zeros((self.blocksize, 1), dtype=np.float32)
                            try:
                                spk_queue.put_nowait(silence)
                            except queue.Full:
                                pass
                        break

        mic_t = threading.Thread(target=_roleplay_mic_reader, daemon=True, name="RoleplayMicReader")
        spk_t = threading.Thread(target=_roleplay_spk_reader, daemon=True, name="RoleplaySpkReader")
        mic_t.start()
        spk_t.start()

        # Consumer: Pull from both queues, align frame counts, write stereo to disk
        try:
            with sf.SoundFile(
                wav_path,
                mode="w",
                samplerate=self.samplerate,
                channels=2,
                subtype="PCM_16",
            ) as wav_file:
                while not (self._stop_event.is_set() and mic_queue.empty() and spk_queue.empty()):
                    c_mic = None
                    c_spk = None

                    try:
                        c_mic = mic_queue.get(timeout=0.15)
                    except queue.Empty:
                        pass

                    try:
                        c_spk = spk_queue.get(timeout=0.15)
                    except queue.Empty:
                        pass

                    # If stopped and both queues drained, exit cleanly
                    if c_mic is None and c_spk is None:
                        if self._stop_event.is_set():
                            break
                        continue

                    # If one channel timed out, fill with digital silence to maintain sync
                    if c_mic is None:
                        c_mic = np.zeros((len(c_spk) if c_spk is not None else self.blocksize, 1), dtype=np.float32)
                    if c_spk is None:
                        c_spk = np.zeros((len(c_mic), 1), dtype=np.float32)

                    n_frames = min(len(c_mic), len(c_spk))
                    if n_frames > 0:
                        stereo_chunk = np.column_stack((c_mic[:n_frames, 0], c_spk[:n_frames, 0]))
                        wav_file.write(stereo_chunk)
                        with self._lock:
                            self._frames_written += n_frames
        except Exception as exc:
            self._last_error = str(exc)
            print(f"[AudioRecorder] Error in roleplay audio recording worker: {exc}")
        finally:
            mic_t.join(timeout=1.5)
            spk_t.join(timeout=1.5)
            self._is_recording = False


# Global singleton instance for the API server
active_recorder = DualChannelAudioRecorder()


def get_audio_levels(
    mic_id: Optional[str] = None,
    speaker_id: Optional[str] = None,
    sample_frames: int = 1600,
    gain_mic: float = 1.0,
    gain_spk: float = 1.0,
) -> Dict[str, Any]:
    """
    Sample audio levels from the selected microphone and speaker loopback.
    If recording is actively running, returns the live streaming RMS levels.
    If idle, captures a brief ~100ms sample to calculate current RMS levels scaled by gain.
    """
    g_mic = max(0.1, min(5.0, float(gain_mic if gain_mic is not None else 1.0)))
    g_spk = max(0.1, min(10.0, float(gain_spk if gain_spk is not None else 1.0)))

    if active_recorder.is_recording:
        return {
            "mic_rms": round(active_recorder.latest_mic_rms, 5),
            "speaker_rms": round(active_recorder.latest_spk_rms, 5),
            "is_recording": True,
            "duration_seconds": active_recorder.duration_seconds,
            "loopback_active": active_recorder.loopback_active,
            "gain_mic": round(active_recorder.gain_mic, 2),
            "gain_spk": round(active_recorder.gain_spk, 2),
        }

    mic_rms = 0.0
    spk_rms = 0.0

    # Non-blocking lock to prevent overlapping test-level polls from contending over the hardware
    if not _test_lock.acquire(blocking=False):
        return {
            "mic_rms": 0.0,
            "speaker_rms": 0.0,
            "is_recording": False,
            "gain_mic": round(g_mic, 2),
            "gain_spk": round(g_spk, 2),
        }

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

    # Scale RMS levels by software gain multipliers
    scaled_mic_rms = min(1.0, mic_rms * g_mic)
    scaled_spk_rms = min(1.0, spk_rms * g_spk)

    return {
        "mic_rms": round(scaled_mic_rms, 5),
        "speaker_rms": round(scaled_spk_rms, 5),
        "is_recording": False,
        "gain_mic": round(g_mic, 2),
        "gain_spk": round(g_spk, 2),
    }
