"""
Isolated Discord Audio Capture using Windows WASAPI Application Loopback.
Captures audio originating strictly from Discord.exe and its child processes,
excluding music from Spotify, YouTube, web browsers, and other system applications.
Requires Windows 10 Build 20348 (Server 2022) or Windows 11.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import platform
import queue
import re
import sys
import threading
import time
from typing import Any, Dict, List, Optional
import uuid

import numpy as np


def is_application_loopback_supported() -> bool:
    """
    Check if the current operating system supports Windows Application Loopback.
    Requires Windows build 20348 (Windows 10 21H2 / Server 2022) or Windows 11.
    """
    if sys.platform != "win32":
        return False
    try:
        ver = sys.getwindowsversion()
        # Windows build 20348 or higher
        return ver.build >= 20348
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Win32 Process Enumeration using Toolhelp32
# ---------------------------------------------------------------------------
TH32CS_SNAPPROCESS = 0x00000002

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def _get_running_processes() -> List[Dict[str, Any]]:
    """Enumerate running Windows processes with PID, parent PID, and executable name."""
    if sys.platform != "win32":
        return []

    kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
    hSnapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if hSnapshot == -1:
        return []

    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)

    results = []
    success = kernel32.Process32FirstW(hSnapshot, ctypes.byref(entry))
    while success:
        results.append({
            "pid": int(entry.th32ProcessID),
            "parent_pid": int(entry.th32ParentProcessID),
            "name": str(entry.szExeFile),
        })
        success = kernel32.Process32NextW(hSnapshot, ctypes.byref(entry))

    kernel32.CloseHandle(hSnapshot)
    return results


def find_discord_pids() -> List[Dict[str, Any]]:
    """
    Find all active Discord processes (Discord.exe, DiscordPTB.exe, DiscordCanary.exe).
    Returns list of process dictionaries.
    """
    procs = _get_running_processes()
    discord_procs = []
    for p in procs:
        lower_name = p["name"].lower()
        if lower_name.startswith("discord") and lower_name.endswith(".exe"):
            discord_procs.append(p)
    return discord_procs


def find_discord_root_pid() -> Optional[int]:
    """
    Identify the root/parent process ID of the Discord process tree.
    In Windows, Discord spawns multiple helper/renderer processes under a root Discord.exe.
    Targeting the root process with PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE
    captures audio rendered by Discord and all of its audio/render workers.
    """
    discord_procs = find_discord_pids()
    if not discord_procs:
        return None

    discord_pids = {p["pid"] for p in discord_procs}

    # Root process is the Discord process whose parent is NOT another Discord process
    for p in discord_procs:
        if p["parent_pid"] not in discord_pids:
            return p["pid"]

    # Fallback: lowest PID among all Discord processes
    return min(p["pid"] for p in discord_procs)


# ---------------------------------------------------------------------------
# Audio Resampling & Downmixing Helper (48kHz Stereo Float -> 16kHz Mono Float)
# ---------------------------------------------------------------------------
def resample_48k_stereo_to_16k_mono(stereo_48k: np.ndarray) -> np.ndarray:
    """
    Convert a 48,000 Hz stereo float32 buffer to 16,000 Hz mono float32.
    Downsampling from 48kHz to 16kHz is an exact 3:1 integer decimation ratio.
    Averages left and right channels to mono, then takes every 3rd sample.
    Returns array of shape (N // 3, 1) in float32.
    """
    if stereo_48k is None or len(stereo_48k) == 0:
        return np.zeros((0, 1), dtype=np.float32)

    # 1. Downmix stereo to mono
    if stereo_48k.ndim == 2 and stereo_48k.shape[1] >= 2:
        mono = 0.5 * (stereo_48k[:, 0] + stereo_48k[:, 1])
    elif stereo_48k.ndim == 2:
        mono = stereo_48k[:, 0]
    else:
        mono = stereo_48k

    # 2. Integer decimation by 3 (48,000 / 3 = 16,000 Hz)
    decimated = mono[::3].astype(np.float32)
    return decimated.reshape(-1, 1)


# ---------------------------------------------------------------------------
# WASAPI COM & Application Loopback Types
# ---------------------------------------------------------------------------
VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK = "VAD\\Process_Loopback"
AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK = 1
PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE = 0

AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_STREAMFLAGS_EVENTCALLBACK = 0x00040000
AUDCLNT_BUFFERFLAGS_SILENT = 0x00000002

class PROCESS_LOOPBACK_PARAMS(ctypes.Structure):
    _fields_ = [
        ("TargetProcessId", wintypes.DWORD),
        ("ProcessLoopbackMode", ctypes.c_uint32),
    ]

class AUDIOCLIENT_ACTIVATION_PARAMS(ctypes.Structure):
    _fields_ = [
        ("ActivationType", ctypes.c_uint32),
        ("ProcessLoopbackParams", PROCESS_LOOPBACK_PARAMS),
    ]

class BLOB(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.ULONG),
        ("pBlobData", ctypes.c_void_p),
    ]

class PROPVARIANT_DUMMY(ctypes.Structure):
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("wReserved1", wintypes.WORD),
        ("wReserved2", wintypes.WORD),
        ("wReserved3", wintypes.WORD),
        ("blob", BLOB),
    ]

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

def _make_guid(s: str) -> GUID:
    u = uuid.UUID(s)
    g = GUID()
    g.Data1 = int.from_bytes(u.bytes_le[0:4], "little")
    g.Data2 = int.from_bytes(u.bytes_le[4:6], "little")
    g.Data3 = int.from_bytes(u.bytes_le[6:8], "little")
    for i in range(8):
        g.Data4[i] = u.bytes_le[8 + i]
    return g

class WAVEFORMATEX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("wFormatTag", wintypes.WORD),
        ("nChannels", wintypes.WORD),
        ("nSamplesPerSec", wintypes.DWORD),
        ("nAvgBytesPerSec", wintypes.DWORD),
        ("nBlockAlign", wintypes.WORD),
        ("wBitsPerSample", wintypes.WORD),
        ("cbSize", wintypes.WORD),
    ]

class WAVEFORMATEXTENSIBLE(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("Format", WAVEFORMATEX),
        ("wValidBitsPerSample", wintypes.WORD),
        ("dwChannelMask", wintypes.DWORD),
        ("SubFormat", GUID),
    ]

def _guid_bytes(s: str) -> bytes:
    return uuid.UUID(s).bytes_le

IID_IAudioClient = _guid_bytes("{1CB9AD4C-DBFA-4c32-B178-C2F568A703b2}")
IID_IAudioCaptureClient = _guid_bytes("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")
IID_IActivateAudioInterfaceCompletionHandler = _guid_bytes("{41d949ab-9862-444a-80f6-c261334da5eb}")
IID_IAgileObject = _guid_bytes("{94ea2b94-e9cc-49e0-c0ff-ee64ca8f5b90}")
IID_IUnknown = _guid_bytes("{00000000-0000-0000-C000-000000000046}")

HRESULT = ctypes.c_long
QueryInterface_proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
AddRef_proto = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)
Release_proto = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)
ActivateCompleted_proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_void_p)

class IActivateAudioInterfaceCompletionHandlerVtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", QueryInterface_proto),
        ("AddRef", AddRef_proto),
        ("Release", Release_proto),
        ("ActivateCompleted", ActivateCompleted_proto),
    ]

class IActivateAudioInterfaceCompletionHandler(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IActivateAudioInterfaceCompletionHandlerVtbl))]

GetActivateResult_proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(HRESULT), ctypes.POINTER(ctypes.c_void_p))

class IActivateAudioInterfaceAsyncOperationVtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", QueryInterface_proto),
        ("AddRef", AddRef_proto),
        ("Release", Release_proto),
        ("GetActivateResult", GetActivateResult_proto),
    ]

class IActivateAudioInterfaceAsyncOperation(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IActivateAudioInterfaceAsyncOperationVtbl))]

Initialize_proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_int, wintypes.DWORD, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p)
SetEventHandle_proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, wintypes.HANDLE)
GetService_proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p))
Start_proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p)
Stop_proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p)

class IAudioClientVtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", ctypes.c_void_p),
        ("AddRef", ctypes.c_void_p),
        ("Release", ctypes.c_void_p),
        ("Initialize", Initialize_proto),
        ("GetBufferSize", ctypes.c_void_p),
        ("GetStreamLatency", ctypes.c_void_p),
        ("GetCurrentPadding", ctypes.c_void_p),
        ("IsFormatSupported", ctypes.c_void_p),
        ("GetMixFormat", ctypes.c_void_p),
        ("GetDevicePeriod", ctypes.c_void_p),
        ("Start", Start_proto),
        ("Stop", Stop_proto),
        ("Reset", ctypes.c_void_p),
        ("SetEventHandle", SetEventHandle_proto),
        ("GetService", GetService_proto),
    ]

class IAudioClient(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IAudioClientVtbl))]

GetBuffer_proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT), ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64))
ReleaseBuffer_proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, wintypes.UINT)
GetNextPacketSize_proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(wintypes.UINT))

class IAudioCaptureClientVtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", ctypes.c_void_p),
        ("AddRef", ctypes.c_void_p),
        ("Release", ctypes.c_void_p),
        ("GetBuffer", GetBuffer_proto),
        ("ReleaseBuffer", ReleaseBuffer_proto),
        ("GetNextPacketSize", GetNextPacketSize_proto),
    ]

class IAudioCaptureClient(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IAudioCaptureClientVtbl))]


def _release_com(pointer: ctypes.c_void_p) -> None:
    """Release an owned COM interface on its capture thread."""
    if pointer.value:
        vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        Release_proto(vtable[2])(pointer)
        pointer.value = None


# ---------------------------------------------------------------------------
# DiscordAudioCapture: Life-cycle Manager
# ---------------------------------------------------------------------------
class DiscordAudioCapture:
    """
    Manages isolated WASAPI loopback audio capture for the Discord application.
    Continuously delivers 16kHz mono audio blocks (default 1600 samples = 0.1s).
    If Discord is closed or has not yet initiated audio output, feeds digital silence
    and periodically attempts activation without dropping session synchronization.
    NEVER falls back to global speaker loopback.
    """

    def __init__(self, samplerate: int = 16000, blocksize: int = 1600):
        self.samplerate = samplerate
        self.blocksize = blocksize
        self._is_running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue(maxsize=150)
        self._lock = threading.Lock()

        # State tracking
        self._target_pid: Optional[int] = None
        self._is_capturing = False
        self._status_message = "Esperando a la aplicación Discord..."
        self._latest_rms = 0.0

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._is_capturing

    @property
    def latest_rms(self) -> float:
        with self._lock:
            return self._latest_rms

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "discord_detected": self._target_pid is not None,
                "target_pid": self._target_pid,
                "is_capturing": self._is_capturing,
                "status_message": self._status_message,
                "latest_rms": round(self._latest_rms, 5),
            }

    def start(self) -> None:
        """Start the background Discord audio capture loop."""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._stop_event.clear()
            self._audio_queue = queue.Queue(maxsize=150)
            self._thread = threading.Thread(
                target=self._worker,
                daemon=True,
                name="DiscordAudioCaptureWorker",
            )
            self._thread.start()

    def stop(self) -> None:
        """Stop capture and release all WASAPI COM resources."""
        with self._lock:
            if not self._is_running:
                return
            self._is_running = False
            self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

        with self._lock:
            self._is_capturing = False
            self._latest_rms = 0.0
            self._status_message = "Captura de Discord detenida."

    def get_audio_chunk(self, num_frames: int = 1600, timeout: float = 0.15) -> np.ndarray:
        """
        Retrieve an audio chunk of the requested frame size at 16,000 Hz (mono).
        Blocks up to timeout seconds waiting for the next audio block from Discord.
        If no audio is available (timeout), returns a silent buffer of exact size
        to ensure seamless audio timeline synchronization with the microphone channel.
        """
        try:
            chunk = self._audio_queue.get(timeout=timeout)
            if len(chunk) == num_frames:
                return chunk
            elif len(chunk) > num_frames:
                return chunk[:num_frames]
            else:
                # Pad to exact frame count
                padded = np.zeros((num_frames, 1), dtype=np.float32)
                padded[:len(chunk), 0] = chunk[:, 0]
                return padded
        except queue.Empty:
            return np.zeros((num_frames, 1), dtype=np.float32)

    def _worker(self) -> None:
        """Background thread executing the WASAPI Application Loopback lifecycle."""
        if not is_application_loopback_supported():
            with self._lock:
                self._status_message = "Application Loopback no compatible con esta versión de Windows (se requiere build 20348 o superior)."
            self._feed_silence_until_stopped()
            return

        kernel32 = ctypes.WinDLL("kernel32.dll")
        mmdevapi = ctypes.WinDLL("mmdevapi.dll")
        ole32 = ctypes.oledll.ole32

        # Initialize COM on this worker thread
        try:
            ole32.CoInitializeEx(None, 0)
        except Exception:
            pass

        completion_event = kernel32.CreateEventW(None, False, False, None)
        activated_client = ctypes.c_void_p(0)
        activate_hr = HRESULT(-1)

        def py_QueryInterface(this, riid, ppv):
            if not ppv:
                return -2147024809
            req = ctypes.string_at(riid, 16)
            if req in (IID_IUnknown, IID_IActivateAudioInterfaceCompletionHandler, IID_IAgileObject):
                ctypes.cast(ppv, ctypes.POINTER(ctypes.c_void_p))[0] = this
                return 0
            ctypes.cast(ppv, ctypes.POINTER(ctypes.c_void_p))[0] = None
            return -2147467262

        def py_AddRef(this):
            return 1

        def py_Release(this):
            return 1

        def py_ActivateCompleted(this, async_op_ptr):
            nonlocal activate_hr, activated_client
            if async_op_ptr:
                async_op = ctypes.cast(async_op_ptr, ctypes.POINTER(IActivateAudioInterfaceAsyncOperation))
                hr_result = HRESULT(0)
                client_ptr = ctypes.c_void_p(0)
                hr = async_op.contents.lpVtbl.contents.GetActivateResult(async_op_ptr, ctypes.byref(hr_result), ctypes.byref(client_ptr))
                activate_hr = hr_result
                if hr == 0 and hr_result.value == 0:
                    activated_client = client_ptr
            kernel32.SetEvent(completion_event)
            return 0

        vtbl = IActivateAudioInterfaceCompletionHandlerVtbl(
            QueryInterface=QueryInterface_proto(py_QueryInterface),
            AddRef=AddRef_proto(py_AddRef),
            Release=Release_proto(py_Release),
            ActivateCompleted=ActivateCompleted_proto(py_ActivateCompleted),
        )
        handler = IActivateAudioInterfaceCompletionHandler(lpVtbl=ctypes.pointer(vtbl))

        # Setup 48kHz stereo float format (standard Windows audio engine format)
        wfx = WAVEFORMATEXTENSIBLE()
        wfx.Format.wFormatTag = 0xFFFE
        wfx.Format.nChannels = 2
        wfx.Format.nSamplesPerSec = 48000
        wfx.Format.wBitsPerSample = 32
        wfx.Format.nBlockAlign = (2 * 32) // 8
        wfx.Format.nAvgBytesPerSec = 48000 * wfx.Format.nBlockAlign
        wfx.Format.cbSize = 22
        wfx.wValidBitsPerSample = 32
        wfx.dwChannelMask = 0x3
        wfx.SubFormat = _make_guid("{00000003-0000-0010-8000-00aa00389b71}")

        hAudioEvent = kernel32.CreateEventW(None, False, False, None)

        resample_buffer_48k = np.zeros((0, 2), dtype=np.float32)

        while not self._stop_event.is_set():
            root_pid = find_discord_root_pid()
            with self._lock:
                self._target_pid = root_pid

            if root_pid is None:
                with self._lock:
                    self._is_capturing = False
                    self._latest_rms = 0.0
                    self._status_message = "Esperando a Discord (abre la aplicación Discord para capturar el audio)..."
                # Emit periodic silence chunks to keep buffer fed
                self._feed_silence_chunk()
                time.sleep(0.1)
                continue

            # Attempt activation for the Discord root PID
            with self._lock:
                self._status_message = f"Discord detectado (PID {root_pid}). Conectando con su árbol de audio..."

            params = AUDIOCLIENT_ACTIVATION_PARAMS()
            params.ActivationType = AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK
            params.ProcessLoopbackParams.TargetProcessId = root_pid
            params.ProcessLoopbackParams.ProcessLoopbackMode = PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE

            prop = PROPVARIANT_DUMMY()
            prop.vt = 65
            prop.blob.cbSize = ctypes.sizeof(params)
            prop.blob.pBlobData = ctypes.cast(ctypes.pointer(params), ctypes.c_void_p)

            kernel32.ResetEvent(completion_event)
            activated_client = ctypes.c_void_p(0)
            activate_hr = HRESULT(-1)

            async_op_out = ctypes.c_void_p(0)
            hr_call = mmdevapi.ActivateAudioInterfaceAsync(
                ctypes.c_wchar_p(VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK),
                IID_IAudioClient,
                ctypes.byref(prop),
                ctypes.byref(handler),
                ctypes.byref(async_op_out),
            )

            if hr_call != 0:
                self._report_native_error("activación", hr_call)
                self._feed_silence_chunk()
                time.sleep(0.5)
                continue

            wait_res = kernel32.WaitForSingleObject(completion_event, 1000)
            if wait_res == 0:
                _release_com(async_op_out)
            if wait_res != 0 or activate_hr.value != 0 or not activated_client.value:
                self._report_native_error("espera de activación" if wait_res != 0 else "resultado de activación",
                                          wait_res if wait_res != 0 else activate_hr.value)
                self._feed_silence_chunk()
                time.sleep(0.2)
                continue

            # Activation succeeded: initialize audio client
            pAudioClient = ctypes.cast(activated_client, ctypes.POINTER(IAudioClient))
            hr_init = pAudioClient.contents.lpVtbl.contents.Initialize(
                activated_client,
                AUDCLNT_SHAREMODE_SHARED,
                AUDCLNT_STREAMFLAGS_LOOPBACK | AUDCLNT_STREAMFLAGS_EVENTCALLBACK,
                2000000,
                0,
                ctypes.byref(wfx),
                None,
            )

            if hr_init != 0:
                self._report_native_error("formato de audio", hr_init)
                _release_com(activated_client)
                self._feed_silence_chunk()
                time.sleep(0.5)
                continue

            hr_event = pAudioClient.contents.lpVtbl.contents.SetEventHandle(activated_client, hAudioEvent)
            if hr_event != 0:
                self._report_native_error("evento de audio", hr_event)
                _release_com(activated_client)
                self._feed_silence_chunk()
                time.sleep(0.5)
                continue

            pCaptureClient_ptr = ctypes.c_void_p(0)
            hr_svc = pAudioClient.contents.lpVtbl.contents.GetService(
                activated_client,
                IID_IAudioCaptureClient,
                ctypes.byref(pCaptureClient_ptr),
            )

            if hr_svc != 0 or not pCaptureClient_ptr.value:
                self._report_native_error("servicio de captura", hr_svc)
                _release_com(pCaptureClient_ptr)
                _release_com(activated_client)
                self._feed_silence_chunk()
                time.sleep(0.5)
                continue

            pCaptureClient = ctypes.cast(pCaptureClient_ptr, ctypes.POINTER(IAudioCaptureClient))

            hr_start = pAudioClient.contents.lpVtbl.contents.Start(activated_client)
            if hr_start != 0:
                self._report_native_error("inicio de captura", hr_start)
                _release_com(pCaptureClient_ptr)
                _release_com(activated_client)
                self._feed_silence_chunk()
                time.sleep(0.5)
                continue

            with self._lock:
                self._is_capturing = True
                self._status_message = f"Audio de Discord (aislado) capturándose activamente (PID {root_pid})."

            print(f"[DiscordAudioCapture] Stream WASAPI iniciado con éxito para Discord (PID {root_pid})")

            # Capture stream loop
            try:
                while not self._stop_event.is_set():
                    wait_ret = kernel32.WaitForSingleObject(hAudioEvent, 100)
                    if wait_ret == 0:
                        pData = ctypes.c_void_p(0)
                        numFrames = wintypes.UINT(0)
                        flags = wintypes.DWORD(0)
                        devPos = ctypes.c_uint64(0)
                        qpcPos = ctypes.c_uint64(0)

                        while True:
                            packetSize = wintypes.UINT(0)
                            pCaptureClient.contents.lpVtbl.contents.GetNextPacketSize(pCaptureClient_ptr, ctypes.byref(packetSize))
                            if packetSize.value == 0:
                                break

                            hr_buf = pCaptureClient.contents.lpVtbl.contents.GetBuffer(
                                pCaptureClient_ptr,
                                ctypes.byref(pData),
                                ctypes.byref(numFrames),
                                ctypes.byref(flags),
                                ctypes.byref(devPos),
                                ctypes.byref(qpcPos),
                            )

                            if hr_buf == 0 and numFrames.value > 0:
                                n_f = numFrames.value
                                is_silent = bool(flags.value & AUDCLNT_BUFFERFLAGS_SILENT)

                                if is_silent or not pData.value:
                                    stereo_48k = np.zeros((n_f, 2), dtype=np.float32)
                                else:
                                    float_count = n_f * 2
                                    arr = (ctypes.c_float * float_count).from_address(pData.value)
                                    stereo_48k = np.frombuffer(arr, dtype=np.float32).reshape(-1, 2).copy()

                                pCaptureClient.contents.lpVtbl.contents.ReleaseBuffer(pCaptureClient_ptr, n_f)

                                # Accumulate 48kHz audio and emit in exact 1600-frame 16kHz blocks
                                resample_buffer_48k = np.vstack((resample_buffer_48k, stereo_48k)) if len(resample_buffer_48k) else stereo_48k

                                # 1600 frames at 16kHz = 4800 frames at 48kHz
                                while len(resample_buffer_48k) >= 4800:
                                    block_48k = resample_buffer_48k[:4800]
                                    resample_buffer_48k = resample_buffer_48k[4800:]
                                    mono_16k = resample_48k_stereo_to_16k_mono(block_48k)
                                    rms = float(np.sqrt(np.mean(mono_16k[:, 0] ** 2)))
                                    with self._lock:
                                        self._latest_rms = rms
                                    self._put_queue(mono_16k)
                            else:
                                break
                    else:
                        # Timeout waiting on event: if queue is hungry, emit silence
                        if self._audio_queue.qsize() < 2:
                            self._feed_silence_chunk()

            except Exception as stream_err:
                print(f"[DiscordAudioCapture] Stream error: {stream_err}")
            finally:
                try:
                    pAudioClient.contents.lpVtbl.contents.Stop(activated_client)
                except Exception:
                    pass
                _release_com(pCaptureClient_ptr)
                _release_com(activated_client)
                with self._lock:
                    self._is_capturing = False

        kernel32.CloseHandle(completion_event)
        kernel32.CloseHandle(hAudioEvent)
        ole32.CoUninitialize()

    def _report_native_error(self, stage: str, result: int) -> None:
        with self._lock:
            self._is_capturing = False
            self._latest_rms = 0.0
            self._status_message = f"Error de captura aislada de Discord: {stage} (0x{result & 0xFFFFFFFF:08X})."

    def _feed_silence_chunk(self) -> None:
        """Enqueue a single block of digital silence (1600 samples at 16kHz)."""
        silence = np.zeros((self.blocksize, 1), dtype=np.float32)
        self._put_queue(silence)

    def _feed_silence_until_stopped(self) -> None:
        """Feed periodic silence until stop event is signaled."""
        while not self._stop_event.is_set():
            self._feed_silence_chunk()
            time.sleep(self.blocksize / self.samplerate)

    def _put_queue(self, chunk: np.ndarray) -> None:
        try:
            self._audio_queue.put_nowait(chunk)
        except queue.Full:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                pass
            self._audio_queue.put_nowait(chunk)
