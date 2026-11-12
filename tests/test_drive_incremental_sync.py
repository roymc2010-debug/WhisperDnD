"""Selective Drive synchronization against a fake provider; never remote user data."""
import hashlib
import io
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.storage.drive_client import GoogleDriveStorage


def body(word):
    return (word + " ").encode() * 150


def provider(tmp_path, files):
    storage = GoogleDriveStorage(str(tmp_path / "credentials.json"), str(tmp_path / "token.json"))
    storage.is_connected = MagicMock(return_value=True)
    service = MagicMock()
    queries = []
    def listing(q=None, **kwargs):
        queries.append(q)
        response = {"files": [{"id": "root", "name": "WhisperDnD"}]} if "mimeType = 'application/vnd.google-apps.folder'" in q and "in parents" not in q else {"files": []}
        if "'root' in parents" in q:
            response = {"files": files}
        return MagicMock(execute=lambda: response)
    service.files.return_value.list.side_effect = listing
    storage._service = service
    storage.download_file_bytes = MagicMock(side_effect=lambda fid: remote_content[fid])
    def upload(path, **kwargs):
        name = Path(path).name
        old = next((f for f in files if f["name"] == name), None)
        item = meta(name, Path(path).read_bytes(), old["id"] if old else f"uploaded-{name}")
        if old:
            files[files.index(old)] = item
        else:
            files.append(item)
        return {"file_id": item["id"]}
    storage.upload_file = MagicMock(side_effect=upload)
    cdir, odir = tmp_path / "campaigns", tmp_path / "output"
    cdir.mkdir(exist_ok=True); odir.mkdir(exist_ok=True)
    return storage, cdir, odir, queries


remote_content = {}


def test_desktop_sync_finds_academic_history_in_profile_exports(tmp_path, monkeypatch):
    monkeypatch.setenv('WHISPER_DESKTOP_MODE', '1')
    monkeypatch.setenv('WHISPER_DESKTOP_DATA_ROOT', str(tmp_path / 'profile'))
    storage, cdir, odir, _ = provider(tmp_path, [])
    (odir / 'apuntes_historial.json').write_text('{"notes": []}', encoding='utf8')
    result = storage.sync_from_google_drive(cdir, odir, dry_run=True)
    assert any(item['file'] == 'apuntes_historial.json' for item in result['actions'])


def meta(name, content, fid="remote"):
    remote_content[fid] = content
    return {"id": fid, "name": name, "mimeType": "text/markdown", "size": str(len(content)),
            "md5Checksum": hashlib.md5(content).hexdigest()}


def test_local_only_change_uploads_without_first_downloading_old_remote(tmp_path):
    files = [meta("apuntes_mesa.md", body("antes"))]
    storage, cdir, odir, _ = provider(tmp_path, files)
    note = odir / files[0]["name"]
    note.write_bytes(body("antes"))
    storage.sync_from_google_drive(cdir, odir)
    note.write_bytes(body("nuevo"))
    storage.download_file_bytes.reset_mock(); storage.upload_file.reset_mock()
    result = storage.sync_from_google_drive(cdir, odir)
    assert note.read_bytes() == body("nuevo")
    storage.download_file_bytes.assert_not_called()
    assert storage.upload_file.call_count == 1
    assert result["uploaded_notes"] == 1
    storage.download_file_bytes.reset_mock(); storage.upload_file.reset_mock()
    storage.sync_from_google_drive(cdir, odir)
    storage.download_file_bytes.assert_not_called(); storage.upload_file.assert_not_called()


def test_remote_only_change_downloads_once_without_echo_upload(tmp_path):
    files = [meta("apuntes_mesa.md", body("antes"))]
    storage, cdir, odir, _ = provider(tmp_path, files)
    note = odir / files[0]["name"]
    note.write_bytes(body("antes"))
    storage.sync_from_google_drive(cdir, odir)
    files[:] = [meta("apuntes_mesa.md", body("remoto"))]
    storage.download_file_bytes.reset_mock(); storage.upload_file.reset_mock()
    result = storage.sync_from_google_drive(cdir, odir)
    assert note.read_bytes() == body("remoto")
    assert storage.download_file_bytes.call_count == 1
    storage.upload_file.assert_not_called()
    assert result["downloaded_notes"] == 1


