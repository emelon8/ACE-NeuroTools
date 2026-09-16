"""Working-state snapshot and materialisation.

The "working tree" of an experiment is the directory holding its live
parameter/configuration files (and small result manifests). ``snapshot``
converts that directory into immutable tree/blob objects; ``materialize``
writes a recorded tree back out. Both operations ignore the ``.evc/``
repository directory itself plus a configurable ignore set, mirroring how git
never tracks ``.git/``.
"""

from __future__ import annotations

from pathlib import Path

from aceneurotools.evc.objects import MODE_DIR, MODE_FILE, Tree, TreeEntry
from aceneurotools.evc.repository import EVC_DIR, ExperimentRepository

DEFAULT_IGNORES = frozenset({EVC_DIR, ".DS_Store", ".git"})


class WorkingTree:
    """Reads and writes the live experiment directory."""

    def __init__(self, repo: ExperimentRepository, ignores: frozenset[str] = DEFAULT_IGNORES):
        self.repo = repo
        self.root = repo.worktree_dir
        self.ignores = ignores

    # -- capture ------------------------------------------------------------

    def snapshot(self) -> str:
        """Write the current directory contents as objects; return the tree id."""
        return self._snapshot_dir(self.root)

    def _snapshot_dir(self, directory: Path) -> str:
        entries = []
        for child in sorted(directory.iterdir(), key=lambda p: p.name):
            if child.name in self.ignores:
                continue
            if child.is_symlink():
                continue  # symlinks are not part of the versioned state (v1)
            if child.is_dir():
                subtree_oid = self._snapshot_dir(child)
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
        target = self.repo.flatten_tree(tree_oid)
        current = self._list_files(self.root)
        for rel_path in sorted(set(current) - set(target)):
            (self.root / rel_path).unlink()
        for rel_path, blob_oid in sorted(target.items()):
            dest = self.root / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(self.repo.read_blob(blob_oid).data)
        self._prune_empty_dirs(self.root)

    # -- inspection ---------------------------------------------------------

    def _list_files(self, directory: Path, prefix: str = "") -> list[str]:
        found = []
        for child in sorted(directory.iterdir(), key=lambda p: p.name):
            if child.name in self.ignores or child.is_symlink():
                continue
            rel = f"{prefix}{child.name}"
            if child.is_dir():
                found.extend(self._list_files(child, prefix=f"{rel}/"))
            elif child.is_file():
                found.append(rel)
        return found

    def _prune_empty_dirs(self, directory: Path) -> None:
        for child in sorted(directory.iterdir(), key=lambda p: p.name):
            if child.name in self.ignores or not child.is_dir() or child.is_symlink():
                continue
            self._prune_empty_dirs(child)
            if not any(child.iterdir()):
                child.rmdir()
