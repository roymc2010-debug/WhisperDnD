"""Slow optional services and native audio must not block unrelated requests."""
import asyncio
import threading
from unittest.mock import MagicMock

import pytest

from src.api import server
from src.api.routers import audio, drive


@pytest.mark.parametrize("operation", ["devices", "levels", "drive_status", "drive_sync"])
def test_slow_device_or_drive_operation_does_not_block_health(operation, monkeypatch):
    release = threading.Event()
    entered = threading.Event()

    def slow(*args, **kwargs):
        entered.set()
        release.wait(timeout=1)
        return False if operation.startswith("drive") else {}

    storage = MagicMock()
    storage.is_connected.side_effect = slow
    monkeypatch.setattr(server, "GoogleDriveStorage", lambda: storage)
    monkeypatch.setattr(server, "get_audio_devices", slow)
    monkeypatch.setattr(server, "get_audio_levels", slow)
    operations = {"devices": audio.get_audio_devices_endpoint, "levels": audio.test_audio_level,
                  "drive_status": drive.get_drive_status, "drive_sync": drive.sync_drive_endpoint}

    async def exercise():
        task = asyncio.create_task(operations[operation]())
        try:
            await asyncio.to_thread(entered.wait, 1)
            assert (await server.keep_alive_ping())["status"] == "alive"
            assert not task.done(), "The slow operation blocked health until it finished"
        finally:
            release.set()
            await task

    asyncio.run(exercise())


def test_key_check_can_finish_when_drive_does_not_respond(monkeypatch):
    release = threading.Event()
    storage = MagicMock()
    storage.is_connected.side_effect = lambda: release.wait(timeout=1)
    monkeypatch.setattr(server, "GoogleDriveStorage", lambda: storage)
    monkeypatch.setattr(server, "extract_client_api_keys", lambda request: ("test-groq", "test-gemini"))
    monkeypatch.setattr(drive, "_keys_cache", {"data": None, "cache_key": None, "timestamp": 0})
    monkeypatch.setattr(drive, "DRIVE_KEY_CHECK_TIMEOUT", 0.03, raising=False)
    monkeypatch.setattr("groq.Client", MagicMock())
    monkeypatch.setattr("google.genai.Client", MagicMock())

    async def exercise():
        try:
            result = await asyncio.wait_for(drive.check_api_keys(), timeout=0.5)
            assert result["groq"] is True
            assert result["gemini"] is True
            assert result["drive"] is None  # no answer is not proof of disconnection
        finally:
            release.set()

    asyncio.run(exercise())


def test_key_only_check_never_touches_drive(monkeypatch):
    monkeypatch.setattr(server, "extract_client_api_keys", lambda request: ("test-groq", "test-gemini"))
    monkeypatch.setattr(drive, "_keys_cache", {"data": None, "cache_key": None, "timestamp": 0})
    monkeypatch.setattr("groq.Client", MagicMock())
    monkeypatch.setattr("google.genai.Client", MagicMock())
    storage = MagicMock(side_effect=AssertionError("Key verification must not access Drive"))
    monkeypatch.setattr(server, "GoogleDriveStorage", storage)
    result = asyncio.run(drive.check_api_keys(include_drive=False))
    assert result["groq"] is True and result["gemini"] is True
    assert result["drive"] is None
    storage.assert_not_called()


def test_slow_drive_token_refresh_does_not_block_key_verification(monkeypatch):
    release, entered = threading.Event(), threading.Event()
    storage = MagicMock()
    def slow():
        entered.set()
        release.wait(timeout=1)
        return True
    storage.is_connected.side_effect = slow
    storage.token_path.is_file.return_value = True
    storage.token_path.read_text.return_value = '{}'
    monkeypatch.setattr(server, "GoogleDriveStorage", lambda: storage)
    monkeypatch.setattr(server, "extract_client_api_keys", lambda request: ("test-groq", "test-gemini"))
    monkeypatch.setattr(drive, "_keys_cache", {"data": None, "cache_key": None, "timestamp": 0})
    monkeypatch.setattr("groq.Client", MagicMock())
    monkeypatch.setattr("google.genai.Client", MagicMock())
    async def exercise():
        task = asyncio.create_task(drive.get_drive_token_endpoint())
        try:
            await asyncio.to_thread(entered.wait, 1)
            # Even the old default check must finish before the Drive refresh.
            monkeypatch.setattr(drive, "DRIVE_KEY_CHECK_TIMEOUT", 0.02)
            result = await asyncio.wait_for(drive.check_api_keys(), timeout=0.4)
            assert result["groq"] is True and result["gemini"] is True
            assert not task.done(), "Drive token refresh blocked unrelated requests"
        finally:
            release.set()
            await task
    asyncio.run(exercise())


def test_startup_drive_refresh_leaves_server_responsive(monkeypatch):
    release = threading.Event()
    entered = threading.Event()
    storage = MagicMock()

    def slow():
        entered.set()
        release.wait(timeout=1)
        return False

    storage.is_connected.side_effect = slow
    monkeypatch.setattr(server, "GoogleDriveStorage", lambda: storage)

    async def exercise():
        original_create = asyncio.create_task
        tasks = []

        def capture(coro):
            task = original_create(coro)
            tasks.append(task)
            return task

        monkeypatch.setattr(asyncio, "create_task", capture)
        await server.on_server_startup()
        try:
            await asyncio.to_thread(entered.wait, 1)
            assert (await server.keep_alive_ping())["status"] == "alive"
            assert not tasks[0].done()
        finally:
            release.set()
            await tasks[0]

    asyncio.run(exercise())


def test_startup_sync_can_be_disabled_for_safe_diagnostics(monkeypatch):
    monkeypatch.setenv("WHISPER_SKIP_STARTUP_DRIVE_SYNC", "1")
    storage = MagicMock(side_effect=AssertionError("Diagnostic startup must not access Drive"))
    monkeypatch.setattr(server, "GoogleDriveStorage", storage)
    async def exercise():
        await server.on_server_startup()
        await asyncio.sleep(0.02)
        storage.assert_not_called()
    asyncio.run(exercise())


def test_explicit_connection_check_bypasses_the_cached_failure(monkeypatch):
    available=[False]
    groq=MagicMock()
    def models():
        if not available[0]:raise RuntimeError('Temporary connectivity failure')
        return []
    groq.models.list.side_effect=models
    monkeypatch.setattr(server,'extract_client_api_keys',lambda request:('test-groq','test-gemini'))
    monkeypatch.setattr(drive,'_keys_cache',{'data':None,'cache_key':None,'timestamp':0})
    monkeypatch.setattr('groq.Client',lambda **kwargs:groq)
    monkeypatch.setattr('google.genai.Client',MagicMock())
    monkeypatch.setattr(server,'GoogleDriveStorage',lambda:(_ for _ in ()).throw(AssertionError('Drive must stay separate')))
    async def exercise():
        first=await drive.check_api_keys(include_drive=False)
        assert first['groq'] is False
        available[0]=True
        cached=await drive.check_api_keys(include_drive=False)
        assert cached['groq'] is False
        fresh=await drive.check_api_keys(include_drive=False,force=True)
        assert fresh['groq'] is True and fresh['gemini'] is True
    asyncio.run(exercise())
