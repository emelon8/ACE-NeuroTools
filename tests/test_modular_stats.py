"""Tests asserting stats is opt-in / modular, not auto-second-half."""

from __future__ import annotations

import builtins


def _feed(monkeypatch, answers: list[str]) -> None:
    iterator = iter(answers)

    def fake_input(prompt: str = "") -> str:
        try:
            return next(iterator)
        except StopIteration as exc:
            raise EOFError from exc

    monkeypatch.setattr(builtins, "input", fake_input)


# ---------------------------------------------------------------------------
# Template default
# ---------------------------------------------------------------------------


def test_template_defaults_to_compute_mode():
    """New lab_config.json templates must default to compute-only."""
    from aceneurotools.init import _lab_config_template

    cfg = _lab_config_template()
    assert cfg["run"]["mode"] == "compute"


# ---------------------------------------------------------------------------
# _select_mode menu shape and defaults
# ---------------------------------------------------------------------------


class _FakeLabConfig:
    """Minimal stand-in matching the attrs _select_mode inspects."""

    class _Run:
        mode = None  # forces the menu to show

    run = _Run()


def test_select_mode_default_is_compute(monkeypatch, capsys):
    from aceneurotools.cli import _select_mode

    _feed(monkeypatch, [""])  # press Enter → default
    chosen = _select_mode(_FakeLabConfig())
    assert chosen == "compute"


def test_select_mode_option_2_promotes_to_all(monkeypatch):
    from aceneurotools.cli import _select_mode

    _feed(monkeypatch, ["2"])
    assert _select_mode(_FakeLabConfig()) == "all"


def test_select_mode_option_3_is_stats_only(monkeypatch):
    from aceneurotools.cli import _select_mode

    _feed(monkeypatch, ["3"])
    assert _select_mode(_FakeLabConfig()) == "stats"


def test_select_mode_accepts_named_aliases(monkeypatch):
    from aceneurotools.cli import _select_mode

    _feed(monkeypatch, ["compute + stats"])
    assert _select_mode(_FakeLabConfig()) == "all"


def test_select_mode_menu_labels_emphasize_optional_stats(monkeypatch, capsys):
    from aceneurotools.cli import _select_mode

    _feed(monkeypatch, [""])
    _select_mode(_FakeLabConfig())
    out = capsys.readouterr().out
    assert "compute" in out
    assert "stats" in out
    # The compute option must be marked default.
    assert "[default]" in out
    # The menu must include a "compute + stats" combined option.
    assert "compute + stats" in out


def test_select_mode_respects_existing_run_mode(monkeypatch, capsys):
    """If lab_config.run.mode is set, no menu is shown."""
    from aceneurotools.cli import _select_mode

    cfg = _FakeLabConfig()
    cfg.run.mode = "stats"
    # No input answers needed — should not prompt.
    chosen = _select_mode(cfg)
    assert chosen == "stats"
    assert "Select Pipeline Mode" not in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Tutorial messaging
# ---------------------------------------------------------------------------


def test_tutorial_mentions_post_compute_prompt(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    from aceneurotools.cli import _tutorial

    _tutorial(tmp_path)
    out = capsys.readouterr().out
    # Tutorial should make clear stats is optional and triggered by a prompt.
    assert "modular opt-in" in out
    assert "compute only" in out
    assert "you'll be asked" in out.lower()
