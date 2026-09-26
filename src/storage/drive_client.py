"""Google Drive storage client for uploading transcripts and chronicles."""

import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES: List[str] = ["https://www.googleapis.com/auth/drive.file"]
DEFAULT_FOLDER_NAME: str = "Whisper AI - Transcripciones"


_active_oauth_flows: Dict[str, Any] = {}
_active_oauth_flow: Optional[Any] = None


def _get_default_redirect_uri() -> str:
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        return f"{render_url.rstrip('/')}/oauth2callback"
    return "http://localhost:8080/api/auth/drive/callback"


class GoogleDriveStorage:
    """Client for authenticating with Google Drive OAuth and uploading files."""

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        token_path: Optional[str] = None,
    ):
        project_root = Path(__file__).resolve().parent.parent.parent
        self.credentials_path = Path(credentials_path) if credentials_path else project_root / "credentials.json"
        self.token_path = Path(token_path) if token_path else project_root / "token.json"
        self._service: Optional[Any] = None

    def is_connected(self) -> bool:
        """
        Check if valid Google Drive OAuth token exists without prompting browser login.
        Refreshes expired token if refresh_token is available.
        """
        if not self.token_path.is_file():
            return False

        try:
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            if creds and creds.valid:
                return True
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self.token_path.write_text(creds.to_json(), encoding="utf-8")
                    return True
                except Exception:
                    return False
        except Exception:
            return False

        return False

    @property
    def service(self) -> Any:
        """Lazy-load the authenticated Google Drive v3 service."""
        if self._service is None:
            self._service = self.authenticate()
        return self._service

    def authenticate(self) -> Any:
        """
        Authenticate with Google Drive API using credentials.json and token.json.
        Runs local webserver OAuth flow if token.json is missing or expired.
        """
        creds: Optional[Credentials] = None

        if self.token_path.is_file():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            except Exception as exc:
                print(f"[GoogleDriveStorage] Error loading token.json: {exc}. Starting fresh OAuth flow.")
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as exc:
                    print(f"[GoogleDriveStorage] Error refreshing token: {exc}. Re-running OAuth flow.")
                    creds = None

            if not creds:
                if not self.credentials_path.is_file():
                    raise FileNotFoundError(
                        f"No se encontró el archivo de credenciales de Google OAuth en: {self.credentials_path}. "
                        "Descarga credentials.json desde Google Cloud Console y colócalo en la raíz del proyecto."
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path),
                    SCOPES,
                )
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(creds.to_json(), encoding="utf-8")

        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def get_authorization_url(
        self,
        redirect_uri: Optional[str] = None,
    ) -> str:
        """
        Generate Google OAuth authorization URL for web flow without running a blocking local server.
        Retains the active flow instance so the PKCE code_verifier is preserved for the callback exchange.
        """
        global _active_oauth_flow, _active_oauth_flows
        if not self.credentials_path.is_file():
            raise FileNotFoundError(
                f"No se encontró el archivo de credenciales de Google OAuth en: {self.credentials_path}. "
                "Descarga credentials.json desde Google Cloud Console y colócalo en la raíz del proyecto."
            )

        active_redirect = redirect_uri or _get_default_redirect_uri()
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.credentials_path),
            SCOPES,
            redirect_uri=active_redirect,
        )
        auth_url, state = flow.authorization_url(
            prompt="consent",
            access_type="offline",
            include_granted_scopes="true",
        )
        _active_oauth_flow = flow
        if state:
            _active_oauth_flows[state] = flow
        return auth_url

    def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Credentials:
        """
        Exchange authorization code received in callback for OAuth credentials and save to token.json.
        Reuses the active flow instance to retain the PKCE code_verifier generated during get_authorization_url.
        """
        global _active_oauth_flow, _active_oauth_flows
        if not self.credentials_path.is_file():
            raise FileNotFoundError(
                f"No se encontró el archivo de credenciales de Google OAuth en: {self.credentials_path}."
            )

        active_redirect = redirect_uri or _get_default_redirect_uri()
        flow: Optional[Any] = None
        if state and state in _active_oauth_flows:
            flow = _active_oauth_flows.pop(state)
        elif _active_oauth_flow is not None:
            flow = _active_oauth_flow
            _active_oauth_flow = None
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_path),
                SCOPES,
                redirect_uri=active_redirect,
            )

        flow.fetch_token(code=code)
        creds = flow.credentials
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(creds.to_json(), encoding="utf-8")
        self._service = None
        _active_oauth_flow = None
        return creds

    def get_or_create_folder(self, folder_name: str = DEFAULT_FOLDER_NAME) -> str:
        """
        Check if folder exists in the user's Drive; create it if missing.
        Returns the folder ID.
        """
        service = self.service
        # Escape single quotes in folder name
        escaped_name = folder_name.replace("'", "\\'")
        query = f"name = '{escaped_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"

        response = service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name)",
        ).execute()

        files = response.get("files", [])
        if files:
            return files[0]["id"]

        # Create the folder if it doesn't exist
        folder_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = service.files().create(
            body=folder_metadata,
            fields="id, name",
        ).execute()

        return folder["id"]

    def upload_file(
        self,
        file_path: str,
        folder_name: str = DEFAULT_FOLDER_NAME,
    ) -> Dict[str, str]:
        """
        Upload a file to the specified folder in Google Drive.

        :param file_path: Absolute or relative local path to the file.
        :param folder_name: Name of the destination folder in Drive.
        :return: Dict containing file_id, file_name, and web_view_link.
        """
        local_path = Path(file_path).resolve()
        if not local_path.is_file():
            raise FileNotFoundError(f"Archivo a subir no encontrado en: {local_path}")

        folder_id = self.get_or_create_folder(folder_name=folder_name)

        # Detect MIME type
        ext = local_path.suffix.lower()
        if ext == ".docx":
            mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif ext == ".md":
            mimetype = "text/markdown"
        elif ext == ".txt":
            mimetype = "text/plain"
        else:
            mimetype, _ = mimetypes.guess_type(str(local_path))
            if not mimetype:
                mimetype = "application/octet-stream"

        media = MediaFileUpload(str(local_path), mimetype=mimetype, resumable=True)
        file_metadata = {
            "name": local_path.name,
            "parents": [folder_id],
        }

        service = self.service
        uploaded = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink",
        ).execute()

        return {
            "file_id": uploaded.get("id", ""),
            "file_name": uploaded.get("name", local_path.name),
            "web_view_link": uploaded.get("webViewLink", ""),
        }
