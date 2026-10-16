"""Workstream 7 regression contracts for the EVC API.

Pins the user-facing contract (``docs/api/evc.md``, module docstrings):

* a corrupt ``.evc/config.json`` (bad JSON, wrong document/field types) is a
  typed ``EVCError`` naming the file — never ``JSONDecodeError``/``TypeError``;
* realistic user mistakes raise the ``EVCError`` family, never bare
  ``ValueError``/``FileNotFoundError``/``OSError`` — the CLI prints
  ``error: ...`` and exits 1 instead of showing a traceback;
* ``aceneurotools.evc`` exports every name that ``aceneurotools.evc.api``
  exports, including every error type;
* the access commands (status/history/show/diff/recover/comments) never
  write anything under ``.evc/`` — not even unreferenced snapshot objects —
  and ``status`` reports an unignored oversized file instead of failing.
"""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

import aceneurotools.evc as evc_package
import aceneurotools.evc.api as api
import aceneurotools.evc.worktree as worktree_module
from aceneurotools.evc import errors as evc_errors
from aceneurotools.evc.__main__ import main as evc_main
from aceneurotools.evc.errors import EVCError, OversizedSnapshotError, UnknownRevisionError
from aceneurotools.evc.hooks import RunRecorder
from aceneurotools.evc.objects import MODE_FILE, Commit, Tree, TreeEntry
from aceneurotools.evc.porcelain import ExperimentVersionControl
from aceneurotools.evc.repository import ExperimentRepository

AUTHOR = "Contract Test <contract@lab>"


def test_csv_import_reports_missing_head_as_typed_error(exp):
    exp_dir, evc = exp
    (evc.repo.evc_dir / "HEAD").unlink()
    with pytest.raises(EVCError, match="HEAD"):
        api.import_experiment(1, exp_dir)


def test_run_failure_reports_missing_head_as_typed_error(exp):
    exp_dir, _ = exp
    recorder = RunRecorder(exp_dir, pipeline="compute")
    (recorder.evc.repo.evc_dir / "HEAD").unlink()
    with pytest.raises(EVCError, match="HEAD"):
        recorder.on_run_failed(RuntimeError("pipeline failure"))


@pytest.fixture()
def exp(tmp_path):
    exp_dir = tmp_path / "exp042"
    exp_dir.mkdir()
    (exp_dir / "params.json").write_text(json.dumps({"gSig": 3}))
    return exp_dir, ExperimentVersionControl.init(exp_dir)


def _run_cli(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = evc_main(list(args))
    return rc, out.getvalue(), err.getvalue()


def _evc_inventory(evc_dir: Path) -> dict[str, str]:
    """Every path under ``.evc/`` with the content hash of each file."""
    inventory: dict[str, str] = {}
    for path in sorted(evc_dir.rglob("*")):
        rel = path.relative_to(evc_dir).as_posix()
        if path.is_dir():
            inventory[rel + "/"] = "dir"
        elif path.is_file():
            inventory[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return inventory


# -- 1. corrupt configuration -------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        b"not json at all {{{",
        b'{"format_version": 1, "hash_a',
        b"[1, 2, 3]",
        b"null",
        b'{"format_version": "2"}',
        b'{"format_version": null}',
        b'{"format_version": 2.5}',
        b'{"format_version": true}',
    ],
    ids=[
        "invalid-json",
        "truncated",
        "json-list",
        "json-null",
        "version-string",
        "version-null",
        "version-float",
        "version-bool",
    ],
)
def test_corrupt_config_raises_typed_error_naming_the_file(tmp_path, payload):
    exp_dir = tmp_path / "exp"
    (exp_dir / ".evc").mkdir(parents=True)
    (exp_dir / ".evc" / "config.json").write_bytes(payload)

    with pytest.raises(EVCError) as excinfo:
        ExperimentRepository.open(exp_dir)

    assert "config.json" in str(excinfo.value)


