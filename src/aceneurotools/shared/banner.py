"""ACE-NeuroTools welcome banner.

Renders a heavy-block ASCII "NEUROTOOLS" / "NEURO" / "N" (picked by
terminal width) with a calcium-green to instrument-cyan vertical
gradient. Optional "Tips for getting started" panel below.

Honors ``NO_COLOR`` (https://no-color.org/) and skips colorization when stdout
is not a TTY so output piped to a file stays clean.

Public API
----------
:func:`render_banner` — print the banner to stdout (or a given Rich console).
:func:`render_tips`   — print the tips panel to stdout.
:func:`welcome`       — convenience: banner + tips back-to-back.
"""

from __future__ import annotations

import os
import sys

# ─────────────────────────────────────────────────────────────────────────────
# ASCII art constants (ANSI Shadow font)
# ─────────────────────────────────────────────────────────────────────────────

LONG_LOGO = r"""███╗   ██╗███████╗██╗   ██╗██████╗  ██████╗ ████████╗ ██████╗  ██████╗ ██╗     ███████╗
████╗  ██║██╔════╝██║   ██║██╔══██╗██╔═══██╗╚══██╔══╝██╔═══██╗██╔═══██╗██║     ██╔════╝
██╔██╗ ██║█████╗  ██║   ██║██████╔╝██║   ██║   ██║   ██║   ██║██║   ██║██║     ███████╗
██║╚██╗██║██╔══╝  ██║   ██║██╔══██╗██║   ██║   ██║   ██║   ██║██║   ██║██║     ╚════██║
██║ ╚████║███████╗╚██████╔╝██║  ██║╚██████╔╝   ██║   ╚██████╔╝╚██████╔╝███████╗███████║
╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝╚══════╝"""

SHORT_LOGO = r"""███╗   ██╗███████╗██╗   ██╗██████╗  ██████╗
████╗  ██║██╔════╝██║   ██║██╔══██╗██╔═══██╗
██╔██╗ ██║█████╗  ██║   ██║██████╔╝██║   ██║
██║╚██╗██║██╔══╝  ██║   ██║██╔══██╗██║   ██║
██║ ╚████║███████╗╚██████╔╝██║  ██║╚██████╔╝
╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝"""

TINY_LOGO = r"""███╗   ██╗
████╗  ██║
██╔██╗ ██║
██║╚██╗██║
██║ ╚████║
╚═╝  ╚═══╝"""

# Width thresholds (columns) for picking which variant to render.
# Each is the logo width + a 1-col safety gutter.
_LONG_MIN_COLS = 87 + 1   # 88
_SHORT_MIN_COLS = 44 + 1  # 45

# Calcium-green → instrument-cyan vertical gradient endpoints.
_GRADIENT_START = (0x00, 0xff, 0x88)  # bright GCaMP green
_GRADIENT_END = (0x00, 0xb4, 0xd8)    # deep cyan

# Tagline shown under the logo.
_TAGLINE = "Analysis of Calcium Imaging & Electrophysiology"


# ─────────────────────────────────────────────────────────────────────────────
# Logo selection
# ─────────────────────────────────────────────────────────────────────────────

def _terminal_width() -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


def _pick_logo(width: int | None = None) -> str:
    if width is None:
        width = _terminal_width()
    if width >= _LONG_MIN_COLS:
        return LONG_LOGO
    if width >= _SHORT_MIN_COLS:
        return SHORT_LOGO
    return TINY_LOGO


# ─────────────────────────────────────────────────────────────────────────────
# Color handling
# ─────────────────────────────────────────────────────────────────────────────

def _should_use_color() -> bool:
    # https://no-color.org/
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    return True


def _interp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(round(a[0] + (b[0] - a[0]) * t)),
        int(round(a[1] + (b[1] - a[1]) * t)),
        int(round(a[2] + (b[2] - a[2]) * t)),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────────────────────────────────────

def render_banner(width: int | None = None, console=None) -> None:
    """Print the banner. Picks long/short/tiny by terminal width.

    Parameters
    ----------
    width : int, optional
        Override the detected terminal width; useful for testing.
    console : rich.console.Console, optional
        Render to a specific Rich console (useful for capturing output).
        Defaults to a new Console bound to stdout.
    """
    logo = _pick_logo(width)
    lines = logo.splitlines()
    art_width = max(len(l) for l in lines)
    show_tagline = art_width >= len(_TAGLINE)
    use_color = _should_use_color()

    if not use_color:
        for line in lines:
            print(line)
        if show_tagline:
            print()
            print(_TAGLINE.center(art_width))
        return

    # Import rich lazily so module import doesn't pay the cost until needed.
    from rich.console import Console
    from rich.text import Text

    if console is None:
        console = Console()

    n_rows = len(lines)
    for i, line in enumerate(lines):
        t = i / max(1, n_rows - 1)
        r, g, b = _interp(_GRADIENT_START, _GRADIENT_END, t)
        styled = Text(line, style=f"bold rgb({r},{g},{b})")
        console.print(styled, soft_wrap=False)

    if show_tagline:
        gr, gg, gb = _GRADIENT_START
        console.print()
        console.print(
            Text(_TAGLINE.center(art_width), style=f"bold rgb({gr},{gg},{gb})")
        )


def render_tips(width: int | None = None, console=None) -> None:
    """Print a short numbered tip list.

    The numbering matches the project's typical first-time-user path:
    initialise → confirm → run.
    """
    if width is None:
        width = _terminal_width()

    use_color = _should_use_color()

    tips = [
        ("First-time setup:",      "ace-neuro --setup"),
        ("Edit",                   "lab_config.json to point at your data"),
        ("Run the full pipeline:", "ace-neuro"),
        ("Get help anywhere:",     "ace-neuro --help"),
    ]

    if not use_color:
        print()
        print("Tips for getting started:")
        for i, (lead, body) in enumerate(tips, 1):
            print(f"  {i}. {lead} {body}")
        return

    from rich.console import Console
    from rich.text import Text

    if console is None:
        console = Console()
    console.print()
    console.print(Text("Tips for getting started:", style="bold"))
    for i, (lead, body) in enumerate(tips, 1):
        line = Text()
        line.append(f"  {i}. ", style="dim")
        line.append(lead + " ", style="default")
        line.append(body, style="cyan")
        console.print(line)


def _clear_screen() -> None:
    """Clear the terminal — TTY only. Silent no-op when piped/redirected."""
    if not sys.stdout.isatty():
        return
    # ESC [2J clears the entire screen; ESC [H homes the cursor.
    # ESC [3J also clears the scrollback (xterm extension; widely supported).
    sys.stdout.write("\x1b[2J\x1b[3J\x1b[H")
    sys.stdout.flush()


def welcome(
    width: int | None = None,
    *,
    clear: bool = True,
    top_padding: int = 2,
    show_tips: bool = False,
) -> None:
    """Print the welcome screen: clear, top-pad, banner. Tips off by default.

    Parameters
    ----------
    width : int, optional
        Override the detected terminal width; useful for testing.
    clear : bool, default True
        Clear the terminal before drawing. Only takes effect on a TTY so
        piped/redirected output stays clean.
    top_padding : int, default 2
        Blank lines to print above the banner so it doesn't hug the top edge.
    show_tips : bool, default False
        Render the legacy numbered tips panel beneath the banner. Off by
        default because first-time users get the setup wizard instead, and
        returning users go straight into the pipeline flow.
    """
    if clear:
        _clear_screen()
    for _ in range(max(0, top_padding)):
        print()
    render_banner(width=width)
    if show_tips:
        render_tips(width=width)
