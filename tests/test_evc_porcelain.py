"""User journeys through the axiomatic commands: record, access, restore,
comment, push — plus the never-lose-anything guarantees."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from aceneurotools.evc.errors import NothingToRecordError, PushRejectedError
from aceneurotools.evc.porcelain import ExperimentVersionControl
from aceneurotools.evc.remote import LocalDirectoryRemote

AUTHOR = "Test Rig <rig@lab>"


@pytest.fixture()
def exp(tmp_path):
    """An initialised experiment directory with one parameter file."""
    exp_dir = tmp_path / "exp042"
    exp_dir.mkdir()
    (exp_dir / "params.json").write_text(json.dumps({"gSig": 3, "min_corr": 0.8}))
    evc = ExperimentVersionControl.init(exp_dir)
    return exp_dir, evc


def _write_params(exp_dir, **params):
    (exp_dir / "params.json").write_text(json.dumps(params))


# -- record ------------------------------------------------------------------


def test_record_and_history(exp):
    exp_dir, evc = exp
    first = evc.record("initial parameters", author=AUTHOR)
    _write_params(exp_dir, gSig=4, min_corr=0.8)
    second = evc.record("bump gSig", author=AUTHOR)
    revisions = evc.history()
    assert [r.oid for r in revisions] == [second, first]
    assert revisions[0].parents == (first,)
    assert revisions[1].parents == ()


def test_record_requires_message_and_changes(exp):
    _, evc = exp
    evc.record("initial", author=AUTHOR)
    with pytest.raises(ValueError):
        evc.record("   ", author=AUTHOR)
    with pytest.raises(NothingToRecordError):
        evc.record("no changes since last record", author=AUTHOR)


def test_record_captures_nested_directories(exp):
    exp_dir, evc = exp
    nested = exp_dir / "results" / "session1"
    nested.mkdir(parents=True)
    (nested / "manifest.json").write_text("{}")
    oid = evc.record("with results manifest", author=AUTHOR)
    assert "results/session1/manifest.json" in evc.show(oid).files


# -- access ------------------------------------------------------------------


def test_status_clean_and_dirty(exp):
    exp_dir, evc = exp
    evc.record("initial", author=AUTHOR)
    assert evc.status().clean
    _write_params(exp_dir, gSig=5, min_corr=0.8)
    report = evc.status()
    assert not report.clean
    assert [c.path for c in report.changes] == ["params.json"]


def test_show_resolves_short_ids(exp):
    _, evc = exp
    oid = evc.record("initial", author=AUTHOR)
    assert evc.show(oid[:8]).oid == oid
    assert evc.show("HEAD").oid == oid
    assert evc.show("main").oid == oid


def test_diff_reports_parameter_level_changes(exp):
    exp_dir, evc = exp
    first = evc.record("initial", author=AUTHOR)
    _write_params(exp_dir, gSig=4, min_corr=0.85)
    (exp_dir / "notes.txt").write_text("session went fine")
    second = evc.record("tweak", author=AUTHOR)
    diffs = {d.path: d for d in evc.diff(first, second)}
    assert diffs["notes.txt"].status == "added"
    changes = {c.key: (c.old, c.new) for c in diffs["params.json"].param_changes}
    assert changes == {"gSig": (3, 4), "min_corr": (0.8, 0.85)}


# -- restore: never destroys ---------------------------------------------------


def test_restore_clean_worktree(exp):
    exp_dir, evc = exp
    first = evc.record("initial", author=AUTHOR)
    _write_params(exp_dir, gSig=9, min_corr=0.5)
    evc.record("wild parameters", author=AUTHOR)
    result = evc.restore(first)
    assert result.safety_snapshot is None
    assert json.loads((exp_dir / "params.json").read_text()) == {
        "gSig": 3, "min_corr": 0.8,
    }
    # the ref did not move: HEAD still names the second revision
    assert evc.history()[0].message == "wild parameters"


def test_restore_dirty_state_is_preserved_and_recoverable(exp):
    exp_dir, evc = exp
    first = evc.record("initial", author=AUTHOR)
    _write_params(exp_dir, gSig=7, min_corr=0.99)  # dirty, unrecorded
    result = evc.restore(first)
    assert result.safety_snapshot is not None
    # the dirty state is reachable via recover() and restorable
    ops = [entry.op for entry in evc.recover()]
    assert "safety-snapshot" in ops
    evc.restore(result.safety_snapshot)
    assert json.loads((exp_dir / "params.json").read_text()) == {
        "gSig": 7, "min_corr": 0.99,
    }


def test_restore_removes_files_absent_from_target(exp):
    exp_dir, evc = exp
    first = evc.record("initial", author=AUTHOR)
    (exp_dir / "extra.txt").write_text("later addition")
    evc.record("added extra", author=AUTHOR)
    evc.restore(first)
    assert not (exp_dir / "extra.txt").exists()
    assert (exp_dir / ".evc").is_dir()  # repository itself untouched


# -- comment -------------------------------------------------------------------


def test_comment_annotates_without_changing_revision(exp):
    _, evc = exp
    oid = evc.record("initial", author=AUTHOR)
    assert evc.comments(oid) is None
    evc.comment(oid, "QC passed; keep as baseline", author=AUTHOR)
    evc.comment(oid, "used in figure 2", author=AUTHOR)
    text = evc.comments(oid)
    assert "QC passed" in text and "figure 2" in text
    assert evc.show(oid).oid == oid  # target revision id unchanged
    with pytest.raises(ValueError):
        evc.comment(oid, "   ")


# -- push ------------------------------------------------------------------------


def test_push_new_remote_then_up_to_date(exp, tmp_path):
    _, evc = exp
    evc.record("initial", author=AUTHOR)
    remote = LocalDirectoryRemote.create(tmp_path / "share")
    first_push = evc.push(remote)
    assert first_push[0].objects_sent > 0
    again = evc.push(remote)
    assert again[0].up_to_date


def test_push_fast_forward_and_comments_travel(exp, tmp_path):
    exp_dir, evc = exp
    oid = evc.record("initial", author=AUTHOR)
    remote = LocalDirectoryRemote.create(tmp_path / "share")
    evc.push(remote)
    _write_params(exp_dir, gSig=4, min_corr=0.8)
    second = evc.record("bump", author=AUTHOR)
    evc.comment(oid, "baseline", author=AUTHOR)
    results = {r.ref: r for r in evc.push(remote)}
    assert results["refs/heads/main"].new_oid == second
    assert "refs/notes/comments" in results
    assert remote.get_ref("refs/heads/main") == second


def test_push_rejects_diverged_remote(exp, tmp_path):
    exp_dir, evc = exp
    evc.record("initial", author=AUTHOR)
    remote = LocalDirectoryRemote.create(tmp_path / "share")
    evc.push(remote)
    # a second clone-like experiment diverges the shared ref
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    (other_dir / "params.json").write_text('{"gSig": 99}')
    other = ExperimentVersionControl.init(other_dir)
    other.record("unrelated history", author=AUTHOR)
    with pytest.raises(PushRejectedError):
        other.push(remote)


# -- CLI smoke --------------------------------------------------------------------


def test_cli_init_record_log_roundtrip(tmp_path):
    exp_dir = tmp_path / "cli_exp"
    exp_dir.mkdir()
    (exp_dir / "params.json").write_text('{"a": 1}')

    def run(*args):
        return subprocess.run(
            [sys.executable, "-m", "aceneurotools.evc", "--dir", str(exp_dir), *args],
            capture_output=True, text=True,
        )

    assert run("init").returncode == 0
    recorded = run("record", "-m", "first", "--author", "T <t@t>")
    assert recorded.returncode == 0, recorded.stderr
    log = run("log")
    assert log.returncode == 0 and "first" in log.stdout
    status = run("status")
    assert "clean" in status.stdout
    bad = run("show", "doesnotexist")
    assert bad.returncode == 1 and "error:" in bad.stderr