def test_config_that_is_a_directory_is_a_typed_error(tmp_path):
    exp_dir = tmp_path / "exp"
    ExperimentRepository.init(exp_dir)
    config = exp_dir / ".evc" / "config.json"
    config.unlink()
    config.mkdir()

    with pytest.raises(EVCError) as excinfo:
        ExperimentRepository.open(exp_dir)

    assert "config.json" in str(excinfo.value)


@pytest.mark.parametrize("version", [0, 1], ids=["old-format", "current-format"])
def test_valid_current_and_older_config_versions_stay_accepted(tmp_path, version):
    exp_dir = tmp_path / "exp"
    ExperimentRepository.init(exp_dir)
    (exp_dir / ".evc" / "config.json").write_text(json.dumps({"format_version": version, "hash_algorithm": "sha256"}))

    opened = ExperimentRepository.open(exp_dir)

    assert opened.evc_dir == exp_dir / ".evc"


def test_newer_format_version_is_still_refused(tmp_path):
    exp_dir = tmp_path / "exp"
    ExperimentRepository.init(exp_dir)
    (exp_dir / ".evc" / "config.json").write_text(json.dumps({"format_version": 999}))

    with pytest.raises(EVCError, match="newer than this software supports"):
        ExperimentRepository.open(exp_dir)


# -- 2. typed errors for realistic user mistakes ------------------------------


def test_init_on_a_file_is_a_typed_error(tmp_path):
    target = tmp_path / "a-file"
    target.write_text("not a directory")

    with pytest.raises(EVCError):
        ExperimentVersionControl.init(target)


def test_init_workspace_collision_is_a_typed_error(tmp_path):
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir()
    (exp_dir / "parameters").write_text("a file where the scaffold needs a directory")

    with pytest.raises(EVCError):
        ExperimentVersionControl.init(exp_dir, workspace=True)


def test_missing_head_file_is_a_typed_error(exp):
    exp_dir, evc = exp
    (exp_dir / ".evc" / "HEAD").unlink()

    with pytest.raises(EVCError):
        evc.status()
    with pytest.raises(EVCError):
        evc.record("cannot read HEAD", author=AUTHOR)


def test_head_pointing_at_a_directory_ref_is_a_typed_error(exp):
    exp_dir, evc = exp
    (exp_dir / ".evc" / "refs" / "heads" / "main").mkdir(parents=True, exist_ok=True)

    with pytest.raises(EVCError):
        evc.status()
    with pytest.raises(EVCError):
        evc.history()


def test_revision_named_like_a_branch_directory_is_unknown(exp):
    exp_dir, evc = exp
    oid = evc.record("first", author=AUTHOR)
    topic = exp_dir / ".evc" / "refs" / "heads" / "topic"
    topic.mkdir()
    (topic / "sub").write_text(oid + "\n")

    with pytest.raises(UnknownRevisionError):
        evc.show("topic")


def test_blank_record_and_comment_text_are_domain_errors(exp):
    exp_dir, evc = exp
    evc.record("first", author=AUTHOR)

    with pytest.raises(EVCError, match="revision message is required"):
        evc.record("   ", author=AUTHOR)

    (exp_dir / "params.json").write_text(json.dumps({"gSig": 4}))
    second = evc.record("second", author=AUTHOR)
    with pytest.raises(EVCError, match="comment text is required"):
        evc.comment(second, "   ", author=AUTHOR)


def test_notes_that_are_not_valid_utf8_are_a_typed_error(exp):
    exp_dir, evc = exp
    oid = evc.record("first", author=AUTHOR)
    blob_oid = evc.repo.write_blob(b"\xff\xfe not text")
    tree_oid = evc.repo.write_tree(Tree(entries=(TreeEntry(mode=MODE_FILE, type="blob", oid=blob_oid, name=oid),)))
    notes_commit = evc.repo.write_commit(
        Commit(
            tree=tree_oid,
            parents=(),
            author=AUTHOR,
            author_time=1,
            author_tz="+0000",
            message="notes",
        )
    )
    notes_ref = exp_dir / ".evc" / "refs" / "notes" / "comments"
    notes_ref.parent.mkdir(parents=True)
    notes_ref.write_text(notes_commit + "\n")

    with pytest.raises(EVCError, match="not valid UTF-8"):
        evc.comments(oid)
    with pytest.raises(EVCError, match="not valid UTF-8"):
        evc.comment(oid, "append", author=AUTHOR)


