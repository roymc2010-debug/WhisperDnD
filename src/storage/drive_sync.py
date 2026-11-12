"""Local sync checkpoints and coalescing; no API calls or content ownership rules."""
from concurrent.futures import Future
from copy import deepcopy
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading


_flights = {}
_flights_lock = threading.Lock()


def content_hash(path):
    try:
        with Path(path).open("rb") as stream:
            h = hashlib.md5()
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()
    except FileNotFoundError:
        return None


def coalesce_sync(function):
    """Simultaneous callers share the same result, not duplicate transfers.

    The synchronous API is called from worker threads by HTTP routes. Waiters
    wait only there; API verification never waits for this future.
    """
    @wraps(function)
    def wrapped(self, campaigns_dir=None, output_dir=None, **kwargs):
        root = Path(__file__).resolve().parents[2]
        cdir = Path(campaigns_dir or root / "data/campaigns").resolve()
        odir = Path(output_dir or root / "data/output").resolve()
        key = (str(self.token_path.resolve()), str(cdir), str(odir),
               tuple(sorted((k, v) for k, v in kwargs.items() if v is not False and v is not None)))
        with _flights_lock:
            future = _flights.get(key)
            owner = future is None
            if owner:
                future = Future()
                _flights[key] = future
        if not owner:
            return deepcopy(future.result())
        try:
            odir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".drive-sync-", dir=odir) as folder:
                self._sync_local.workspace = Path(folder)
                result = function(self, campaigns_dir, output_dir, **kwargs)
            future.set_result(deepcopy(result))
            return result
        except BaseException as exc:
            future.set_exception(exc)
            raise
        finally:
            with _flights_lock:
                if _flights.get(key) is future:
                    _flights.pop(key)
    return wrapped


class SyncCheckpoint:
    """Three-way hash comparison. Unknown divergence is never size equality."""
    def __init__(self, directory, scope):
        fingerprint = hashlib.sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()[:16]
        self.path = Path(directory) / f".drive-sync-{fingerprint}.json"
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.entries = data["entries"] if data.get("version") == 1 else {}
        except (OSError, ValueError, KeyError):
            self.entries = {}

    def direction(self, path, remote, *, campaign=False):
        local = content_hash(path)
        if local is None:
            return "download"
        digest = remote.get("md5Checksum")
        if digest and local == str(digest).lower():
            return "equal"
        previous = self.entries.get(str(Path(path).resolve()))
        if previous and previous.get("remote_id") == remote.get("id") and digest:
            local_changed = local != previous.get("local_md5")
            remote_changed = str(digest).lower() != previous.get("remote_md5")
            if not local_changed and not remote_changed:
                return "equal"  # accepted campaign serialization may differ
            if local_changed and not remote_changed:
                return "upload"
            if remote_changed and not local_changed:
                return "download"
            return "conflict"
        # Campaigns retain the existing schema/freshness importer; it needs a
        # read to decide on first contact. Documents have no such safe rule.
        return "probe" if campaign else "conflict"

    def remember(self, path, remote, remote_digest=None, *, local_digest=None):
        local = local_digest or content_hash(path)
        digest = remote_digest or remote.get("md5Checksum")
        if local and digest and isinstance(remote.get("id"), str):
            self.entries[str(Path(path).resolve())] = {
                "local_md5": local, "remote_md5": str(digest).lower(),
                "remote_id": remote.get("id"),
            }

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                         prefix=".drive-checkpoint-", delete=False) as stream:
            json.dump({"version": 1, "entries": self.entries}, stream, ensure_ascii=False)
            temp = stream.name
        os.replace(temp, self.path)
