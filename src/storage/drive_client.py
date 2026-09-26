"""Google Drive storage client for uploading transcripts and chronicles."""

import io
import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES: List[str] = ["https://www.googleapis.com/auth/drive.file"]
DEFAULT_FOLDER_NAME: str = "Whisper AI - Transcripciones"


_active_oauth_flows: Dict[str, Any] = {}
_active_oauth_flow: Optional[Any] = None


def _get_default_redirect_uri() -> str:
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        return f"{render_url.rstrip('/')}/oauth2callback"
    return "http://localhost:8080/api/auth/drive/callback"


def ensure_google_credentials_file(
    explicit_path: Optional[Path] = None,
    project_root: Optional[Path] = None,
) -> Path:
    """
    Ensure Google credentials.json exists on disk.
    If missing, checks GOOGLE_CREDENTIALS_JSON environment variable and writes it physically.
    Supports Render Docker (/app/credentials.json), local project root, and secret mounts.
    """
    if explicit_path and explicit_path.is_file():
        return explicit_path

    root = project_root or Path(__file__).resolve().parent.parent.parent
    local_path = root / "credentials.json"
    app_path = Path("/app/credentials.json")

    # If running in Docker or Linux, prefer /app/credentials.json if it exists
    if app_path.is_file():
        return app_path
    if local_path.is_file():
        return local_path

    # Check common secret mount paths on Render
    render_secret = Path("/etc/secrets/credentials.json")
    if render_secret.is_file():
        return render_secret

    # Check environment variable GOOGLE_CREDENTIALS_JSON
    env_creds = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if env_creds and env_creds.strip():
        # Prefer /app/credentials.json in Linux/container if /app exists or is current dir
        if os.name != "nt" and (Path("/app").is_dir() or str(root).startswith("/app")):
            target_path = app_path
        else:
            target_path = explicit_path or local_path

        try:
            os.makedirs(os.path.dirname(str(target_path)), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(env_creds.strip())
            print(f"Archivo {target_path} generado con éxito desde variable de entorno.")
            # Also write to local_path if distinct
            if target_path != local_path and not local_path.is_file():
                try:
                    os.makedirs(os.path.dirname(str(local_path)), exist_ok=True)
                    with open(local_path, "w", encoding="utf-8") as f:
                        f.write(env_creds.strip())
                except Exception:
                    pass
            return target_path
        except Exception as e:
            print(f"Error escribiendo credentials.json: {e}")

    return explicit_path or (app_path if (os.name != "nt" and Path("/app").is_dir()) else local_path)


def ensure_google_token_file(
    explicit_path: Optional[Path] = None,
    project_root: Optional[Path] = None,
) -> Path:
    """
    Ensure Google token.json exists on disk.
    If missing, checks GOOGLE_TOKEN_JSON environment variable and writes it physically.
    """
    if explicit_path and explicit_path.is_file():
        return explicit_path

    root = project_root or Path(__file__).resolve().parent.parent.parent
    local_path = root / "token.json"
    app_path = Path("/app/token.json")

    if app_path.is_file():
        return app_path
    if local_path.is_file():
        return local_path

    render_token = Path("/etc/secrets/token.json")
    if render_token.is_file():
        return render_token

    env_token = os.environ.get("GOOGLE_TOKEN_JSON")
    if env_token and env_token.strip():
        target_path = app_path if (os.name != "nt" and (Path("/app").is_dir() or str(root).startswith("/app"))) else local_path
        if explicit_path:
            target_path = explicit_path

        try:
            os.makedirs(os.path.dirname(str(target_path)), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(env_token.strip())
            print(f"Archivo {target_path} generado con éxito desde variable de entorno.")
            return target_path
        except Exception as e:
            print(f"Error escribiendo token.json: {e}")

    return explicit_path or (app_path if (os.name != "nt" and Path("/app").is_dir()) else local_path)


class GoogleDriveStorage:
    """Client for authenticating with Google Drive OAuth and uploading files."""

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        token_path: Optional[str] = None,
    ):
        project_root = Path(__file__).resolve().parent.parent.parent
        explicit_creds = Path(credentials_path) if credentials_path else None
        self.credentials_path = ensure_google_credentials_file(explicit_creds, project_root)

        explicit_token = Path(token_path) if token_path else None
        self.token_path = ensure_google_token_file(explicit_token, project_root)
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
        Upload or update a file in the specified folder in Google Drive.

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
        elif ext == ".json":
            mimetype = "application/json"
        else:
            mimetype, _ = mimetypes.guess_type(str(local_path))
            if not mimetype:
                mimetype = "application/octet-stream"

        media = MediaFileUpload(str(local_path), mimetype=mimetype, resumable=True)
        service = self.service

        # Check if file with same name already exists in destination folder to update rather than duplicate
        escaped_filename = local_path.name.replace("'", "\\'")
        check_q = f"name = '{escaped_filename}' and '{folder_id}' in parents and trashed = false"
        try:
            existing = service.files().list(q=check_q, spaces="drive", fields="files(id, name, webViewLink)").execute().get("files", [])
        except Exception:
            existing = []

        if existing:
            file_id = existing[0]["id"]
            uploaded = service.files().update(
                fileId=file_id,
                media_body=media,
                fields="id, name, webViewLink",
            ).execute()
        else:
            file_metadata = {
                "name": local_path.name,
                "parents": [folder_id],
            }
            uploaded = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id, name, webViewLink",
            ).execute()

        web_link = uploaded.get("webViewLink") or (f"https://drive.google.com/file/d/{uploaded.get('id')}/view" if uploaded.get("id") else "")
        return {
            "file_id": uploaded.get("id", ""),
            "file_name": uploaded.get("name", local_path.name),
            "web_view_link": web_link,
        }

    def download_file_bytes(self, file_id: str) -> bytes:
        """Download binary content of a file from Google Drive."""
        service = self.service
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return fh.getvalue()

    def sync_from_google_drive(
        self,
        campaigns_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Bidirectional sync with Google Drive:
        1. Finds app root folder(s) in Google Drive ('WhisperDnD', 'Whisper AI - Transcripciones', etc.).
        2. Recursively searches subfolders for campaign JSONs (.json) and session chronicles / notes (.md, .docx, .txt).
        3. Downloads remote campaign states to local data/campaigns/ and restores them into memory.
        4. Downloads remote notes to local data/output/.
        5. Pushes local campaigns up to Drive if not present in Drive.
        """
        if not self.is_connected():
            return {
                "status": "not_connected",
                "synced_campaigns": 0,
                "synced_notes": 0,
                "message": "Google Drive no está conectado. Inicia sesión con Google Drive primero.",
            }

        project_root = Path(__file__).resolve().parent.parent.parent
        c_dir = campaigns_dir or (project_root / "data" / "campaigns")
        o_dir = output_dir or (project_root / "data" / "output")
        c_dir.mkdir(parents=True, exist_ok=True)
        o_dir.mkdir(parents=True, exist_ok=True)

        service = self.service

        # 1. Locate app folders
        folder_candidates = ["WhisperDnD", DEFAULT_FOLDER_NAME, "Whisper AI - Transcripciones", "WhisperApp"]
        env_folder = os.environ.get("GOOGLE_DRIVE_FOLDER_NAME")
        if env_folder and env_folder not in folder_candidates:
            folder_candidates.insert(0, env_folder)

        found_root_ids: List[str] = []
        seen_ids = set()
        for fname in folder_candidates:
            escaped_name = fname.replace("'", "\\'")
            query = f"name = '{escaped_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            try:
                res = service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
                for item in res.get("files", []):
                    fid = item["id"]
                    if fid not in seen_ids:
                        seen_ids.add(fid)
                        found_root_ids.append(fid)
            except Exception as e:
                print(f"[GoogleDriveStorage] Error searching folder '{fname}': {e}")

        # If none found, create 'WhisperDnD'
        if not found_root_ids:
            try:
                primary_id = self.get_or_create_folder("WhisperDnD")
                found_root_ids.append(primary_id)
            except Exception as e:
                print(f"[GoogleDriveStorage] Could not create primary folder: {e}")

        # 2. Traverse folders recursively to find all files
        drive_files: List[Dict[str, Any]] = []
        folder_queue = list(found_root_ids)
        visited_folders = set(found_root_ids)

        while folder_queue:
            cur_fid = folder_queue.pop(0)
            page_token = None
            while True:
                try:
                    res = service.files().list(
                        q=f"'{cur_fid}' in parents and trashed = false",
                        spaces="drive",
                        fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                        pageToken=page_token,
                        pageSize=100,
                    ).execute()
                    for f in res.get("files", []):
                        if f.get("mimeType") == "application/vnd.google-apps.folder":
                            if f["id"] not in visited_folders:
                                visited_folders.add(f["id"])
                                folder_queue.append(f["id"])
                        else:
                            drive_files.append(f)
                    page_token = res.get("nextPageToken")
                    if not page_token:
                        break
                except Exception as e:
                    print(f"[GoogleDriveStorage] Error listing folder '{cur_fid}': {e}")
                    break

        synced_campaign_names: List[str] = []
        downloaded_campaigns = 0
        uploaded_campaigns = 0
        downloaded_notes = 0
        remote_filenames = {f.get("name"): f for f in drive_files if f.get("name")}

        # 3. PULL: Download from Google Drive to local server
        for f in drive_files:
            fname = f.get("name", "")
            fid = f.get("id")
            if not fname or not fid:
                continue

            lower_name = fname.lower()
            if lower_name.endswith(".json"):
                try:
                    content = self.download_file_bytes(fid)
                    data = json.loads(content.decode("utf-8"))
                    if isinstance(data, dict) and (
                        "campaign_name" in data
                        or "campaign_id" in data
                        or "universal_pcs" in data
                        or "sessions" in data
                        or "roster" in data
                    ):
                        local_target = c_dir / fname
                        should_write = True
                        if local_target.is_file():
                            try:
                                local_data = json.loads(local_target.read_text(encoding="utf-8"))
                                local_sess = int(local_data.get("last_session", 0))
                                remote_sess = int(data.get("last_session", 0))
                                if local_sess > remote_sess:
                                    should_write = False
                            except Exception:
                                should_write = True

                        if should_write:
                            local_target.write_bytes(content)
                            downloaded_campaigns += 1
                            c_name = data.get("campaign_name", local_target.stem)
                            if c_name not in synced_campaign_names:
                                synced_campaign_names.append(c_name)
                    else:
                        local_target = o_dir / fname
                        if not local_target.is_file():
                            local_target.write_bytes(content)
                            downloaded_notes += 1
                except Exception as exc:
                    print(f"[GoogleDriveStorage] Error processing json {fname}: {exc}")

            elif lower_name.endswith((".md", ".docx", ".txt")):
                local_target = o_dir / fname
                if not local_target.is_file():
                    try:
                        content = self.download_file_bytes(fid)
                        local_target.write_bytes(content)
                        downloaded_notes += 1
                    except Exception as exc:
                        print(f"[GoogleDriveStorage] Error downloading file {fname}: {exc}")

        # 4. PUSH: Upload local campaigns not yet in Google Drive
        primary_folder = "WhisperDnD"
        for local_json in c_dir.glob("*.json"):
            if local_json.name not in remote_filenames:
                try:
                    self.upload_file(str(local_json.resolve()), folder_name=primary_folder)
                    uploaded_campaigns += 1
                    if local_json.stem not in synced_campaign_names:
                        synced_campaign_names.append(local_json.stem)
                except Exception as exc:
                    print(f"[GoogleDriveStorage] Error uploading local campaign {local_json.name}: {exc}")

        return {
            "status": "success",
            "synced_campaigns": len(synced_campaign_names),
            "downloaded_campaigns": downloaded_campaigns,
            "uploaded_campaigns": uploaded_campaigns,
            "downloaded_notes": downloaded_notes,
            "campaign_names": synced_campaign_names,
            "synced_notes": downloaded_notes,
            "message": f"Sincronización con Drive completada: {len(synced_campaign_names)} campañas ({downloaded_campaigns} descargadas, {uploaded_campaigns} respaldadas) y {downloaded_notes} notas/documentos sincronizados.",
        }
