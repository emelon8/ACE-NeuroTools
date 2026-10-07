"""The invisible CLI (D05 step 4): every EVC command emits machine-readable
JSON with --json, shaped by the frozen evc.api dataclasses — exercised
through the `ace-neuro history` delegation path agents will actually use."""

from __future__ import annotations

import json

import pytest

import aceneurotools.evc.worktree as worktree_module
from aceneurotools.cli import main as cli_main
from aceneurotools.evc.pointers import write_manifest

AUTHOR = "Test Rig <rig@lab>"


@pytest.fixture()
def exp(tmp_path, capsys):
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir()
    assert cli_main(["history", "--dir", str(exp_dir), "init", "--workspace", "--json"]) == 0
    init_payload = json.loads(capsys.readouterr().out)
    assert init_payload["workspace"] is True and init_payload["initialized"].endswith(".evc")
    (exp_dir / "parameters" / "params.json").write_text(json.dumps({"gSig": 3}))
    return exp_dir


def _run(exp_dir, capsys, *args, expect_rc=0):
    rc = cli_main(["history", "--dir", str(exp_dir), *args, "--json"])
    assert rc == expect_rc, capsys.readouterr()
    return json.loads(capsys.readouterr().out)


def test_record_status_log_show_are_machine_readable(exp, capsys):
    recorded = _run(exp, capsys, "record", "-m", "initial", "--author", AUTHOR)
    oid = recorded["recorded"]
    assert len(oid) == 64

    status = _run(exp, capsys, "status")
    assert status == {"branch": "main", "head": oid, "clean": True, "changes": []}

    (exp / "parameters" / "params.json").write_text(json.dumps({"gSig": 4}))
    dirty = _run(exp, capsys, "status")
    assert dirty["clean"] is False
    assert dirty["changes"][0]["path"] == "parameters/params.json"

    _run(exp, capsys, "record", "-m", "bump gSig", "--author", AUTHOR)
    log = _run(exp, capsys, "log")
    assert [r["message"] for r in log["revisions"]] == ["bump gSig", "initial"]

    shown = _run(exp, capsys, "show", oid[:8])
    assert shown["oid"] == oid
    assert "parameters/params.json" in shown["files"]


def test_diff_reports_parameter_changes_as_json(exp, capsys):
    first = _run(exp, capsys, "record", "-m", "initial", "--author", AUTHOR)["recorded"]
    (exp / "parameters" / "params.json").write_text(json.dumps({"gSig": 4}))
    _run(exp, capsys, "record", "-m", "bump", "--author", AUTHOR)
    diff = _run(exp, capsys, "diff", first, "HEAD")
    change = diff["changes"][0]
    assert change["path"] == "parameters/params.json"
    assert change["param_changes"] == [{"key": "gSig", "old": 3, "new": 4}]


def test_restore_comment_recover_push_as_json(exp, capsys, tmp_path):
    first = _run(exp, capsys, "record", "-m", "initial", "--author", AUTHOR)["recorded"]
    (exp / "parameters" / "params.json").write_text(json.dumps({"gSig": 9}))

    restored = _run(exp, capsys, "restore", first)
    assert restored["restored"] == first
    assert restored["safety_snapshot"]  # dirty state preserved

    assert "notes_commit" in _run(exp, capsys, "comment", "HEAD", "-m", "QC passed")
    assert "QC passed" in _run(exp, capsys, "comments", "HEAD")["comments"]

    journal = _run(exp, capsys, "recover")["journal"]
    assert {"record", "safety-snapshot", "restore"} <= {e["op"] for e in journal}

    push = _run(exp, capsys, "push", str(tmp_path / "share"))
    assert push["results"][0]["ref"] == "refs/heads/main"
    assert push["results"][0]["objects_sent"] > 0


def test_verify_emits_report_json_even_on_failure(exp, capsys):
    run = exp / "results" / "run-001"
    run.mkdir(parents=True)
    (run / "trace.npz").write_bytes(b"npz")
    write_manifest(run)

    clean = _run(exp, capsys, "verify", "run-001")
    assert clean["clean"] is True and clean["verified"] == ["trace.npz"]

    (run / "trace.npz").write_bytes(b"tampered")
    failed = _run(exp, capsys, "verify", "run-001", expect_rc=1)
    assert failed["clean"] is False and failed["modified"] == ["trace.npz"]


def test_errors_stay_on_stderr_not_json(exp, capsys):
    rc = cli_main(["history", "--dir", str(exp), "show", "nope", "--json"])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.out == ""
    assert "error:" in captured.err


def test_record_explains_why_an_oversized_file_is_refused(exp, capsys, monkeypatch):
    monkeypatch.setattr(worktree_module, "MAX_SNAPSHOT_BLOB_BYTES", 16)
    payload = exp / "legacy-recording.tiff"
    payload.write_bytes(b"x" * 17)

    rc = cli_main(
        [
            "history",
            "--dir",
            str(exp),
            "record",
            "-m",
            "must refuse bulk",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert captured.out == ""
    assert "error: Refusing to snapshot" in captured.err
    assert "legacy-recording.tiff" in captured.err
    assert "because EVC revisions copy file contents into .evc/objects" in captured.err
    assert "unexpectedly large and slow" in captured.err
    assert "source file was left untouched" in captured.err
    assert "artifacts/" in captured.err
    assert ".evc/ignore" in captured.err