def test_notes_ref_pointing_at_a_missing_object_is_a_typed_error(exp):
    exp_dir, evc = exp
    oid = evc.record("first", author=AUTHOR)
    notes_ref = exp_dir / ".evc" / "refs" / "notes" / "comments"
    notes_ref.parent.mkdir(parents=True)
    notes_ref.write_text("f" * 64 + "\n")

    with pytest.raises(EVCError):
        evc.comments(oid)
    with pytest.raises(EVCError):
        evc.comment(oid, "annotate", author=AUTHOR)


def test_corrupt_journal_is_a_typed_error(exp):
    exp_dir, evc = exp
    evc.record("first", author=AUTHOR)
    with (exp_dir / ".evc" / "journal.log").open("a", encoding="utf-8") as handle:
        handle.write("garbage-without-tabs\n")

    with pytest.raises(EVCError, match="journal"):
        evc.recover()


def test_cli_init_on_a_file_exits_1_with_an_error_not_a_traceback(tmp_path):
    target = tmp_path / "a-file"
    target.write_text("not a directory")

    rc, out, err = _run_cli("--dir", str(target), "init")

    assert rc == 1
    assert out == ""
    assert err.startswith("error:")


def test_cli_blank_record_message_exits_1_with_an_error(tmp_path):
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir()
    (exp_dir / "params.json").write_text("{}")
    assert _run_cli("--dir", str(exp_dir), "init")[0] == 0

    rc, out, err = _run_cli("--dir", str(exp_dir), "record", "-m", "   ", "--json")

    assert rc == 1
    assert out == ""
    assert err.startswith("error:")


def test_cli_dir_pointing_at_a_file_exits_1_with_an_error(tmp_path):
    target = tmp_path / "a-file"
    target.write_text("not a directory")

    rc, out, err = _run_cli("--dir", str(target), "status", "--json")

    assert rc == 1
    assert out == ""
    assert err.startswith("error:")


def test_cli_verify_missing_run_dir_exits_1_with_an_error(tmp_path):
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir()
    assert _run_cli("--dir", str(exp_dir), "init", "--workspace")[0] == 0

    rc, out, err = _run_cli("--dir", str(exp_dir), "verify", "no-such-run", "--json")

    assert rc == 1
    assert out == ""
    assert err.startswith("error:") and "manifest" in err


# -- 3. export / JSON contract consistency ------------------------------------


def test_evc_package_exports_every_api_name():
    assert set(api.__all__) <= set(evc_package.__all__)
    missing = [name for name in api.__all__ if not hasattr(evc_package, name)]
    assert missing == []


def test_every_error_type_is_exported_by_both_public_packages():
    error_names = {
        name for name, value in vars(evc_errors).items() if isinstance(value, type) and issubclass(value, EVCError)
    }
    assert error_names  # sanity: the scan found the hierarchy
    assert error_names <= set(evc_package.__all__)
    assert error_names <= set(api.__all__)
    for name in sorted(error_names):
        assert getattr(evc_package, name) is getattr(evc_errors, name)
        assert getattr(api, name) is getattr(evc_errors, name)


def test_cli_status_json_matches_the_frozen_dataclass_fields(exp):
    exp_dir, evc = exp
    evc.record("first", author=AUTHOR)
    (exp_dir / "params.json").write_text(json.dumps({"gSig": 4}))

    rc, out, _ = _run_cli("--dir", str(exp_dir), "status", "--json")

    assert rc == 0
    assert set(json.loads(out)) == {field.name for field in dataclasses.fields(api.StatusReport)}


