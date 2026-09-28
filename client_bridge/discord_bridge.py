"""WhisperDnD Local Discord Voice Activity Bridge for Cloud Render.

Captures stereo audio locally (WASAPI Loopback):
  - Channel 1 (Left): User Microphone
  - Channel 2 (Right): Discord / System Loopback
Collects millisecond-accurate Discord IPC speaking events.
Packages audio + discord_events.json and uploads directly to the WhisperDnD Render cloud backend:
  POST /api/sessions/upload-with-telemetry
"""

import argparse
import asyncio
import datetime
import io
import json
import logging
import os
import platform
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("discord_bridge")

STREAMKIT_CLIENT_ID = "207646673902501888"
DISCORD_RPC_ORIGIN = "https://streamkit.discord.com"
DEFAULT_SERVER_URL = os.environ.get("WHISPERDND_SERVER_URL", "https://whisperdnd.onrender.com")
TOKEN_FILE = Path.home() / ".whisperdnd" / "discord_token.json"


# ---------------------------------------------------------------------------
# Discord IPC Client (Named Pipe & WebSocket)
# ---------------------------------------------------------------------------

class DiscordIpcClient:
    """
    Connects to the local Discord desktop app via:
    1. Windows Named Pipe (\\\\.\\pipe\\discord-ipc-0..9)
    2. Local RPC WebSocket (ws://127.0.0.1:6463..6472)
    Tracks speaking events (SPEAKING_START, SPEAKING_STOP, SPEAKING, VOICE_SETTINGS_UPDATE)
    with millisecond accuracy.
    """

    OP_HANDSHAKE = 0
    OP_FRAME = 1
    OP_CLOSE = 2
    OP_PING = 3
    OP_PONG = 4

    def __init__(self, client_id: str = STREAMKIT_CLIENT_ID):
        self.client_id = client_id
        self.is_connected: bool = False
        self.connection_mode: Optional[str] = None  # "pipe" or "websocket"
        self.current_channel_id: Optional[str] = None
        self.current_channel_name: Optional[str] = None

        # Tracking state
        self.session_start_time: Optional[float] = None
        self.is_tracking: bool = False
        self.participants: Dict[str, Dict[str, str]] = {}  # user_id -> participant_dict
        self.users: Dict[str, str] = {}  # user_id -> display_name
        self.active_speaking: Dict[str, float] = {}  # user_id -> rel_start_sec
        self.speaking_log: List[Dict[str, Any]] = []

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._ws: Optional[Any] = None
        self._pipe: Optional[Any] = None
        self._access_token: Optional[str] = None
        self._last_subscribed_channel_id: Optional[str] = None

        # Load cached token if available
        self._load_cached_token()

    def _load_cached_token(self) -> None:
        try:
            if TOKEN_FILE.is_file():
                data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
                self._access_token = data.get("access_token")
        except Exception:
            self._access_token = None

    def _save_cached_token(self, token_data: Dict[str, Any]) -> None:
        try:
            TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_FILE.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
            self._access_token = token_data.get("access_token")
        except Exception as exc:
            logger.debug("[DiscordIPC] Could not cache token: %s", exc)

    def start(self) -> None:
        """Start background listener thread."""
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="DiscordIpcThread")
            self._thread.start()

    def stop(self) -> None:
        """Stop background listener thread and close connections."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None
        self.is_connected = False

    def start_session(self, start_time: Optional[float] = None) -> None:
        """Start tracking speaking intervals relative to recording start."""
        with self._lock:
            self.session_start_time = start_time if start_time is not None else time.time()
            self.is_tracking = True
            self.speaking_log.clear()
            self.active_speaking.clear()
        self.start()

    def stop_session(self) -> List[Dict[str, Any]]:
        """Stop tracking session, close open speaking intervals, and return the log."""
        with self._lock:
            if not self.is_tracking:
                return list(self.speaking_log)
            self.is_tracking = False
            now_rel = (time.time() - self.session_start_time) if self.session_start_time else 0.0

            # Close any active open speaking intervals
            for uid, s_start in list(self.active_speaking.items()):
                spk_name = self.users.get(uid, "Discord")
                self.speaking_log.append({
                    "start": round(s_start, 3),
                    "end": round(max(s_start, now_rel), 3),
                    "speaker": spk_name,
                    "user_id": uid,
                })
            self.active_speaking.clear()
            return list(self.speaking_log)

    def get_participants_list(self) -> List[Dict[str, str]]:
        with self._lock:
            return list(self.participants.values())

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            active_spk_names = [self.users.get(uid, uid) for uid in self.active_speaking.keys()]
            return {
                "connected": self.is_connected,
                "mode": self.connection_mode,
                "channel_id": self.current_channel_id,
                "channel_name": self.current_channel_name,
                "participants_count": len(self.participants),
                "participants": list(self.participants.values()),
                "active_speakers": active_spk_names,
                "logged_events_count": len(self.speaking_log),
            }

    def _worker_loop(self) -> None:
        """Main connection and reconnection worker loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_async_listener())
        except Exception as exc:
            logger.debug("[DiscordIPC] Worker error: %s", exc)
        finally:
            loop.close()

    async def _run_async_listener(self) -> None:
        """Try Named Pipe first on Windows, fallback to WebSocket."""
        while not self._stop_event.is_set():
            # 1. Try Named Pipe on Windows
            if platform.system() == "Windows":
                pipe_conn = await self._try_connect_named_pipe()
                if pipe_conn:
                    self.connection_mode = "pipe"
                    self.is_connected = True
                    try:
                        await self._listen_named_pipe(pipe_conn)
                    except Exception as e:
                        logger.debug("[DiscordIPC] Named pipe disconnected: %s", e)
                    finally:
                        self.is_connected = False
                        self.connection_mode = None
                        try:
                            pipe_conn.close()
                        except Exception:
                            pass
                    if self._stop_event.is_set():
                        return

            # 2. Try WebSocket (Windows / Linux / macOS)
            ws_conn = await self._try_connect_websocket()
            if ws_conn:
                self.connection_mode = "websocket"
                self.is_connected = True
                try:
                    await self._listen_websocket(ws_conn)
                except Exception as e:
                    logger.debug("[DiscordIPC] WebSocket disconnected: %s", e)
                finally:
                    self.is_connected = False
                    self.connection_mode = None
                    try:
                        await ws_conn.close()
                    except Exception:
                        pass

            # Pause before retrying scan
            for _ in range(6):
                if self._stop_event.is_set():
                    return
                await asyncio.sleep(0.5)

    # -----------------------------------------------------------------------
    # Named Pipe Driver (Windows)
    # -----------------------------------------------------------------------
    async def _try_connect_named_pipe(self) -> Optional[Any]:
        """Scan \\\\.\\pipe\\discord-ipc-0 through 9."""
        for i in range(10):
            pipe_path = f"\\\\.\\pipe\\discord-ipc-{i}"
            try:
                # Open pipe synchronously in binary unbuffered mode
                pipe = open(pipe_path, "r+b", buffering=0)
                # Send Handshake: opcode 0, JSON payload
                handshake_payload = json.dumps({"v": 1, "client_id": self.client_id}).encode("utf-8")
                header = struct.pack("<II", self.OP_HANDSHAKE, len(handshake_payload))
                pipe.write(header + handshake_payload)

                # Read handshake response
                resp_header = pipe.read(8)
                if len(resp_header) == 8:
                    op, length = struct.unpack("<II", resp_header)
                    if op == self.OP_FRAME:
                        raw_data = pipe.read(length).decode("utf-8")
                        msg = json.loads(raw_data)
                        if msg.get("evt") == "READY":
                            logger.info("[DiscordIPC] Connected via Named Pipe: %s", pipe_path)
                            return pipe
                pipe.close()
            except Exception:
                continue
        return None

    async def _pipe_send(self, pipe: Any, cmd: str, args: Dict[str, Any], evt: Optional[str] = None) -> str:
        nonce = str(uuid.uuid4())
        payload_dict: Dict[str, Any] = {"cmd": cmd, "nonce": nonce}
        if args:
            payload_dict["args"] = args
        if evt:
            payload_dict["evt"] = evt
        payload_bytes = json.dumps(payload_dict).encode("utf-8")
        header = struct.pack("<II", self.OP_FRAME, len(payload_bytes))
        pipe.write(header + payload_bytes)
        return nonce

    async def _listen_named_pipe(self, pipe: Any) -> None:
        """Handle incoming frames from Discord Named Pipe."""
        # 1. Authenticate with access_token or authorize
        authed = await self._pipe_authenticate(pipe)
        if not authed:
            logger.warning("[DiscordIPC] Named pipe authentication failed.")
            return

        # 2. Subscribe to voice channel events and query current channel
        await self._pipe_send(pipe, "SUBSCRIBE", {}, evt="VOICE_CHANNEL_SELECT")
        await self._pipe_send(pipe, "SUBSCRIBE", {}, evt="VOICE_SETTINGS_UPDATE")
        await self._pipe_send(pipe, "GET_SELECTED_VOICE_CHANNEL", {})

        loop = asyncio.get_event_loop()
        while not self._stop_event.is_set():
            # Non-blocking read via threadpool
            resp_header = await loop.run_in_executor(None, pipe.read, 8)
            if not resp_header or len(resp_header) < 8:
                break
            op, length = struct.unpack("<II", resp_header)
            if op == self.OP_CLOSE:
                break
            if op == self.OP_PING:
                pong_header = struct.pack("<II", self.OP_PONG, 0)
                pipe.write(pong_header)
                continue
            if op == self.OP_FRAME:
                raw_bytes = await loop.run_in_executor(None, pipe.read, length)
                try:
                    msg = json.loads(raw_bytes.decode("utf-8"))
                    await self._dispatch_message(msg, send_fn=lambda c, a, e=None: self._pipe_send(pipe, c, a, e))
                except Exception as exc:
                    logger.debug("[DiscordIPC] Error processing pipe message: %s", exc)

    async def _pipe_authenticate(self, pipe: Any) -> bool:
        """Authenticate on pipe connection."""
        loop = asyncio.get_event_loop()
        if self._access_token:
            await self._pipe_send(pipe, "AUTHENTICATE", {"access_token": self._access_token})
            resp_header = await loop.run_in_executor(None, pipe.read, 8)
            if len(resp_header) == 8:
                _, length = struct.unpack("<II", resp_header)
                raw = (await loop.run_in_executor(None, pipe.read, length)).decode("utf-8")
                msg = json.loads(raw)
                if msg.get("cmd") == "AUTHENTICATE" and msg.get("evt") != "ERROR":
                    return True

        # Fallback: AUTHORIZE
        await self._pipe_send(pipe, "AUTHORIZE", {"client_id": self.client_id, "scopes": ["rpc"]})
        resp_header = await loop.run_in_executor(None, pipe.read, 8)
        if len(resp_header) == 8:
            _, length = struct.unpack("<II", resp_header)
            raw = (await loop.run_in_executor(None, pipe.read, length)).decode("utf-8")
            msg = json.loads(raw)
            code = msg.get("data", {}).get("code")
            if code:
                new_token = await self._exchange_streamkit_code(code)
                if new_token:
                    await self._pipe_send(pipe, "AUTHENTICATE", {"access_token": new_token})
                    resp_header2 = await loop.run_in_executor(None, pipe.read, 8)
                    if len(resp_header2) == 8:
                        _, length2 = struct.unpack("<II", resp_header2)
                        raw2 = (await loop.run_in_executor(None, pipe.read, length2)).decode("utf-8")
                        msg2 = json.loads(raw2)
                        return bool(msg2.get("cmd") == "AUTHENTICATE" and msg2.get("evt") != "ERROR")
        return False

    # -----------------------------------------------------------------------
    # WebSocket Driver (Cross-Platform)
    # -----------------------------------------------------------------------
    async def _try_connect_websocket(self) -> Optional[Any]:
        """Scan WebSocket ports 6463-6472."""
        try:
            import websockets
        except ImportError:
            logger.debug("[DiscordIPC] websockets library not installed; using named pipe only.")
            return None

        for port in range(6463, 6473):
            if self._stop_event.is_set():
                return None
            url = f"ws://127.0.0.1:{port}/?v=1&client_id={self.client_id}"
            try:
                ws = await asyncio.wait_for(
                    websockets.connect(url, origin=DISCORD_RPC_ORIGIN, close_timeout=1.0),
                    timeout=1.0,
                )
                raw_ready = await asyncio.wait_for(ws.recv(), timeout=2.0)
                ready_msg = json.loads(raw_ready)
                if ready_msg.get("evt") == "READY":
                    logger.info("[DiscordIPC] Connected via WebSocket on port %d", port)
                    return ws
                await ws.close()
            except Exception:
                continue
        return None

    async def _ws_send(self, ws: Any, cmd: str, args: Dict[str, Any], evt: Optional[str] = None) -> str:
        nonce = str(uuid.uuid4())
        payload: Dict[str, Any] = {"cmd": cmd, "nonce": nonce}
        if args:
            payload["args"] = args
        if evt:
            payload["evt"] = evt
        await ws.send(json.dumps(payload))
        return nonce

    async def _listen_websocket(self, ws: Any) -> None:
        """Handle incoming frames from Discord RPC WebSocket."""
        # 1. Authenticate
        authed = await self._ws_authenticate(ws)
        if not authed:
            logger.warning("[DiscordIPC] WebSocket authentication failed.")
            return

        # 2. Subscribe and query
        await self._ws_send(ws, "SUBSCRIBE", {}, evt="VOICE_CHANNEL_SELECT")
        await self._ws_send(ws, "SUBSCRIBE", {}, evt="VOICE_SETTINGS_UPDATE")
        await self._ws_send(ws, "GET_SELECTED_VOICE_CHANNEL", {})

        async for raw_msg in ws:
            if self._stop_event.is_set():
                break
            try:
                msg = json.loads(raw_msg)
                await self._dispatch_message(msg, send_fn=lambda c, a, e=None: self._ws_send(ws, c, a, e))
            except Exception as exc:
                logger.debug("[DiscordIPC] WebSocket dispatch error: %s", exc)

    async def _ws_authenticate(self, ws: Any) -> bool:
        if self._access_token:
            await self._ws_send(ws, "AUTHENTICATE", {"access_token": self._access_token})
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                msg = json.loads(raw)
                if msg.get("cmd") == "AUTHENTICATE" and msg.get("evt") != "ERROR":
                    return True
            except Exception:
                pass

        await self._ws_send(ws, "AUTHORIZE", {"client_id": self.client_id, "scopes": ["rpc"]})
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            msg = json.loads(raw)
            code = msg.get("data", {}).get("code")
            if code:
                new_token = await self._exchange_streamkit_code(code)
                if new_token:
                    await self._ws_send(ws, "AUTHENTICATE", {"access_token": new_token})
                    raw2 = await asyncio.wait_for(ws.recv(), timeout=3.0)
                    msg2 = json.loads(raw2)
                    return bool(msg2.get("cmd") == "AUTHENTICATE" and msg2.get("evt") != "ERROR")
        except Exception as exc:
            logger.debug("[DiscordIPC] OAuth exchange error: %s", exc)
        return False

    async def _exchange_streamkit_code(self, code: str) -> Optional[str]:
        """Exchange OAuth authorization code for StreamKit token."""
        try:
            loop = asyncio.get_event_loop()

            def _req():
                req = urllib.request.Request(
                    "https://streamkit.discord.com/overlay/token",
                    data=json.dumps({"code": code}).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "WhisperDnD-Bridge/1.0",
                    },
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    return json.loads(r.read().decode("utf-8"))

            tdata = await loop.run_in_executor(None, _req)
            new_token = tdata.get("access_token")
            if new_token:
                self._save_cached_token(tdata)
                return str(new_token)
        except Exception as exc:
            logger.debug("[DiscordIPC] StreamKit token exchange error: %s", exc)
        return None

    # -----------------------------------------------------------------------
    # Event Dispatching & Diarization Logic
    # -----------------------------------------------------------------------
    async def _dispatch_message(self, msg: Dict[str, Any], send_fn: Callable) -> None:
        cmd = msg.get("cmd")
        evt = msg.get("evt")
        data = msg.get("data") or {}

        if cmd == "GET_SELECTED_VOICE_CHANNEL" or (cmd == "DISPATCH" and evt == "VOICE_CHANNEL_SELECT"):
            await self._handle_channel_select(data, send_fn)

        elif cmd == "DISPATCH" and evt in ("VOICE_STATE_CREATE", "VOICE_STATE_UPDATE"):
            self._handle_voice_state_update(data)

        elif cmd == "DISPATCH" and evt == "VOICE_STATE_DELETE":
            self._handle_voice_state_delete(data)

        elif cmd == "DISPATCH" and evt == "SPEAKING_START":
            self._handle_speaking_start(data)

        elif cmd == "DISPATCH" and evt == "SPEAKING_STOP":
            self._handle_speaking_stop(data)

        elif cmd == "DISPATCH" and evt == "SPEAKING":
            self._handle_speaking_event(data)

        elif cmd == "DISPATCH" and evt == "VOICE_SETTINGS_UPDATE":
            logger.debug("[DiscordIPC] VOICE_SETTINGS_UPDATE received: %s", data)

    async def _handle_channel_select(self, data: Dict[str, Any], send_fn: Callable) -> None:
        channel_id = data.get("id") or data.get("channel_id")
        channel_name = data.get("name")
        voice_states = data.get("voice_states") or []

        with self._lock:
            if not channel_id:
                self.current_channel_id = None
                self.current_channel_name = None
                self.participants.clear()
                self._last_subscribed_channel_id = None
                logger.info("[DiscordIPC] Disconnected from voice channel.")
                return

            self.current_channel_id = str(channel_id)
            if channel_name:
                self.current_channel_name = str(channel_name)
            self.participants.clear()

            for vs in voice_states:
                u = vs.get("user") or {}
                uid = str(u.get("id") or "").strip()
                if not uid:
                    continue
                username = str(u.get("username") or "").strip()
                nick = vs.get("nick")
                display_name = str(nick or u.get("global_name") or u.get("display_name") or username).strip()
                best_name = display_name or username or f"User-{uid[:4]}"

                self.users[uid] = best_name
                self.participants[uid] = {
                    "user_id": uid,
                    "username": username or best_name,
                    "display_name": best_name,
                }

            logger.info("[DiscordIPC] Active voice channel: '%s' (%s) with %d participants",
                        self.current_channel_name or "Voice Channel", self.current_channel_id, len(self.participants))

        # Subscribe to channel events
        if channel_id and channel_id != self._last_subscribed_channel_id:
            self._last_subscribed_channel_id = channel_id
            for sub_evt in ("SPEAKING_START", "SPEAKING_STOP", "VOICE_STATE_CREATE", "VOICE_STATE_UPDATE", "VOICE_STATE_DELETE"):
                try:
                    await send_fn("SUBSCRIBE", {"channel_id": channel_id}, sub_evt)
                except Exception as exc:
                    logger.debug("[DiscordIPC] Error subscribing to %s: %s", sub_evt, exc)

    def _handle_voice_state_update(self, data: Dict[str, Any]) -> None:
        vs = data or {}
        u = vs.get("user") or {}
        uid = str(u.get("id") or "").strip()
        if not uid:
            return
        username = str(u.get("username") or "").strip()
        nick = vs.get("nick")
        display_name = str(nick or u.get("global_name") or u.get("display_name") or username).strip()
        best_name = display_name or username or f"User-{uid[:4]}"

        with self._lock:
            self.users[uid] = best_name
            self.participants[uid] = {
                "user_id": uid,
                "username": username or best_name,
                "display_name": best_name,
            }

    def _handle_voice_state_delete(self, data: Dict[str, Any]) -> None:
        uid = str((data or {}).get("user_id") or (data or {}).get("user", {}).get("id") or "").strip()
        if uid:
            with self._lock:
                self.participants.pop(uid, None)

    def _handle_speaking_start(self, data: Dict[str, Any]) -> None:
        uid = str((data or {}).get("user_id") or "").strip()
        if not uid:
            return
        with self._lock:
            if not self.is_tracking or not self.session_start_time:
                return
            now_rel = max(0.0, time.time() - self.session_start_time)
            if uid not in self.active_speaking:
                self.active_speaking[uid] = now_rel

    def _handle_speaking_stop(self, data: Dict[str, Any]) -> None:
        uid = str((data or {}).get("user_id") or "").strip()
        if not uid:
            return
        with self._lock:
            if not self.is_tracking or not self.session_start_time:
                return
            now_rel = max(0.0, time.time() - self.session_start_time)
            if uid in self.active_speaking:
                start_rel = self.active_speaking.pop(uid)
                spk_name = self.users.get(uid, "Discord")
                self.speaking_log.append({
                    "start": round(start_rel, 3),
                    "end": round(max(start_rel, now_rel), 3),
                    "speaker": spk_name,
                    "user_id": uid,
                })

    def _handle_speaking_event(self, data: Dict[str, Any]) -> None:
        is_spk = bool(data.get("speaking"))
        if is_spk:
            self._handle_speaking_start(data)
        else:
            self._handle_speaking_stop(data)