def test_both_sides_changed_preserves_local_and_reports_conflict(tmp_path):
    files = [meta("apuntes_mesa.md", body("antes"))]
    storage, cdir, odir, _ = provider(tmp_path, files)
    note = odir / files[0]["name"]
    note.write_bytes(body("antes"))
    storage.sync_from_google_drive(cdir, odir)
    note.write_bytes(body("local"))
    files[:] = [meta("apuntes_mesa.md", body("remoto"))]
    storage.download_file_bytes.reset_mock(); storage.upload_file.reset_mock()
    result = storage.sync_from_google_drive(cdir, odir)
    assert result["status"] == "partial"
    assert result["conflicts"][0]["file"] == note.name
    assert note.read_bytes() == body("local")
    storage.download_file_bytes.assert_not_called(); storage.upload_file.assert_not_called()


def test_unchanged_files_make_no_transfers_and_no_account_wide_search(tmp_path):
    files = [meta("apuntes_mesa.md", body("igual"))]
    storage, cdir, odir, queries = provider(tmp_path, files)
    (odir / files[0]["name"]).write_bytes(body("igual"))
    storage.sync_from_google_drive(cdir, odir)
    storage.sync_from_google_drive(cdir, odir)
    storage.download_file_bytes.assert_not_called(); storage.upload_file.assert_not_called()
    assert len([q for q in queries if "in parents" not in q]) <= 2


def test_changed_files_download_concurrently_with_a_limit(tmp_path):
    files = [meta(f"apuntes_{i}.md", body(f"nota{i}"), f"id{i}") for i in range(6)]
    storage, cdir, odir, _ = provider(tmp_path, files)
    lock = threading.Lock(); two_entered = threading.Event()
    active = peak = 0
    def download(fid):
        nonlocal active, peak
        with lock:
            active += 1; peak = max(peak, active)
            if active >= 2: two_entered.set()
        two_entered.wait(0.3)
        time.sleep(0.015)
        with lock: active -= 1
        return remote_content[fid]
    storage.download_file_bytes.side_effect = download
    storage.sync_from_google_drive(cdir, odir)
    assert 2 <= peak <= 4
    assert len(list(odir.glob("*.md"))) == 6


def test_overlapping_sync_requests_share_one_transfer(tmp_path):
    files = [meta("apuntes_mesa.md", body("remoto"))]
    storage, cdir, odir, _ = provider(tmp_path, files)
    entered, release = threading.Event(), threading.Event()
    def download(fid):
        entered.set(); release.wait(1)
        return remote_content[fid]
    storage.download_file_bytes.side_effect = download
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(storage.sync_from_google_drive, cdir, odir)
        assert entered.wait(1)
        second = pool.submit(storage.sync_from_google_drive, cdir, odir)
        time.sleep(0.05)
        release.set()
        one, two = first.result(), second.result()
    assert one["status"] == two["status"] == "success"
    assert storage.download_file_bytes.call_count == 1


def test_same_size_without_checksum_is_not_proof_of_matching_content(tmp_path):
    files = [meta("apuntes_mesa.md", body("BBBBB"))]
    del files[0]["md5Checksum"]
    storage, cdir, odir, _ = provider(tmp_path, files)
    note = odir / files[0]["name"]
    note.write_bytes(body("AAAAA"))
    result = storage.sync_from_google_drive(cdir, odir)
    assert result["status"] == "partial"
    assert note.read_bytes() == body("AAAAA")
    storage.upload_file.assert_not_called()


