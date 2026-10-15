"""Regression tests for CLI configuration-path handling."""

from __future__ import annotations

from aceneurotools import cli
from aceneurotools.config.lab_config import ConditionSpec, LabConfig
from aceneurotools.shared import banner


def _silence_banner(monkeypatch) -> None:
    monkeypatch.setattr(banner, "welcome", lambda: None)


def test_explicit_missing_config_returns_error_without_side_effects(monkeypatch, tmp_path, capsys):
    _silence_banner(monkeypatch)
    missing = tmp_path / "missing" / "lab_config.json"
    setup_called = False

    def unexpected_setup() -> int:
        nonlocal setup_called
        setup_called = True
        return 0

    monkeypatch.setattr(cli, "_setup_wizard", unexpected_setup)

    rc = cli.main(["--config", str(missing), "--yes", "--headless"])

    captured = capsys.readouterr()
    assert rc == 1
    assert str(missing) in captured.err
    assert "--setup" in captured.err
    assert "--project-path" in captured.err
    assert captured.out == ""
    assert setup_called is False
    assert list(tmp_path.rglob("*")) == []


def test_implicit_missing_config_still_runs_setup(monkeypatch, tmp_path):
    _silence_banner(monkeypatch)
    monkeypatch.chdir(tmp_path)
    setup_calls = 0

    def fake_setup() -> int:
        nonlocal setup_calls
        setup_calls += 1
        return 73

    monkeypatch.setattr(cli, "_setup_wizard", fake_setup)

    assert cli.main([]) == 73
    assert setup_calls == 1


def test_explicit_setup_still_runs_with_missing_config(monkeypatch, tmp_path):
    _silence_banner(monkeypatch)
    missing = tmp_path / "missing.json"
    setup_calls = 0

    def fake_setup() -> int:
        nonlocal setup_calls
        setup_calls += 1
        return 74

    monkeypatch.setattr(cli, "_setup_wizard", fake_setup)

    assert cli.main(["--setup", "--config", str(missing)]) == 74
    assert setup_calls == 1


def test_existing_config_reaches_normal_flow(monkeypatch, tmp_path):
    _silence_banner(monkeypatch)
    config_path = tmp_path / "lab_config.json"
    LabConfig(
        primary_channel="calcium",
        freq_range=[0.5, 30.0],
        conditions={"control": ConditionSpec(subjects=[1], is_drug=False)},
        time_windows={1: [[0.0, 10.0], [10.0, 20.0]]},
    ).to_json(config_path)
    confirm_calls = 0

    def decline_paths(_config: LabConfig) -> bool:
        nonlocal confirm_calls
        confirm_calls += 1
        return False

    monkeypatch.setattr(cli, "_confirm_paths", decline_paths)

    assert cli.main(["--config", str(config_path)]) == 0
    assert confirm_calls == 1
