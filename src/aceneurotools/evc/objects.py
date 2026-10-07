"""Immutable object model: blobs, trees, and commits.

Follows git's content-addressable object design (Pro Git §10.2 "Git Objects",
https://git-scm.com/book/en/v2/Git-Internals-Git-Objects): every object is
serialised as ``<type> <size>\\0<body>``, hashed, and stored under its hash, so
identical content always has the same id and objects are immutable by
construction.

Documented deviations from git (see docs/design/experiment-version-control.md):

* **SHA-256** object ids instead of SHA-1, per git's own hash-function
  transition plan (git docs: gitformat-hash-function-transition).
* **Text tree format**: one ``<mode> <type> <oid>\\t<name>`` line per entry
  (the format ``git cat-file -p`` displays) instead of git's binary tree
  encoding. Entries are sorted by name, so serialisation is deterministic.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from aceneurotools.evc.errors import InvalidObjectError

BLOB = "blob"
TREE = "tree"
COMMIT = "commit"
OBJECT_TYPES = (BLOB, TREE, COMMIT)

MODE_FILE = "100644"
MODE_DIR = "040000"

_NAME_FORBIDDEN = ("/", "\0", "\t", "\n")


def object_id(obj_type: str, body: bytes) -> str:
    """Return the SHA-256 object id of ``<type> <size>\\0<body>`` (git's header rule)."""
    if obj_type not in OBJECT_TYPES:
        raise InvalidObjectError(f"unknown object type: {obj_type!r}")
    header = f"{obj_type} {len(body)}\0".encode()
    return hashlib.sha256(header + body).hexdigest()


@dataclass(frozen=True)
class Blob:
    """Raw file content (a parameter file, manifest, note, ...)."""

    data: bytes

    @property
    def type(self) -> str:
        return BLOB

    def serialize(self) -> bytes:
        return self.data

    @classmethod
    def parse(cls, body: bytes) -> Blob:
        return cls(data=body)

    @property
    def oid(self) -> str:
        return object_id(BLOB, self.serialize())


@dataclass(frozen=True)
class TreeEntry:
    """One row of a tree: a named pointer to a blob or subtree."""

    mode: str
    type: str
    oid: str
    name: str

    def __post_init__(self) -> None:
        if self.type not in (BLOB, TREE):
            raise InvalidObjectError(f"tree entry type must be blob or tree, got {self.type!r}")
        if self.mode not in (MODE_FILE, MODE_DIR):
            raise InvalidObjectError(f"unsupported tree entry mode: {self.mode!r}")
        if (self.type == TREE) != (self.mode == MODE_DIR):
            raise InvalidObjectError(f"mode {self.mode!r} inconsistent with type {self.type!r}")
        if not self.name:
            raise InvalidObjectError("tree entry name must be non-empty")
        if any(ch in self.name for ch in _NAME_FORBIDDEN) or self.name in (".", ".."):
            raise InvalidObjectError(f"illegal tree entry name: {self.name!r}")


@dataclass(frozen=True)
class Tree:
    """A directory snapshot: sorted, named references to blobs and subtrees."""

    entries: tuple[TreeEntry, ...]

    def __post_init__(self) -> None:
        names = [e.name for e in self.entries]
        if len(set(names)) != len(names):
            raise InvalidObjectError("duplicate names in tree")
        object.__setattr__(self, "entries", tuple(sorted(self.entries, key=lambda e: e.name)))

    @property
    def type(self) -> str:
        return TREE

    def serialize(self) -> bytes:
        lines = [f"{e.mode} {e.type} {e.oid}\t{e.name}\n" for e in self.entries]
        return "".join(lines).encode()

    @classmethod
    def parse(cls, body: bytes) -> Tree:
        entries = []
        for line in body.decode().splitlines():
            if not line:
                continue
            try:
                meta, name = line.split("\t", 1)
                mode, otype, oid = meta.split(" ")
            except ValueError as exc:
                raise InvalidObjectError(f"malformed tree entry: {line!r}") from exc
            entries.append(TreeEntry(mode=mode, type=otype, oid=oid, name=name))
        return cls(entries=tuple(entries))

    @property
    def oid(self) -> str:
        return object_id(TREE, self.serialize())


@dataclass(frozen=True)
class Commit:
    """A recorded experiment revision.

    Serialised exactly in git's commit field order (Pro Git §10.2):
    ``tree``, zero or more ``parent`` lines, ``author``, ``committer``,
    blank line, message.
    """

    tree: str
    parents: tuple[str, ...]
    author: str
    author_time: int
    author_tz: str
    message: str
    committer: str = field(default="")
    committer_time: int = field(default=0)
    committer_tz: str = field(default="")

    def __post_init__(self) -> None:
        if "\n" in self.author or "<" not in self.author:
            raise InvalidObjectError(f"author must be single-line 'Name <email>', got {self.author!r}")
        if not self.committer:
            object.__setattr__(self, "committer", self.author)
            object.__setattr__(self, "committer_time", self.author_time)
            object.__setattr__(self, "committer_tz", self.author_tz)

    @property
    def type(self) -> str:
        return COMMIT

    def serialize(self) -> bytes:
        lines = [f"tree {self.tree}"]
        lines.extend(f"parent {p}" for p in self.parents)
        lines.append(f"author {self.author} {self.author_time} {self.author_tz}")
        lines.append(f"committer {self.committer} {self.committer_time} {self.committer_tz}")
        return ("\n".join(lines) + "\n\n" + self.message).encode()

    @classmethod
    def parse(cls, body: bytes) -> Commit:
        text = body.decode()
        try:
            headers, message = text.split("\n\n", 1)
        except ValueError as exc:
            raise InvalidObjectError("commit missing blank line before message") from exc
        tree = ""
        parents: list[str] = []
        author = committer = ""
        a_time = c_time = 0
        a_tz = c_tz = "+0000"
        for line in headers.splitlines():
            key, _, value = line.partition(" ")
            if key == "tree":
                tree = value
            elif key == "parent":
                parents.append(value)
            elif key in ("author", "committer"):
                ident, _, tail = value.rpartition("> ")
                who = ident + ">"
                try:
                    ts, tz = tail.split(" ")
                except ValueError as exc:
                    raise InvalidObjectError(f"malformed {key} line: {line!r}") from exc
                if key == "author":
                    author, a_time, a_tz = who, int(ts), tz
                else:
                    committer, c_time, c_tz = who, int(ts), tz
            else:
                raise InvalidObjectError(f"unknown commit header: {key!r}")
        if not tree or not author:
            raise InvalidObjectError("commit requires tree and author headers")
        return cls(
            tree=tree,
            parents=tuple(parents),
            author=author,
            author_time=a_time,
            author_tz=a_tz,
            message=message,
            committer=committer,
            committer_time=c_time,
            committer_tz=c_tz,
        )

    @property
    def oid(self) -> str:
        return object_id(COMMIT, self.serialize())