def test_cli_verify_json_reports_the_computed_clean_field(tmp_path):
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir()
    assert _run_cli("--dir", str(exp_dir), "init", "--workspace")[0] == 0
    run_dir = exp_dir / "results" / "run-001"
    run_dir.mkdir(parents=True)
    (run_dir / "trace.npz").write_bytes(b"npz")
    from aceneurotools.evc.pointers import write_manifest

    write_manifest(run_dir)

    rc, out, _ = _run_cli("--dir", str(exp_dir), "verify", "run-001", "--json")

    assert rc == 0
    payload = json.loads(out)
    assert set(payload) == {field.name for field in dataclasses.fields(api.ManifestVerification)} | {"clean"}
    assert payload["clean"] is True


# -- 4. access commands are strictly read-only --------------------------------


def test_access_commands_never_mutate_the_repository(exp):
    exp_dir, evc = exp
    evc.record("first", author=AUTHOR)
    evc.comment("HEAD", "annotated", author=AUTHOR)  # mutating: do it before the inventory
    (exp_dir / "params.json").write_text(json.dumps({"gSig": 4}))
    evc_dir = exp_dir / ".evc"
    before = _evc_inventory(evc_dir)

    reads = {
        "status": lambda: evc.status(),
        "history": lambda: evc.history(),
        "show": lambda: evc.show("HEAD"),
        "diff": lambda: evc.diff("HEAD", "HEAD"),
        "recover": lambda: evc.recover(),
        "comments": lambda: evc.comments("HEAD"),
    }
    for name, read in reads.items():
        read()
        assert _evc_inventory(evc_dir) == before, f"{name}() mutated .evc/"

    assert not [path for path in evc_dir.rglob(".tmp-*")]


def test_status_on_unborn_head_is_read_only(tmp_path):
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir()
    (exp_dir / "params.json").write_text("{}")
    evc = ExperimentVersionControl.init(exp_dir)
    before = _evc_inventory(exp_dir / ".evc")

    report = evc.status()

    assert report.head is None and not report.clean
    assert _evc_inventory(exp_dir / ".evc") == before


def test_status_keeps_parameter_level_diffs_without_persisting(exp):
    exp_dir, evc = exp
    evc.record("first", author=AUTHOR)
    (exp_dir / "params.json").write_text(json.dumps({"gSig": 4, "min_corr": 0.8}))
    evc_dir = exp_dir / ".evc"
    before = _evc_inventory(evc_dir)

    report = evc.status()

    change = report.changes[0]
    assert (change.path, change.status) == ("params.json", "modified")
    assert {(param.key, param.old, param.new) for param in change.param_changes} == {
        ("gSig", 3, 4),
        ("min_corr", "<absent>", 0.8),
    }
    assert _evc_inventory(evc_dir) == before


def test_status_reports_added_and_removed_paths_read_only(exp):
    exp_dir, evc = exp
    evc.record("first", author=AUTHOR)
    (exp_dir / "params.json").unlink()
    (exp_dir / "session_notes.txt").write_text("kept as a note")
    evc_dir = exp_dir / ".evc"
    before = _evc_inventory(evc_dir)

    report = evc.status()

    assert {(change.path, change.status) for change in report.changes} == {
        ("params.json", "removed"),
        ("session_notes.txt", "added"),
    }
    assert _evc_inventory(evc_dir) == before


def test_status_reports_oversized_files_instead_of_failing_and_stays_read_only(exp, monkeypatch):
    exp_dir, evc = exp
    evc.record("first", author=AUTHOR)
    payload = exp_dir / "legacy-recording.tiff"
    payload.write_bytes(b"x" * 17)
    monkeypatch.setattr(worktree_module, "MAX_SNAPSHOT_BLOB_BYTES", 16)
    evc_dir = exp_dir / ".evc"
    before = _evc_inventory(evc_dir)

    report = evc.status()

    assert not report.clean
    assert [(change.path, change.status) for change in report.changes] == [("legacy-recording.tiff", "added")]
    assert _evc_inventory(evc_dir) == before
    # recording still refuses the same file: the ceiling keeps history small
    with pytest.raises(OversizedSnapshotError):
        evc.record("must refuse bulk", author=AUTHOR)
