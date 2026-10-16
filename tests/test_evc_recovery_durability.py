"""Failure injection for EVC ref/journal durability.

The guarantees exercised here are deliberately split into three levels:

* **atomic replacement** — a reader never sees a partial HEAD/ref/object;
  ``os.replace`` either happens completely or not at all;
* **process crash** — residual ``.tmp-*`` files and orphan objects are
  harmless, a stale lock is never auto-deleted, and recovery still returns
  every complete journal entry;
* **power loss** — file contents are fsynced before any rename (recorded with
  spies); no stronger claim is made than the filesystem honours.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from aceneurotools.evc.errors import EVCError, JournalCorruptError, RefConflictError
from aceneurotools.evc.objects import Commit
from aceneurotools.evc.porcelain import ExperimentVersionControl
from aceneurotools.evc.refs import ZERO_OID, RefStore
from aceneurotools.evc.repository import ExperimentRepository
from aceneurotools.evc.store import FileObjectStore

OID_A = "a" * 64
OID_B = "b" * 64
AUTHOR = "Durability Test <test@lab>"


@pytest.fixture()
def repo(tmp_path):
    return ExperimentRepository.init(tmp_path / "exp")


def _journal_path(repo: ExperimentRepository) -> Path:
    return repo.evc_dir / "journal.log"


# -- journal parsing ---------------------------------------------------------


@pytest.mark.parametrize(
    "tail",
    [
        "1700000000\trefs/heads/main\t" + OID_A,  # interrupted after the old oid
        "not-a-timestamp\trefs/heads/main\t" + ZERO_OID + "\t" + OID_A + "\trecord\tmsg",
    ],
    ids=["missing-fields", "bad-timestamp"],
)
def test_truncated_final_journal_line_keeps_preceding_history(repo, tail):
    """H2: an interrupted final append must not hide earlier recovery history."""
    repo.refs.update_ref("refs/heads/main", OID_A, expected_old=None, op="record", message="first")
    repo.refs.update_ref("refs/heads/main", OID_B, expected_old=OID_A, op="record", message="second")
    with _journal_path(repo).open("a", encoding="utf-8") as fh:
        fh.write(tail)  # no trailing newline: the append was cut mid-write

    entries = repo.refs.journal()
    assert [e.new for e in entries] == [OID_A, OID_B]
    assert [e.op for e in entries] == ["record", "record"]

    recovered = ExperimentVersionControl(repo).recover()
    assert [e.new for e in recovered] == [OID_B, OID_A]


def test_valid_final_journal_line_without_trailing_newline_parses(repo):
    """A complete line at EOF is an entry, not a truncation."""
    line = f"1700000000\trefs/heads/main\t{ZERO_OID}\t{OID_A}\trecord\tno newline at eof"
    _journal_path(repo).write_text(line, encoding="utf-8")
    entries = repo.refs.journal()
    assert len(entries) == 1
    assert entries[0].timestamp == 1700000000
    assert entries[0].new == OID_A
    assert entries[0].message == "no newline at eof"


@pytest.mark.parametrize("tail", [b"garbage", b"1700000000\trefs/heads/main\t", b"\xc3"])
def test_record_after_interrupted_journal_append_keeps_recovery_usable(tmp_path, tail):
    directory = tmp_path / "exp"
    directory.mkdir()
    params = directory / "params.json"
    params.write_text('{"value": 1}', encoding="utf-8")
    evc = ExperimentVersionControl.init(directory)
    first = evc.record("first", author=AUTHOR)
    journal = evc.repo.evc_dir / "journal.log"
    complete_history = journal.read_bytes()
    with journal.open("ab") as handle:
        handle.write(tail)
    assert [entry.new for entry in evc.recover()] == [first]

    params.write_text('{"value": 2}', encoding="utf-8")
    second = evc.record("second", author=AUTHOR)

    assert [entry.new for entry in evc.recover()] == [second, first]
    assert journal.read_bytes().startswith(complete_history)
    assert [entry.message for entry in evc.recover()] == ["second", "first"]


def test_append_preserves_complete_unterminated_entry(repo):
    journal = _journal_path(repo)
    existing = f"1700000000\trefs/heads/main\t{ZERO_OID}\t{OID_A}\trecord\tkept".encode()
    journal.write_bytes(existing)
    repo.refs.append_journal("refs/heads/main", OID_A, OID_B, "record", "next")
    assert journal.read_bytes().startswith(existing + b"\n")
    assert [(entry.new, entry.message) for entry in repo.refs.journal()] == [(OID_A, "kept"), (OID_B, "next")]


def test_middle_journal_corruption_blocks_ref_movement_and_preserves_bytes(repo):
    repo.refs.update_ref("refs/heads/main", OID_A, expected_old=None)
    journal = _journal_path(repo)
    damaged = journal.read_bytes() + b"corrupt complete entry\n"
    journal.write_bytes(damaged)
    with pytest.raises(JournalCorruptError):
        repo.refs.update_ref("refs/heads/main", OID_B, expected_old=OID_A)
    assert repo.head_oid() == OID_A
    assert journal.read_bytes() == damaged


def test_existing_journal_lock_blocks_ref_movement_without_removing_lock(repo):
    repo.refs.update_ref("refs/heads/main", OID_A, expected_old=None)
    lock = repo.evc_dir / "journal.log.lock"
    lock.write_bytes(b"another writer")
    with pytest.raises(RefConflictError, match="journal"):
        repo.refs.update_ref("refs/heads/main", OID_B, expected_old=OID_A)
    assert repo.head_oid() == OID_A
    assert lock.read_bytes() == b"another writer"
    assert not (repo.evc_dir / "refs/heads/main.lock").exists()


def test_truncated_multibyte_tail_does_not_break_recovery(repo):
    """A power cut mid-character must not turn recovery into a decode crash."""
    repo.refs.update_ref("refs/heads/main", OID_A, expected_old=None, op="record", message="first")
    # Second entry's message ends in "é"; only its first (of two) bytes hit disk.
    line = f"1700000000\trefs/heads/main\t{OID_A}\t{OID_B}\trecord\tcaf".encode() + b"\xc3"
    with _journal_path(repo).open("ab") as fh:
        fh.write(line)
    entries = repo.refs.journal()  # must not raise UnicodeDecodeError
    assert entries[0].new == OID_A
    assert entries[1].new == OID_B  # all fields were complete; only the message tail was torn


@pytest.mark.parametrize(
    "bad",
    [
        "garbage without tab fields",
        "nope\trefs/heads/main\t" + ZERO_OID + "\t" + OID_A + "\trecord\tmsg",
    ],
    ids=["wrong-field-count", "non-integer-timestamp"],
)
def test_malformed_middle_journal_line_raises_typed_error(repo, bad):
    """H3: middle corruption must surface with the journal path and line number."""
    repo.refs.update_ref("refs/heads/main", OID_A, expected_old=None, op="record", message="first")
    repo.refs.update_ref("refs/heads/main", OID_B, expected_old=OID_A, op="record", message="second")
    journal = _journal_path(repo)
    lines = journal.read_text(encoding="utf-8").splitlines()
    lines.insert(1, bad)  # line 2 of the new file, with valid entries before and after
    journal.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(JournalCorruptError) as excinfo:
        repo.refs.journal()
    message = str(excinfo.value)
    assert isinstance(excinfo.value, EVCError)
    assert str(journal) in message
    assert "line 2" in message

    with pytest.raises(JournalCorruptError):
        ExperimentVersionControl(repo).recover()


def test_malformed_terminated_final_line_still_raises(repo):
    """Only an *unterminated* tail is an interrupted append; a full bad line
    (newline included) proves the bytes reached disk, so it is corruption."""
    repo.refs.update_ref("refs/heads/main", OID_A, expected_old=None, op="record", message="first")
    with _journal_path(repo).open("a", encoding="utf-8") as fh:
        fh.write("garbage after a terminating newline\n")

    with pytest.raises(JournalCorruptError) as excinfo:
        repo.refs.journal()
    assert "line 2" in str(excinfo.value)


def test_blank_journal_lines_are_skippable_anywhere(repo):
    line_a = f"1700000001\trefs/heads/main\t{ZERO_OID}\t{OID_A}\trecord\tfirst"
    line_b = f"1700000002\trefs/heads/main\t{OID_A}\t{OID_B}\trecord\tsecond"
    _journal_path(repo).write_text(f"\n   \n{line_a}\n\n\t\n{line_b}\n", encoding="utf-8")
    entries = repo.refs.journal()
    assert [e.timestamp for e in entries] == [1700000001, 1700000002]
    assert [e.new for e in entries] == [OID_A, OID_B]


# -- HEAD atomicity -----------------------------------------------------------


def test_write_head_ref_replaces_atomically_and_leaves_no_temp(repo):
    assert (repo.evc_dir / "HEAD").read_text(encoding="utf-8") == "ref: refs/heads/main\n"
    repo.refs.write_head_ref("refs/heads/other")
    assert (repo.evc_dir / "HEAD").read_text(encoding="utf-8") == "ref: refs/heads/other\n"
    assert repo.refs.read_head_ref() == "refs/heads/other"
    assert list(repo.evc_dir.glob(".tmp-head-*")) == []


def test_write_head_ref_keeps_old_head_when_replace_fails(repo, monkeypatch):
    """A crash after staging but before the rename leaves the old HEAD intact."""

    def crash_before_replace(src, dst):
        raise OSError("simulated crash between staging and os.replace")

    monkeypatch.setattr(os, "replace", crash_before_replace)
    with pytest.raises(OSError):
        repo.refs.write_head_ref("refs/heads/other")

    assert (repo.evc_dir / "HEAD").read_text(encoding="utf-8") == "ref: refs/heads/main\n"
    assert repo.refs.read_head_ref() == "refs/heads/main"
    assert list(repo.evc_dir.glob(".tmp-head-*")) == []  # no temp litter


def test_write_head_ref_validates_ref_name_before_staging(repo):
    with pytest.raises(EVCError):
        repo.refs.write_head_ref("../outside")
    assert repo.refs.read_head_ref() == "refs/heads/main"
    assert list(repo.evc_dir.glob(".tmp-head-*")) == []


def test_write_head_ref_fsyncs_staged_head_before_replace(repo, monkeypatch):
    events: list[str] = []
    real_fsync, real_replace = os.fsync, os.replace

    def fsync_spy(fd):
        events.append("fsync")
        return real_fsync(fd)

    def replace_spy(src, dst):
        events.append("replace")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "fsync", fsync_spy)
    monkeypatch.setattr(os, "replace", replace_spy)
    repo.refs.write_head_ref("refs/heads/other")

    assert "replace" in events
    assert events.index("fsync") < events.index("replace")


# -- ref atomicity and locking ------------------------------------------------


def test_update_ref_replace_failure_keeps_old_ref_and_releases_lock(repo, monkeypatch):
    repo.refs.update_ref("refs/heads/main", OID_A, expected_old=None)
    ref_file = repo.evc_dir / "refs" / "heads" / "main"
    lock_path = ref_file.with_name(ref_file.name + ".lock")

    def crash_before_replace(src, dst):
        raise OSError("simulated crash between staging and os.replace")

    monkeypatch.setattr(os, "replace", crash_before_replace)
    with pytest.raises(OSError):
        repo.refs.update_ref("refs/heads/main", OID_B, expected_old=OID_A)

    assert repo.refs.read_ref("refs/heads/main") == OID_A
    assert ref_file.read_text(encoding="utf-8") == OID_A + "\n"  # still only a full oid
    assert not lock_path.exists()
    assert list(ref_file.parent.glob(".tmp-ref-*")) == []


def test_ref_file_content_is_only_ever_a_full_oid(repo):
    repo.refs.update_ref("refs/heads/main", OID_A, expected_old=None)
    ref_file = repo.evc_dir / "refs" / "heads" / "main"
    assert ref_file.read_text(encoding="utf-8") == OID_A + "\n"
    repo.refs.update_ref("refs/heads/main", OID_B, expected_old=OID_A)
    assert ref_file.read_text(encoding="utf-8") == OID_B + "\n"


def test_cas_mismatch_releases_its_lock(repo):
    repo.refs.update_ref("refs/heads/main", OID_A, expected_old=None)
    lock_path = repo.evc_dir / "refs" / "heads" / "main.lock"
    with pytest.raises(RefConflictError):
        repo.refs.update_ref("refs/heads/main", OID_B, expected_old=None)
    assert not lock_path.exists()


def test_stale_lock_is_never_auto_removed(repo):
    """Age/PID heuristics can delete a live lock; a crashed lock stays until a
    human removes it, and the error says so."""
    ref_file = repo.evc_dir / "refs" / "heads" / "main"
    lock_path = ref_file.with_name(ref_file.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("", encoding="utf-8")
    old = lock_path.stat().st_mtime - 3600
    os.utime(lock_path, (old, old))  # a genuinely old lock — still not removed

    with pytest.raises(RefConflictError) as excinfo:
        repo.refs.update_ref("refs/heads/main", OID_A, expected_old=None)

    assert lock_path.exists()
    message = str(excinfo.value)
    assert str(lock_path) in message
    assert "manually" in message
    assert not ref_file.exists()  # the blocked update did not move the ref


# -- fsync ordering (power-loss ladder) ---------------------------------------


def test_object_write_fsyncs_content_before_replace(tmp_path, monkeypatch):
    events: list[tuple[str, str]] = []
    real_fsync, real_replace = os.fsync, os.replace

    def fsync_spy(fd):
        events.append(("fsync", "fd"))
        return real_fsync(fd)

    def replace_spy(src, dst):
        events.append(("replace", str(Path(dst).name)))
        return real_replace(src, dst)

    monkeypatch.setattr(os, "fsync", fsync_spy)
    monkeypatch.setattr(os, "replace", replace_spy)

    store = FileObjectStore(tmp_path / "objects")
    oid = store.write("blob", b"durable bytes")
    assert store.read(oid)[1] == b"durable bytes"
    kinds = [kind for kind, _ in events]
    assert "replace" in kinds
    assert kinds.index("fsync") < kinds.index("replace")


def test_ref_update_fsyncs_staged_oid_before_replace(repo, monkeypatch):
    events: list[str] = []
    real_fsync, real_replace = os.fsync, os.replace

    def fsync_spy(fd):
        events.append("fsync")
        return real_fsync(fd)

    def replace_spy(src, dst):
        events.append("replace")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "fsync", fsync_spy)
    monkeypatch.setattr(os, "replace", replace_spy)
    repo.refs.update_ref("refs/heads/main", OID_A, expected_old=None)

    assert "replace" in events
    assert events.index("fsync") < events.index("replace")


def test_fsync_directory_swallows_platforms_that_forbid_opening_directories(tmp_path, monkeypatch):
    """Windows cannot ``os.open`` a directory; that must never break a write."""

    def refuse_directory_open(path, flags):
        raise PermissionError(13, "directory handles are not supported")

    monkeypatch.setattr(os, "open", refuse_directory_open)
    RefStore._fsync_directory(tmp_path)  # must not raise


def test_fsync_directory_swallows_filesystems_that_reject_directory_fsync(tmp_path, monkeypatch):
    def refuse_fsync(fd):
        raise OSError("EINVAL: inode does not support fsync")

    monkeypatch.setattr(os, "fsync", refuse_fsync)
    RefStore._fsync_directory(tmp_path)  # must not raise


def test_append_journal_fsyncs_the_journal_file_before_returning(repo, monkeypatch):
    journal = _journal_path(repo)
    fsynced: list[tuple[int, int]] = []
    real_fsync = os.fsync

    def fsync_spy(fd):
        st = os.fstat(fd)
        fsynced.append((st.st_dev, st.st_ino))
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fsync_spy)
    repo.refs.append_journal("refs/heads/main", ZERO_OID, OID_A, "record", "durable entry")

    stat = journal.stat()
    assert (stat.st_dev, stat.st_ino) in fsynced
    assert repo.refs.journal()[-1].new == OID_A


# -- crash windows -------------------------------------------------------------


def test_crash_between_object_write_and_ref_update_is_harmless(tmp_path):
    """Objects are written before the ref moves; a crash in between leaves an
    unreachable object and an unchanged repository head."""
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir()
    (exp_dir / "params.json").write_text('{"a": 1}', encoding="utf-8")
    evc = ExperimentVersionControl.init(exp_dir)
    first = evc.record("first", author=AUTHOR)

    # "Crash": a fully written, fsynced commit object whose ref update never ran.
    tree_oid = evc.worktree.snapshot()
    orphan = evc.repo.write_commit(
        Commit(tree=tree_oid, parents=(first,), author=AUTHOR, author_time=999, author_tz="+0000", message="lost")
    )

    assert evc.repo.refs.head_oid() == first
    assert evc.repo.objects.exists(orphan)
    assert orphan not in evc.repo.reachable_objects(first)  # unreachable: harmless
    assert [e.new for e in evc.recover()] == [first]  # no journal event either


def test_crash_between_ref_replace_and_journal_append_keeps_history(repo, monkeypatch):
    """The documented window: the ref has moved but the newest journal event is
    missing; every earlier entry is still intact and recoverable."""
    repo.refs.update_ref("refs/heads/main", OID_A, expected_old=None, op="record", message="first")
    journal_before = _journal_path(repo).read_bytes()

    def crash_before_append(*args, **kwargs):
        raise RuntimeError("simulated crash before journal append")

    monkeypatch.setattr(RefStore, "_append_journal_line", crash_before_append)
    with pytest.raises(RuntimeError):
        repo.refs.update_ref("refs/heads/main", OID_B, expected_old=OID_A, op="record", message="second")

    # the ref replace already happened (that is the documented crash window)...
    assert repo.refs.read_ref("refs/heads/main") == OID_B
    # ...but the journal was not touched and old history remains fully readable
    assert _journal_path(repo).read_bytes() == journal_before
    monkeypatch.undo()
    assert [e.new for e in repo.refs.journal()] == [OID_A]
    assert [e.new for e in ExperimentVersionControl(repo).recover()] == [OID_A]
    assert not (repo.evc_dir / "refs" / "heads" / "main.lock").exists()  # lock released
