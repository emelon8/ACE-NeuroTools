"""References and the recovery journal.

Follows git's reference design (Pro Git §10.3 "Git References"): a ref is a
file under ``refs/`` whose content is a full object id; ``HEAD`` is a symbolic
ref of the form ``ref: refs/heads/<name>``. Updates go through a
compare-and-set method (the equivalent of ``git update-ref``) — refs are never
edited ad hoc.

Every ref update is appended to an immutable **journal** (git's reflog idea,
Pro Git §10.4): tab-separated ``timestamp  ref  old  new  op  message`` lines.
The journal is what makes "recover what I just lost" possible — any object id
that ever appeared in it can be restored even if no ref points to it anymore.

Durability ladder (what survives what):

* **Atomic replacement** — ``HEAD`` and ref files are staged next to their
  destination as ``.tmp-head-*`` / ``.tmp-ref-*``, flushed and fsynced, then
  swapped in with :func:`os.replace`, so a reader never observes an empty or
  partial ref file; a ref file's content is only ever a full object id.
* **Process crash** — residual staging files may remain on disk but are
  ignored (``list_refs`` skips them); refs point only at objects that were
  fully written and fsynced *before* the ref was replaced. A crash after the
  ref replace but before the journal append leaves history intact but the
  newest journal event missing — ``journal()``/``recover()`` still return
  every earlier event. A ``<ref>.lock`` left by a crash is never
  auto-deleted: remove it manually once no other process is running.
* **Power loss** — file contents are fsynced and the parent directory is
  fsynced best-effort where the platform supports it (Windows cannot open a
  directory, so there the directory fsync is silently skipped). No guarantee
  stronger than the filesystem actually honours is claimed.

Order of a single update: object contents fsynced → ref staged/fsynced/
replaced → journal appended/fsynced.
"""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from aceneurotools.evc.errors import EVCError, JournalCorruptError, RefConflictError

ZERO_OID = "0" * 64
DEFAULT_BRANCH = "main"


@dataclass(frozen=True)
class JournalEntry:
    timestamp: int
    ref: str
    old: str
    new: str
    op: str
    message: str