def test_two_different_remote_histories_for_one_campaign_are_not_chosen_automatically(tmp_path):
    def campaign(numbers):
        return json.dumps({"campaign_name": "Mesa", "sessions": [{"session_number": n} for n in numbers]}).encode()
    files = [meta("mesa.json", campaign([1]), "first"),
             meta("otra_copia.json", campaign([1, 2]), "second")]
    storage, cdir, odir, _ = provider(tmp_path, files)
    result = storage.sync_from_google_drive(cdir, odir)
    assert result["status"] == "partial"
    assert not list(cdir.glob("*.json"))
    storage.upload_file.assert_not_called()


def test_native_parallel_downloads_use_distinct_http_transports(tmp_path, monkeypatch):
    files = [meta(f"apuntes_{i}.md", body("remoto"), f"id{i}") for i in range(3)]
    storage, cdir, odir, _ = provider(tmp_path, files)
    # Use the actual download adapter with a fake HTTP provider/downloader.
    storage.download_file_bytes = GoogleDriveStorage.download_file_bytes.__get__(storage)
    storage._service.files.return_value.get_media.side_effect = lambda fileId: SimpleNamespace(
        http=storage._service._http, fid=fileId)
    created, used = [], []
    barrier = threading.Barrier(2)
    def transport(credentials, http):
        result = SimpleNamespace(http=MagicMock())
        created.append(result)
        return result
    monkeypatch.setattr("google_auth_httplib2.AuthorizedHttp", transport)
    class Download:
        def __init__(self, stream, request):
            self.stream, self.request = stream, request
        def next_chunk(self):
            used.append(self.request.http)
            try:
                barrier.wait(0.3)
            except threading.BrokenBarrierError:
                pass
            self.stream.write(remote_content[self.request.fid])
            return None, True
    monkeypatch.setattr("src.storage.drive_client.MediaIoBaseDownload", Download)
    storage.sync_from_google_drive(cdir, odir)
    assert len({id(http) for http in used}) == 3
    assert all(http is not storage._service._http for http in used)
    assert all(http.http.close.call_count == 1 for http in created)


def test_dry_run_does_not_download_upload_or_create_checkpoint(tmp_path):
    files = [meta("apuntes_mesa.md", body("remoto"))]
    storage, cdir, odir, _ = provider(tmp_path, files)
    result = storage.sync_from_google_drive(cdir, odir, dry_run=True)
    assert result["dry_run"] is True
    assert result["actions"] == [{"file": "apuntes_mesa.md", "direction": "download"}]
    storage.download_file_bytes.assert_not_called(); storage.upload_file.assert_not_called()
    assert not list(tmp_path.glob(".drive-sync-*.json"))


def test_download_preserves_a_local_edit_made_during_transfer(tmp_path):
    files = [meta("apuntes_mesa.md", body("antes"))]
    storage, cdir, odir, _ = provider(tmp_path, files)
    note = odir / files[0]["name"]
    note.write_bytes(body("antes"))
    storage.sync_from_google_drive(cdir, odir)
    files[:] = [meta(note.name, body("remoto"))]
    def incoming(fid):
        note.write_bytes(body("cambio mientras descargaba"))
        return remote_content[fid]
    storage.download_file_bytes.side_effect = incoming
    storage.upload_file.reset_mock()
    result = storage.sync_from_google_drive(cdir, odir)
    assert result["status"] == "partial"
    assert note.read_bytes() == body("cambio mientras descargaba")
    storage.upload_file.assert_not_called()


def test_upload_uses_a_coherent_snapshot_and_retains_newer_local_changes(tmp_path):
    files = [meta("apuntes_mesa.md", body("antes"))]
    storage, cdir, odir, _ = provider(tmp_path, files)
    note = odir / files[0]["name"]
    note.write_bytes(body("antes"))
    storage.sync_from_google_drive(cdir, odir)
    note.write_bytes(body("subiendo"))
    upload = storage.upload_file.side_effect
    def concurrent_edit(path, **kwargs):
        assert Path(path) != note
        note.write_bytes(body("nuevo"))
        return upload(path, **kwargs)
    storage.upload_file.side_effect = concurrent_edit
    result = storage.sync_from_google_drive(cdir, odir)
    assert result["status"] == "partial"
    assert note.read_bytes() == body("nuevo")
    assert remote_content["remote"] == body("subiendo")
    storage.upload_file.side_effect = upload
    storage.download_file_bytes.reset_mock()
    storage.sync_from_google_drive(cdir, odir)
    storage.download_file_bytes.assert_not_called()
    assert remote_content["remote"] == body("nuevo")


