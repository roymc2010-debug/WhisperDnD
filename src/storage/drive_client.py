"""Google Drive storage client for uploading transcripts and chronicles."""

import hashlib
import io
import json
import mimetypes
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from src.storage.drive_sync import SyncCheckpoint, coalesce_sync, content_hash
from src.runtime_paths import resolve_runtime_paths, is_desktop_runtime

SCOPES: List[str] = ["https://www.googleapis.com/auth/drive.file"]
DEFAULT_FOLDER_NAME: str = "WhisperDnD"


_active_oauth_flows: Dict[str, Any] = {}
_active_oauth_flow: Optional[Any] = None


def _get_default_redirect_uri() -> str:
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        return f"{render_url.rstrip('/')}/oauth2callback"
    return "http://localhost:8080/api/auth/drive/callback"


def _desktop_client_metadata(text: str) -> Dict[str, Any]:
    """Validate distributable desktop client metadata without exposing its values."""
    try:
        document = json.loads(text)
    except (ValueError, TypeError):
        raise ValueError("La configuración OAuth de escritorio no contiene JSON válido.") from None
    installed = document.get("installed") if isinstance(document, dict) else None
    if not isinstance(installed, dict) or not all(
        isinstance(installed.get(key), str) and installed[key].strip()
        for key in ("client_id", "auth_uri", "token_uri")
    ):
        raise ValueError("Esta instalación requiere configuración OAuth de tipo Aplicación de escritorio.")
    allowed = ("client_id", "project_id", "auth_uri", "token_uri", "auth_provider_x509_cert_url",
               "client_secret", "redirect_uris")
    return {"installed": {key: installed[key] for key in allowed if key in installed}}


def _packaged_credentials_file(resources: Path) -> Path:
    target = resolve_runtime_paths(resource_dir=resources).config_dir / "credentials.json"
    if target.is_file():
        _desktop_client_metadata(target.read_text(encoding="utf-8"))
        return target
    text = os.environ.get("GOOGLE_CREDENTIALS_JSON", "").strip()
    if not text:
        bundled = resources / "oauth" / "drive-desktop.json"
        if bundled.is_file():
            text = bundled.read_text(encoding="utf-8")
    if text:
        metadata = _desktop_client_metadata(text)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return target


def prepare_google_credentials_for_startup(resources: Path) -> Path:
    """Prepare optional packaged Drive config without blocking the rest of the app."""
    target = resolve_runtime_paths(resource_dir=resources).config_dir / "credentials.json"
    try:
        return _packaged_credentials_file(resources)
    except (OSError, ValueError) as exc:
        # Never log configuration contents or silently write an invalid payload.
        print(f"[Drive] Configuración OAuth no disponible al iniciar ({type(exc).__name__}).")
        return target


def ensure_google_credentials_file(
    explicit_path: Optional[Path] = None,
    project_root: Optional[Path] = None,
) -> Path:
    """
    Ensure Google credentials.json exists on disk.
    If missing, checks GOOGLE_CREDENTIALS_JSON environment variable and writes it physically.
    Packaged Windows uses per-user config and approved desktop client metadata.
    Development retains project roots, Render Docker and secret mount behavior.
    """
    if explicit_path is not None:
        return explicit_path

    if is_desktop_runtime():
        resources = project_root if project_root is not None else Path(__file__).resolve().parent.parent.parent
        return _packaged_credentials_file(resources)

    if project_root is not None:
        local_path = project_root / "credentials.json"
        if local_path.is_file():
            return local_path
        env_creds = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if env_creds and env_creds.strip():
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(env_creds.strip(), encoding="utf-8")
            print(f"Archivo {local_path} generado con éxito desde variable de entorno.")
        return local_path

    root = Path(__file__).resolve().parent.parent.parent
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
            target_path = local_path

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

    return app_path if (os.name != "nt" and Path("/app").is_dir()) else local_path


