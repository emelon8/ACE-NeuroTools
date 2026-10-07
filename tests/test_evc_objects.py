"""Object model: identity, serialization round-trips, validation."""

from __future__ import annotations

import hashlib

import pytest

from aceneurotools.evc.errors import InvalidObjectError
from aceneurotools.evc.objects import (
    MODE_DIR,
    MODE_FILE,
    Blob,
    Commit,
    Tree,
    TreeEntry,
    object_id,
)


def test_object_id_matches_git_header_rule():
    body = b"what is up, doc?"
    expected = hashlib.sha256(b"blob 16\0" + body).hexdigest()
    assert object_id("blob", body) == expected


def test_object_id_rejects_unknown_type():
    with pytest.raises(InvalidObjectError):
        object_id("banana", b"")


def test_blob_round_trip_and_stable_id():
    blob = Blob(data=b'{"gSig": 3}')
    assert Blob.parse(blob.serialize()) == blob
    assert blob.oid == Blob(data=b'{"gSig": 3}').oid  # same content, same id


def test_tree_sorts_entries_and_round_trips():
    entry_b = TreeEntry(mode=MODE_FILE, type="blob", oid="b" * 64, name="beta.json")
    entry_a = TreeEntry(mode=MODE_FILE, type="blob", oid="a" * 64, name="alpha.json")
    tree = Tree(entries=(entry_b, entry_a))
    assert [e.name for e in tree.entries] == ["alpha.json", "beta.json"]
    assert Tree(entries=(entry_a, entry_b)).oid == tree.oid  # order-independent id
    assert Tree.parse(tree.serialize()) == tree


def test_tree_rejects_duplicates_and_bad_names():
    entry = TreeEntry(mode=MODE_FILE, type="blob", oid="a" * 64, name="x")
    with pytest.raises(InvalidObjectError):
        Tree(entries=(entry, entry))
    for bad in ("a/b", "a\tb", "a\nb", "", ".", ".."):
        with pytest.raises(InvalidObjectError):
            TreeEntry(mode=MODE_FILE, type="blob", oid="a" * 64, name=bad)


def test_tree_entry_mode_type_consistency():
    with pytest.raises(InvalidObjectError):
        TreeEntry(mode=MODE_DIR, type="blob", oid="a" * 64, name="x")
    with pytest.raises(InvalidObjectError):
        TreeEntry(mode=MODE_FILE, type="tree", oid="a" * 64, name="x")


def test_commit_serializes_in_git_field_order_and_round_trips():
    commit = Commit(
        tree="t" * 64,
        parents=("p" * 64,),
        author="Eli Keldsen <elikeldsen@gmail.com>",
        author_time=1757900000,
        author_tz="+0000",
        message="tune gSig for line 96\n\nDetails here.",
    )
    text = commit.serialize().decode()
    lines = text.split("\n")
    assert lines[0].startswith("tree ")
    assert lines[1].startswith("parent ")
    assert lines[2].startswith("author ")
    assert lines[3].startswith("committer ")
    assert lines[4] == ""
    parsed = Commit.parse(commit.serialize())
    assert parsed == commit
    assert parsed.oid == commit.oid


def test_root_commit_has_no_parents():
    commit = Commit(
        tree="t" * 64,
        parents=(),
        author="A <a@b>",
        author_time=1,
        author_tz="+0000",
        message="root",
    )
    assert b"parent" not in commit.serialize()
    assert Commit.parse(commit.serialize()).parents == ()


def test_commit_rejects_malformed_author():
    with pytest.raises(InvalidObjectError):
        Commit(tree="t" * 64, parents=(), author="no email", author_time=1, author_tz="+0000", message="m")


def test_commit_message_preserved_exactly():
    message = "line one\n\nbody with tabs\t and unicode µ\n"
    commit = Commit(tree="t" * 64, parents=(), author="A <a@b>", author_time=1, author_tz="+0000", message=message)
    assert Commit.parse(commit.serialize()).message == message
