"""ExperimentRepository — the plumbing layer.

Owns the on-disk layout of one experiment's ``.evc/`` directory and exposes
git-plumbing-style primitives (hash-object, cat-file, commit-tree, update-ref,
rev-parse). Porcelain commands are built exclusively from these primitives, the
same layered design git itself uses (Pro Git §10.1: "plumbing and porcelain").

Layout inside an experiment directory::

    <experiment>/.evc/
        config.json          format + hash-algorithm declaration
        HEAD                 symbolic ref, e.g. "ref: refs/heads/main"
        objects/ab/cd...     zlib loose objects (content-addressed)
        refs/heads/<name>    branch heads
        refs/notes/comments  post-hoc annotation history
        journal.log          append-only recovery journal (reflog)
"""

from __future__ import annotations

import json
from pathlib import Path

from aceneurotools.evc.errors import (
    EVCError,
    ObjectNotFoundError,
    RepositoryExistsError,
    RepositoryNotFoundError,
    UnknownRevisionError,
)
from aceneurotools.evc.objects import COMMIT, Blob, Commit, Tree
from aceneurotools.evc.refs import DEFAULT_BRANCH, RefStore
from aceneurotools.evc.store import FileObjectStore

EVC_DIR = ".evc"
FORMAT_VERSION = 1
HASH_ALGORITHM = "sha256"
NOTES_REF = "refs/notes/comments"


class ExperimentRepository:
    """Plumbing operations over one experiment's object store and refs."""

    def __init__(self, worktree_dir: Path) -> None:
        self.worktree_dir = Path(worktree_dir)
        self.evc_dir = self.worktree_dir / EVC_DIR
        self.objects = FileObjectStore(self.evc_dir / "objects")
        self.refs = RefStore(self.evc_dir)

    # -- lifecycle ----------------------------------------------------------

    @classmethod
    def init(cls, worktree_dir: Path, branch: str = DEFAULT_BRANCH) -> ExperimentRepository:
        worktree_dir = Path(worktree_dir)
        evc_dir = worktree_dir / EVC_DIR
        if evc_dir.exists():
            raise RepositoryExistsError(f"repository already exists at {evc_dir}")
        (evc_dir / "objects").mkdir(parents=True)
        (evc_dir / "refs" / "heads").mkdir(parents=True)
        (evc_dir / "config.json").write_text(
            json.dumps(
                {"format_version": FORMAT_VERSION, "hash_algorithm": HASH_ALGORITHM},
                indent=2,
            )
            + "\n"
        )
        repo = cls(worktree_dir)
        repo.refs.write_head_ref(f"refs/heads/{branch}")
        return repo

    @classmethod
    def open(cls, worktree_dir: Path) -> ExperimentRepository:
        worktree_dir = Path(worktree_dir)
        evc_dir = worktree_dir / EVC_DIR
        if not evc_dir.is_dir():
            raise RepositoryNotFoundError(f"no {EVC_DIR} repository in {worktree_dir}")
        config_path = evc_dir / "config.json"
        if config_path.exists():
            config = json.loads(config_path.read_text())
            if config.get("format_version", 0) > FORMAT_VERSION:
                raise EVCError(
                    f"repository format {config['format_version']} is newer than "
                    f"this software supports ({FORMAT_VERSION})"
                )
        return cls(worktree_dir)

    # -- object plumbing ----------------------------------------------------

    def write_blob(self, data: bytes) -> str:
        return self.objects.write("blob", data)

    def write_tree(self, tree: Tree) -> str:
        return self.objects.write("tree", tree.serialize())

    def write_commit(self, commit: Commit) -> str:
        return self.objects.write("commit", commit.serialize())

    def read_blob(self, oid: str) -> Blob:
        obj_type, body = self.objects.read(oid)
        if obj_type != "blob":
            raise EVCError(f"object {oid} is a {obj_type}, expected blob")
        return Blob.parse(body)

    def read_tree(self, oid: str) -> Tree:
        obj_type, body = self.objects.read(oid)
        if obj_type != "tree":
            raise EVCError(f"object {oid} is a {obj_type}, expected tree")
        return Tree.parse(body)

    def read_commit(self, oid: str) -> Commit:
        obj_type, body = self.objects.read(oid)
        if obj_type != COMMIT:
            raise EVCError(f"object {oid} is a {obj_type}, expected commit")
        return Commit.parse(body)

    # -- revision resolution (rev-parse) -------------------------------------

    def resolve(self, revish: str) -> str:
        """Resolve ``HEAD``, a branch name, or a (short) object id to a commit id."""
        if revish == "HEAD":
            oid = self.refs.head_oid()
            if oid is None:
                raise UnknownRevisionError("HEAD is unborn: nothing recorded yet")
            return oid
        branch_oid = self.refs.read_ref(f"refs/heads/{revish}") if "/" not in revish else None
        if branch_oid:
            return branch_oid
        try:
            oid = self.objects.resolve_prefix(revish)
        except ObjectNotFoundError as exc:
            raise UnknownRevisionError(f"unknown revision: {revish!r}") from exc
        obj_type, _ = self.objects.read(oid)
        if obj_type != COMMIT:
            raise UnknownRevisionError(f"{revish!r} names a {obj_type}, not a revision")
        return oid

    # -- history walks ------------------------------------------------------

    def walk_first_parent(self, start_oid: str) -> list[str]:
        """Commit ids from ``start_oid`` back to the root, first-parent line."""
        chain = []
        oid: str | None = start_oid
        while oid is not None:
            chain.append(oid)
            parents = self.read_commit(oid).parents
            oid = parents[0] if parents else None
        return chain

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        """True if ``ancestor`` is reachable from ``descendant`` (or equal)."""
        pending = [descendant]
        seen: set[str] = set()
        while pending:
            oid = pending.pop()
            if oid == ancestor:
                return True
            if oid in seen:
                continue
            seen.add(oid)
            pending.extend(self.read_commit(oid).parents)
        return False

    def reachable_objects(self, commit_oid: str) -> set[str]:
        """All object ids (commits, trees, blobs) reachable from a commit."""
        result: set[str] = set()
        pending_commits = [commit_oid]
        while pending_commits:
            coid = pending_commits.pop()
            if coid in result:
                continue
            result.add(coid)
            commit = self.read_commit(coid)
            pending_commits.extend(commit.parents)
            pending_trees = [commit.tree]
            while pending_trees:
                toid = pending_trees.pop()
                if toid in result:
                    continue
                result.add(toid)
                for entry in self.read_tree(toid).entries:
                    if entry.type == "tree":
                        pending_trees.append(entry.oid)
                    else:
                        result.add(entry.oid)
        return result

    def flatten_tree(self, tree_oid: str, prefix: str = "") -> dict[str, str]:
        """Map ``path -> blob oid`` for every file under a tree."""
        flat: dict[str, str] = {}
        for entry in self.read_tree(tree_oid).entries:
            path = f"{prefix}{entry.name}"
            if entry.type == "tree":
                flat.update(self.flatten_tree(entry.oid, prefix=f"{path}/"))
            else:
                flat[path] = entry.oid
        return flat
