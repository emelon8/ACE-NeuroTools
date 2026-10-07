"""Store integrity, refs compare-and-set, journal, revision resolution."""

from __future__ import annotations

import zlib

import pytest

from aceneurotools.evc.errors import (
    AmbiguousIdError,
    CorruptObjectError,
    ObjectNotFoundError,
    RefConflictError,
    RepositoryExistsError,
    RepositoryNotFoundError,
    UnknownRevisionError,
)
from aceneurotools.evc.objects import Commit, Tree
from aceneurotools.evc.repository import ExperimentRepository
from aceneurotools.evc.store import FileObjectStore


@pytest.fixture()
def repo(tmp_path):
    return ExperimentRepository.init(tmp_path / "exp")


def _commit(repo, tree_oid, parents=(), message="m", when=1000):
    commit = Commit(
        tree=tree_oid, parents=tuple(parents), author="T <t@t>", author_time=when, author_tz="+0000", message=message
    )
    return repo.write_commit(commit)


def test_init_layout_and_reopen(tmp_path):
    ExperimentRepository.init(tmp_path / "exp")
    evc_dir = tmp_path / "exp" / ".evc"
    assert (evc_dir / "objects").is_dir()
    assert (evc_dir / "HEAD").read_text() == "ref: refs/heads/main\n"
    assert (evc_dir / "config.json").exists()
    reopened = ExperimentRepository.open(tmp_path / "exp")
    assert reopened.refs.read_head_ref() == "refs/heads/main"
    with pytest.raises(RepositoryExistsError):
        ExperimentRepository.init(tmp_path / "exp")
    with pytest.raises(RepositoryNotFoundError):
        ExperimentRepository.open(tmp_path / "elsewhere")


def test_store_write_is_idempotent_and_read_verifies(repo):
    oid_1 = repo.write_blob(b"content")
    oid_2 = repo.write_blob(b"content")
    assert oid_1 == oid_2
    assert repo.read_blob(oid_1).data == b"content"


def test_store_detects_corruption(tmp_path):
    store = FileObjectStore(tmp_path / "objects")
    oid = store.write("blob", b"good bytes")
    path = tmp_path / "objects" / oid[:2] / oid[2:]
    path.write_bytes(zlib.compress(b"blob 9\0bad bytes"))
    with pytest.raises(CorruptObjectError):
        store.read(oid)


def test_store_missing_object_and_prefix_resolution(repo):
    with pytest.raises(ObjectNotFoundError):
        repo.objects.read("f" * 64)
    oid = repo.write_blob(b"unique content for prefix test")
    assert repo.objects.resolve_prefix(oid[:8]) == oid
    with pytest.raises(ObjectNotFoundError):
        repo.objects.resolve_prefix("abc")  # too short
    with pytest.raises(ObjectNotFoundError):
        repo.objects.resolve_prefix("0000")


def test_prefix_resolution_reports_ambiguity(tmp_path):
    # Deterministically find two blob bodies whose ids share a 4-hex prefix,
    # store only those two, and check the short prefix is rejected as ambiguous.
    from aceneurotools.evc.objects import object_id

    seen: dict[str, bytes] = {}
    colliding: tuple[bytes, bytes] | None = None
    for i in range(100_000):
        body = f"content {i}".encode()
        prefix = object_id("blob", body)[:4]
        if prefix in seen:
            colliding = (seen[prefix], body)
            break
        seen[prefix] = body
    assert colliding is not None, "no 4-hex prefix collision in 100k tries (impossible)"
    store = FileObjectStore(tmp_path / "objects")
    oid_a = store.write("blob", colliding[0])
    store.write("blob", colliding[1])
    with pytest.raises(AmbiguousIdError):
        store.resolve_prefix(oid_a[:4])


def test_update_ref_compare_and_set(repo):
    tree_oid = repo.write_tree(Tree(entries=()))
    first = _commit(repo, tree_oid, message="first")
    second = _commit(repo, tree_oid, parents=(first,), message="second")
    repo.refs.update_ref("refs/heads/main", first, expected_old=None)
    with pytest.raises(RefConflictError):
        repo.refs.update_ref("refs/heads/main", second, expected_old=None)
    repo.refs.update_ref("refs/heads/main", second, expected_old=first)
    assert repo.refs.read_ref("refs/heads/main") == second


def test_journal_records_every_update(repo):
    tree_oid = repo.write_tree(Tree(entries=()))
    first = _commit(repo, tree_oid, message="first")
    repo.refs.update_ref("refs/heads/main", first, expected_old=None, op="record", message="first")
    entries = repo.refs.journal()
    assert len(entries) == 1
    assert entries[0].new == first
    assert entries[0].op == "record"
    assert entries[0].old == "0" * 64


def test_resolve_head_branch_and_prefix(repo):
    tree_oid = repo.write_tree(Tree(entries=()))
    first = _commit(repo, tree_oid, message="first")
    repo.refs.update_ref("refs/heads/main", first, expected_old=None)
    assert repo.resolve("HEAD") == first
    assert repo.resolve("main") == first
    assert repo.resolve(first[:10]) == first
    with pytest.raises(UnknownRevisionError):
        repo.resolve("no-such-branch")
    blob_oid = repo.write_blob(b"not a commit, definitely")
    with pytest.raises(UnknownRevisionError):
        repo.resolve(blob_oid)


def test_unborn_head_raises(repo):
    with pytest.raises(UnknownRevisionError):
        repo.resolve("HEAD")


def test_history_walk_and_ancestry(repo):
    tree_oid = repo.write_tree(Tree(entries=()))
    a = _commit(repo, tree_oid, message="a", when=1)
    b = _commit(repo, tree_oid, parents=(a,), message="b", when=2)
    c = _commit(repo, tree_oid, parents=(b,), message="c", when=3)
    assert repo.walk_first_parent(c) == [c, b, a]
    assert repo.is_ancestor(a, c)
    assert not repo.is_ancestor(c, a)
    assert repo.is_ancestor(c, c)


def test_reachable_objects_covers_commits_trees_blobs(repo):
    blob_oid = repo.write_blob(b"data")
    from aceneurotools.evc.objects import MODE_FILE, TreeEntry

    tree = Tree(entries=(TreeEntry(mode=MODE_FILE, type="blob", oid=blob_oid, name="f"),))
    tree_oid = repo.write_tree(tree)
    a = _commit(repo, tree_oid, message="a")
    b = _commit(repo, tree_oid, parents=(a,), message="b")
    reachable = repo.reachable_objects(b)
    assert {a, b, tree_oid, blob_oid} <= reachable
