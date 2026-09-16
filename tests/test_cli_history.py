"""Phase 5 CLI surface: `ace-neuro history` delegates verbatim to the EVC
porcelain — every command reachable, headless-safe output, --experiment
resolution via ExperimentDataManager."""

from __future__ import annotations

import json

import pytest

from aceneurotools.cli import main as cli_main
from aceneurotools.evc.pointers import write_manifest

AUTHOR = "Test Rig <rig@lab>"


def _history(*args: str) -> int:
    return cli_main(["history", *args])


@pytest.fixture()
def exp(tmp_path):
    """A workspace experiment initialised through the ace-neuro CLI itself."""
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir()
    assert _history("--dir", str(exp_dir), "init", "--workspace") == 0
    (exp_dir / "parameters" / "params.json").write_text(json.dumps({"gSig": 3}))
    return exp_dir


def test_every_porcelain_command_reachable(exp, tmp_path, capsys):
    d = str(exp)
    assert _history("--dir", d, "record", "-m", "initial", "--author", AUTHOR) == 0
    first = capsys.readouterr().out.split()[-1]

    assert _history("--dir", d, "status") == 0
    assert "clean" in capsys.readouterr().out

    (exp / "parameters" / "params.json").write_text(json.dumps({"gSig": 4}))
    assert _history("--dir", d, "record", "-m", "bump gSig", "--author", AUTHOR) == 0
    capsys.readouterr()

    assert _history("--dir", d, "log") == 0
    out = capsys.readouterr().out
    assert "bump gSig" in out and "initial" in out

    assert _history("--dir", d, "show", first) == 0
    assert "parameters/params.json" in capsys.readouterr().out

    assert _history("--dir", d, "diff", first, "HEAD") == 0
    assert "gSig" in capsys.readouterr().out

    assert _history("--dir", d, "comment", "HEAD", "-m", "QC passed") == 0
    assert _history("--dir", d, "comments", "HEAD") == 0
    assert "QC passed" in capsys.readouterr().out

    assert _history("--dir", d, "restore", first) == 0
    assert json.loads((exp / "parameters" / "params.json").read_text()) == {"gSig": 3}
    assert _history("--dir", d, "recover") == 0
    assert "restore" in capsys.readouterr().out

    remote = tmp_path / "share"
    assert _history("--dir", d, "push", str(remote)) == 0
    assert "refs/heads/main" in capsys.readouterr().out

    run = exp / "results" / "run-001"
    run.mkdir(parents=True)  # restore pruned the empty scaffold dirs
    (run / "trace.npz").write_bytes(b"npz")
    write_manifest(run)
    assert _history("--dir", d, "verify", "run-001") == 0
    assert "1 artifact(s) verified" in capsys.readouterr().out


def test_history_without_command_prints_usage(capsys):
    assert cli_main(["history"]) == 2
    err = capsys.readouterr().err
    assert "usage: ace-neuro history" in err and "verify" in err


def test_history_errors_are_headless_safe(exp, capsys):
    rc = _history("--dir", str(exp), "show", "doesnotexist")
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_experiment_flag_resolves_via_experiment_data_manager(
    exp, monkeypatch, capsys
):
    import aceneurotools.shared.experiment_data_manager as edm_mod

    class FakeEDM:
        def __init__(self, line_num, project_path=None, data_path=None,
                     auto_import_analysis_params=True):
            self.line_num = line_num
            self.metadata = {"calcium imaging directory": exp}

        def get_miniscope_directory(self):
            return exp

    monkeypatch.setattr(edm_mod, "ExperimentDataManager", FakeEDM)
    assert _history("--experiment", "42", "status") == 0
    assert "branch main" in capsys.readouterr().out


def test_experiment_flag_missing_row_fails_actionably(monkeypatch, capsys):
    import aceneurotools.shared.experiment_data_manager as edm_mod

    class NoRowEDM:
        def __init__(self, *args, **kwargs):
            self.metadata = None

    monkeypatch.setattr(edm_mod, "ExperimentDataManager", NoRowEDM)
    assert _history("--experiment", "999", "status") == 1
    assert "no experiments.csv row" in capsys.readouterr().err
