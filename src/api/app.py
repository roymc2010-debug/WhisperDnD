"""FastAPI application alias for src.api.server."""

from src.api.server import (
    app,
    serve_index,
    transcribe_youtube,
    transcribe_file,
    export_to_drive,
    YouTubeTranscribeRequest,
    TranscribeResponse,
    DriveExportRequest,
    DriveExportResponse,
)

__all__ = [
    "app",
    "serve_index",
    "transcribe_youtube",
    "transcribe_file",
    "export_to_drive",
    "YouTubeTranscribeRequest",
    "TranscribeResponse",
    "DriveExportRequest",
    "DriveExportResponse",
]