def test_incomplete_remote_inventory_cannot_be_used_to_create_files(tmp_path):
    storage, cdir, odir, _ = provider(tmp_path, [])
    (odir / "apuntes_mesa.md").write_bytes(body("local"))
    original = storage._service.files.return_value.list.side_effect
    def unavailable(q=None, **kwargs):
        if "in parents" in q:
            raise RuntimeError("Listing unavailable")
        return original(q=q, **kwargs)
    storage._service.files.return_value.list.side_effect = unavailable
    result = storage.sync_from_google_drive(cdir, odir)
    assert result["status"] == "partial"
    storage.upload_file.assert_not_called()


def test_download_with_wrong_checksum_is_never_applied(tmp_path):
    files = [meta("apuntes_mesa.md", body("antes"))]
    storage, cdir, odir, _ = provider(tmp_path, files)
    note = odir / files[0]["name"]
    note.write_bytes(body("antes"))
    storage.sync_from_google_drive(cdir, odir)
    files[:] = [meta(note.name, body("remoto"))]
    storage.download_file_bytes.side_effect = lambda fid: body("corrupto")
    storage.upload_file.reset_mock()
    result = storage.sync_from_google_drive(cdir, odir)
    assert result["status"] == "partial"
    assert note.read_bytes() == body("antes")
    storage.upload_file.assert_not_called()


def test_managed_docx_and_transcripts_upload_but_benchmarks_do_not(tmp_path):
    storage, cdir, odir, _ = provider(tmp_path, [])
    (odir / "mesa_sesion_1.docx").write_bytes(b"docx fixture")
    (odir / "mesa_sesion_1_transcripcion.txt").write_text("Dialogo guardado", encoding="utf-8")
    (odir / "test_report_privado.txt").write_text("No sincronizar", encoding="utf-8")
    result = storage.sync_from_google_drive(cdir, odir)
    uploaded = {Path(call.args[0]).name for call in storage.upload_file.call_args_list}
    assert uploaded == {"mesa_sesion_1.docx", "mesa_sesion_1_transcripcion.txt"}
    assert result["uploaded_notes"] == 2


def test_upload_closes_its_file_stream_even_after_provider_failure(tmp_path, monkeypatch):
    files = [meta("apuntes_mesa.md", body("antes"))]
    storage, cdir, odir, _ = provider(tmp_path, files)
    note = odir / "apuntes_mesa.md"
    note.write_bytes(body("nuevo"))
    storage.upload_file = GoogleDriveStorage.upload_file.__get__(storage)
    stream = io.BytesIO(body("nuevo"))
    monkeypatch.setattr("src.storage.drive_client.MediaFileUpload", lambda *a, **k: SimpleNamespace(stream=lambda: stream))
    storage._service.files.return_value.update.return_value.execute.side_effect = RuntimeError("provider failed")
    with pytest.raises(RuntimeError, match="provider failed"):
        storage.upload_file(str(note))
    assert stream.closed


def test_dry_run_does_not_propose_uploading_duplicate_remote_names(tmp_path):
    files = [meta("apuntes_mesa.md", body("uno"), "one"),
             meta("apuntes_mesa.md", body("dos"), "two")]
    storage, cdir, odir, _ = provider(tmp_path, files)
    (odir / "apuntes_mesa.md").write_bytes(body("local"))
    result = storage.sync_from_google_drive(cdir, odir, dry_run=True)
    assert result["conflicts"]
    assert not any(a["direction"] == "upload" for a in result["actions"])
