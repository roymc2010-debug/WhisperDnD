r"""Run pytest with temporary app data, dummy credentials and blocked outbound TCP.

Usage: .venv\Scripts\python.exe -X utf8 scripts/run_offline_tests.py -q
Native audio capture tests remain disabled. asyncio's local socket pairs are allowed.
"""
import os
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch


def main(args=None):
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    connect = socket.socket.connect
    connect_ex = socket.socket.connect_ex

    def blocked(*unused_args, **unused_kwargs):
        raise RuntimeError("Network disabled for offline regression tests")

    def local_connect(sock, address):
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return connect(sock, address)
        return blocked()

    def local_connect_ex(sock, address):
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return connect_ex(sock, address)
        return blocked()

    with tempfile.TemporaryDirectory(prefix="whisperdnd-offline-") as temporary:
        sandbox = Path(temporary)
        environment = {f"WHISPER_{key}_DIR": str(sandbox / key.lower())
                       for key in ("INPUT", "OUTPUT", "CAMPAIGNS", "QUOTA")}
        environment.update(TESTING="1", WHISPER_ENV="test", WHISPER_NATIVE_AUDIO_TEST="0",
                           GEMINI_API_KEY="offline-test-key", GROQ_API_KEY="offline-test-key",
                           GOOGLE_API_KEY="offline-test-key")
        with patch.dict(os.environ, environment), patch.object(socket.socket, "connect", local_connect), \
                patch.object(socket.socket, "connect_ex", local_connect_ex), \
                patch.object(socket, "create_connection", blocked):
            import pytest
            return pytest.main(["--basetemp", str(sandbox / "pytest"),
                                *(sys.argv[1:] if args is None else args)])


if __name__ == "__main__":
    raise SystemExit(main())
