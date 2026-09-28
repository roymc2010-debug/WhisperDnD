"""WhisperDnD Client Bridge: Local Discord Voice Activity & Audio Capture Bridge."""

from .discord_bridge import (
    DiscordBridge,
    DiscordIpcClient,
    WASAPIStereoRecorder,
    record_session_with_telemetry,
)

__all__ = [
    "DiscordBridge",
    "DiscordIpcClient",
    "WASAPIStereoRecorder",
    "record_session_with_telemetry",
]