def ensure_google_token_file(
    explicit_path: Optional[Path] = None,
    project_root: Optional[Path] = None,
) -> Path:
    """
    Ensure Google token.json exists on disk.
    If missing, checks GOOGLE_TOKEN_JSON environment variable and writes it physically.
    """
    if explicit_path is not None:
        return explicit_path

    if is_desktop_runtime():
        resources = project_root if project_root is not None else Path(__file__).resolve().parent.parent.parent
        project_root = resolve_runtime_paths(resource_dir=resources).config_dir

    if project_root is not None:
        local_path = project_root / "token.json"
        backup_path = project_root / "token_backup.json"
        if local_path.is_file():
            # Keep backup synchronized
            try:
                if not backup_path.is_file():
                    backup_path.write_text(local_path.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                pass
            return local_path
        if backup_path.is_file():
            try:
                local_path.write_text(backup_path.read_text(encoding="utf-8"), encoding="utf-8")
                print(f"[ensure_google_token_file] token.json restaurado exitosamente desde {backup_path}")
                return local_path
            except Exception:
                pass
        env_token = os.environ.get("GOOGLE_TOKEN_JSON")
        if env_token and env_token.strip():
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(env_token.strip(), encoding="utf-8")
            try:
                backup_path.write_text(env_token.strip(), encoding="utf-8")
            except Exception:
                pass
            print(f"Archivo {local_path} generado con éxito desde variable de entorno.")
        return local_path

    root = Path(__file__).resolve().parent.parent.parent
    local_path = root / "token.json"
    backup_path = root / "token_backup.json"
    app_path = Path("/app/token.json")

    if app_path.is_file():
        return app_path
    if local_path.is_file():
        return local_path
    if backup_path.is_file():
        try:
            local_path.write_text(backup_path.read_text(encoding="utf-8"), encoding="utf-8")
            return local_path
        except Exception:
            pass

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
        self._folder_ids = {}
        self._folder_lock = threading.Lock()
        self._transfer_local = threading.local()
        self._sync_local = threading.local()

    def _transfer_http(self):
        """Each transfer worker owns its HTTP transport (httplib2 is not thread-safe)."""
        http = getattr(self._transfer_local, "http", None)
        if http is None:
            import google_auth_httplib2
            import httplib2
            credentials = self.service._http.credentials
            http = google_auth_httplib2.AuthorizedHttp(credentials, http=httplib2.Http(timeout=20))
            self._transfer_local.http = http
        return http

    def _execute_request(self, request):
        if getattr(self._transfer_local, "active", False):
            return request.execute(http=self._transfer_http())
        return request.execute()

    def _parallel_call(self, function, *args):
        self._transfer_local.active = True
        try:
            return function(*args)
        finally:
            http = getattr(self._transfer_local, "http", None)
            if http is not None:
                http.http.close()
                del self._transfer_local.http
            self._transfer_local.active = False
            self._transfer_local.upload_index = None

    def is_connected(self) -> bool:
        """
        Check if valid Google Drive OAuth token exists without prompting browser login.
        Proactively refreshes expired or stale token if refresh_token is available.
        """
        if not self.token_path.is_file():
            # Try restoring from token_backup.json
            backup_file = self.token_path.parent / "token_backup.json"
            if backup_file.is_file():
                try:
                    self.token_path.write_text(backup_file.read_text(encoding="utf-8"), encoding="utf-8")
                except Exception:
                    pass
            if not self.token_path.is_file():
                return False

        try:
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            if creds and creds.valid:
                return True
            if creds and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    creds_json = creds.to_json()
                    self.token_path.write_text(creds_json, encoding="utf-8")
                    backup_file = self.token_path.parent / "token_backup.json"
                    try:
                        backup_file.write_text(creds_json, encoding="utf-8")
                    except Exception:
                        pass
                    self._service = None
                    return True
                except Exception as exc:
                    print(f"[GoogleDriveStorage] Error refreshing token: {exc}")
                    return False
        except Exception as exc:
            print(f"[GoogleDriveStorage] Error inspecting credentials: {exc}")
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
        Proactively refreshes credentials using refresh_token without blocking the web process.
        """
        creds: Optional[Credentials] = None

        if not self.token_path.is_file():
            backup_file = self.token_path.parent / "token_backup.json"
            if backup_file.is_file():
                try:
                    self.token_path.write_text(backup_file.read_text(encoding="utf-8"), encoding="utf-8")
                except Exception:
                    pass

        if self.token_path.is_file():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            except Exception as exc:
                print(f"[GoogleDriveStorage] Error loading token.json: {exc}")
                creds = None

        if creds and not creds.valid and creds.refresh_token:
            try:
                creds.refresh(Request())
                creds_json = creds.to_json()
                self.token_path.parent.mkdir(parents=True, exist_ok=True)
                self.token_path.write_text(creds_json, encoding="utf-8")
                backup_file = self.token_path.parent / "token_backup.json"
                try:
                    backup_file.write_text(creds_json, encoding="utf-8")
                except Exception:
                    pass
            except Exception as exc:
                print(f"[GoogleDriveStorage] Error refreshing token: {exc}")
                creds = None

        if not creds or not creds.valid:
            if not self.credentials_path.is_file():
                raise FileNotFoundError(
                    f"No se encontró el archivo de credenciales de Google OAuth en: {self.credentials_path}. "
                    "Descarga credentials.json desde Google Cloud Console y colócalo en la raíz del proyecto."
                )
            raise RuntimeError(
                "La sesión de Google Drive no está conectada o ha expirado. "
                "Conéctala desde la interfaz web con el botón 'Conectar Google Drive'."
            )

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
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
        os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

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
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
        os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

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

        # Ensure flow has a redirect_uri set; if already set during get_authorization_url, keep it exact
        if not getattr(flow, "redirect_uri", None):
            flow.redirect_uri = active_redirect

        flow.fetch_token(code=code)
        creds = flow.credentials
        creds_json = creds.to_json()
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(creds_json, encoding="utf-8")
        backup_file = self.token_path.parent / "token_backup.json"
        try:
            backup_file.write_text(creds_json, encoding="utf-8")
        except Exception:
            pass
        # Also mirror to /app/token.json if running in container
        container_token = Path("/app/token.json")
        if not is_desktop_runtime() and container_token.parent.exists():
            try:
                container_token.write_text(creds_json, encoding="utf-8")
            except Exception:
                pass
        self._service = None
        _active_oauth_flow = None
        return creds

    def restore_from_client_token(self, token_data: Union[Dict[str, Any], str]) -> bool:
        """
        Restore OAuth credentials from client-provided token data (localStorage).
        Saves token to local token_path, token_backup.json, and /app/token.json, then verifies connection.
        """
        try:
            if isinstance(token_data, str):
                token_dict = json.loads(token_data)
            else:
                token_dict = dict(token_data)

            # Ensure valid dict
            if not isinstance(token_dict, dict) or not (
                "token" in token_dict or "refresh_token" in token_dict
            ):
                return False

            token_json_str = json.dumps(token_dict, indent=2)
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(token_json_str, encoding="utf-8")

            backup_file = self.token_path.parent / "token_backup.json"
            try:
                backup_file.write_text(token_json_str, encoding="utf-8")
            except Exception:
                pass

            # Also sync to /app/token.json if directory exists in container
            container_token = Path("/app/token.json")
            if not is_desktop_runtime() and container_token.parent.exists():
                try:
                    container_token.write_text(token_json_str, encoding="utf-8")
                except Exception:
                    pass

            self._service = None
            return self.is_connected()
        except Exception as exc:
            print(f"[GoogleDriveStorage] Error restoring client token: {exc}")
            return False

    def get_user_info(self) -> Dict[str, Optional[str]]:
        """
        Retrieve authenticated user info (emailAddress, displayName, photoLink) from Google Drive API.
        """
        if not self.is_connected():
            return {"email": None, "name": None, "photo_link": None}
        try:
            about = self.service.about().get(fields="user(displayName,emailAddress,photoLink)").execute()
            user = about.get("user", {})
            return {
                "email": user.get("emailAddress"),
                "name": user.get("displayName"),
                "photo_link": user.get("photoLink"),
            }
        except Exception as exc:
            print(f"[GoogleDriveStorage] Error fetching user info: {exc}")
            return {"email": None, "name": None, "photo_link": None}

    def disconnect(self) -> bool:
        """
        Disconnect Google Drive by removing token.json and clearing active credentials/service.
        """
        self._service = None
        success = True
        try:
            if self.token_path.is_file():
                self.token_path.unlink()
        except Exception as exc:
            print(f"[GoogleDriveStorage] Error deleting {self.token_path}: {exc}")
            success = False

        backup_file = self.token_path.parent / "token_backup.json"
        if backup_file.is_file():
            try:
                backup_file.unlink()
            except Exception:
                pass

        container_token = Path("/app/token.json")
        if not is_desktop_runtime() and container_token.is_file():
            try:
                container_token.unlink()
            except Exception:
                pass

        return success

    def get_or_create_folder(self, folder_name: str = DEFAULT_FOLDER_NAME) -> str:
        """
        Check if folder exists in the user's Drive; create it if missing.
        Returns the folder ID.
        """
        with self._folder_lock:
            if folder_name in self._folder_ids:
                return self._folder_ids[folder_name]
            service = self.service
            # Escape single quotes in folder name
            escaped_name = folder_name.replace("'", "\\'")
            query = f"name = '{escaped_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"

            response = self._execute_request(service.files().list(
                q=query,
                spaces="drive",
                fields="files(id, name)",
            ))

            files = response.get("files", [])
            if files:
                self._folder_ids[folder_name] = files[0]["id"]
                return files[0]["id"]

            # Create the folder if it doesn't exist
            folder_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            folder = self._execute_request(service.files().create(
                body=folder_metadata,
                fields="id, name",
            ))

            self._folder_ids[folder_name] = folder["id"]
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

        # Privacy & isolation safeguard: Never upload local ASR benchmark test reports to Google Drive
        if "transcription-tests" in str(local_path).lower() or local_path.name.startswith("test_report_"):
            raise ValueError(f"Los informes de prueba locales ({local_path.name}) son confidenciales y no se sincronizan a Google Drive.")

        # Quality filter: reject tiny notes <500 bytes or <100 words from being uploaded to Drive
        if local_path.suffix.lower() == ".md" and not local_path.name.endswith("_grimorio.md") and local_path.name != "manifest.md":
            try:
                if local_path.stat().st_size < 500:
                    print(f"[GoogleDriveStorage] upload_file skipped stub note {local_path.name} (size < 500 bytes)")
                    return {"file_id": "", "file_name": local_path.name, "web_view_link": "", "skipped": "quality_filter"}
                txt_preview = local_path.read_text(encoding="utf-8", errors="replace")
                if len(txt_preview.strip().split()) < 100:
                    print(f"[GoogleDriveStorage] upload_file skipped stub note {local_path.name} (< 100 words)")
                    return {"file_id": "", "file_name": local_path.name, "web_view_link": "", "skipped": "quality_filter"}
            except Exception:
                pass

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
        try:
            service = self.service

            # A complete sync inventory avoids a new name query for every upload.
            index = getattr(self._transfer_local, "upload_index", None)
            if index is not None:
                remote = index.get(local_path.name) or index.get(local_path.name.casefold())
                existing = [remote] if remote else []
            else:
                escaped_filename = local_path.name.replace("'", "\\'")
                check_q = f"name = '{escaped_filename}' and '{folder_id}' in parents and trashed = false"
                existing = self._execute_request(service.files().list(
                    q=check_q, spaces="drive", fields="files(id, name, webViewLink)")).get("files", [])

            if existing:
                file_id = existing[0]["id"]
                uploaded = self._execute_request(service.files().update(
                    fileId=file_id,
                    media_body=media,
                    fields="id, name, webViewLink",
                ))
            else:
                file_metadata = {
                    "name": local_path.name,
                    "parents": [folder_id],
                }
                uploaded = self._execute_request(service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, name, webViewLink",
                ))

            web_link = uploaded.get("webViewLink") or (f"https://drive.google.com/file/d/{uploaded.get('id')}/view" if uploaded.get("id") else "")
            return {
                "file_id": uploaded.get("id", ""),
                "file_name": uploaded.get("name", local_path.name),
                "web_view_link": web_link,
            }
        finally:
            media.stream().close()

    def download_file_bytes(self, file_id: str) -> bytes:
        """Download binary content of a file from Google Drive."""
        service = self.service
        request = service.files().get_media(fileId=file_id)
        if getattr(self._transfer_local, "active", False):
            request.http = self._transfer_http()
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return fh.getvalue()

    def delete_file(self, filename: str, folder_name: str = DEFAULT_FOLDER_NAME) -> bool:
        """Trash or delete a file in the specified Drive folder."""
        if not self.is_connected():
            return False
        try:
            service = self.service
            folder_id = self.get_or_create_folder(folder_name=folder_name)
            escaped_name = filename.replace("'", "\\'")
            q = f"name = '{escaped_name}' and '{folder_id}' in parents and trashed = false"
            res = service.files().list(q=q, spaces="drive", fields="files(id, name)").execute()
            deleted = False
            for item in res.get("files", []):
                service.files().delete(fileId=item["id"]).execute()
                deleted = True
            return deleted
        except Exception as e:
            print(f"[GoogleDriveStorage] Error deleting {filename} from Drive: {e}")
            return False

    @coalesce_sync
    def sync_from_google_drive(
        self,
        campaigns_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        dry_run: bool = False,
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
        if is_desktop_runtime():
            paths = resolve_runtime_paths(resource_dir=project_root)
            c_dir = campaigns_dir or paths.campaigns_dir
            o_dir = output_dir or paths.output_dir
        from src.storage.campaign_manager import CampaignManager
        c_dir.mkdir(parents=True, exist_ok=True)
        o_dir.mkdir(parents=True, exist_ok=True)

        # One configured workspace; no writes to alternate data/output trees.
        target_data_dirs = [o_dir if is_desktop_runtime() else c_dir.parent]
        target_output_dirs = [o_dir]

        service = self.service

        # 1. Locate app folders
        transport = getattr(getattr(service, "_http", None), "http", None)
        if transport is not None:
            transport.timeout = 20
        env_folder = os.environ.get("GOOGLE_DRIVE_FOLDER_NAME")
        raw_candidates = [
            env_folder,
            "WhisperDnD",
            "whisperdnd",
            "Whisper_DnD",
            DEFAULT_FOLDER_NAME,
            "Whisper AI - Transcripciones",
            "WhisperApp",
        ]
        folder_candidates: List[str] = []
        for fc in raw_candidates:
            if fc and isinstance(fc, str) and fc not in folder_candidates:
                folder_candidates.append(fc)

        found_root_ids: List[str] = []
        inventory_errors = []
        listing_complete = True
        seen_ids = set()
        page_token = None
        folder_clauses = ["name = '" + name.replace("'", "\\'") + "'" for name in folder_candidates]
        root_query = "(" + " or ".join(folder_clauses) + ") and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        while True:
            try:
                res = service.files().list(q=root_query, spaces="drive",
                    fields="nextPageToken,files(id,name)", pageToken=page_token).execute()
                for item in res.get("files", []):
                    if item["id"] not in seen_ids:
                        seen_ids.add(item["id"])
                        found_root_ids.append(item["id"])
                    if item.get("name") == "WhisperDnD":
                        self._folder_ids["WhisperDnD"] = item["id"]
                page_token = res.get("nextPageToken")
                if not page_token:
                    break
            except Exception as exc:
                listing_complete = False
                inventory_errors.append({"file": "Drive inventory", "message": str(exc)})
                break

        # If none found, create 'WhisperDnD'
        if not found_root_ids and listing_complete and not dry_run:
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
            folder_id = cur_fid
            page_token = None
            while True:
                try:
                    # Buscar tanto JSON de D&D como Markdown de Work & Study
                    query = f"'{folder_id}' in parents and (name contains '.json' or name contains '.md' or name contains '.docx' or name contains '.txt' or mimeType = 'application/vnd.google-apps.folder') and trashed = false"
                    res = service.files().list(
                        q=query,
                        spaces="drive",
                        fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, md5Checksum)",
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
                    print(f"[GoogleDriveStorage] Error listing folder '{folder_id}': {e}")
                    listing_complete = False
                    inventory_errors.append({"file": folder_id, "message": str(e)})
                    break

        campaign_errors = list(inventory_errors)
        conflicts = []
        synced_campaign_names: List[str] = []
        downloaded_campaigns = 0
        uploaded_campaigns = 0
        downloaded_notes = 0
        # Detect duplicate names rather than arbitrarily selecting a remote copy.
        by_name = {}
        for remote in drive_files:
            name = remote.get("name", "")
            if not name or name != Path(name).name:
                continue
            key = name.casefold()
            if remote.get("id") not in {r.get("id") for r in by_name.get(key, [])}:
                by_name.setdefault(key, []).append(remote)
        duplicate_names = {name for name, values in by_name.items() if len(values) > 1}
        for name in duplicate_names:
            conflicts.append({"file": name, "message": "Hay varias copias remotas con ese nombre; no se eligió una automáticamente."})
        drive_files = [values[0] for name, values in by_name.items() if name not in duplicate_names]
        remote_filenames = {r["name"]: r for r in drive_files}
        remote_filenames.update({r["name"].casefold(): r for r in drive_files})
        checkpoint = SyncCheckpoint(c_dir.parent, {"roots": sorted(found_root_ids), "token_path": str(self.token_path.resolve()),
                                                  "campaigns": str(c_dir.resolve()), "output": str(o_dir.resolve())})
        directions, local_paths, before_hashes = {}, {}, {}
        skipped_files = set()
        imported_files = set()
        download_cache, download_errors = {}, {}
        for remote in drive_files:
            name, fid = remote["name"], remote.get("id")
            lower = name.lower()
            if not fid or lower in ("manifest.json", "credentials.json", "token.json", "token_backup.json"):
                continue
            if lower == "apuntes_historial.json":
                local = target_data_dirs[0] / name
            elif lower.endswith(".json"):
                local = c_dir / f"{CampaignManager.sanitize_name(Path(name).stem)}.json"
            elif lower.endswith((".md", ".txt", ".docx", ".zip")):
                local = o_dir / name
            else:
                continue
            is_campaign = lower.endswith((".json", ".zip")) and lower != "apuntes_historial.json"
            direction = checkpoint.direction(local, remote, campaign=is_campaign)
            directions[fid], local_paths[fid], before_hashes[fid] = direction, local, content_hash(local)
            if local.name != name and is_campaign:
                remote_filenames[local.name] = remote
            if direction == "equal":
                skipped_files.add(name)
                checkpoint.remember(local, remote)
            elif direction == "conflict":
                conflicts.append({"file": name, "message": "Local y Drive difieren sin una base común verificable, o ambos cambiaron. Se conservan las dos copias."})
        if dry_run:
            actions = [{"file": r["name"], "direction": directions[r["id"]]}
                       for r in drive_files if r.get("id") in directions]
            candidates = [*c_dir.glob("*.json"), *[p for p in o_dir.iterdir() if p.is_file() and p.suffix.lower() in (".md", ".docx", ".txt")]]
            history = target_data_dirs[0] / "apuntes_historial.json"
            if history.is_file():
                candidates.append(history)
            for local in candidates:
                if (local.name.casefold() in duplicate_names or local.name in remote_filenames
                        or local.name.casefold() in remote_filenames or local.name.startswith(".")
                        or local.name.lower().startswith("test_report_")):
                    continue
                if local.suffix == ".json" and local.name != "apuntes_historial.json":
                    try:
                        data = json.loads(local.read_text(encoding="utf-8"))
                        if CampaignManager.is_backup_campaign_file(local, data):
                            continue
                        from src.storage.campaign_ingest import assert_campaign_formats_agree
                        assert_campaign_formats_agree(CampaignManager(str(c_dir)), data.get("campaign_name") or local.stem)
                    except Exception as exc:
                        campaign_errors.append({"file": local.name, "message": str(exc)})
                        continue
                elif local.name.endswith("_grimorio.md") or local.name == "manifest.md":
                    continue
                elif local.suffix.lower() == ".md" and (local.stat().st_size < 500 or len(local.read_text(encoding="utf-8", errors="replace").split()) < 100):
                    continue
                actions.append({"file": local.name, "direction": "upload"})
            return {"status": "partial" if conflicts or campaign_errors else "success", "dry_run": True,
                    "actions": actions, "conflicts": conflicts, "campaign_errors": campaign_errors,
                    "listing_complete": listing_complete, "transferred_files": 0}
        planned_downloads = [r for r in drive_files if directions.get(r.get("id")) in ("download", "probe")]
        # Fetch independent files concurrently. Only validated local commits below
        # are serialized, so the two campaign formats cannot race each other.
        if planned_downloads:
            with ThreadPoolExecutor(max_workers=min(4, len(planned_downloads))) as executor:
                pending = {executor.submit(self._parallel_call, self.download_file_bytes, r["id"]): r
                           for r in planned_downloads}
                for future in as_completed(pending):
                    remote = pending.pop(future)
                    fid = remote["id"]
                    try:
                        data = future.result()
                        expected = remote.get("md5Checksum")
                        if expected and hashlib.md5(data).hexdigest().lower() != str(expected).lower():
                            raise ValueError("La descarga no coincide con la huella de Drive; no se aplicó.")
                        target = self._sync_local.workspace / str(len(download_cache))
                        target.write_bytes(data)
                        download_cache[fid] = target
                    except Exception as exc:
                        download_errors[fid] = str(exc)
                        campaign_errors.append({"file": remote["name"], "message": str(exc)})

        # Distinct filenames can still contain two histories for the same
        # campaign. Inspect all fetched identities before committing either.
        campaign_sources = {}
        for remote in planned_downloads:
            fid, name = remote["id"], remote["name"]
            if fid not in download_cache or name.lower() == "apuntes_historial.json":
                continue
            try:
                content = download_cache[fid].read_bytes()
                if name.lower().endswith(".zip"):
                    import zipfile
                    with zipfile.ZipFile(io.BytesIO(content)) as archive:
                        entries = archive.namelist()
                        entry = "campaign.json" if "campaign.json" in entries else next(
                            n for n in entries if n.endswith(".json") and not n.endswith("manifest.json"))
                        data = json.loads(archive.read(entry))
                elif name.lower().endswith(".json"):
                    data = json.loads(content)
                else:
                    continue
                if not isinstance(data, dict) or "sessions" not in data or CampaignManager.is_backup_campaign_file(Path(name), data):
                    continue
                cname = data.get("campaign_name") or data.get("name") or data.get("title") or Path(name).stem
                canonical = CampaignManager.sanitize_name(cname) + ".json"
                campaign_sources.setdefault(canonical, []).append(name)
            except (ValueError, KeyError, StopIteration, OSError):
                continue  # The normal validated importer below reports the error.
        for canonical, names in campaign_sources.items():
            if len(names) > 1:
                conflicts.append({"file": canonical, "remote_files": names,
                                  "message": "Varias historias remotas corresponden a la misma campaña; no se importó ninguna."})
                for name in names:
                    conflicts.append({"file": name, "message": "Copia remota ambigua; requiere revisión."})

        def _matches_local_file(local_f, remote_meta):
            if not local_f.is_file():
                return False
            return checkpoint.direction(local_f, remote_meta,
                campaign=local_f.suffix.lower() == ".json" and local_f.name != "apuntes_historial.json") == "equal"

        def _downloaded(fid):
            return download_cache[fid].read_bytes()

        blocked_names = duplicate_names | {item["file"] for item in conflicts} | {item["file"] for item in campaign_errors}
        blocked_names |= {name.casefold() for name in blocked_names}
        blocked_names |= {CampaignManager.sanitize_name(Path(name).stem) + ".json"
                          for name in list(blocked_names) if name.lower().endswith((".json", ".zip"))}

        # 3. PULL: Download from Google Drive to local server
        for f in drive_files:
            fname = f.get("name", "")
            fid = f.get("id")
            if not fname or not fid:
                continue

            lower_name = fname.lower()
            if fname.casefold() in blocked_names or fname in blocked_names or fid not in directions or directions[fid] in ("equal", "upload"):
                continue
            if fid in download_errors:
                continue
            if content_hash(local_paths[fid]) != before_hashes[fid]:
                conflicts.append({"file": fname, "message": "El archivo local cambió durante la transferencia; no se sobrescribió."})
                blocked_names.add(fname)
                continue
            if lower_name.endswith(".json"):
                if lower_name == "manifest.json":
                    continue
                if lower_name == "apuntes_historial.json":
                    # Smart Skip: if local apuntes_historial.json matches remote md5/size, skip download
                    primary_hist = target_data_dirs[0] / "apuntes_historial.json" if target_data_dirs else None
                    if primary_hist and _matches_local_file(primary_hist, f):
                        continue
                    try:
                        content = _downloaded(fid)
                        for d_dir in target_data_dirs:
                            try:
                                (d_dir / "apuntes_historial.json").write_bytes(content)
                            except Exception:
                                pass

                        imported_files.add(fname)
                        checkpoint.remember(local_paths[fid], f, hashlib.md5(content).hexdigest())

                        # Reconstruct any missing note .md files across all target_output_dirs
                        parsed_notes = json.loads(content.decode("utf-8"))
                        notes_list = (
                            parsed_notes.get("notes", [])
                            if isinstance(parsed_notes, dict)
                            else (parsed_notes if isinstance(parsed_notes, list) else [])
                        )
                        for note in notes_list:
                            if isinstance(note, dict) and note.get("filename") and note.get("content"):
                                note_name = Path(note["filename"]).name
                                note_content = note.get("content", "")
                                note_size = int(note.get("size_bytes") or len(note_content.encode("utf-8")))
                                note_words = int(note.get("word_count") or len(note_content.strip().split()))
                                if note_size < 500 or note_words < 100:
                                    continue
                                for out_d in target_output_dirs:
                                    try:
                                        note_target = out_d / note_name
                                        if not note_target.is_file():
                                            note_target.write_text(note_content, encoding="utf-8")
                                    except Exception:
                                        pass
                                downloaded_notes += 1
                    except Exception as exc:
                        print(f"[GoogleDriveStorage] Error restoring apuntes_historial.json: {exc}")
                    continue

                # Smart Skip: if local campaign file already matches remote md5/size, skip download
                local_camp_cand = c_dir / fname
                if _matches_local_file(local_camp_cand, f):
                    try:
                        c_data = json.loads(local_camp_cand.read_text(encoding="utf-8"))
                        c_name = (
                            c_data.get("campaign_name")
                            or c_data.get("name")
                            or c_data.get("title")
                            or Path(fname).stem
                        )
                        if c_name and c_name not in synced_campaign_names:
                            synced_campaign_names.append(c_name)
                    except Exception:
                        pass
                    continue

                try:
                    content = _downloaded(fid)
                    data = json.loads(content.decode("utf-8"))
                    if isinstance(data, dict):
                        if CampaignManager.is_backup_campaign_file(Path(fname), data):
                            continue
                        c_name = (
                            data.get("campaign_name")
                            or data.get("name")
                            or data.get("title")
                            or Path(fname).stem
                        )
                        if "campaign_name" not in data:
                            data["campaign_name"] = c_name
                            content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")

                        from src.storage.campaign_manager import CampaignManager
                        from src.storage.campaign_ingest import restore_drive_campaign
                        actual_path = CampaignManager(campaigns_dir=str(c_dir)).get_campaign_path(c_name)
                        if restore_drive_campaign(CampaignManager(campaigns_dir=str(c_dir)), data):
                            downloaded_campaigns += 1
                            imported_files.add(fname)
                            imported_files.add(actual_path.name)
                            checkpoint.remember(actual_path, f, hashlib.md5(content).hexdigest())
                        elif actual_path.is_file() and json.loads(actual_path.read_text(encoding="utf-8")) == data:
                            imported_files.add(fname)
                            imported_files.add(actual_path.name)
                            checkpoint.remember(actual_path, f, hashlib.md5(content).hexdigest())

                        if c_name and c_name not in synced_campaign_names:
                            synced_campaign_names.append(c_name)
                    else:
                        local_target = o_dir / fname
                        if not local_target.is_file():
                            local_target.write_bytes(content)
                            downloaded_notes += 1
                except Exception as exc:
                    campaign_errors.append({"file": fname, "message": str(exc)})
                    blocked_names.add(fname)
                    print(f"[GoogleDriveStorage] Error processing json {fname}: {exc}")

            elif lower_name.endswith(".zip"):
                try:
                    content = _downloaded(fid)
                    import zipfile
                    with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
                        namelist = zf.namelist()
                        camp_json_name = None
                        if "campaign.json" in namelist:
                            camp_json_name = "campaign.json"
                        else:
                            for n in namelist:
                                if n.endswith(".json") and not n.endswith("manifest.json"):
                                    camp_json_name = n
                                    break
                        if camp_json_name:
                            camp_dict = json.loads(zf.read(camp_json_name).decode("utf-8"))
                            if isinstance(camp_dict, dict):
                                c_name = (
                                    camp_dict.get("campaign_name")
                                    or camp_dict.get("name")
                                    or Path(fname).stem.replace("Campaña_", "").replace("Campana_", "")
                                )
                                camp_dict["campaign_name"] = c_name
                                if CampaignManager.is_backup_campaign_file(Path(fname), camp_dict):
                                    continue
                                from src.storage.campaign_manager import CampaignManager
                                safe_name = CampaignManager.sanitize_name(c_name)
                                target_file = c_dir / f"{safe_name}.json"
                                from src.storage.campaign_ingest import restore_drive_campaign
                                if not restore_drive_campaign(CampaignManager(campaigns_dir=str(c_dir)), camp_dict):
                                    continue
                                downloaded_campaigns += 1
                                if c_name not in synced_campaign_names:
                                    synced_campaign_names.append(c_name)
                                for item in namelist:
                                    if item.endswith((".md", ".docx", ".txt")):
                                        out_target = o_dir / Path(item).name
                                        if not out_target.is_file():
                                            out_target.write_bytes(zf.read(item))
                                            downloaded_notes += 1
                except Exception as exc:
                    campaign_errors.append({"file": fname, "message": str(exc)})
                    blocked_names.add(fname)
                    print(f"[GoogleDriveStorage] Error processing zip {fname}: {exc}")

            elif lower_name.endswith(".md"):
                is_grimorio = lower_name.endswith("_grimorio.md") or lower_name == "manifest.md"

                remote_size = f.get("size")
                if remote_size is not None and not is_grimorio:
                    try:
                        if int(remote_size) < 500:
                            print(f"[GoogleDriveStorage] Skipping stub note {fname} (remote size < 500 bytes)")
                            continue
                    except Exception:
                        pass

                # Smart Skip: if already exists locally and matches remote md5/size, skip download
                if target_output_dirs and all(_matches_local_file(out_d / fname, f) for out_d in target_output_dirs):
                    continue

                try:
                    content = _downloaded(fid)

                    if not is_grimorio:
                        if len(content) < 500:
                            print(f"[GoogleDriveStorage] Skipping stub note {fname} (downloaded size < 500 bytes)")
                            continue
                        text_str = content.decode("utf-8", errors="replace")
                        if len(text_str.strip().split()) < 100:
                            print(f"[GoogleDriveStorage] Skipping stub note {fname} (words < 100)")
                            continue

                    written_any = False
                    for out_d in target_output_dirs:
                        try:
                            out_d.mkdir(parents=True, exist_ok=True)
                            (out_d / fname).write_bytes(content)
                            written_any = True
                        except Exception:
                            pass

                    if written_any:
                        downloaded_notes += 1
                        imported_files.add(fname)
                        checkpoint.remember(local_paths[fid], f, hashlib.md5(content).hexdigest())
                except Exception as exc:
                    campaign_errors.append({"file": fname, "message": str(exc)})
                    blocked_names.add(fname)
                    print(f"[GoogleDriveStorage] Error downloading md note {fname}: {exc}")

            elif lower_name.endswith((".docx", ".txt")):
                # Smart Skip: if already exists locally and matches remote md5/size, skip download
                if target_output_dirs and all(_matches_local_file(out_d / fname, f) for out_d in target_output_dirs):
                    continue
                try:
                    content = _downloaded(fid)
                    written_any = False
                    for out_d in target_output_dirs:
                        try:
                            out_d.mkdir(parents=True, exist_ok=True)
                            (out_d / fname).write_bytes(content)
                            written_any = True
                        except Exception:
                            pass
                    if written_any:
                        downloaded_notes += 1
                except Exception as exc:
                    campaign_errors.append({"file": fname, "message": str(exc)})
                    blocked_names.add(fname)
                    print(f"[GoogleDriveStorage] Error downloading file {fname}: {exc}")

        # 4. PUSH: Upload local campaigns and academic notes not yet in Google Drive
        primary_folder = "WhisperDnD"
        uploaded_notes = 0

        def _upload_snapshot(source):
            # Upload an immutable owned copy so a concurrent local save cannot
            # produce a torn remote document or make us mark newer data saved.
            before = content_hash(source)
            data = source.read_bytes()
            digest = hashlib.md5(data).hexdigest()
            if before != digest:
                raise RuntimeError("El archivo cambió al preparar la subida; vuelve a sincronizar.")
            target_dir = workspace / "uploads"
            target_dir.mkdir(exist_ok=True)
            snapshot = target_dir / source.name
            snapshot.write_bytes(data)
            self._transfer_local.upload_index = remote_filenames
            result = self.upload_file(str(snapshot), folder_name=primary_folder)
            if result.get("skipped") or not isinstance(result.get("file_id"), str) or not result.get("file_id"):
                raise RuntimeError("Drive no confirmó una subida válida.")
            checkpoint.remember(source, {"id": result["file_id"]}, digest, local_digest=digest)
            if content_hash(source) != digest:
                raise RuntimeError("Se respaldó una copia coherente, pero el archivo local volvió a cambiar. Hay cambios pendientes.")
            return result

        workspace = self._sync_local.workspace

        # An incomplete pull cannot establish that overwriting remote history is safe.
        campaigns_to_upload = []
        for local_json in ([] if campaign_errors or not listing_complete else c_dir.glob("*.json")):
            if local_json.name in blocked_names or local_json.name.casefold() in blocked_names or local_json.name in imported_files:
                continue
            try:
                from src.storage.campaign_manager import CampaignManager
                from src.storage.campaign_ingest import assert_campaign_formats_agree
                upload_state = json.loads(local_json.read_text(encoding="utf-8"))
                if CampaignManager.is_backup_campaign_file(local_json, upload_state):
                    continue
                assert_campaign_formats_agree(CampaignManager(campaigns_dir=str(c_dir)),
                                              upload_state.get("campaign_name") or local_json.stem)
            except Exception as exc:
                campaign_errors.append({"file": local_json.name, "message": str(exc)})
                continue

            should_upload = False
            if local_json.name not in remote_filenames:
                should_upload = True
            else:
                rem_file = remote_filenames[local_json.name]
                if not _matches_local_file(local_json, rem_file):
                    should_upload = True

            if should_upload:
                campaigns_to_upload.append(local_json)
            else:
                try:
                    c_data = json.loads(local_json.read_text(encoding="utf-8"))
                    c_name = c_data.get("campaign_name") or local_json.stem
                    if c_name not in synced_campaign_names:
                        synced_campaign_names.append(c_name)
                except Exception:
                    pass

        def _upload_single_campaign(lj: Path):
            _upload_snapshot(lj)
            try:
                c_d = json.loads(lj.read_text(encoding="utf-8"))
                c_n = c_d.get("campaign_name") or lj.stem
            except Exception:
                c_n = lj.stem
            return lj.name, c_n

        if len(campaigns_to_upload) > 1:
            with ThreadPoolExecutor(max_workers=min(4, len(campaigns_to_upload))) as executor:
                futures = {executor.submit(self._parallel_call, _upload_single_campaign, lj): lj for lj in campaigns_to_upload}
                for fut in as_completed(futures):
                    try:
                        _, c_n = fut.result()
                        uploaded_campaigns += 1
                        if c_n not in synced_campaign_names:
                            synced_campaign_names.append(c_n)
                    except Exception as exc:
                        campaign_errors.append({"file": futures[fut].name, "message": str(exc)})
                        print(f"[GoogleDriveStorage] Error uploading local campaign in parallel: {exc}")
        elif len(campaigns_to_upload) == 1:
            try:
                _, c_n = self._parallel_call(_upload_single_campaign, campaigns_to_upload[0])
                uploaded_campaigns += 1
                if c_n not in synced_campaign_names:
                    synced_campaign_names.append(c_n)
            except Exception as exc:
                campaign_errors.append({"file": campaigns_to_upload[0].name, "message": str(exc)})
                print(f"[GoogleDriveStorage] Error uploading local campaign {campaigns_to_upload[0].name}: {exc}")

        # Push consolidated apuntes_historial.json if present locally (upload or overwrite)
        pushed_historial = False
        for d_dir in target_data_dirs:
            local_historial = d_dir / "apuntes_historial.json"
            if local_historial.is_file() and not pushed_historial and listing_complete and local_historial.name not in blocked_names:
                if local_historial.name in imported_files:
                    pushed_historial = True
                    break
                rem_hist = remote_filenames.get("apuntes_historial.json")
                if rem_hist and _matches_local_file(local_historial, rem_hist):
                    pushed_historial = True
                    break
                try:
                    self._parallel_call(_upload_snapshot, local_historial)
                    pushed_historial = True
                    uploaded_notes += 1
                except Exception as exc:
                    campaign_errors.append({"file": local_historial.name, "message": str(exc)})
                    print(f"[GoogleDriveStorage] Error uploading apuntes_historial.json: {exc}")

        # Back up managed documents as well as notes, never benchmark reports.
        notes_to_upload = []
        seen_md_names = set()
        for out_d in target_output_dirs:
            if out_d.is_dir():
                for note_p in out_d.iterdir():
                    if not note_p.is_file() or note_p.suffix.lower() not in (".md", ".docx", ".txt"):
                        continue
                    if note_p.name.lower().startswith("test_report_"):
                        continue
                    if note_p.name in blocked_names or note_p.name.casefold() in blocked_names or note_p.name in imported_files or not listing_complete:
                        continue
                    if note_p.name.endswith("_grimorio.md") or note_p.name == "manifest.md":
                        continue
                    if note_p.name not in seen_md_names:
                        seen_md_names.add(note_p.name)
                        if note_p.name not in remote_filenames and note_p.name.casefold() not in remote_filenames:
                            try:
                                if note_p.suffix.lower() == ".md":
                                    if note_p.stat().st_size < 500:
                                        continue
                                    txt_preview = note_p.read_text(encoding="utf-8", errors="replace")
                                    if len(txt_preview.strip().split()) < 100:
                                        continue
                                notes_to_upload.append(note_p)
                            except Exception:
                                pass
                        else:
                            rem_n = remote_filenames.get(note_p.name) or remote_filenames[note_p.name.casefold()]
                            if not _matches_local_file(note_p, rem_n):
                                notes_to_upload.append(note_p)

        def _upload_single_note(np: Path):
            _upload_snapshot(np)
            return np.name

        if len(notes_to_upload) > 1:
            with ThreadPoolExecutor(max_workers=min(4, len(notes_to_upload))) as executor:
                futures = {executor.submit(self._parallel_call, _upload_single_note, np): np for np in notes_to_upload}
                for fut in as_completed(futures):
                    try:
                        fut.result()
                        uploaded_notes += 1
                    except Exception as exc:
                        campaign_errors.append({"file": futures[fut].name, "message": str(exc)})
                        print(f"[GoogleDriveStorage] Error uploading local note in parallel: {exc}")
        elif len(notes_to_upload) == 1:
            try:
                self._parallel_call(_upload_single_note, notes_to_upload[0])
                uploaded_notes += 1
            except Exception as exc:
                campaign_errors.append({"file": notes_to_upload[0].name, "message": str(exc)})
                print(f"[GoogleDriveStorage] Error uploading local note {notes_to_upload[0].name}: {exc}")

        # Ensure all existing local campaigns are included in synced_campaign_names
        for local_json in c_dir.glob("*.json"):
            try:
                local_data = json.loads(local_json.read_text(encoding="utf-8"))
                if CampaignManager.is_backup_campaign_file(local_json, local_data):
                    continue
                c_name = local_data.get("campaign_name") or local_json.stem
                if c_name and c_name not in synced_campaign_names:
                    synced_campaign_names.append(c_name)
            except Exception:
                pass

        total_synced_notes = downloaded_notes + uploaded_notes
        if listing_complete:
            checkpoint.save()
        return {
            "conflicts": conflicts,
            "skipped_files": len(skipped_files),
            "status": "partial" if campaign_errors or conflicts else "success",
            "campaign_errors": campaign_errors,
            "synced_campaigns": len(synced_campaign_names),
            "downloaded_campaigns": downloaded_campaigns,
            "uploaded_campaigns": uploaded_campaigns,
            "downloaded_notes": downloaded_notes,
            "uploaded_notes": uploaded_notes,
            "campaign_names": synced_campaign_names,
            "synced_notes": total_synced_notes,
            "message": ("Hay archivos pendientes; revisa campaign_errors y conflicts. " if campaign_errors or conflicts else "") + f"Sincronización con Drive completada: {len(synced_campaign_names)} campañas ({downloaded_campaigns} descargadas, {uploaded_campaigns} respaldadas) y {total_synced_notes} notas/documentos sincronizados ({downloaded_notes} descargadas, {uploaded_notes} respaldadas).",
        }
