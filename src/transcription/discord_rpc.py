"""Discord Local RPC Speaker Tracker via desktop WebSocket IPC.

Connects to local Discord desktop client via StreamKit client ID (zero developer registration required)
to track real-time voice channel participants and speaking activity.
"""

import asyncio
import json
import logging
from pathlib import Path
import threading
import time
import urllib.request
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("discord_rpc")

STREAMKIT_CLIENT_ID = "207646673902501888"
DISCORD_RPC_ORIGIN = "https://streamkit.discord.com"
RPC_PORTS = range(6463, 6473)
TOKEN_FILE = Path("data/.discord_token.json")


class DiscordRpcTracker:
    """
    Tracks Discord voice channel speaking events using Discord's local desktop RPC WebSocket.
    Runs a non-blocking background worker that records speaking intervals relative
    to an audio recording session.
    """

    def __init__(self, client_id: str = STREAMKIT_CLIENT_ID):
        self.client_id = client_id
        self.ws: Optional[Any] = None
        self.session_start_time: Optional[float] = None
        self.is_tracking: bool = False
        self.users: Dict[str, str] = {}  # user_id -> display_name/username
        self.participants: Dict[str, Dict[str, str]] = {}  # user_id -> {"user_id": str, "username": str, "display_name": str}
        self.channel_name: Optional[str] = None
        self.active_speaking: Dict[str, float] = {}  # user_id -> rel_start_sec
        self.speaking_log: List[Dict[str, Any]] = []  # [{"start": float, "end": float, "speaker": str, "user_id": str}]
        self.current_channel_id: Optional[str] = None

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._connected: bool = False
        self._last_subscribed_channel_id: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        """True if actively connected to local Discord desktop RPC WebSocket."""
        return self._connected

    @property
    def connected(self) -> bool:
        """Alias for is_connected."""
        return self._connected

    def ensure_running(self) -> None:
        """Ensure background WebSocket worker thread is running."""
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="DiscordRpcTracker")
            self._thread.start()

    async def connect(self, timeout: float = 1.5) -> bool:
        """
        Asynchronously ensure the connection is active.
        Waits up to `timeout` seconds for connection to be confirmed.
        """
        self.ensure_running()
        start = time.time()
        while time.time() - start < timeout:
            if self._connected:
                return True
            await asyncio.sleep(0.1)
        return self._connected

    def get_active_participants(self) -> Dict[str, Any]:
        """Return current voice channel state and list of participants."""
        with self._lock:
            return {
                "connected": bool(self._connected and self.current_channel_id),
                "rpc_connected": bool(self._connected),
                "channel_id": self.current_channel_id,
                "channel_name": self.channel_name,
                "participants": list(self.participants.values()),
            }

    def start_session(self, start_time: Optional[float] = None) -> None:
        """Start tracking speaking events relative to session recording start."""
        with self._lock:
            self.session_start_time = start_time if start_time is not None else time.time()
            self.is_tracking = True
            self.speaking_log.clear()
            self.active_speaking.clear()

        # Ensure background connection thread is running
        self.ensure_running()

    def stop_session(self) -> List[Dict[str, Any]]:
        """Stop tracking session, close any active speaking intervals, and return the log."""
        with self._lock:
            if not self.is_tracking:
                return list(self.speaking_log)

            self.is_tracking = False
            now_rel = (time.time() - self.session_start_time) if self.session_start_time else 0.0

            # Close any active open speaking intervals
            for uid, s_start in list(self.active_speaking.items()):
                speaker_name = self.users.get(uid, "Discord")
                self.speaking_log.append({
                    "start": round(s_start, 2),
                    "end": round(max(s_start, now_rel), 2),
                    "speaker": speaker_name,
                    "user_id": uid,
                })
            self.active_speaking.clear()
            return list(self.speaking_log)

    def close(self) -> None:
        """Completely stop background worker thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run_loop(self) -> None:
        """Thread worker running asyncio loop for WebSocket connection."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._connect_and_listen())
        except Exception as exc:
            logger.debug("[DiscordRpcTracker] Worker loop error: %s", exc)
        finally:
            loop.close()

    async def _authenticate(self, ws: Any) -> bool:
        """
        Authenticate with Discord RPC.
        Tries saved access_token first, then falls back to StreamKit OAuth code exchange.
        """
        token = None
        if TOKEN_FILE.is_file():
            try:
                tdata = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
                token = tdata.get("access_token")
            except Exception:
                token = None

        if token:
            nonce = str(uuid.uuid4())
            await ws.send(json.dumps({
                "cmd": "AUTHENTICATE",
                "args": {"access_token": token},
                "nonce": nonce,
            }))
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                msg = json.loads(raw)
                if msg.get("cmd") == "AUTHENTICATE" and msg.get("evt") != "ERROR":
                    return True
            except Exception as e:
                logger.debug("[DiscordRpcTracker] Cached token rejected: %s", e)

        # Fallback: Request AUTHORIZE code with StreamKit scopes
        nonce = str(uuid.uuid4())
        await ws.send(json.dumps({
            "cmd": "AUTHORIZE",
            "args": {"client_id": self.client_id, "scopes": ["rpc"]},
            "nonce": nonce,
        }))
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            msg = json.loads(raw)
            code = msg.get("data", {}).get("code")
            if not code:
                return False

            req = urllib.request.Request(
                "https://streamkit.discord.com/overlay/token",
                data=json.dumps({"code": code}).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                tdata = json.loads(r.read().decode("utf-8"))
                new_token = tdata.get("access_token")
                if new_token:
                    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
                    TOKEN_FILE.write_text(json.dumps(tdata, indent=2), encoding="utf-8")
                    await ws.send(json.dumps({
                        "cmd": "AUTHENTICATE",
                        "args": {"access_token": new_token},
                        "nonce": str(uuid.uuid4()),
                    }))
                    raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                    msg = json.loads(raw)
                    return bool(msg.get("cmd") == "AUTHENTICATE" and msg.get("evt") != "ERROR")
        except Exception as exc:
            logger.debug("[DiscordRpcTracker] OAuth code exchange failed: %s", exc)
        return False

    async def _connect_and_listen(self) -> None:
        """Attempt to connect across ports 6463-6472 and handle Discord RPC events."""
        try:
            import websockets
        except ImportError:
            logger.warning("[DiscordRpcTracker] websockets package not installed. Skipping Discord RPC.")
            return

        while not self._stop_event.is_set():
            ws = None
            connected_port = None
            for port in RPC_PORTS:
                if self._stop_event.is_set():
                    return
                url = f"ws://127.0.0.1:{port}/?v=1&client_id={self.client_id}"
                try:
                    ws = await asyncio.wait_for(
                        websockets.connect(
                            url,
                            origin=DISCORD_RPC_ORIGIN,
                            close_timeout=1.0,
                        ),
                        timeout=1.0,
                    )
                    connected_port = port
                    break
                except Exception:
                    continue

            if not ws:
                with self._lock:
                    self._connected = False
                    self.ws = None
                # Wait 2 seconds before retrying scan
                for _ in range(4):
                    if self._stop_event.is_set():
                        return
                    await asyncio.sleep(0.5)
                continue

            try:
                # 1. Listen for READY dispatch
                raw_ready = await asyncio.wait_for(ws.recv(), timeout=2.0)
                ready_msg = json.loads(raw_ready)
                if ready_msg.get("evt") != "READY":
                    await ws.close()
                    continue

                # 2. Authenticate
                authed = await self._authenticate(ws)
                if not authed:
                    logger.warning("[DiscordRpcTracker] Could not authenticate with local Discord RPC on port %d", connected_port)
                    await ws.close()
                    await asyncio.sleep(3.0)
                    continue

                with self._lock:
                    self.ws = ws
                    self._connected = True
                logger.info("[DiscordRpcTracker] Connected & authenticated to Discord RPC on port %d", connected_port)

                # 3. Subscribe to voice channel select & query current voice channel
                await ws.send(json.dumps({
                    "cmd": "SUBSCRIBE",
                    "evt": "VOICE_CHANNEL_SELECT",
                    "nonce": str(uuid.uuid4()),
                }))
                await ws.send(json.dumps({
                    "cmd": "GET_SELECTED_VOICE_CHANNEL",
                    "nonce": str(uuid.uuid4()),
                }))

                async for raw_msg in ws:
                    if self._stop_event.is_set():
                        break
                    try:
                        msg = json.loads(raw_msg)
                    except Exception:
                        continue

                    cmd = msg.get("cmd")
                    evt = msg.get("evt")
                    data = msg.get("data") or {}

                    if cmd == "GET_SELECTED_VOICE_CHANNEL" or (cmd == "DISPATCH" and evt == "VOICE_CHANNEL_SELECT"):
                        await self._handle_voice_channel_select(ws, data)

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

            except Exception as exc:
                logger.debug("[DiscordRpcTracker] WebSocket connection lost: %s", exc)
            finally:
                with self._lock:
                    self._connected = False
                    self.ws = None
                try:
                    await ws.close()
                except Exception:
                    pass

    async def _handle_voice_channel_select(self, ws: Any = None, data: Optional[Dict[str, Any]] = None) -> None:
        """Process voice channel updates, update participants list and subscribe to speaking events."""
        if data is None and isinstance(ws, dict):
            data = ws
            ws = None
        data = data or {}

        channel_id = data.get("id") or data.get("channel_id")
        channel_name = data.get("name")
        voice_states = data.get("voice_states") or []

        with self._lock:
            if not channel_id:
                # Disconnected from voice channel
                self.current_channel_id = None
                self.channel_name = None
                self.participants.clear()
                self._last_subscribed_channel_id = None
                return

            self.current_channel_id = str(channel_id)
            if channel_name:
                self.channel_name = str(channel_name)
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

        if ws is not None and channel_id and channel_id != getattr(self, "_last_subscribed_channel_id", None):
            self._last_subscribed_channel_id = channel_id
            # Subscribe to SPEAKING and voice state events on this voice channel
            for sub_evt in ("SPEAKING_START", "SPEAKING_STOP", "VOICE_STATE_CREATE", "VOICE_STATE_UPDATE", "VOICE_STATE_DELETE"):
                try:
                    sub_cmd = {
                        "cmd": "SUBSCRIBE",
                        "evt": sub_evt,
                        "args": {"channel_id": channel_id},
                        "nonce": str(uuid.uuid4()),
                    }
                    await ws.send(json.dumps(sub_cmd))
                except Exception as exc:
                    logger.debug("[DiscordRpcTracker] Error subscribing to %s: %s", sub_evt, exc)

    def _handle_voice_state_update(self, data: Dict[str, Any]) -> None:
        """Update participant display name or details when voice state changes."""
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
        """Remove participant when leaving the voice channel."""
        u = (data or {}).get("user") or {}
        uid = str(u.get("id") or (data or {}).get("user_id") or "").strip()
        if uid:
            with self._lock:
                self.participants.pop(uid, None)

    def _handle_speaking_start(self, data: Dict[str, Any]) -> None:
        """Record when a user starts speaking."""
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
        """Record when a user stops speaking."""
        uid = str((data or {}).get("user_id") or "").strip()
        if not uid:
            return

        with self._lock:
            if not self.is_tracking or not self.session_start_time:
                return
            now_rel = max(0.0, time.time() - self.session_start_time)
            if uid in self.active_speaking:
                start_rel = self.active_speaking.pop(uid)
                speaker_name = self.users.get(uid, "Discord")
                self.speaking_log.append({
                    "start": round(start_rel, 2),
                    "end": round(max(start_rel, now_rel), 2),
                    "speaker": speaker_name,
                    "user_id": uid,
                })

    def _handle_speaking_event(self, data: Dict[str, Any]) -> None:
        """Handle real-time user green circle toggle on/off (legacy SPEAKING event)."""
        is_speaking = bool(data.get("speaking"))
        if is_speaking:
            self._handle_speaking_start(data)
        else:
            self._handle_speaking_stop(data)

    @staticmethod
    def match_user_id_in_interval(
        start_sec: float,
        end_sec: float,
        speaking_log: Optional[List[Dict[str, Any]]] = None,
        min_overlap_sec: float = 0.15,
    ) -> Optional[str]:
        """
        Cross-reference segment interval [start_sec, end_sec] against speaking_log.
        Returns the user_id with the highest time overlap during the interval,
        or None if no match exceeds min_overlap_sec.
        """
        if not speaking_log:
            return None

        best_uid = None
        max_overlap = 0.0

        for item in speaking_log:
            spk_start = float(item.get("start", 0.0))
            spk_end = float(item.get("end", spk_start))
            overlap = max(0.0, min(end_sec, spk_end) - max(start_sec, spk_start))
            if overlap > max_overlap:
                max_overlap = overlap
                best_uid = item.get("user_id")

        if max_overlap >= min_overlap_sec and best_uid:
            return str(best_uid)
        return None

    @staticmethod
    def match_speaker_in_interval(
        start_sec: float,
        end_sec: float,
        speaking_log: Optional[List[Dict[str, Any]]] = None,
        min_overlap_sec: float = 0.15,
    ) -> Optional[str]:
        """
        Cross-reference segment interval [start_sec, end_sec] against speaking_log.
        Returns the speaker name with the highest time overlap during the interval,
        or None if no match exceeds min_overlap_sec.
        """
        if not speaking_log:
            return None

        best_speaker = None
        max_overlap = 0.0

        for item in speaking_log:
            spk_start = float(item.get("start", 0.0))
            spk_end = float(item.get("end", spk_start))
            overlap = max(0.0, min(end_sec, spk_end) - max(start_sec, spk_start))
            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = item.get("speaker") or item.get("username") or item.get("display_name")

        if max_overlap >= min_overlap_sec and best_speaker:
            return best_speaker
        return None


# Global singleton instance
discord_tracker = DiscordRpcTracker()

# Module-level helper aliases
match_user_id_in_interval = DiscordRpcTracker.match_user_id_in_interval
match_speaker_in_interval = DiscordRpcTracker.match_speaker_in_interval
