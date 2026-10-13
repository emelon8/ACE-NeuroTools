"""Corruption, interrupted writes, manifests, and recoverable experiment history."""

from __future__ import annotations

import hashlib
import json
import zlib
from concurrent.futures import ThreadPoolExecutor

import pytest

from aceneurotools.config.config_utils import load_analysis_params
from aceneurotools.evc import pointers, refs, store
from aceneurotools.evc.csv_bridge import ANALYSIS_CNMFE_DOC, extract, import_experiment, writeback
from aceneurotools.evc.errors import CorruptObjectError, EVCError, InvalidObjectError, ManifestError, RefConflictError
from aceneurotools.evc.pointers import hash_artifact, read_manifest, verify_manifest, write_manifest
from aceneurotools.evc.porcelain import ExperimentVersionControl
from aceneurotools.evc.refs import RefStore
from aceneurotools.evc.store import FileObjectStore


@pytest.mark.parametrize(
    "payload",
    [
        b"not compressed",
        zlib.compress(b"blob nope\0data"),
        zlib.compress(b"blob 7\0data"),
        zlib.compress(b"banana 4\0data"),
        zlib.compress(b"blob 4data"),
        zlib.compress(b"\xff 4\0data"),
    ],
)
def test_corrupt_history_always_raises_a_domain_error(tmp_path, payload):
    objects = FileObjectStore(tmp_path)
    oid = objects.write("blob", b"original")
    (tmp_path / oid[:2] / oid[2:]).write_bytes(payload)
    with pytest.raises(CorruptObjectError):
        objects.read(oid)


@pytest.mark.parametrize("oid", ["", "a", "g" * 64, "../outside", "/tmp/file", "a" * 63, "A" * 64])
def test_store_rejects_invalid_object_paths(tmp_path, oid):
    objects = FileObjectStore(tmp_path)
    with pytest.raises(InvalidObjectError):
        objects.read(oid)
    with pytest.raises(InvalidObjectError):
        objects.exists(oid)


def test_interrupted_object_write_leaves_no_object_or_temp_files(tmp_path, monkeypatch):
    objects = FileObjectStore(tmp_path)

    def fail(*args):
        raise OSError("interrupted write")

    monkeypatch.setattr(store.os, "replace", fail)
    with pytest.raises(OSError):
        objects.write("blob", b"new")
    assert list(objects.iter_oids()) == []
    assert not list(tmp_path.rglob(".tmp-*"))


def test_parallel_identical_writes_are_complete_and_idempotent(tmp_path):
    objects = FileObjectStore(tmp_path)
    payload = b"recording configuration\0" * 1000
    with ThreadPoolExecutor(max_workers=4) as executor:
        oids = list(executor.map(lambda _: objects.write("blob", payload), range(20)))
    assert len(set(oids)) == 1
    assert objects.read(oids[0]) == ("blob", payload)
    assert list(objects.iter_oids()) == [oids[0]]
    assert not list(tmp_path.rglob(".tmp-*"))


def test_store_inventory_ignores_nonobject_entries(tmp_path):
    objects = FileObjectStore(tmp_path)
    oid = objects.write("blob", b"good")
    (tmp_path / "zz").mkdir()
    (tmp_path / "zz" / ("a" * 62)).write_bytes(b"noise")
    (tmp_path / oid[:2] / "notes.txt").write_text("not an object")
    (tmp_path / oid[:2] / ("b" * 62)).mkdir()
    assert list(objects.iter_oids()) == [oid]


def manifest(tmp_path, mutate):
    (tmp_path / "result.bin").write_bytes(b"result")
    path = write_manifest(tmp_path, pipeline="compute", revision="r1")
    payload = json.loads(path.read_text())
    mutate(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("relative", ["../outside", "/tmp/file", "..\\outside", "C:\\file", "", "."])
def test_manifest_pointer_cannot_escape_artifact_root(tmp_path, relative):
    manifest(tmp_path, lambda data: data["artifacts"][0].update(relpath=relative))
    with pytest.raises(ManifestError):
        verify_manifest(tmp_path)


@pytest.mark.parametrize("field,value", [("sha256", "x"), ("size", -1), ("size", 1.5), ("size", True)])
def test_manifest_pointer_requires_real_digest_and_nonnegative_integer_size(tmp_path, field, value):
    manifest(tmp_path, lambda data: data["artifacts"][0].update({field: value}))
    with pytest.raises(ManifestError):
        read_manifest(tmp_path)


@pytest.mark.parametrize("artifacts", [None, {}, "files", [1], [None]])
def test_malformed_artifact_list_has_actionable_error(tmp_path, artifacts):
    manifest(tmp_path, lambda data: data.update(artifacts=artifacts))
    with pytest.raises(ManifestError):
        verify_manifest(tmp_path)


def test_duplicate_manifest_paths_are_rejected(tmp_path):
    manifest(tmp_path, lambda data: data["artifacts"].append(data["artifacts"][0].copy()))
    with pytest.raises(ManifestError, match="duplicate"):
        verify_manifest(tmp_path)


def test_failed_manifest_replace_preserves_previous_provenance(tmp_path, monkeypatch):
    (tmp_path / "result.bin").write_bytes(b"original")
    path = write_manifest(tmp_path)
    original = path.read_bytes()
    (tmp_path / "result.bin").write_bytes(b"changed")

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(pointers.os, "replace", fail)
    with pytest.raises(OSError):
        write_manifest(tmp_path)
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(".tmp-manifest-*"))


