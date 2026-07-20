"""Tests for the ace-neuro --setup first-time wizard."""

from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from aceneurotools.cli import _setup_wizard, _tutorial


def _feed_inputs(monkeypatch, answers: list[str]) -> list[str]:
    """Patch builtins.input to return successive `answers`. Records prompts."""
    prompts: list[str] = []
    iterator = iter(answers)

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        try:
            return next(iterator)
        except StopIteration as exc:
            raise EOFError from exc

    monkeypatch.setattr(builtins, "input", fake_input)
    return prompts


def test_wizard_generates_three_templates(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    _feed_inputs(monkeypatch, [str(tmp_path), "n"])  # path + decline tutorial
    rc = _setup_wizard()
    assert rc == 0
    assert (tmp_path / "lab_config.json").exists()
    assert (tmp_path / "stats_config.json").exists()
    assert (tmp_path / "experiments_template.csv").exists()


def test_wizard_default_to_cwd_when_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.chdir(tmp_path)
    _feed_inputs(monkeypatch, ["", "n"])
    rc = _setup_wizard()
    assert rc == 0
    assert (tmp_path / "lab_config.json").exists()


def test_wizard_offers_tutorial_at_end(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    _feed_inputs(monkeypatch, [str(tmp_path), "n"])
    _setup_wizard()
    out = capsys.readouterr().out
    assert "Step 1 — Choose a project directory" in out
    assert "Step 2 — Generate template files" in out
    assert "Step 3 — Optional: guided tutorial" in out
    assert "guided tour of every data path" in out
    # Declined tutorial → Setup complete message + run command
    assert "Setup complete." in out
    assert "ace-neuro" in out


def test_wizard_runs_tutorial_when_user_accepts(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    _feed_inputs(monkeypatch, [str(tmp_path), "y"])
    _setup_wizard()
    out = capsys.readouterr().out
    # Tutorial section headings appear
    assert "Guided tutorial: data paths" in out
    assert "lab_config.json" in out and "paths" in out
    assert "experiments.csv" in out
    assert "Tutorial complete." in out


def test_tutorial_covers_every_data_path(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    _tutorial(tmp_path)
    out = capsys.readouterr().out
    # 4 lab_config path keys
    for key in ("project_path", "data_path", "output_dir", "calcium_signal_dir"):
        assert key in out, f"tutorial missing {key!r}"
    # 2 experiments.csv columns
    assert "ephys directory" in out
    assert "calcium imaging directory" in out
    # Each section includes example + gotcha
    assert out.count("Example:") >= 6
    assert out.count("Gotcha:") >= 6


def test_tutorial_explains_stats_is_modular(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    _tutorial(tmp_path)
    out = capsys.readouterr().out
    assert "Pipeline structure" in out
    assert "modular opt-in" in out
    # The tutorial must say compute is the default and the user is asked
    # about stats after compute completes.
    assert "compute only" in out
    assert "ask" in out.lower() or "asked" in out.lower()


def test_wizard_skips_when_files_exist_and_user_declines(monkeypatch, tmp_path):
    monkeypatch.setenv("NO_COLOR", "1")
    (tmp_path / "lab_config.json").write_text('{"existing": true}')
    original = (tmp_path / "lab_config.json").read_text()
    # path → decline overwrite → decline tutorial
    _feed_inputs(monkeypatch, [str(tmp_path), "n", "n"])
    rc = _setup_wizard()
    assert rc == 0
    assert (tmp_path / "lab_config.json").read_text() == original
    assert not (tmp_path / "stats_config.json").exists()


def test_wizard_overwrites_when_user_confirms(monkeypatch, tmp_path):
    monkeypatch.setenv("NO_COLOR", "1")
    (tmp_path / "lab_config.json").write_text('{"existing": true}')
    # path → confirm overwrite → decline tutorial
    _feed_inputs(monkeypatch, [str(tmp_path), "y", "n"])
    rc = _setup_wizard()
    assert rc == 0
    text = (tmp_path / "lab_config.json").read_text()
    assert '"existing": true' not in text
    assert (tmp_path / "stats_config.json").exists()


def test_wizard_cancelled_by_eof(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.chdir(tmp_path)
    _feed_inputs(monkeypatch, [])
    rc = _setup_wizard()
    assert rc == 1
    assert "cancelled" in capsys.readouterr().out.lower()
