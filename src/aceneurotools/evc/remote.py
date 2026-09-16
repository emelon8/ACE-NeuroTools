"""Remotes: publishing experiment history to a shared store.

Push follows git's transfer model in miniature: send every object reachable
from the local head that the remote lacks, then update the remote ref —
**fast-forward only** (the remote head must be an ancestor of what we push, or
unset). Non-fast-forward pushes are rejected rather than force-overwritten;
there is deliberately no ``--force`` in v1.

``LocalDirectoryRemote`` is the first backend (a lab share / synced folder).
The ``Remote`` ABC is the seam where Box, SSH, or an HTTP service plug in
later without touching porcelain.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from aceneurotools.evc.errors import PushRejectedError, RefConflictError
from aceneurotools.evc.refs import RefStore
from aceneurotools.evc.repository import ExperimentRepository
from aceneurotools.evc.store import FileObjectStore


class Remote(ABC):
    """Minimal object-and-ref transfer interface."""

    @abstractmethod
    def has_object(self, oid: str) -> bool: ...

    @abstractmethod
    def receive_object(self, obj_type: str, body: bytes) -> str: ...

    @abstractmethod
    def read_object(self, oid: str) -> tuple[str, bytes]: ...

    @abstractmethod
    def get_ref(self, ref: str) -> str | None: ...

    @abstractmethod
    def set_ref(self, ref: str, new_oid: str, expected_old: str | None) -> None:
        """Compare-and-set; must raise RefConflictError on a lost race."""


class LocalDirectoryRemote(Remote):
    """A bare repository in a local/shared directory (objects + refs, no worktree)."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.objects = FileObjectStore(self.root / "objects")
        self.refs = RefStore(self.root)

    @classmethod
    def create(cls, root: Path) -> LocalDirectoryRemote:
        root = Path(root)
        (root / "objects").mkdir(parents=True, exist_ok=True)
        (root / "refs" / "heads").mkdir(parents=True, exist_ok=True)
        return cls(root)

    def has_object(self, oid: str) -> bool:
        return self.objects.exists(oid)

    def receive_object(self, obj_type: str, body: bytes) -> str:
        return self.objects.write(obj_type, body)

    def read_object(self, oid: str) -> tuple[str, bytes]:
        return self.objects.read(oid)

    def get_ref(self, ref: str) -> str | None:
        return self.refs.read_ref(ref)

    def set_ref(self, ref: str, new_oid: str, expected_old: str | None) -> None:
        self.refs.update_ref(ref, new_oid, expected_old, op="push", message="received push")


@dataclass(frozen=True)
class PushResult:
    ref: str
    old_oid: str | None
    new_oid: str
    objects_sent: int
    up_to_date: bool = False


def push_ref(repo: ExperimentRepository, remote: Remote, ref: str) -> PushResult:
    """Push one local ref to the remote, fast-forward only."""
    local_oid = repo.refs.read_ref(ref)
    if local_oid is None:
        raise PushRejectedError(f"nothing to push: local ref {ref} is unset")
    remote_oid = remote.get_ref(ref)
    if remote_oid == local_oid:
        return PushResult(ref=ref, old_oid=remote_oid, new_oid=local_oid,
                          objects_sent=0, up_to_date=True)
    if remote_oid is not None:
        if not repo.objects.exists(remote_oid):
            raise PushRejectedError(
                f"remote {ref} is at {remote_oid[:12]}, which is unknown locally; "
                "fetch/sync the remote history first"
            )
        if not repo.is_ancestor(remote_oid, local_oid):
            raise PushRejectedError(
                f"non-fast-forward: remote {ref} at {remote_oid[:12]} is not an "
                f"ancestor of local {local_oid[:12]}"
            )
    sent = 0
    for oid in sorted(repo.reachable_objects(local_oid)):
        if not remote.has_object(oid):
            obj_type, body = repo.objects.read(oid)
            remote.receive_object(obj_type, body)
            sent += 1
    try:
        remote.set_ref(ref, local_oid, expected_old=remote_oid)
    except RefConflictError as exc:
        raise PushRejectedError(f"remote {ref} changed during push: {exc}") from exc
    return PushResult(ref=ref, old_oid=remote_oid, new_oid=local_oid, objects_sent=sent)