# ---------------------------------------------------------------------------
# WASAPI Stereo Audio Recorder
# ---------------------------------------------------------------------------

class WASAPIStereoRecorder:
    """
    Captures 2-channel stereo audio via Windows WASAPI:
      - Channel 1 (Left): Selected Physical Microphone (User).
      - Channel 2 (Right): Selected Playback Device Loopback (Discord/Headphones).
    Streams directly to a 16-bit PCM WAV at 16,000 Hz.
    """

    def __init__(self, samplerate: int = 16000, blocksize: int = 1600):
        self.samplerate = samplerate
        self.blocksize = blocksize  # 0.1s slices
        self.is_recording: bool = False
        self.output_wav_path: Optional[str] = None
        self.latest_mic_rms: float = 0.0
        self.latest_spk_rms: float = 0.0

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_time: float = 0.0
        self._lock = threading.Lock()

    @staticmethod
    def list_devices() -> Dict[str, List[Dict[str, str]]]:
        """List microphones and playback devices available for loopback."""
        try:
            import soundcard as sc
            mics = [{"id": str(m.id), "name": str(m.name)} for m in sc.all_microphones(include_loopback=False)]
            speakers = [{"id": str(s.id), "name": str(s.name)} for s in sc.all_speakers()]
            return {"microphones": mics, "speakers": speakers}
        except Exception as exc:
            return {"microphones": [], "speakers": [], "error": str(exc)}

    def start(
        self,
        output_path: str,
        mic_id: Optional[str] = None,
        speaker_id: Optional[str] = None,
    ) -> str:
        """Start dual-channel recording in background thread."""
        with self._lock:
            if self.is_recording:
                raise RuntimeError("Recording is already in progress.")
            self.output_wav_path = str(Path(output_path).resolve())
            Path(self.output_wav_path).parent.mkdir(parents=True, exist_ok=True)
            self._stop_event.clear()
            self._start_time = time.time()
            self.is_recording = True

            self._thread = threading.Thread(
                target=self._worker,
                args=(self.output_wav_path, mic_id, speaker_id),
                daemon=True,
                name="WASAPIStereoRecorderThread",
            )
            self._thread.start()
            return self.output_wav_path

    def stop(self) -> str:
        """Stop recording and return completed WAV path."""
        with self._lock:
            if not self.is_recording:
                return self.output_wav_path or ""
            self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        with self._lock:
            self.is_recording = False
            return self.output_wav_path or ""

    def _worker(self, wav_path: str, mic_id: Optional[str], speaker_id: Optional[str]) -> None:
        try:
            import numpy as np
            import soundcard as sc
            import soundfile as sf
        except ImportError as exc:
            self.is_recording = False
            raise RuntimeError(f"Dependencies soundcard, soundfile, and numpy are required: {exc}")

        # 1. Resolve Microphone
        mic = None
        if mic_id:
            try:
                mic = sc.get_microphone(id=mic_id)
            except Exception:
                pass
        if not mic:
            try:
                mic = sc.default_microphone()
            except Exception:
                all_m = sc.all_microphones(include_loopback=False)
                mic = all_m[0] if all_m else None

        # 2. Resolve Speaker Loopback
        loopback = None
        if speaker_id:
            try:
                loopback = sc.get_microphone(id=speaker_id, include_loopback=True)
            except Exception:
                pass
        if not loopback:
            try:
                spk = sc.default_speaker()
                if spk:
                    loopback = sc.get_microphone(id=spk.id, include_loopback=True)
            except Exception:
                pass
        if not loopback:
            for m in sc.all_microphones(include_loopback=True):
                if getattr(m, "isloopback", False):
                    loopback = m
                    break

        if not mic:
            raise RuntimeError("No physical microphone found for recording.")

        # 3. Stream to SoundFile
        try:
            with sf.SoundFile(
                wav_path,
                mode="w",
                samplerate=self.samplerate,
                channels=2,
                subtype="PCM_16",
            ) as sf_file:
                # Open mic and loopback recorder contexts
                with mic.recorder(samplerate=self.samplerate, channels=1, blocksize=self.blocksize) as mic_rec:
                    if loopback:
                        with loopback.recorder(samplerate=self.samplerate, channels=1, blocksize=self.blocksize) as spk_rec:
                            while not self._stop_event.is_set():
                                m_data = mic_rec.record(numframes=self.blocksize)
                                s_data = spk_rec.record(numframes=self.blocksize)

                                # Ensure same length
                                min_len = min(len(m_data), len(s_data))
                                m_slice = m_data[:min_len, 0] if m_data.ndim == 2 else m_data[:min_len]
                                s_slice = s_data[:min_len, 0] if s_data.ndim == 2 else s_data[:min_len]

                                # Stack Channel 1 (Mic Left) and Channel 2 (Discord Right)
                                stereo_frame = np.column_stack((m_slice, s_slice))
                                sf_file.write(stereo_frame)

                                # Update VU levels
                                self.latest_mic_rms = float(np.sqrt(np.mean(m_slice ** 2)))
                                self.latest_spk_rms = float(np.sqrt(np.mean(s_slice ** 2)))
                    else:
                        # Fallback if loopback unavailable: record mic on left, silence on right
                        logger.warning("[WASAPI] Loopback unavailable, recording microphone only.")
                        while not self._stop_event.is_set():
                            m_data = mic_rec.record(numframes=self.blocksize)
                            m_slice = m_data[:, 0] if m_data.ndim == 2 else m_data
                            silence = np.zeros_like(m_slice)
                            stereo_frame = np.column_stack((m_slice, silence))
                            sf_file.write(stereo_frame)
                            self.latest_mic_rms = float(np.sqrt(np.mean(m_slice ** 2)))
                            self.latest_spk_rms = 0.0
        except Exception as exc:
            logger.error("[WASAPI] Recording worker error: %s", exc)
        finally:
            self.is_recording = False