class RefStore:
    """Filesystem-backed refs + symbolic HEAD + append-only journal."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)  # the .evc directory

    # -- plain refs ---------------------------------------------------------

    def _ref_path(self, ref: str) -> Path:
        if not ref.startswith("refs/") or ".." in ref.split("/") or any(c in ref for c in ("\\", "\0", "\n", "\t")):
            raise EVCError(f"illegal ref name: {ref!r}")
        path = self.root / ref
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise EVCError(f"ref resolves outside the repository: {ref!r}")
        return path

    def read_ref(self, ref: str) -> str | None:
        path = self._ref_path(ref)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8").strip() or None

    def update_ref(
        self,
        ref: str,
        new_oid: str,
        expected_old: str | None,
        op: str = "update",
        message: str = "",
    ) -> None:
        """Compare-and-set a ref (git ``update-ref`` semantics) and journal it.

        ``expected_old`` is the oid the caller believes the ref currently has
        (None for "must not exist yet"). A mismatch raises RefConflictError
        instead of silently clobbering someone else's update.

        Concurrency is guarded by an exclusive ``<ref>.lock`` file
        (``O_EXCL``) that is released in ``finally``. A lock file left behind
        by a crash is deliberately **not** auto-deleted (elapsed-time or PID
        heuristics can delete a live lock); later updates raise
        RefConflictError until a human has verified no other process is
        running and removes it.
        """
        path = self._ref_path(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_name(path.name + ".lock")
        try:
            fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise RefConflictError(
                f"ref {ref} is being updated; reload and retry. If a previous "
                f"process crashed, {lock_path} can be removed manually after "
                "verifying no other process is running."
            ) from exc
        os.close(fd)
        staged = None
        try:
            current = self.read_ref(ref)
            if current != expected_old:
                raise RefConflictError(f"ref {ref} is {current or 'unset'}, expected {expected_old or 'unset'}")
            # Lock and validate the shared journal before moving the ref. A
            # competing writer or pre-existing corruption must not move HEAD
            # and then fail to record the event.
            with self._journal_writer() as journal:
                temporary_fd, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-ref-")
                staged = Path(temporary_name)
                with os.fdopen(temporary_fd, "w", encoding="utf-8") as handle:
                    handle.write(new_oid + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(staged, path)
                self._fsync_directory(path.parent)  # durability of the rename itself (best effort)
                self._append_journal_line(journal, ref, current or ZERO_OID, new_oid, op, message)
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
            lock_path.unlink(missing_ok=True)

    def list_refs(self, prefix: str = "refs/") -> dict[str, str]:
        base = self._ref_path(prefix)
        found: dict[str, str] = {}
        if not base.exists():
            return found
        for path in sorted(base.rglob("*")):
            if path.is_file() and not path.name.endswith(".lock") and not path.name.startswith(".tmp-ref-"):
                ref = str(path.relative_to(self.root)).replace("\\", "/")
                value = path.read_text(encoding="utf-8").strip()
                if value:
                    found[ref] = value
        return found

    # -- symbolic HEAD ------------------------------------------------------

    def read_head_ref(self) -> str:
        """Return the ref name HEAD points at (``refs/heads/<name>``)."""
        text = (self.root / "HEAD").read_text().strip()
        if not text.startswith("ref: "):
            raise EVCError(f"HEAD is not a symbolic ref: {text!r}")
        return text[len("ref: ") :]

    def write_head_ref(self, ref: str) -> None:
        """Point HEAD at ``ref`` atomically.

        The new symbolic ref is staged as ``.tmp-head-*`` in the ``.evc``
        directory, flushed and fsynced, then swapped in with :func:`os.replace`
        — an interrupted write never leaves an empty or partial HEAD.
        """
        self._ref_path(ref)  # same ref-name validation as every ref operation
        staged: Path | None = None
        try:
            fd, tmp_name = tempfile.mkstemp(dir=self.root, prefix=".tmp-head-")
            staged = Path(tmp_name)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f"ref: {ref}\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(staged, self.root / "HEAD")
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
        self._fsync_directory(self.root)  # durability of the rename itself (best effort)

    def head_oid(self) -> str | None:
        return self.read_ref(self.read_head_ref())

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        """Best-effort directory fsync; a silent no-op where unsupported.

        Opening a directory for reading is not permitted on Windows and some
        filesystems reject ``fsync`` on directory handles; neither case may
        break a ref update, so both are swallowed.
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

    # -- journal (reflog) ---------------------------------------------------

    @property
    def _journal_path(self) -> Path:
        return self.root / "journal.log"

    def append_journal(self, ref: str, old: str, new: str, op: str, message: str) -> None:
        """Serialize an append, repairing only an interrupted final entry.

        A complete final entry without a newline is preserved and terminated;
        an incomplete final entry is removed before the next append. Earlier
        corruption raises JournalCorruptError without changing the file.
        """
        with self._journal_writer() as journal:
            self._append_journal_line(journal, ref, old, new, op, message)

    @contextmanager
    def _journal_writer(self) -> Iterator[BinaryIO]:
        lock_path = self._journal_path.with_name("journal.log.lock")
        try:
            fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise RefConflictError(
                f"journal is being updated; reload and retry. If a previous process crashed, "
                f"remove {lock_path} manually after verifying no other process is running."
            ) from exc
        os.close(fd)
        try:
            with self._journal_path.open("a+b") as journal:
                journal.seek(0)
                content = journal.read()
                self._journal_entries(content.decode("utf-8", errors="replace"))
                if content and not content.endswith(b"\n"):
                    tail = content.rsplit(b"\n", 1)[-1]
                    if self._parse_journal_line(tail.decode("utf-8", errors="replace")) is None:
                        journal.truncate(len(content) - len(tail))
                    else:
                        journal.write(b"\n")
                    journal.flush()
                    os.fsync(journal.fileno())
                journal.seek(0, os.SEEK_END)
                yield journal
        finally:
            lock_path.unlink(missing_ok=True)

    def _append_journal_line(self, journal: BinaryIO, ref: str, old: str, new: str, op: str, message: str) -> None:
        message = message.replace("\t", " ").replace("\n", " ")
        line = f"{int(time.time())}\t{ref}\t{old}\t{new}\t{op}\t{message}\n"
        journal.write(line.encode("utf-8"))
        journal.flush()
        os.fsync(journal.fileno())
        self._fsync_directory(self._journal_path.parent)  # durability of a newly created journal (best effort)

    def journal(self) -> list[JournalEntry]:
        """Parse every complete journal line, oldest first.

        Blank/whitespace-only lines are skipped wherever they occur. Exactly
        one truncation is tolerated: an *unterminated* final line (an append
        interrupted mid-write, possibly including a torn multi-byte character)
        is dropped so every preceding entry stays recoverable; a valid final
        line without a trailing newline is a complete entry and parses
        normally. Any other malformed line — wrong field count or a
        non-integer timestamp — raises :class:`JournalCorruptError` naming the
        journal path and its 1-based line number; corruption in the middle of
        the journal is never silently discarded.
        """
        if not self._journal_path.exists():
            return []
        # ``errors="replace"`` keeps a torn multi-byte character in the tail
        # from turning the whole recovery into a UnicodeDecodeError.
        text = self._journal_path.read_text(encoding="utf-8", errors="replace")
        return self._journal_entries(text)

    def _journal_entries(self, text: str) -> list[JournalEntry]:
        lines = text.split("\n")
        unterminated_tail = not text.endswith("\n")
        entries: list[JournalEntry] = []
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            entry = self._parse_journal_line(line)
            if entry is None:
                if unterminated_tail and index == len(lines) - 1:
                    continue  # interrupted append: drop only this tail
                raise JournalCorruptError(f"journal {self._journal_path}: malformed line {index + 1}: {line!r}")
            entries.append(entry)
        return entries

    @staticmethod
    def _parse_journal_line(line: str) -> JournalEntry | None:
        """Return the entry a journal line encodes, or None if malformed."""
        fields = line.split("\t", 5)
        if len(fields) != 6:
            return None
        ts, ref, old, new, op, message = fields
        try:
            timestamp = int(ts)
        except ValueError:
            return None
        return JournalEntry(timestamp=timestamp, ref=ref, old=old, new=new, op=op, message=message)
