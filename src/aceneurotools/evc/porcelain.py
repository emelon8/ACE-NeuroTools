"""ExperimentVersionControl — the porcelain (user-facing axiomatic commands).

Built entirely from repository plumbing, mirroring git's porcelain/plumbing
split (Pro Git §10.1). The command set maps onto the four user axioms:

===========  ==================================================================
Axiom        Commands
===========  ==================================================================
**access**   ``status`` ``history`` ``show`` ``diff`` ``recover``
**restore**  ``restore`` (never destroys: dirty state is auto-snapshotted to
             the journal first; refs never move backwards)
**comment**  ``record(message)`` (revision message) and ``comment(rev, text)``
             (post-hoc annotation via a notes ref, git-notes style — history
             is annotated, never rewritten)
**push**     ``push`` (fast-forward-only publication to a shared remote)
===========  ==================================================================

Invariants (the axioms the design doc derives):

1. Objects are immutable and content-addressed; recorded history cannot be
   silently altered.
2. Every ref movement is journaled; any oid the journal has ever seen remains
   restorable.
3. ``restore`` copies an old revision *forward* into the working state; it
   never rewinds a branch ref.
4. Publication is fast-forward-only; shared history is append-only.
"""

from __future__ import annotations

import getpass
import platform
import time
from dataclasses import dataclass, field
from pathlib import Path

from aceneurotools.evc.diff import FileDiff, diff_trees
from aceneurotools.evc.errors import NothingToRecordError
from aceneurotools.evc.objects import MODE_FILE, Commit, Tree, TreeEntry
from aceneurotools.evc.refs import DEFAULT_BRANCH, JournalEntry
from aceneurotools.evc.remote import PushResult, Remote, push_ref
from aceneurotools.evc.repository import NOTES_REF, ExperimentRepository
from aceneurotools.evc.worktree import WorkingTree


def _default_author() -> str:
    user = getpass.getuser() or "unknown"
    host = platform.node() or "local"
    return f"{user} <{user}@{host}>"


@dataclass(frozen=True)
class RevisionInfo:
    oid: str
    tree: str
    parents: tuple[str, ...]
    author: str
    author_time: int
    message: str
    files: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class StatusReport:
    branch: str
    head: str | None
    clean: bool
    changes: tuple[FileDiff, ...]


@dataclass(frozen=True)
class RestoreResult:
    restored: str
    safety_snapshot: str | None


