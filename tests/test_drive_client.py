"""Unit tests for Google Drive client storage and upload functionality."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.storage.drive_client import GoogleDriveStorage, SCOPES, DEFAULT_FOLDER_NAME


class TestGoogleDriveStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir_obj.name)
        self.dummy_creds = self.test_dir / "credentials.json"
        self.dummy_token = self.test_dir / "token.json"

        # Create a dummy credentials file
        self.dummy_creds.write_text(json.dumps({"installed": {"client_id": "test", "client_secret": "test"}}))

    def tearDown(self):
        self.temp_dir_obj.cleanup()

    def test_init_paths(self):
        storage = GoogleDriveStorage(
            credentials_path=str(self.dummy_creds),
            token_path=str(self.dummy_token),
        )
        self.assertEqual(storage.credentials_path, self.dummy_creds)
        self.assertEqual(storage.token_path, self.dummy_token)

    @patch("src.storage.drive_client.build")
    @patch("src.storage.drive_client.Credentials")
    def test_authenticate_with_existing_token(self, mock_creds_class, mock_build):
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        # Create token file so it attempts reading
        self.dummy_token.write_text(json.dumps({"token": "dummy_token"}))

        storage = GoogleDriveStorage(
            credentials_path=str(self.dummy_creds),
            token_path=str(self.dummy_token),
        )
        storage.authenticate()

        mock_creds_class.from_authorized_user_file.assert_called_once_with(str(self.dummy_token), SCOPES)
        mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds)

    @patch("src.storage.drive_client.build")
    @patch("src.storage.drive_client.InstalledAppFlow")
    def test_authenticate_new_token_flow(self, mock_flow_class, mock_build):
        mock_flow = MagicMock()
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.to_json.return_value = json.dumps({"token": "new_saved_token"})
        mock_flow.run_local_server.return_value = mock_creds
        mock_flow_class.from_client_secrets_file.return_value = mock_flow

        storage = GoogleDriveStorage(
            credentials_path=str(self.dummy_creds),
            token_path=str(self.dummy_token),
        )
        storage.authenticate()

        mock_flow_class.from_client_secrets_file.assert_called_once_with(str(self.dummy_creds), SCOPES)
        mock_flow.run_local_server.assert_called_once_with(port=0)
        self.assertTrue(self.dummy_token.is_file())
        self.assertIn("new_saved_token", self.dummy_token.read_text())

    def test_get_or_create_folder_existing(self):
        storage = GoogleDriveStorage(
            credentials_path=str(self.dummy_creds),
            token_path=str(self.dummy_token),
        )
        mock_service = MagicMock()
        mock_files = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.return_value = {"files": [{"id": "existing_folder_123", "name": DEFAULT_FOLDER_NAME}]}
        mock_files.list.return_value = mock_list
        mock_service.files.return_value = mock_files
        storage._service = mock_service

        folder_id = storage.get_or_create_folder(DEFAULT_FOLDER_NAME)
        self.assertEqual(folder_id, "existing_folder_123")

    def test_get_or_create_folder_creates_new(self):
        storage = GoogleDriveStorage(
            credentials_path=str(self.dummy_creds),
            token_path=str(self.dummy_token),
        )
        mock_service = MagicMock()
        mock_files = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.return_value = {"files": []}
        mock_create = MagicMock()
        mock_create.execute.return_value = {"id": "new_created_folder_456", "name": DEFAULT_FOLDER_NAME}
        mock_files.list.return_value = mock_list
        mock_files.create.return_value = mock_create
        mock_service.files.return_value = mock_files
        storage._service = mock_service

        folder_id = storage.get_or_create_folder(DEFAULT_FOLDER_NAME)
        self.assertEqual(folder_id, "new_created_folder_456")
        mock_files.create.assert_called_once()

    @patch("src.storage.drive_client.MediaFileUpload")
    def test_upload_file(self, mock_media_class):
        test_file = self.test_dir / "sample.docx"
        test_file.write_text("dummy docx content")

        storage = GoogleDriveStorage(
            credentials_path=str(self.dummy_creds),
            token_path=str(self.dummy_token),
        )
        mock_service = MagicMock()
        mock_files = MagicMock()

        # Mock folder list/create
        mock_list = MagicMock()
        mock_list.execute.return_value = {"files": [{"id": "folder_789"}]}
        mock_files.list.return_value = mock_list

        # Mock file upload create
        mock_create = MagicMock()
        mock_create.execute.return_value = {
            "id": "uploaded_file_id_999",
            "name": "sample.docx",
            "webViewLink": "https://drive.google.com/file/d/uploaded_file_id_999/view",
        }
        mock_files.create.return_value = mock_create
        mock_files.update.return_value = mock_create
        mock_service.files.return_value = mock_files
        storage._service = mock_service

        result = storage.upload_file(str(test_file))
        self.assertEqual(result["file_id"], "uploaded_file_id_999")
        self.assertEqual(result["file_name"], "sample.docx")
        self.assertEqual(result["web_view_link"], "https://drive.google.com/file/d/uploaded_file_id_999/view")

    def test_is_connected_false_when_token_missing(self):
        storage = GoogleDriveStorage(
            credentials_path=str(self.dummy_creds),
            token_path=str(self.dummy_token),
        )
        self.assertFalse(storage.is_connected())

    @patch("src.storage.drive_client.Credentials")
    def test_is_connected_true_when_token_valid(self, mock_creds_class):
        self.dummy_token.write_text(json.dumps({"token": "valid"}))
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        storage = GoogleDriveStorage(
            credentials_path=str(self.dummy_creds),
            token_path=str(self.dummy_token),
        )
        self.assertTrue(storage.is_connected())

    @patch("src.storage.drive_client.InstalledAppFlow")
    def test_get_authorization_url(self, mock_flow_class):
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?test=1", "state123")
        mock_flow_class.from_client_secrets_file.return_value = mock_flow

        storage = GoogleDriveStorage(
            credentials_path=str(self.dummy_creds),
            token_path=str(self.dummy_token),
        )
        url = storage.get_authorization_url("http://localhost:8080/api/auth/drive/callback")
        self.assertEqual(url, "https://accounts.google.com/o/oauth2/auth?test=1")
        mock_flow_class.from_client_secrets_file.assert_called_once_with(
            str(self.dummy_creds),
            SCOPES,
            redirect_uri="http://localhost:8080/api/auth/drive/callback",
        )

    @patch("src.storage.drive_client.InstalledAppFlow")
    def test_exchange_code_for_token(self, mock_flow_class):
        mock_flow = MagicMock()
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = json.dumps({"token": "exchanged_code_token"})
        mock_flow.credentials = mock_creds
        mock_flow_class.from_client_secrets_file.return_value = mock_flow

        storage = GoogleDriveStorage(
            credentials_path=str(self.dummy_creds),
            token_path=str(self.dummy_token),
        )
        creds = storage.exchange_code_for_token("test_auth_code_123")
        mock_flow.fetch_token.assert_called_once_with(code="test_auth_code_123")
        self.assertTrue(self.dummy_token.is_file())
        self.assertIn("exchanged_code_token", self.dummy_token.read_text())

    @patch("src.storage.drive_client.InstalledAppFlow")
    def test_retains_flow_between_auth_url_and_exchange(self, mock_flow_class):
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?test=1", "state_abc")
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = json.dumps({"token": "retained_flow_token"})
        mock_flow.credentials = mock_creds
        mock_flow_class.from_client_secrets_file.return_value = mock_flow

        storage = GoogleDriveStorage(
            credentials_path=str(self.dummy_creds),
            token_path=str(self.dummy_token),
        )
        url = storage.get_authorization_url()
        self.assertEqual(url, "https://accounts.google.com/o/oauth2/auth?test=1")

        # In exchange, it should NOT create a new flow; it should reuse mock_flow with PKCE verifier
        mock_flow_class.from_client_secrets_file.reset_mock()
        creds = storage.exchange_code_for_token("auth_code_xyz", state="state_abc")

        # from_client_secrets_file should NOT have been called again!
        mock_flow_class.from_client_secrets_file.assert_not_called()
        mock_flow.fetch_token.assert_called_once_with(code="auth_code_xyz")
        self.assertTrue(self.dummy_token.is_file())
        self.assertIn("retained_flow_token", self.dummy_token.read_text())

    def test_sync_from_google_drive_whisperdnd_json(self):
        storage = GoogleDriveStorage(
            credentials_path=str(self.dummy_creds),
            token_path=str(self.dummy_token),
        )
        # Mock is_connected
        storage.is_connected = MagicMock(return_value=True)

        mock_service = MagicMock()
        mock_files = MagicMock()

        def list_side_effect(q=None, **kwargs):
            m = MagicMock()
            if "name = 'WhisperDnD'" in (q or ""):
                m.execute.return_value = {"files": [{"id": "folder_whisperdnd_123", "name": "WhisperDnD"}]}
            elif "'folder_whisperdnd_123' in parents" in (q or ""):
                m.execute.return_value = {
                    "files": [
                        {
                            "id": "file_strahd_json_456",
                            "name": "La_Maldicion_de_Strahd.json",
                            "mimeType": "application/json",
                        }
                    ],
                    "nextPageToken": None,
                }
            else:
                m.execute.return_value = {"files": [], "nextPageToken": None}
            return m

        mock_files.list.side_effect = list_side_effect
        mock_service.files.return_value = mock_files
        storage._service = mock_service

        campaign_data = {
            "campaign_name": "La Maldición de Strahd",
            "dm": "Roy",
            "sessions": [{"session_number": 1, "title": "Llegada a Barovia"}],
            "universal_pcs": [{"name": "Kaelen", "class": "Paladin"}],
        }
        storage.download_file_bytes = MagicMock(return_value=json.dumps(campaign_data).encode("utf-8"))

        c_dir = self.test_dir / "campaigns"
        o_dir = self.test_dir / "output"

        res = storage.sync_from_google_drive(campaigns_dir=c_dir, output_dir=o_dir)

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["downloaded_campaigns"], 1)
        self.assertIn("La Maldición de Strahd", res["campaign_names"])

        saved_file = c_dir / "La_Maldicion_de_Strahd.json"
        self.assertTrue(saved_file.is_file())
        saved_json = json.loads(saved_file.read_text(encoding="utf-8"))
        self.assertEqual(saved_json["campaign_name"], "La Maldición de Strahd")
        self.assertEqual(saved_json["dm"], "Roy")

    def test_sync_from_google_drive_academic_notes(self):
        storage = GoogleDriveStorage(
            credentials_path=str(self.dummy_creds),
            token_path=str(self.dummy_token),
        )
        storage.is_connected = MagicMock(return_value=True)

        mock_service = MagicMock()
        mock_files = MagicMock()

        def list_side_effect(q=None, **kwargs):
            m = MagicMock()
            if "name = 'WhisperDnD'" in (q or ""):
                m.execute.return_value = {"files": [{"id": "folder_whisperdnd_123", "name": "WhisperDnD"}]}
            elif "'folder_whisperdnd_123' in parents" in (q or ""):
                m.execute.return_value = {
                    "files": [
                        {
                            "id": "file_historial_json_111",
                            "name": "apuntes_historial.json",
                            "mimeType": "application/json",
                        }
                    ],
                    "nextPageToken": None,
                }
            else:
                m.execute.return_value = {"files": [], "nextPageToken": None}
            return m

        mock_files.list.side_effect = list_side_effect
        mock_service.files.return_value = mock_files
        storage._service = mock_service

        historial_data = {
            "total_notes": 1,
            "notes": [
                {
                    "filename": "apuntes_calculo_vectorial.md",
                    "title": "Cálculo Vectorial",
                    "content": "# Cálculo Vectorial\n\nTeorema de Green y divergencia.",
                }
            ]
        }
        storage.download_file_bytes = MagicMock(return_value=json.dumps(historial_data).encode("utf-8"))
        storage.upload_file = MagicMock(return_value={"file_id": "test_upload_id"})

        c_dir = self.test_dir / "campaigns"
        o_dir = self.test_dir / "output"
        o_dir.mkdir(parents=True, exist_ok=True)

        # Create a local note that is not on Drive to test PUSH
        local_note = o_dir / "apuntes_fisica_cuantica.md"
        local_note.write_text("# Física Cuántica\n\nEcuación de Schrödinger.", encoding="utf-8")

        res = storage.sync_from_google_drive(campaigns_dir=c_dir, output_dir=o_dir)

        self.assertEqual(res["status"], "success")
        self.assertGreaterEqual(res["downloaded_notes"], 1)
        self.assertGreaterEqual(res["uploaded_notes"], 1)

        # Check restored file from historial
        restored_note = o_dir / "apuntes_calculo_vectorial.md"
        self.assertTrue(restored_note.is_file())
        self.assertIn("Teorema de Green", restored_note.read_text(encoding="utf-8"))

        # Verify upload_file was called for local_note
        uploaded_names = [call.args[0] for call in storage.upload_file.call_args_list]
        self.assertTrue(any("apuntes_fisica_cuantica.md" in name for name in uploaded_names))


if __name__ == "__main__":
    unittest.main()

