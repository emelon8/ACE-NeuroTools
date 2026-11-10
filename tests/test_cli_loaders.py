"""Tests for ``ace-neuro loaders`` (list / validate / detect)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from aceneurotools import cli
from aceneurotools.shared import banner

EXAMPLES = Path(__file__).parent / "data" / "loaders"


@pytest.fixture(autouse=True)
def _no_banner(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail() -> None:
        raise AssertionError("loaders commands must not print the pipeline banner")

    monkeypatch.setattr(banner, "welcome", fail)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    folder = tmp_path / "project" / "loaders"
    folder.mkdir(parents=True)
    for example in EXAMPLES.glob("*.json"):
        shutil.copy(example, folder / example.name)
    return folder.parent


def _touch(folder: Path, *names: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"")
    return folder


# ── validate ──────────────────────────────────────────────────────────────────

def test_validate_examples_ok(capsys: pytest.CaptureFixture[str]) -> None:
    files = [str(EXAMPLES / "neuralynx-example.json"), str(EXAMPLES / "rhs2116-example.json")]
    assert cli.main(["loaders", "validate", *files]) == 0
    out, err = capsys.readouterr()
    assert f"{files[0]}: ok (neuralynx-example, neo)" in out
    assert f"{files[1]}: ok (rhs2116-example, raw_binary)" in out
    assert err == ""


def test_validate_reports_each_problem(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    doc = json.loads((EXAMPLES / "neuralynx-example.json").read_text())
    doc["reader"]["io"] = "NoSuchIO"
    doc["lable"] = "typo"
    bad = tmp_path / "neuralynx-example.json"
    bad.write_text(json.dumps(doc))
    good = str(EXAMPLES / "rhs2116-example.json")

    assert cli.main(["loaders", "validate", good, str(bad)]) == 1
    out, err = capsys.readouterr()
    assert f"{good}: ok" in out
    assert f"{bad}: reader.io: 'NoSuchIO' is not a neo IO in neo.io.iolist" in err
    assert f"{bad}: lable: unknown key; did you mean 'label'?" in err
    assert "1 of 2 file(s) invalid" in err


def test_validate_invalid_json_and_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{")
    missing = tmp_path / "missing.json"
    assert cli.main(["loaders", "validate", str(broken), str(missing)]) == 1
    _, err = capsys.readouterr()
    assert f"{broken}: (document): invalid JSON" in err
    assert f"{missing}: (document): cannot read file" in err


def test_validate_requires_a_file() -> None:
    with pytest.raises(SystemExit) as info:
        cli.main(["loaders", "validate"])
    assert info.value.code == 2


def test_loaders_requires_an_action() -> None:
    with pytest.raises(SystemExit) as info:
        cli.main(["loaders"])
    assert info.value.code == 2


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_without_loaders_folder(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["loaders", "list", "--project-path", str(tmp_path)]) == 0
    out, _ = capsys.readouterr()
    assert "NeuralynxDataManager" in out
    assert "RHS2116DataManager" in out
    assert out.index("NeuralynxDataManager") < out.index("RHS2116DataManager")  # factory order
    assert "Project definitions: none" in out


def test_list_defaults_to_current_directory(project: Path, monkeypatch: pytest.MonkeyPatch,
                                            capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(project)
    assert cli.main(["loaders", "list"]) == 0
    out, _ = capsys.readouterr()
    assert "neuralynx-example  [neo]" in out
    assert "rhs2116-example  [raw_binary]" in out


def test_list_reports_bad_files(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "loaders" / "broken.json").write_text('{"schema": "ace-loader/9"}')
    assert cli.main(["loaders", "list", "--project-path", str(project)]) == 1
    out, err = capsys.readouterr()
    assert "neuralynx-example  [neo]" in out
    broken = project / "loaders" / "broken.json"
    assert f"{broken}: schema: unsupported version 'ace-loader/9'" in err


def test_list_uses_loader_name_when_a_manager_defines_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                          capsys: pytest.CaptureFixture[str]) -> None:
    from aceneurotools.ephys.neuralynx_data_manager import NeuralynxDataManager

    monkeypatch.setattr(NeuralynxDataManager, "loader_name", "neuralynx", raising=False)
    assert cli.main(["loaders", "list", "--project-path", str(tmp_path)]) == 0
    out, _ = capsys.readouterr()
    assert "  neuralynx  (aceneurotools.ephys.neuralynx_data_manager.NeuralynxDataManager)" in out


# ── detect ────────────────────────────────────────────────────────────────────

def test_detect_neuralynx_folder(project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rec = _touch(tmp_path / "rec", "Events.nev", "CSC1.ncs")
    assert cli.main(["loaders", "detect", str(rec), "--project-path", str(project)]) == 0
    out, err = capsys.readouterr()
    builtin, _, defs = out.partition("Project definitions that match")
    assert "NeuralynxDataManager" in builtin and "RHS2116DataManager" not in builtin
    assert "neuralynx-example  [neo]  matched: *.nev (1)" in defs
    assert "rhs2116" not in defs
    assert "Several" not in out
    assert err == ""


def test_detect_rhs2116_folder(project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rec = _touch(tmp_path / "rec", "start-time_0.csv", "rhs2116pair-ac_0.raw", "rhs2116pair-clock_0.raw",
                 "rhs2116pair-dc_0.raw")
    assert cli.main(["loaders", "detect", str(rec), "--project-path", str(project)]) == 0
    out, _ = capsys.readouterr()
    builtin, _, defs = out.partition("Project definitions that match")
    assert "RHS2116DataManager" in builtin and "NeuralynxDataManager" not in builtin
    assert "rhs2116-example  [raw_binary]  matched: *.raw (3)" in defs


def test_detect_ambiguous_folder(project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rec = _touch(tmp_path / "rec", "Events.nev", "x.raw")
    assert cli.main(["loaders", "detect", str(rec), "--project-path", str(project)]) == 0
    out, _ = capsys.readouterr()
    assert "EphysDataManager.create() currently uses the first: NeuralynxDataManager" in out
    assert "Several definitions match" in out
    assert "ADR 0008" in out


def test_detect_nothing_matches(project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rec = _touch(tmp_path / "rec", "notes.txt")
    assert cli.main(["loaders", "detect", str(rec), "--project-path", str(project)]) == 1
    out, _ = capsys.readouterr()
    assert out.count("(none)") == 2


def test_detect_missing_folder(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["loaders", "detect", str(tmp_path / "missing"), "--project-path", str(tmp_path)]) == 1
    _, err = capsys.readouterr()
    assert "not a folder" in err


def test_detect_skips_invalid_definitions(project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "loaders" / "broken.json").write_text("[]")
    rec = _touch(tmp_path / "rec", "Events.nev")
    assert cli.main(["loaders", "detect", str(rec), "--project-path", str(project)]) == 0
    out, err = capsys.readouterr()
    assert "neuralynx-example  [neo]" in out
    assert "Skipped 1 invalid definition file(s)" in err
    assert "broken.json: (document): a loader definition must be a JSON object" in err


# ── the main command is unchanged and stays light ─────────────────────────────

def test_help_does_not_import_heavy_modules() -> None:
    code = (
        "import sys\n"
        "from aceneurotools import cli\n"
        "try:\n"
        "    cli.main(['--help'])\n"
        "except SystemExit:\n"
        "    pass\n"
        "heavy = [m for m in ('neo', 'aceneurotools.ephys', 'aceneurotools.shared.loader_definitions') "
        "if m in sys.modules]\n"
        "print('HEAVY', heavy)\n"
    )
    src = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": src},
    )
    assert result.returncode == 0, result.stderr
    assert "HEAVY []" in result.stdout
    assert "loaders" in result.stdout  # the subcommand is listed in --help


def test_main_without_subcommand_still_reaches_config_flow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(banner, "welcome", lambda: None)
    missing = tmp_path / "missing.json"
    assert cli.main(["--config", str(missing), "--yes", "--headless"]) == 1


# ── review round 1 regressions ────────────────────────────────────────────────

_PERMISSIONS_APPLY = not (os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0))


@pytest.mark.skipif(not _PERMISSIONS_APPLY, reason="permission bits do not block reads here")
def test_detect_reports_unreadable_recording_folder(
    tmp_path: Path, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rec = _touch(tmp_path / "rec", "Events.nev")
    rec.chmod(0)
    try:
        code = cli.main(["loaders", "detect", str(rec), "--project-path", str(project)])
    finally:
        rec.chmod(0o755)
    assert code == 1
    assert "cannot read folder" in capsys.readouterr().err


def test_detect_warns_when_project_folder_is_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rec = _touch(tmp_path / "rec", "Events.nev")
    code = cli.main(["loaders", "detect", str(rec), "--project-path", str(tmp_path / "nope")])
    out = capsys.readouterr()
    assert code == 0  # the built-in Neuralynx loader still matches
    assert "project folder not found" in out.err


@pytest.mark.skipif(not _PERMISSIONS_APPLY, reason="permission bits do not block reads here")
def test_list_fails_on_unreadable_loaders_folder(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    folder = project / "loaders"
    folder.chmod(0)
    try:
        code = cli.main(["loaders", "list", "--project-path", str(project)])
    finally:
        folder.chmod(0o755)
    assert code == 1
    assert "cannot read folder" in capsys.readouterr().err


# ── Built-in names are reserved, as in the workbench ─────────────────────────

def _reserved_copy(folder: Path, name: str = "neuralynx") -> Path:
    doc = json.loads((EXAMPLES / "neuralynx-example.json").read_text())
    doc["name"] = name
    path = folder / f"{name}.json"
    path.write_text(json.dumps(doc))
    return path


@pytest.mark.parametrize("name", ["neuralynx", "rhs2116", "neuralynxdatamanager"])
def test_validate_refuses_built_in_loader_names(tmp_path: Path, name: str, capsys: pytest.CaptureFixture[str]) -> None:
    path = _reserved_copy(tmp_path, name)
    assert cli.main(["loaders", "validate", str(path)]) == 1
    _, err = capsys.readouterr()
    assert f"{path}: name: '{name}' is already used by a built-in loader" in err


def test_list_refuses_built_in_loader_names(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _reserved_copy(project / "loaders")
    assert cli.main(["loaders", "list", "--project-path", str(project)]) == 1
    out, err = capsys.readouterr()
    assert "neuralynx-example  [neo]" in out
    assert "\n  neuralynx  [neo]" not in out
    assert f"{path}: name: 'neuralynx' is already used by a built-in loader" in err


def test_detect_skips_built_in_loader_names(project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _reserved_copy(project / "loaders")
    rec = _touch(tmp_path / "rec", "Events.nev")
    assert cli.main(["loaders", "detect", str(rec), "--project-path", str(project)]) == 0
    out, err = capsys.readouterr()
    assert "neuralynx-example  [neo]  matched" in out
    assert "\n  neuralynx  [neo]" not in out
    assert "Skipped 1 invalid definition file(s)" in err and "already used by a built-in loader" in err


def test_cli_and_workbench_reserve_the_same_names() -> None:
    from aceneurotools.gui import loaders as gui_loaders

    gui_loaders._builtins_cache = None
    assert cli._reserved_loader_names() == gui_loaders.reserved_names()
    assert {"neuralynx", "neuralynxdatamanager", "rhs2116", "rhs2116datamanager"} <= cli._reserved_loader_names()
