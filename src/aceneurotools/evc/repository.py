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
        if worktree_dir.exists() and not worktree_dir.is_dir():
            raise EVCError(f"cannot initialise a repository in {worktree_dir}: not a directory")
        try:
            (evc_dir / "objects").mkdir(parents=True)
            (evc_dir / "refs" / "heads").mkdir(parents=True)
        except OSError as exc:
            raise EVCError(f"cannot initialise a repository in {worktree_dir}: {exc}") from exc
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
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise EVCError(f"invalid JSON in repository config {config_path}: {exc}") from exc
            except (OSError, UnicodeDecodeError) as exc:
                raise EVCError(f"cannot read repository config {config_path}: {exc}") from exc
            if not isinstance(config, dict):
                raise EVCError(
                    f"invalid repository config {config_path}: expected a JSON object, got {type(config).__name__}"
                )
            version = config.get("format_version", 0)
            if isinstance(version, bool) or not isinstance(version, int):
                raise EVCError(
                    f"invalid repository config {config_path}: format_version must be an integer, got {version!r}"
                )
            if version > FORMAT_VERSION:
                raise EVCError(f"repository format {version} is newer than this software supports ({FORMAT_VERSION})")
        return cls(worktree_dir)

    # -- ref access (typed errors for a malformed repository) ----------------

    def head_ref(self) -> str:
        """The ref HEAD points at (``refs/heads/<name>``)."""
        try:
            return self.refs.read_head_ref()
        except (OSError, UnicodeDecodeError) as exc:
            raise EVCError(f"cannot read {self.evc_dir / 'HEAD'}: {exc}") from exc

    def read_ref(self, ref: str) -> str | None:
        """A ref's commit id, or None when the ref does not exist."""
        try:
            return self.refs.read_ref(ref)
        except (OSError, UnicodeDecodeError) as exc:
            raise EVCError(f"cannot read ref {ref}: {exc}") from exc

    def head_oid(self) -> str | None:
        """HEAD's commit id, or None while the branch is unborn."""
        return self.read_ref(self.head_ref())

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
            oid = self.head_oid()
            if oid is None:
                raise UnknownRevisionError("HEAD is unborn: nothing recorded yet")
            return oid
        branch_oid = None
        if "/" not in revish and (self.evc_dir / "refs" / "heads" / revish).is_file():
            # is_file() first: a directory left under refs/heads/ (a branch
            # namespace collision) cannot name a revision, and reading it
            # would raise OSError instead of UnknownRevisionError.
            branch_oid = self.read_ref(f"refs/heads/{revish}")
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
