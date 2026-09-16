"""Phase 1 workspace contract: declarative ignore globs and the scaffolded
experiment layout — bulk recordings never enter the object store."""

from __future__ import annotations

import json
import time

import pytest

from aceneurotools.evc.errors import EVCError
from aceneurotools.evc.porcelain import ExperimentVersionControl
from aceneurotools.evc.workspace import (
    DEFAULT_IGNORE_PATTERNS,
    ExperimentWorkspace,
    write_default_ignore,
)
from aceneurotools.evc.worktree import IGNORE_FILE, IgnoreRules

AUTHOR = "Test Rig <rig@lab>"


@pytest.fixture()
def exp(tmp_path):
    """An initialised workspace-mode experiment with one parameter file."""
    exp_dir = tmp_path / "exp042"
    exp_dir.mkdir()
    evc = ExperimentVersionControl.init(exp_dir, workspace=True)
    (exp_dir / "parameters" / "params.json").write_text(json.dumps({"gSig": 3}))
    return exp_dir, evc


# -- IgnoreRules (unit) -------------------------------------------------------


def test_ignore_rules_match_name_globs_at_any_depth():
    rules = IgnoreRules(patterns=("*.avi", "*.mmap"))
    assert rules.ignores("0.avi", is_dir=False)
    assert rules.ignores("session1/deep/1.avi", is_dir=False)
    assert rules.ignores("memmap_d1.mmap", is_dir=False)
    assert not rules.ignores("params.json", is_dir=False)


def test_ignore_rules_directory_only_patterns():
    rules = IgnoreRules(patterns=("saved_movies/",))
    assert rules.ignores("saved_movies", is_dir=True)
    assert rules.ignores("session1/saved_movies", is_dir=True)
    # a *file* named saved_movies is not covered by a directory pattern
    assert not rules.ignores("saved_movies", is_dir=False)


def test_ignore_rules_path_patterns_are_root_relative():
    rules = IgnoreRules(patterns=("results/tmp-*",))
    assert rules.ignores("results/tmp-123", is_dir=True)
    assert not rules.ignores("other/results/tmp-123", is_dir=True)
    assert not rules.ignores("results/final", is_dir=True)


def test_ignore_rules_load_skips_comments_and_blanks(tmp_path):
    ignore = tmp_path / "ignore"
    ignore.write_text("# comment\n\n*.avi\n  saved_movies/  \n")
    rules = IgnoreRules.load(ignore)
    assert rules.patterns == ("*.avi", "saved_movies/")


def test_ignore_rules_missing_file_means_no_rules(tmp_path):
    assert IgnoreRules.load(tmp_path / "does-not-exist").patterns == ()


# -- init / scaffold ----------------------------------------------------------


def test_init_writes_default_ignore_file(tmp_path):
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir()
    ExperimentVersionControl.init(exp_dir)
    content = (exp_dir / ".evc" / IGNORE_FILE).read_text()
    for pattern in DEFAULT_IGNORE_PATTERNS:
        assert pattern in content.splitlines()


def test_init_never_overwrites_an_edited_ignore_file(tmp_path):
    exp_dir = tmp_path / "exp"
    (exp_dir / ".evc").mkdir(parents=True)
    custom = (exp_dir / ".evc" / IGNORE_FILE)
    custom.write_text("*.custom\n")
    write_default_ignore(exp_dir / ".evc")
    assert custom.read_text() == "*.custom\n"


def test_init_workspace_scaffolds_layout(exp):
    exp_dir, _ = exp
    assert (exp_dir / "parameters").is_dir()
    assert (exp_dir / "results").is_dir()
    assert (exp_dir / "artifacts").is_dir()


def test_run_dir_resolves_and_rejects_illegal_ids(tmp_path):
    workspace = ExperimentWorkspace(tmp_path)
    assert workspace.run_dir("run-001") == tmp_path / "results" / "run-001"
    for bad in ("", ".", "..", "a/b", "a\\b"):
        with pytest.raises(EVCError):
            workspace.run_dir(bad)


# -- snapshots exclude bulk ---------------------------------------------------


def test_snapshot_excludes_ignored_bulk(exp):
    exp_dir, evc = exp
    (exp_dir / "0.avi").write_bytes(b"raw movie bytes")
    (exp_dir / "estimates.hdf5").write_bytes(b"hdf5 bytes")
    (exp_dir / "saved_movies").mkdir()
    (exp_dir / "saved_movies" / "clip.bin").write_bytes(b"clip")
    (exp_dir / "artifacts" / "big.dat").write_bytes(b"bulk")
    oid = evc.record("initial parameters", author=AUTHOR)
    files = evc.show(oid).files
    assert "parameters/params.json" in files
    assert not any(".avi" in f or ".hdf5" in f for f in files)
    assert not any(f.startswith(("saved_movies", "artifacts")) for f in files)


def test_bulk_avi_records_fast_with_zero_bytes_stored(exp):
    """Acceptance (scaled down): a large sparse .avi in the workspace records
    quickly and none of its bytes enter ``.evc/objects``."""
    exp_dir, evc = exp
    movie = exp_dir / "movie.avi"
    with open(movie, "wb") as fh:  # sparse: 256 MB extent, no disk cost
        fh.seek(256 * 1024 * 1024 - 1)
        fh.write(b"\0")
    start = time.perf_counter()
    evc.record("params only", author=AUTHOR)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    objects_dir = exp_dir / ".evc" / "objects"
    total = sum(p.stat().st_size for p in objects_dir.rglob("*") if p.is_file())
    assert total < 64 * 1024  # a few small parameter objects, no movie bytes


def test_edited_ignore_file_takes_effect_immediately(exp):
    exp_dir, evc = exp
    (exp_dir / "trace.npz").write_bytes(b"npz bytes")
    with open(exp_dir / ".evc" / IGNORE_FILE, "a") as fh:
        fh.write("*.npz\n")
    oid = evc.record("without npz", author=AUTHOR)
    assert "trace.npz" not in evc.show(oid).files


def test_restore_leaves_ignored_bulk_untouched(exp):
    exp_dir, evc = exp
    first = evc.record("initial", author=AUTHOR)
    (exp_dir / "0.avi").write_bytes(b"movie")
    (exp_dir / "parameters" / "params.json").write_text(json.dumps({"gSig": 9}))
    evc.record("bump", author=AUTHOR)
    evc.restore(first)
    assert (exp_dir / "0.avi").read_bytes() == b"movie"
    assert json.loads((exp_dir / "parameters" / "params.json").read_text()) == {"gSig": 3}
