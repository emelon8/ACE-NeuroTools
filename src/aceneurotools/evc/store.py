"""Content-addressed object storage.

Mirrors git's loose-object store (Pro Git §10.2): each object is zlib-compressed
``<type> <size>\\0<body>`` written to ``objects/<first-2-hex>/<rest>``. Writes
are atomic (temp file + rename) and idempotent — an object that already exists
is never rewritten, which is what makes history immutable. Reads re-hash the
payload and refuse to return bytes whose id does not match (integrity check).

Durability ladder:

* **Atomic replacement** — the payload is staged as ``.tmp-obj-*`` next to its
  destination and swapped in with :func:`os.replace`, so a reader never
  observes a partially written object.
* **Process crash** — the staged payload is flushed and fsynced *before* the
  rename, and a ref is only updated after :meth:`FileObjectStore.write` has
  returned, so any object a ref points at was fully written. A crash may leave
  ``.tmp-obj-*`` files behind; they are never read (lookups go by content id)
  and never rewritten, so they are harmless.
* **Power loss** — file contents are fsynced, and the parent directory is
  fsynced best-effort after the rename where the platform supports it
  (Windows cannot open a directory, so the directory fsync is silently
  skipped). No guarantee stronger than the filesystem actually honours is
  claimed.
"""

from __future__ import annotations

import os
import tempfile
import zlib
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from aceneurotools.evc.errors import (
    AmbiguousIdError,
    CorruptObjectError,
    InvalidObjectError,
    ObjectNotFoundError,
)
from aceneurotools.evc.objects import OBJECT_TYPES, object_id

_OID_HEX_LEN = 64  # SHA-256


def _fsync_directory(directory: Path) -> None:
    """Best-effort directory fsync; a silent no-op where unsupported.

    Windows does not allow ``os.open`` on a directory and some filesystems
    reject ``fsync`` on directory handles; neither may break an object write.
    """
    try:
        dir_fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


class ObjectStore(ABC):
    """Minimal interface every object store backend must provide."""

    @abstractmethod
    def write(self, obj_type: str, body: bytes) -> str:
        """Store an object; return its id. Idempotent."""

    @abstractmethod
    def read(self, oid: str) -> tuple[str, bytes]:
        """Return ``(type, body)`` for an object id. Verifies integrity."""

    @abstractmethod
    def exists(self, oid: str) -> bool: ...

    @abstractmethod
    def iter_oids(self) -> Iterator[str]:
        """Yield every stored object id."""


class FileObjectStore(ObjectStore):
    """Loose-object store on the local filesystem (git's layout)."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, oid: str) -> Path:
        if not isinstance(oid, str) or len(oid) != _OID_HEX_LEN or any(c not in "0123456789abcdef" for c in oid):
            raise InvalidObjectError(f"not a valid full object id: {oid!r}")
        return self.root / oid[:2] / oid[2:]

    def write(self, obj_type: str, body: bytes) -> str:
        if obj_type not in OBJECT_TYPES:
            raise InvalidObjectError(f"unknown object type: {obj_type!r}")
        oid = object_id(obj_type, body)
        path = self._path(oid)
        if path.exists():
            return oid  # immutable: identical content is already stored
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = zlib.compress(f"{obj_type} {len(body)}\0".encode() + body)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-obj-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())  # durable before the rename: refs may point here next
            os.replace(tmp_name, path)
            _fsync_directory(path.parent)  # durability of the rename itself (best effort)
        except BaseException:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise
        return oid

    def read(self, oid: str) -> tuple[str, bytes]:
        path = self._path(oid)
        if not path.exists():
            raise ObjectNotFoundError(f"object {oid} not found")
        try:
            raw = zlib.decompress(path.read_bytes())
        except zlib.error as exc:
            raise CorruptObjectError(f"object {oid}: invalid compressed data") from exc
        header, separator, body = raw.partition(b"\0")
        if not separator:
            raise CorruptObjectError(f"object {oid}: missing header separator")
        try:
            obj_type, size_text = header.decode().split(" ")
            declared_size = int(size_text)
        except ValueError as exc:
            raise CorruptObjectError(f"object {oid}: malformed header") from exc
        if declared_size != len(body):
            raise CorruptObjectError(f"object {oid}: size mismatch")
        if obj_type not in OBJECT_TYPES:
            raise CorruptObjectError(f"object {oid}: unknown type {obj_type!r}")
        if object_id(obj_type, body) != oid:
            raise CorruptObjectError(f"object {oid}: content does not match id")
        return obj_type, body

    def exists(self, oid: str) -> bool:
        return self._path(oid).exists()

    def iter_oids(self) -> Iterator[str]:
        if not self.root.exists():
            return
        for fan_out in sorted(self.root.iterdir()):
            if not fan_out.is_dir() or len(fan_out.name) != 2 or any(c not in "0123456789abcdef" for c in fan_out.name):
                continue
            for entry in sorted(fan_out.iterdir()):
                if (
                    entry.is_file()
                    and len(entry.name) == _OID_HEX_LEN - 2
                    and all(c in "0123456789abcdef" for c in entry.name)
                ):
                    yield fan_out.name + entry.name

    def resolve_prefix(self, prefix: str) -> str:
        """Expand a short (>= 4 hex chars) unique object-id prefix to a full id."""
        prefix = prefix.lower()
        if len(prefix) == _OID_HEX_LEN:
            if not self.exists(prefix):
                raise ObjectNotFoundError(f"object {prefix} not found")
            return prefix
        if len(prefix) < 4 or any(c not in "0123456789abcdef" for c in prefix):
            raise ObjectNotFoundError(f"not a valid object-id prefix: {prefix!r}")
        matches = [oid for oid in self.iter_oids() if oid.startswith(prefix)]
        if not matches:
            raise ObjectNotFoundError(f"no object matches prefix {prefix!r}")
        if len(matches) > 1:
            raise AmbiguousIdError(f"prefix {prefix!r} matches {len(matches)} objects")
        return matches[0]
