"""Tests for aceneurotools.shared.banner."""

from __future__ import annotations

from io import StringIO

from aceneurotools.shared.banner import (
    LONG_LOGO,
    SHORT_LOGO,
    TINY_LOGO,
    _interp,
    _pick_logo,
    _should_use_color,
    render_banner,
    render_tips,
    welcome,
)

# ---------------------------------------------------------------------------
# Logo dimensions / selection
# ---------------------------------------------------------------------------


def test_logos_have_six_rows():
    for logo in (LONG_LOGO, SHORT_LOGO, TINY_LOGO):
        assert logo.count("\n") == 5  # 6 rows separated by 5 newlines


def test_long_logo_widest_tiny_narrowest():
    def w(s: str) -> int:
        return max(len(line) for line in s.splitlines())

    assert w(LONG_LOGO) > w(SHORT_LOGO) > w(TINY_LOGO)


def test_pick_long_at_wide_terminal():
    assert _pick_logo(width=120) is LONG_LOGO


def test_pick_short_at_mid_terminal():
    assert _pick_logo(width=70) is SHORT_LOGO


def test_pick_tiny_at_narrow_terminal():
    assert _pick_logo(width=30) is TINY_LOGO


def test_pick_long_default_when_no_width_given(monkeypatch):
    monkeypatch.setattr("aceneurotools.shared.banner._terminal_width", lambda: 120)
    assert _pick_logo() is LONG_LOGO


# ---------------------------------------------------------------------------
# Color interpolation
# ---------------------------------------------------------------------------


def test_interp_endpoints_exact():
    a = (0, 255, 136)
    b = (0, 180, 216)
    assert _interp(a, b, 0.0) == a
    assert _interp(a, b, 1.0) == b


def test_interp_midpoint():
    a = (0, 0, 0)
    b = (100, 100, 100)
    assert _interp(a, b, 0.5) == (50, 50, 50)


def test_interp_clamps_via_rounding():
    """Float t inside [0,1] should produce ints inside the rgb bound."""
    a, b = (10, 20, 30), (200, 100, 50)
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        r, g, blue = _interp(a, b, t)
        assert 0 <= r <= 255
        assert 0 <= g <= 255
        assert 0 <= blue <= 255


# ---------------------------------------------------------------------------
# NO_COLOR / non-TTY behavior
# ---------------------------------------------------------------------------


def test_should_use_color_off_when_no_color_set(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    assert _should_use_color() is False


def test_should_use_color_off_when_not_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    assert _should_use_color() is False


def test_should_use_color_on_when_tty_and_no_no_color(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    assert _should_use_color() is True


# ---------------------------------------------------------------------------
# Banner output (capture stdout, both colored and plain modes)
# ---------------------------------------------------------------------------


def test_render_banner_plain_writes_logo_and_tagline(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    render_banner(width=120)
    out = capsys.readouterr().out
    assert "███" in out
    assert "Analysis of Calcium Imaging" in out


def test_render_banner_picks_logo_per_width(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    render_banner(width=30)
    out = capsys.readouterr().out
    # Tiny logo is much shorter — max line width should be ~10
    max_w = max(len(line) for line in out.splitlines() if line.strip())
    assert max_w < 20


def test_render_tips_plain_writes_numbered_tips(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    render_tips()
    out = capsys.readouterr().out
    assert "Tips for getting started:" in out
    assert "1." in out
    assert "ace-neuro" in out


def test_render_banner_color_mode_uses_rich(monkeypatch):
    """In color mode, banner is routed through Rich Console."""
    from rich.console import Console

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, color_system="truecolor", width=120)
    render_banner(width=120, console=console)
    captured = buf.getvalue()
    # Truecolor escape sequence for rgb()
    assert "\x1b[" in captured
    # Logo still present
    assert "███" in captured


def test_tagline_uses_gradient_start_color(monkeypatch):
    """Tagline must match the bright top-of-gradient color (calcium green)."""
    from rich.console import Console

    from aceneurotools.shared.banner import _GRADIENT_START

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, color_system="truecolor", width=120)
    render_banner(width=120, console=console)
    captured = buf.getvalue()
    # Truecolor escape for the gradient start RGB must appear adjacent to the tagline.
    r, g, b = _GRADIENT_START
    expected_escape = f"\x1b[1;38;2;{r};{g};{b}m"
    # The tagline line must include this escape immediately preceding the text.
    tagline_idx = captured.find("Analysis of Calcium Imaging")
    assert tagline_idx != -1, "tagline missing from rendered output"
    # Look back for the bright-green escape in the preceding 200 bytes.
    preceding = captured[max(0, tagline_idx - 200) : tagline_idx]
    assert expected_escape in preceding


def test_welcome_emits_banner_only_by_default(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    welcome(width=120)
    out = capsys.readouterr().out
    assert "███" in out
    # Tips panel must NOT appear by default — first-time users get the
    # setup wizard, returning users go straight into the pipeline.
    assert "Tips for getting started:" not in out


def test_welcome_emits_tips_when_explicitly_requested(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    welcome(width=120, show_tips=True)
    out = capsys.readouterr().out
    assert "███" in out
    assert "Tips for getting started:" in out


def test_welcome_emits_clear_sequence_on_tty(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    welcome(width=120)
    out = capsys.readouterr().out
    # ESC[2J = clear screen, ESC[3J = clear scrollback, ESC[H = home cursor
    assert "\x1b[2J" in out
    assert "\x1b[H" in out


def test_welcome_skips_clear_when_not_tty(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    welcome(width=120)
    out = capsys.readouterr().out
    assert "\x1b[2J" not in out
    assert "\x1b[H" not in out


def test_welcome_clear_can_be_disabled(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    welcome(width=120, clear=False)
    out = capsys.readouterr().out
    assert "\x1b[2J" not in out


def test_welcome_top_padding_prints_blank_lines(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    welcome(width=120, clear=False, top_padding=3)
    out = capsys.readouterr().out
    # The first three "lines" of stdout should all be empty before the banner.
    lines = out.splitlines()
    assert lines[:3] == ["", "", ""]
    # Banner still follows.
    assert any("███" in line for line in lines[3:])


def test_welcome_zero_padding_no_top_blanks(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    welcome(width=120, clear=False, top_padding=0)
    out = capsys.readouterr().out
    # First non-empty line should be the banner — no blanks first.
    # At this width the banner leads with the card icon, then the letterform.
    first = out.splitlines()[0]
    assert first.startswith("╔")
    assert "█" in first


# ---------------------------------------------------------------------------
# Icon + logo rendering
# ---------------------------------------------------------------------------


def test_long_banner_leads_with_icon_then_logo(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    render_banner(width=120)
    rows = capsys.readouterr().out.splitlines()
    # Row 0 begins with the card icon frame, then carries the N letterform.
    assert rows[0].startswith("╔")
    assert "███╗" in rows[0]
    # Row 5 ends with the logo's bottom shadow corner.
    assert rows[5].endswith("╝")


def test_tiny_banner_uses_tiny_logo(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    render_banner(width=30)
    rows = capsys.readouterr().out.splitlines()
    max_w = max(len(r) for r in rows if r.strip())
    assert max_w < 20


def test_short_banner_uses_short_logo(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    render_banner(width=60)
    rows = capsys.readouterr().out.splitlines()
    # icon (10) + gutter (5) + SHORT_LOGO (44 cols) = 59.
    max_w = max(len(r) for r in rows if r.strip())
    assert 50 < max_w <= 60