class ExperimentVersionControl:
    """Facade the GUI, CLI, and pipelines all talk to (shared-backend rule)."""

    def __init__(self, repo: ExperimentRepository) -> None:
        self.repo = repo
        self.worktree = WorkingTree(repo)

    # -- lifecycle ----------------------------------------------------------

    @classmethod
    def init(cls, experiment_dir: str | Path,
             branch: str = DEFAULT_BRANCH) -> ExperimentVersionControl:
        return cls(ExperimentRepository.init(Path(experiment_dir), branch=branch))

    @classmethod
    def open(cls, experiment_dir: str | Path) -> ExperimentVersionControl:
        return cls(ExperimentRepository.open(Path(experiment_dir)))

    # -- record (commit) ----------------------------------------------------

    def record(self, message: str, author: str | None = None,
               author_time: int | None = None) -> str:
        """Record the current working state as a new revision; return its id."""
        if not message.strip():
            raise ValueError("a revision message is required")
        tree_oid = self.worktree.snapshot()
        branch_ref = self.repo.refs.read_head_ref()
        head_oid = self.repo.refs.read_ref(branch_ref)
        if head_oid is not None and self.repo.read_commit(head_oid).tree == tree_oid:
            raise NothingToRecordError("working state is identical to the current revision")
        commit = Commit(
            tree=tree_oid,
            parents=(head_oid,) if head_oid else (),
            author=author or _default_author(),
            author_time=author_time if author_time is not None else int(time.time()),
            author_tz="+0000",
            message=message,
        )
        new_oid = self.repo.write_commit(commit)
        self.repo.refs.update_ref(branch_ref, new_oid, expected_old=head_oid,
                                  op="record", message=message.splitlines()[0])
        return new_oid

    # -- access -------------------------------------------------------------

    def status(self) -> StatusReport:
        branch_ref = self.repo.refs.read_head_ref()
        branch = branch_ref.rsplit("/", 1)[-1]
        head_oid = self.repo.refs.read_ref(branch_ref)
        if head_oid is None:
            return StatusReport(branch=branch, head=None, clean=False, changes=())
        work_tree = self.worktree.snapshot()
        head_tree = self.repo.read_commit(head_oid).tree
        if work_tree == head_tree:
            return StatusReport(branch=branch, head=head_oid, clean=True, changes=())
        changes = tuple(diff_trees(self.repo, head_tree, work_tree))
        return StatusReport(branch=branch, head=head_oid, clean=False, changes=changes)

    def history(self, limit: int | None = None) -> list[RevisionInfo]:
        head_oid = self.repo.refs.head_oid()
        if head_oid is None:
            return []
        chain = self.repo.walk_first_parent(head_oid)
        if limit is not None:
            chain = chain[:limit]
        return [self._revision_info(oid, with_files=False) for oid in chain]

    def show(self, revish: str = "HEAD") -> RevisionInfo:
        oid = self.repo.resolve(revish)
        return self._revision_info(oid, with_files=True)

    def diff(self, rev_a: str, rev_b: str = "HEAD") -> list[FileDiff]:
        tree_a = self.repo.read_commit(self.repo.resolve(rev_a)).tree
        tree_b = self.repo.read_commit(self.repo.resolve(rev_b)).tree
        return diff_trees(self.repo, tree_a, tree_b)

    def recover(self) -> list[JournalEntry]:
        """Every journaled event, newest first — including safety snapshots
        that no branch points at. Any ``new`` oid here can be ``restore``\\d."""
        return list(reversed(self.repo.refs.journal()))

    # -- restore ------------------------------------------------------------

    def restore(self, revish: str, author: str | None = None) -> RestoreResult:
        """Make the working state match ``revish`` — without losing anything.

        If the working state is dirty, it is first recorded as a *safety
        snapshot* commit reachable only through the journal (git's dangling
        commit + reflog recovery model), then the target revision's tree is
        materialised. Branch refs never move: recovering an old state and
        keeping it means calling ``record`` afterwards, which appends a new
        revision whose content equals the old one.
        """
        target_oid = self.repo.resolve(revish)
        target_tree = self.repo.read_commit(target_oid).tree
        safety_oid: str | None = None

        head_oid = self.repo.refs.head_oid()
        work_tree = self.worktree.snapshot()
        head_tree = self.repo.read_commit(head_oid).tree if head_oid else None
        if work_tree != head_tree:
            safety = Commit(
                tree=work_tree,
                parents=(head_oid,) if head_oid else (),
                author=author or _default_author(),
                author_time=int(time.time()),
                author_tz="+0000",
                message=f"auto: working state before restore of {target_oid[:12]}",
            )
            safety_oid = self.repo.write_commit(safety)
            self.repo.refs.append_journal(
                ref="(dangling)", old=head_oid or "0" * 64, new=safety_oid,
                op="safety-snapshot", message="working state preserved before restore",
            )

        self.worktree.materialize(target_tree)
        self.repo.refs.append_journal(
            ref=self.repo.refs.read_head_ref(), old=head_oid or "0" * 64, new=target_oid,
            op="restore", message=f"working state set to {target_oid[:12]} (ref not moved)",
        )
        return RestoreResult(restored=target_oid, safety_snapshot=safety_oid)

    # -- comment (annotate without rewriting) ---------------------------------

    def comment(self, revish: str, text: str, author: str | None = None) -> str:
        """Attach a comment to an existing revision (git-notes model).

        Comments live in a parallel history under ``refs/notes/comments``:
        a commit whose tree maps ``<target oid> -> note blob``. Appending a
        comment adds a notes commit; the target revision itself is untouched.
        """
        if not text.strip():
            raise ValueError("comment text is required")
        target_oid = self.repo.resolve(revish)
        who = author or _default_author()
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        entry_text = f"[{stamp} UTC] {who}\n{text.strip()}\n"

        notes_head = self.repo.refs.read_ref(NOTES_REF)
        notes: dict[str, str] = {}
        if notes_head is not None:
            notes_tree = self.repo.read_commit(notes_head).tree
            notes = dict(self.repo.flatten_tree(notes_tree))
        existing = notes.get(target_oid)
        if existing is not None:
            previous = self.repo.read_blob(existing).data.decode()
            entry_text = previous + "\n" + entry_text
        notes[target_oid] = self.repo.write_blob(entry_text.encode())

        tree = Tree(entries=tuple(
            TreeEntry(mode=MODE_FILE, type="blob", oid=blob_oid, name=name)
            for name, blob_oid in notes.items()
        ))
        notes_commit = Commit(
            tree=self.repo.write_tree(tree),
            parents=(notes_head,) if notes_head else (),
            author=who,
            author_time=int(time.time()),
            author_tz="+0000",
            message=f"comment on {target_oid[:12]}",
        )
        new_notes_oid = self.repo.write_commit(notes_commit)
        self.repo.refs.update_ref(NOTES_REF, new_notes_oid, expected_old=notes_head,
                                  op="comment", message=f"comment on {target_oid[:12]}")
        return new_notes_oid

    def comments(self, revish: str) -> str | None:
        """Return the accumulated comments on a revision, or None."""
        target_oid = self.repo.resolve(revish)
        notes_head = self.repo.refs.read_ref(NOTES_REF)
        if notes_head is None:
            return None
        notes_tree = self.repo.read_commit(notes_head).tree
        blob_oid = self.repo.flatten_tree(notes_tree).get(target_oid)
        if blob_oid is None:
            return None
        return self.repo.read_blob(blob_oid).data.decode()

    # -- push ----------------------------------------------------------------

    def push(self, remote: Remote, include_comments: bool = True) -> list[PushResult]:
        """Publish this experiment's history (and comments) to a shared remote."""
        results = [push_ref(self.repo, remote, self.repo.refs.read_head_ref())]
        if include_comments and self.repo.refs.read_ref(NOTES_REF) is not None:
            results.append(push_ref(self.repo, remote, NOTES_REF))
        return results

    # -- internals ------------------------------------------------------------

    def _revision_info(self, oid: str, with_files: bool) -> RevisionInfo:
        commit = self.repo.read_commit(oid)
        files: tuple[str, ...] = ()
        if with_files:
            files = tuple(sorted(self.repo.flatten_tree(commit.tree)))
        return RevisionInfo(
            oid=oid, tree=commit.tree, parents=commit.parents, author=commit.author,
            author_time=commit.author_time, message=commit.message, files=files,
        )
