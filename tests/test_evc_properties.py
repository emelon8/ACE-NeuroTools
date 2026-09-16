"""Phase 7 long-term regression net: property-based round-trips over the
object model and store. Requires hypothesis (dev extra); skipped when absent."""

from __future__ import annotations

import string
import tempfile
from pathlib import Path

import pytest

hypothesis = pytest.importorskip("hypothesis")

from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from aceneurotools.evc.objects import (  # noqa: E402
    MODE_DIR,
    MODE_FILE,
    Blob,
    Commit,
    Tree,
    TreeEntry,
    object_id,
)
from aceneurotools.evc.store import FileObjectStore  # noqa: E402

_settings = settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)

oids = st.text(alphabet="0123456789abcdef", min_size=64, max_size=64)
names = st.text(
    alphabet=string.ascii_letters + string.digits + "-_.",
    min_size=1,
    max_size=24,
).filter(lambda s: s not in (".", ".."))
identities = names.map(lambda s: f"{s} <{s}@lab>")
timezones = st.sampled_from(["+0000", "-0700", "+0530", "-1200", "+1400"])


@st.composite
def tree_entries(draw) -> tuple[TreeEntry, ...]:
    unique_names = draw(st.lists(names, max_size=8, unique=True))
    entries = []
    for name in unique_names:
        is_dir = draw(st.booleans())
        entries.append(
            TreeEntry(
                mode=MODE_DIR if is_dir else MODE_FILE,
                type="tree" if is_dir else "blob",
                oid=draw(oids),
                name=name,
            )
        )
    return tuple(entries)


@st.composite
def commits(draw) -> Commit:
    return Commit(
        tree=draw(oids),
        parents=tuple(draw(st.lists(oids, max_size=3))),
        author=draw(identities),
        author_time=draw(st.integers(min_value=0, max_value=2**40)),
        author_tz=draw(timezones),
        message=draw(st.text(max_size=200)),
    )


# -- objects: serialize/parse round-trips -------------------------------------


@_settings
@given(data=st.binary(max_size=4096))
def test_blob_round_trip_and_stable_id(data):
    blob = Blob(data=data)
    assert Blob.parse(blob.serialize()) == blob
    assert blob.oid == object_id("blob", data)


@_settings
@given(entries=tree_entries())
def test_tree_round_trip_and_order_invariance(entries):
    tree = Tree(entries=entries)
    assert Tree.parse(tree.serialize()) == tree
    # identical content in any insertion order has the identical id
    assert Tree(entries=tuple(reversed(entries))).oid == tree.oid


@_settings
@given(commit=commits())
def test_commit_round_trip(commit):
    parsed = Commit.parse(commit.serialize())
    assert parsed == commit
    assert parsed.oid == commit.oid
    # committer defaults to author (git rule) and survives the round-trip
    assert parsed.committer == commit.author


# -- store: write/read round-trips --------------------------------------------


@_settings
@given(
    obj_type=st.sampled_from(["blob", "tree", "commit"]),
    body=st.binary(max_size=4096),
)
def test_store_round_trip_and_idempotent_writes(obj_type, body):
    with tempfile.TemporaryDirectory() as root:
        store = FileObjectStore(Path(root))
        oid = store.write(obj_type, body)
        assert oid == object_id(obj_type, body)
        assert store.write(obj_type, body) == oid  # idempotent
        read_type, read_body = store.read(oid)
        assert (read_type, read_body) == (obj_type, body)
        assert list(store.iter_oids()) == [oid]
