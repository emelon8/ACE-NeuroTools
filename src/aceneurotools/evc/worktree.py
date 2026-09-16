"""Working-state snapshot and materialisation.

The "working tree" of an experiment is the directory holding its live
parameter/configuration files (and small result manifests). ``snapshot``
converts that directory into immutable tree/blob objects; ``materialize``
writes a recorded tree back out. Both operations ignore the ``.evc/``
repository directory itself plus a configurable ignore set, mirroring how git
never tracks ``.git/``.

What is versioned is policy, not code (plan §Phase 1): in addition to the
small structural ignore set below, patterns are read from the declarative
``.evc/ignore`` file — one name or glob per line — so bulk artifacts (raw
recordings, memmaps) never enter the object store. See
:class:`IgnoreRules` for the matching rules and
``aceneurotools.evc.workspace`` for the safe defaults written at ``init``.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from aceneurotools.evc.objects import MODE_DIR, MODE_FILE, Tree, TreeEntry
from aceneurotools.evc.repository import EVC_DIR, ExperimentRepository

#: Structural ignores that hold even without an ignore file: the repository
#: itself is never versioned (git never tracks ``.git/``), nor OS/VCS noise.
DEFAULT_IGNORES = frozenset({EVC_DIR, ".DS_Store", ".git"})

#: Name of the declarative ignore file inside ``.evc/``.
IGNORE_FILE = "ignore"


@dataclass(frozen=True)
class IgnoreRules:
    """Glob patterns from ``.evc/ignore`` deciding what stays unversioned.

    File format — one pattern per line, blank lines and ``#`` comments
    skipped:

    * a trailing ``/`` restricts the pattern to directories
      (``saved_movies/`` ignores directories of that name, not files);
    * a pattern containing ``/`` is matched against the path relative to the
      experiment root (``results/tmp-*``);
    * any other pattern is matched against the entry's name at any depth
      (``*.avi``).

    Matching is case-sensitive on every platform (``fnmatchcase``) so
    snapshots are deterministic across machines.
    """

    patterns: tuple[str, ...] = ()

    @classmethod
    def load(cls, path: Path) -> IgnoreRules:
        """Read an ignore file; a missing file means no extra rules."""
        if not path.is_file():
            return cls()
        patterns = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
        return cls(patterns=tuple(patterns))

    def ignores(self, rel_path: str, is_dir: bool) -> bool:
        """True if an entry at ``rel_path`` (relative to the root) is ignored."""
        name = rel_path.rsplit("/", 1)[-1]
        for pattern in self.patterns:
            dir_only = pattern.endswith("/")
            if dir_only and not is_dir:
                continue
            stripped = pattern.rstrip("/")
            target = rel_path if "/" in stripped else name
            if fnmatchcase(target, stripped):
                return True
        return False


class WorkingTree:
    """Reads and writes the live experiment directory."""

    def __init__(self, repo: ExperimentRepository, ignores: frozenset[str] = DEFAULT_IGNORES):
        self.repo = repo
        self.root = repo.worktree_dir
        self.ignores = ignores

    def _ignore_rules(self) -> IgnoreRules:
        """Load ``.evc/ignore`` fresh per operation so edits take effect."""
        return IgnoreRules.load(self.repo.evc_dir / IGNORE_FILE)

    def _skip(self, child: Path, rel_path: str, rules: IgnoreRules) -> bool:
        if child.name in self.ignores:
            return True
        if child.is_symlink():
            return True  # symlinks are not part of the versioned state (v1)
        return rules.ignores(rel_path, child.is_dir())

    # -- capture ------------------------------------------------------------

    def snapshot(self) -> str:
        """Write the current directory contents as objects; return the tree id."""
        return self._snapshot_dir(self.root, self._ignore_rules(), prefix="")

    def _snapshot_dir(self, directory: Path, rules: IgnoreRules, prefix: str) -> str:
        entries = []
        for child in sorted(directory.iterdir(), key=lambda p: p.name):
            rel_path = f"{prefix}{child.name}"
            if self._skip(child, rel_path, rules):
                continue
            if child.is_dir():
                subtree_oid = self._snapshot_dir(child, rules, prefix=f"{rel_path}/")
                entries.append(
                    TreeEntry(mode=MODE_DIR, type="tree", oid=subtree_oid, name=child.name)
                )
            elif child.is_file():
                blob_oid = self.repo.write_blob(child.read_bytes())
                entries.append(
                    TreeEntry(mode=MODE_FILE, type="blob", oid=blob_oid, name=child.name)
                )
        return self.repo.write_tree(Tree(entries=tuple(entries)))

    # -- restore ------------------------------------------------------------

    def materialize(self, tree_oid: str) -> None:
        """Make the working directory exactly match a recorded tree.

        Files not present in the target tree are removed (ignored names are
        left untouched); directories are created as needed. Callers are
        responsible for preserving dirty state first — see
        ``ExperimentVersionControl.restore``, which snapshots before it
        overwrites so nothing is ever lost.
        """
        rules = self._ignore_rules()
        target = self.repo.flatten_tree(tree_oid)
        current = self._list_files(self.root, rules)
        for rel_path in sorted(set(current) - set(target)):
            (self.root / rel_path).unlink()
        for rel_path, blob_oid in sorted(target.items()):
            dest = self.root / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(self.repo.read_blob(blob_oid).data)
        self._prune_empty_dirs(self.root, rules)

    # -- inspection ---------------------------------------------------------

    def _list_files(self, directory: Path, rules: IgnoreRules, prefix: str = "") -> list[str]:
        found = []
        for child in sorted(directory.iterdir(), key=lambda p: p.name):
            rel_path = f"{prefix}{child.name}"
            if self._skip(child, rel_path, rules):
                continue
            if child.is_dir():
                found.extend(self._list_files(child, rules, prefix=f"{rel_path}/"))
            elif child.is_file():
                found.append(rel_path)
        return found

    def _prune_empty_dirs(self, directory: Path, rules: IgnoreRules, prefix: str = "") -> None:
        for child in sorted(directory.iterdir(), key=lambda p: p.name):
            rel_path = f"{prefix}{child.name}"
            if not child.is_dir() or self._skip(child, rel_path, rules):
                continue
            self._prune_empty_dirs(child, rules, prefix=f"{rel_path}/")
            if not any(child.iterdir()):
                child.rmdir()