def test_manifest_hashes_multiple_chunks_and_empty_files(tmp_path):
    payload = bytes(range(256)) * 8193
    (tmp_path / "large.bin").write_bytes(payload)
    (tmp_path / "empty.bin").write_bytes(b"")
    assert hash_artifact(tmp_path / "large.bin") == hashlib.sha256(payload).hexdigest()
    write_manifest(tmp_path, pipeline="stats", revision="known-revision")
    assert verify_manifest(tmp_path).verified == ("empty.bin", "large.bin")
    assert all(p.producer == {"pipeline": "stats", "revision": "known-revision"} for p in read_manifest(tmp_path))


def test_stale_reference_update_never_changes_ref_or_journal(tmp_path):
    evc = ExperimentVersionControl.init(tmp_path)
    (tmp_path / "config.json").write_text("first")
    first = evc.record("first\twith tabs\nbody preserved", author="Test <t@lab>")
    before = evc.repo.refs.journal()
    with pytest.raises(RefConflictError):
        evc.repo.refs.update_ref("refs/heads/main", "f" * 64, expected_old=None)
    assert evc.repo.refs.head_oid() == first
    assert evc.repo.refs.journal() == before
    assert before[0].message == "first with tabs"
    assert evc.show(first).message == "first\twith tabs\nbody preserved"


@pytest.mark.parametrize("ref", ["main", "refs/../outside", "refs/heads/..\\outside", "refs/heads/a\nnew"])
def test_invalid_reference_names_cannot_modify_history(tmp_path, ref):
    reference = RefStore(tmp_path)
    with pytest.raises(EVCError):
        reference.update_ref(ref, "a" * 64, expected_old=None)
    assert list(tmp_path.iterdir()) == []


def test_ref_inventory_head_and_empty_journal(tmp_path):
    reference = RefStore(tmp_path)
    assert reference.journal() == []
    assert reference.list_refs() == {}
    reference.write_head_ref("refs/heads/main")
    reference.update_ref("refs/heads/main", "a" * 64, expected_old=None)
    reference.update_ref("refs/heads/second", "b" * 64, expected_old=None)
    assert reference.head_oid() == "a" * 64
    assert reference.list_refs("refs/heads/") == {"refs/heads/main": "a" * 64, "refs/heads/second": "b" * 64}
    with (tmp_path / "journal.log").open("a") as handle:
        handle.write("\n")
    assert len(reference.journal()) == 2
    (tmp_path / "HEAD").write_text("broken")
    with pytest.raises(EVCError, match="symbolic"):
        reference.head_oid()


def test_ref_replace_failure_keeps_old_ref_and_journal_and_cleans_lock(tmp_path, monkeypatch):
    reference = RefStore(tmp_path)
    reference.update_ref("refs/heads/main", "a" * 64, expected_old=None)
    before = reference.journal()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(refs.os, "replace", fail)
    with pytest.raises(OSError):
        reference.update_ref("refs/heads/main", "b" * 64, expected_old="a" * 64)
    assert reference.read_ref("refs/heads/main") == "a" * 64
    assert reference.journal() == before
    assert not list(tmp_path.rglob("*.lock"))


def test_concurrent_ref_updates_have_only_one_winner(tmp_path):
    import threading

    reference = RefStore(tmp_path)
    reference.update_ref("refs/heads/main", "a" * 64, expected_old=None)
    start = threading.Barrier(4)

    def update(index):
        start.wait(timeout=5)
        try:
            reference.update_ref("refs/heads/main", str(index) * 64, expected_old="a" * 64)
        except RefConflictError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=4) as executor:
        winners = list(executor.map(update, range(4)))
    assert sum(winners) == 1
    assert len(reference.journal()) == 2
    assert reference.read_ref("refs/heads/main") == str(winners.index(True)) * 64
    assert not list(tmp_path.rglob("*.lock"))


def test_backend_csv_history_restore_preserves_unsaved_work_and_bulk_artifacts(tmp_path):
    (tmp_path / "experiments.csv").write_text("line number,id,comments\n1,R1,baseline\n2,R2,untouched\n")
    (tmp_path / "analysis_parameters.csv").write_text("line number,crop,decay_time\n1,False,0.5\n2,True,1\n")
    imported = import_experiment(1, tmp_path, author="Test <t@lab>")
    evc = ExperimentVersionControl.open(tmp_path)
    (tmp_path / "artifacts" / "recording.raw").write_bytes(b"irreplaceable recording")
    doc_path = tmp_path / "parameters" / ANALYSIS_CNMFE_DOC
    doc = json.loads(doc_path.read_text())
    doc["params"]["decay_time"] = 0.75
    doc_path.write_text(json.dumps(doc))
    writeback(tmp_path)
    assert load_analysis_params(1, tmp_path)["crop"] is False
    changed = evc.record("reviewed change", author="Test <t@lab>")
    extract(1, tmp_path)
    doc = json.loads(doc_path.read_text())
    doc["params"]["decay_time"] = 0.9
    doc_path.write_text(json.dumps(doc))
    result = evc.restore(imported.revision, author="Test <t@lab>")
    assert result.safety_snapshot is not None
    assert json.loads(doc_path.read_text())["params"]["decay_time"] == 0.5
    assert evc.repo.refs.head_oid() == changed
    assert (tmp_path / "artifacts" / "recording.raw").read_bytes() == b"irreplaceable recording"
    evc.restore(result.safety_snapshot, author="Test <t@lab>")
    assert json.loads(doc_path.read_text())["params"]["decay_time"] == 0.9
    assert any(entry.op == "safety-snapshot" for entry in evc.recover())