# ---------------------------------------------------------------------------
# Discord Bridge Orchestrator & Uploader
# ---------------------------------------------------------------------------

class DiscordBridge:
    """
    Coordinates local Discord IPC event tracking, WASAPI stereo loopback recording,
    telemetry generation, and uploading to the cloud WhisperDnD server on Render.
    """

    def __init__(
        self,
        server_url: str = DEFAULT_SERVER_URL,
        client_id: str = STREAMKIT_CLIENT_ID,
        output_dir: Optional[str] = None,
    ):
        self.server_url = server_url.rstrip("/")
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "recordings"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.ipc = DiscordIpcClient(client_id=client_id)
        self.recorder = WASAPIStereoRecorder(samplerate=16000)

        self.current_wav_path: Optional[str] = None
        self.current_json_path: Optional[str] = None
        self.session_start_time: float = 0.0

    def start_recording(
        self,
        mic_id: Optional[str] = None,
        speaker_id: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Start both Discord IPC tracking and stereo audio capture."""
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        wav_filename = f"session_bridge_{now_str}.wav"
        json_filename = f"discord_events_{now_str}.json"

        self.current_wav_path = str(self.output_dir / wav_filename)
        self.current_json_path = str(self.output_dir / json_filename)
        self.session_start_time = time.time()

        # 1. Start Discord IPC tracking
        self.ipc.start_session(self.session_start_time)

        # 2. Start WASAPI Audio Recording
        self.recorder.start(
            output_path=self.current_wav_path,
            mic_id=mic_id,
            speaker_id=speaker_id,
        )

        return self.current_wav_path, self.current_json_path

    def stop_recording(self) -> Dict[str, Any]:
        """Stop recording, finalize discord_events.json, and return paths and metadata."""
        # 1. Stop audio recording
        final_wav = self.recorder.stop()

        # 2. Stop Discord tracking and get log
        events = self.ipc.stop_session()
        participants = self.ipc.get_participants_list()
        duration_sec = round(time.time() - self.session_start_time, 2) if self.session_start_time else 0.0

        telemetry_payload = {
            "version": "1.0",
            "generated_by": "WhisperDnD Local Discord Bridge",
            "session_start_time": self.session_start_time,
            "session_start_iso": datetime.datetime.fromtimestamp(self.session_start_time).isoformat() if self.session_start_time else "",
            "duration_seconds": duration_sec,
            "channel_id": self.ipc.current_channel_id,
            "channel_name": self.ipc.current_channel_name,
            "participants": participants,
            "events": events,
            "audio_file": Path(final_wav).name if final_wav else "",
        }

        # Write discord_events.json
        if self.current_json_path:
            Path(self.current_json_path).write_text(
                json.dumps(telemetry_payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        return {
            "wav_path": final_wav,
            "json_path": self.current_json_path,
            "duration": duration_sec,
            "events_count": len(events),
            "participants_count": len(participants),
            "telemetry": telemetry_payload,
        }

    def upload_to_render(
        self,
        wav_path: str,
        events_json_path: str,
        campaign_name: str,
        session_number: Optional[int] = None,
        roster: Optional[List[Dict[str, Any]]] = None,
        roster_json: Optional[str] = None,
        target_language: str = "es",
        recording_mode: str = "roleplay",
        engine: str = "groq",
        gemini_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        timeout: int = 300,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Upload the stereo WAV audio and discord_events.json via multipart POST
        to /api/sessions/upload-with-telemetry on the Render server.
        """
        upload_endpoint = f"{self.server_url}/api/sessions/upload-with-telemetry"
        if on_progress:
            on_progress(f"Enviando audio y telemetría a {upload_endpoint}...")

        wav_file_path = Path(wav_path)
        events_file_path = Path(events_json_path)

        if not wav_file_path.is_file():
            raise FileNotFoundError(f"Audio file '{wav_path}' not found.")
        if not events_file_path.is_file():
            raise FileNotFoundError(f"Telemetry file '{events_json_path}' not found.")

        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        body_bytes = io.BytesIO()

        def _add_field(name: str, value: str):
            body_bytes.write(f"--{boundary}\r\n".encode("utf-8"))
            body_bytes.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
            body_bytes.write(f"{value}\r\n".encode("utf-8"))

        def _add_file(name: str, filename: str, content: bytes, content_type: str):
            body_bytes.write(f"--{boundary}\r\n".encode("utf-8"))
            body_bytes.write(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8"))
            body_bytes.write(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
            body_bytes.write(content)
            body_bytes.write(b"\r\n")

        # 1. Add form metadata
        _add_field("campaign_name", campaign_name)
        if session_number is not None:
            _add_field("session_number", str(session_number))
        if roster:
            _add_field("roster_json", json.dumps(roster, ensure_ascii=False))
        elif roster_json:
            _add_field("roster_json", roster_json)
        _add_field("target_language", target_language)
        _add_field("recording_mode", recording_mode)
        _add_field("engine", engine)
        if gemini_api_key:
            _add_field("gemini_api_key", gemini_api_key)
        if groq_api_key:
            _add_field("groq_api_key", groq_api_key)

        # 2. Add files
        _add_file("events_file", events_file_path.name, events_file_path.read_bytes(), "application/json")
        _add_file("audio_file", wav_file_path.name, wav_file_path.read_bytes(), "audio/wav")

        # Close boundary
        body_bytes.write(f"--{boundary}--\r\n".encode("utf-8"))
        final_payload = body_bytes.getvalue()

        # Headers
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(final_payload)),
            "User-Agent": "WhisperDnD-DiscordBridge/1.0",
        }
        if gemini_api_key:
            headers["X-Gemini-Key"] = gemini_api_key
        if groq_api_key:
            headers["X-Groq-Key"] = groq_api_key

        if on_progress:
            size_mb = round(len(final_payload) / (1024 * 1024), 2)
            on_progress(f"Subiendo {size_mb} MB al servidor... Esto puede tardar unos momentos.")

        req = urllib.request.Request(upload_endpoint, data=final_payload, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                resp_bytes = response.read()
                data = json.loads(resp_bytes.decode("utf-8"))
                if on_progress:
                    on_progress("¡Sesión procesada exitosamente en el servidor de Render!")
                return data
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                detail = err_json.get("detail", err_body)
            except Exception:
                detail = err_body
            raise RuntimeError(f"Error {err.code} del servidor de Render: {detail}") from err
        except Exception as exc:
            raise RuntimeError(f"Error al conectar con {self.server_url}: {exc}") from exc


# ---------------------------------------------------------------------------
# CLI & Terminal Workflow
# ---------------------------------------------------------------------------

def draw_vu_meter(rms: float, width: int = 10) -> str:
    """ASCII VU meter bar for terminal monitoring."""
    level = min(1.0, max(0.0, rms * 15.0))
    filled = int(round(level * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}]"


def record_session_with_telemetry(
    campaign_name: str,
    server_url: str = DEFAULT_SERVER_URL,
    session_number: Optional[int] = None,
    target_language: str = "es",
    recording_mode: str = "roleplay",
    engine: str = "groq",
    mic_id: Optional[str] = None,
    speaker_id: Optional[str] = None,
    output_dir: Optional[str] = None,
    gemini_key: Optional[str] = None,
    groq_key: Optional[str] = None,
    auto_upload: bool = True,
) -> Dict[str, Any]:
    """Interactive console helper to execute the bridge workflow."""
    print("=" * 64)
    print(" 🎲 WhisperDnD - Puente Local de Discord para Cloud Render")
    print("=" * 64)
    print(f" • Servidor Render : {server_url}")
    print(f" • Campaña Destino : {campaign_name}")
    print(f" • Modo / Motor    : {recording_mode.upper()} / {engine.upper()}")
    print("=" * 64)

    bridge = DiscordBridge(server_url=server_url, output_dir=output_dir)

    print("\n[1/4] Conectando con Discord en tu PC...")
    bridge.ipc.start()
    time.sleep(1.2)

    status = bridge.ipc.get_status()
    if status["connected"]:
        mode_str = "Named Pipe" if status["mode"] == "pipe" else "WebSocket RPC"
        print(f"  ✓ Conectado a Discord IPC ({mode_str})")
        ch_name = status["channel_name"] or "Canal de voz no detectado"
        print(f"  ✓ Canal activo: 🔊 \"{ch_name}\"")
        participants = status["participants"]
        print(f"  ✓ Participantes detectados ({len(participants)}):")
        for p in participants:
            print(f"     - {p['display_name']} (@{p['username']}) [ID: {p['user_id']}]")
    else:
        print("  ⚠️ No se detectó Discord en ejecución o llamada activa.")
        print("    (Puedes continuar; el audio estéreo se grabará de todos modos).")

    print("\n[2/4] Preparando dispositivos de audio (WASAPI Loopback)...")
    devices = WASAPIStereoRecorder.list_devices()
    print(f"  ✓ Micrófonos encontrados: {len(devices.get('microphones', []))}")
    print(f"  ✓ Salidas de audio/Loopback: {len(devices.get('speakers', []))}")

    print("\n" + "-" * 64)
    input(" Presiona ENTER para INICIAR la grabación de la sesión D&D... ")
    print("-" * 64)

    wav_path, json_path = bridge.start_recording(mic_id=mic_id, speaker_id=speaker_id)
    print(f"\n🔴 GRABANDO SESIÓN...")
    print(f"   Audio WAV  : {Path(wav_path).name}")
    print(f"   Telemetría : {Path(json_path).name}")
    print("   Presiona ENTER o escribe 'q' + ENTER para DETENER la sesión...\n")

    stop_requested = threading.Event()

    def _wait_for_input():
        try:
            sys.stdin.readline()
        except Exception:
            pass
        stop_requested.set()

    input_thread = threading.Thread(target=_wait_for_input, daemon=True)
    input_thread.start()

    start_t = time.time()
    try:
        while not stop_requested.is_set():
            time.sleep(0.3)
            elapsed = int(time.time() - start_t)
            m, s = divmod(elapsed, 60)
            h, m = divmod(m, 60)
            time_str = f"{h:02d}:{m:02d}:{s:02d}"

            mic_vu = draw_vu_meter(bridge.recorder.latest_mic_rms)
            spk_vu = draw_vu_meter(bridge.recorder.latest_spk_rms)

            ipc_stat = bridge.ipc.get_status()
            speakers = ", ".join(ipc_stat["active_speakers"][:3]) or "Silencio"

            sys.stdout.write(f"\r [REC {time_str}] Mic: {mic_vu} | Discord: {spk_vu} | Hablando: {speakers:<20}")
            sys.stdout.flush()
    except KeyboardInterrupt:
        print("\n[!] Detención solicitada por teclado.")
    finally:
        sys.stdout.write("\n")

    print("\n[3/4] Deteniendo grabación y generando bitácora de telemetría...")
    session_result = bridge.stop_recording()
    print(f"  ✓ Grabación finalizada: {session_result['duration']} s")
    print(f"  ✓ Intervalos de voz registrados: {session_result['events_count']}")
    print(f"  ✓ Archivo de telemetría guardado: {session_result['json_path']}")

    if not auto_upload:
        print("\n[✓] Modo local: Archivos conservados en disco. No se subió al servidor.")
        bridge.ipc.stop()
        return session_result

    print("\n[4/4] Empaquetando y enviando a Render (/api/sessions/upload-with-telemetry)...")
    active_gemini_key = gemini_key or os.environ.get("GEMINI_API_KEY")
    active_groq_key = groq_key or os.environ.get("GROQ_API_KEY")

    try:
        server_res = bridge.upload_to_render(
            wav_path=session_result["wav_path"],
            events_json_path=session_result["json_path"],
            campaign_name=campaign_name,
            session_number=session_number,
            target_language=target_language,
            recording_mode=recording_mode,
            engine=engine,
            gemini_api_key=active_gemini_key,
            groq_api_key=active_groq_key,
            on_progress=lambda msg: print(f"  • {msg}"),
        )
        print("\n" + "=" * 64)
        print(" 🎉 ¡SESIÓN D&D PROCESADA CON ÉXITO EN RENDER!")
        print("=" * 64)
        print(f" • Campaña         : {server_res.get('campaign_name', campaign_name)}")
        print(f" • Sesión N.º      : {server_res.get('session_number', 1)}")
        print(f" • Título          : {server_res.get('session_title', 'Sesión')}")
        print(f" • Eventos Fusionados: {server_res.get('telemetry_events_count', 0)}")
        print(f" • Documento Word  : {server_res.get('docx_filename', '-')}")
        print(f" • Documento MD    : {server_res.get('md_filename', '-')}")
        print("=" * 64)
        return server_res
    except Exception as exc:
        print(f"\n❌ Error al procesar en Render: {exc}")
        print(f"   (Tus archivos locales están seguros en: {session_result['wav_path']})")
        raise
    finally:
        bridge.ipc.stop()


def main():
    parser = argparse.ArgumentParser(
        description="WhisperDnD Local Discord Voice Activity Bridge for Cloud Render"
    )
    parser.add_argument("--campaign", "-c", type=str, default=None, help="Nombre de la campaña D&D en Render")
    parser.add_argument("--server-url", "-s", type=str, default=DEFAULT_SERVER_URL, help="URL base del servidor WhisperDnD en Render")
    parser.add_argument("--session", "-n", type=int, default=None, help="Número de sesión")
    parser.add_argument("--lang", "-l", type=str, default="es", choices=["es", "en"], help="Idioma objetivo")
    parser.add_argument("--mode", "-m", type=str, default="roleplay", choices=["roleplay", "class"], help="Modo de grabación")
    parser.add_argument("--engine", "-e", type=str, default="groq", choices=["groq", "local"], help="Motor de transcripción Whisper")
    parser.add_argument("--gemini-key", type=str, default=None, help="API Key de Gemini (o vía env GEMINI_API_KEY)")
    parser.add_argument("--groq-key", type=str, default=None, help="API Key de Groq (o vía env GROQ_API_KEY)")
    parser.add_argument("--mic", type=str, default=None, help="ID o nombre de dispositivo de micrófono")
    parser.add_argument("--speaker", type=str, default=None, help="ID o nombre de dispositivo de altavoces/auriculares para loopback")
    parser.add_argument("--output-dir", "-o", type=str, default=None, help="Directorio para guardar grabaciones locales")
    parser.add_argument("--list-devices", action="store_true", help="Listar dispositivos de audio y salir")
    parser.add_argument("--test-discord", action="store_true", help="Probar conexión con Discord IPC y salir")
    parser.add_argument("--no-upload", action="store_true", help="Grabar y generar telemetría sin subir al servidor")

    args = parser.parse_args()

    if args.list_devices:
        print("=== Dispositivos de Audio Disponibles ===")
        devs = WASAPIStereoRecorder.list_devices()
        print("\nMicrophones (Entrada):")
        for m in devs.get("microphones", []):
            print(f"  [{m['id']}] {m['name']}")
        print("\nSpeakers / Playback (Loopback):")
        for s in devs.get("speakers", []):
            print(f"  [{s['id']}] {s['name']}")
        return

    if args.test_discord:
        print("Probando conexión a Discord IPC...")
        ipc = DiscordIpcClient()
        ipc.start()
        time.sleep(2.0)
        stat = ipc.get_status()
        print("Estado Discord IPC:", json.dumps(stat, indent=2, ensure_ascii=False))
        ipc.stop()
        return

    camp_name = args.campaign
    if not camp_name:
        try:
            camp_name = input("Introduce el nombre de la campaña D&D en Render: ").strip()
        except KeyboardInterrupt:
            print("\nCancelado.")
            return

    if not camp_name:
        print("Error: Se requiere un nombre de campaña.")
        return

    record_session_with_telemetry(
        campaign_name=camp_name,
        server_url=args.server_url,
        session_number=args.session,
        target_language=args.lang,
        recording_mode=args.mode,
        engine=args.engine,
        mic_id=args.mic,
        speaker_id=args.speaker,
        output_dir=args.output_dir,
        gemini_key=args.gemini_key,
        groq_key=args.groq_key,
        auto_upload=not args.no_upload,
    )


if __name__ == "__main__":
    main()
