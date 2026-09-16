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
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from aceneurotools.evc.errors import EVCError, RefConflictError

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
        if not ref.startswith("refs/") or ".." in ref.split("/"):
            raise EVCError(f"illegal ref name: {ref!r}")
        return self.root / ref

    def read_ref(self, ref: str) -> str | None:
        path = self._ref_path(ref)
        if not path.exists():
            return None
        return path.read_text().strip() or None

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
        """
        path = self._ref_path(ref)
        current = self.read_ref(ref)
        if current != expected_old:
            raise RefConflictError(
                f"ref {ref} is {current or 'unset'}, expected {expected_old or 'unset'}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_oid + "\n")
        self.append_journal(ref, current or ZERO_OID, new_oid, op, message)

    def list_refs(self, prefix: str = "refs/") -> dict[str, str]:
        base = self.root / prefix
        found: dict[str, str] = {}
        if not base.exists():
            return found
        for path in sorted(base.rglob("*")):
            if path.is_file():
                ref = str(path.relative_to(self.root)).replace("\\", "/")
                value = path.read_text().strip()
                if value:
                    found[ref] = value
        return found

    # -- symbolic HEAD ------------------------------------------------------

    def read_head_ref(self) -> str:
        """Return the ref name HEAD points at (``refs/heads/<name>``)."""
        text = (self.root / "HEAD").read_text().strip()
        if not text.startswith("ref: "):
            raise EVCError(f"HEAD is not a symbolic ref: {text!r}")
        return text[len("ref: "):]

    def write_head_ref(self, ref: str) -> None:
        (self.root / "HEAD").write_text(f"ref: {ref}\n")

    def head_oid(self) -> str | None:
        return self.read_ref(self.read_head_ref())

    # -- journal (reflog) ---------------------------------------------------

    @property
    def _journal_path(self) -> Path:
        return self.root / "journal.log"

    def append_journal(self, ref: str, old: str, new: str, op: str, message: str) -> None:
        message = message.replace("\t", " ").replace("\n", " ")
        line = f"{int(time.time())}\t{ref}\t{old}\t{new}\t{op}\t{message}\n"
        with self._journal_path.open("a", encoding="utf-8") as fh:
            fh.write(line)

    def journal(self) -> list[JournalEntry]:
        if not self._journal_path.exists():
            return []
        entries = []
        for line in self._journal_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            ts, ref, old, new, op, message = line.split("\t", 5)
            entries.append(
                JournalEntry(
                    timestamp=int(ts), ref=ref, old=old, new=new, op=op, message=message
                )
            )
        return entries
