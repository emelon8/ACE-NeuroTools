"""
ACE-NeuroTools master CLI entry point.

Invoked as ``ace-neuro`` after ``pip install -e .``.

Usage
-----
::

    # Full pipeline (compute calcium signal files, then run stats)
    ace-neuro

    # Specify config location explicitly
    ace-neuro --config C:\\path\\to\\lab_config.json

    # Override pipeline mode
    ace-neuro --mode stats

    # Process only specific subjects
    ace-neuro --line-nums 97 101 --mode stats

    # Skip path-confirmation prompt (useful in automated scripts)
    ace-neuro --yes

First-time setup::

    python -m aceneurotools.init --project-path /your/project

The command looks for ``lab_config.json`` in the current working directory
unless ``--config`` is supplied.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aceneurotools.multimodal.lab_config import LabConfig

# ─────────────────────────────────────────────────────────────────────────────
# Terminal layout constants
# ─────────────────────────────────────────────────────────────────────────────

_W = 80  # banner / divider width


# ─────────────────────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────────────────────

def _banner() -> str:
    """Return the 80-column ASCII art welcome banner."""
    border = "#" * _W
    blank = "%%" + " " * (_W - 4) + "%%"

    def _row(text: str) -> str:
        return "%%" + ("  " + text).ljust(_W - 4) + "%%"

    # 5-row block letters for A, C, E, N, E, U, R, O
    A = [" ### ", "#   #", "#####", "#   #", "#   #"]
    C = ["#### ", "#    ", "#    ", "#    ", "#### "]
    E = ["#####", "#    ", "###  ", "#    ", "#####"]
    N = ["#   #", "##  #", "# # #", "#  ##", "#   #"]
    U = ["#   #", "#   #", "#   #", "#   #", " ### "]
    R = ["#### ", "#   #", "#### ", "# #  ", "#  ##"]
    O = [" ### ", "#   #", "#   #", "#   #", " ### "]

    sep = " "   # 1-char gap between letters
    gap = "    "  # 4-char gap between ACE and NEURO

    art_rows: list[str] = []
    for i in range(5):
        row = (
            A[i] + sep + C[i] + sep + E[i]
            + gap
            + N[i] + sep + E[i] + sep + U[i] + sep + R[i] + sep + O[i]
        )
        art_rows.append(row)

    return "\n".join([
        border,
        blank,
        *[_row(line) for line in art_rows],
        blank,
        _row("              T  O  O  L  S   ·   v 0 . 1 . 0"),
        blank,
        _row("    Analysis of Calcium Imaging & Electrophysiology"),
        blank,
        border,
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Interactive UI helpers
# ─────────────────────────────────────────────────────────────────────────────

def _divider(title: str = "") -> str:
    """Return a horizontal divider, optionally with a centred title."""
    if not title:
        return "\n" + "─" * _W
    label = f"  {title}  "
    right = "─" * max(0, _W - len(label) - 2)
    return f"\n──{label}{right}"


def _confirm_paths(lab_config: LabConfig) -> bool:
    """Print a path/settings summary and ask the user to confirm.

    Returns ``True`` if the user accepts, ``False`` to abort.
    """
    paths = lab_config.paths
    run = lab_config.run

    print(_divider("Project Configuration"))
    print()

    project_path = paths.project_path if paths else "(not set — will use config file directory)"
    data_path = paths.data_path if paths else "(not set — resolved from experiments.csv)"
    output_dir = paths.output_dir if paths else "(not set — defaults to <project>/stats_results)"
    calcium_dir = paths.calcium_signal_dir if paths else "(not set)"

    print(f"  Project path:        {project_path}")
    print(f"  Data path:           {data_path}")
    print(f"  Output directory:    {output_dir}")
    print(f"  Calcium signal dir:  {calcium_dir}")
    print()

    all_subjects = lab_config.all_line_nums()
    display_subjects = (run.line_nums if run and run.line_nums else None) or all_subjects
    print(f"  Subjects ({len(display_subjects)}):        {display_subjects}")
    print(f"  Channel:             {lab_config.primary_channel}")
    print(
        f"  Frequency range:     "
        f"{lab_config.freq_range[0]} – {lab_config.freq_range[1]} Hz"
    )
    if run and run.analyses:
        print(f"  Analyses:            {', '.join(run.analyses)}")
    print()

    try:
        answer = input("  Are these settings correct? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  Interrupted.")
        return False

    return answer in ("", "y", "yes")


def _select_mode(lab_config: LabConfig) -> str | None:
    """Present the mode selection menu and return the chosen mode.

    Returns ``None`` if the user interrupted or quit.
    If ``lab_config.run.mode`` is already set, that value is returned
    immediately without prompting.
    """
    if lab_config.run and lab_config.run.mode:
        return lab_config.run.mode

    print(_divider("Select Pipeline Mode"))
    print()
    print("  1.  compute  —  Generate calcium signal files from raw videos")
    print("  2.  stats    —  Run statistical analyses (requires calcium signal files)")
    print("  3.  all      —  Run compute then stats  [default]")
    print()

    try:
        answer = input("  Selection [3]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  Interrupted.")
        return None

    if answer in ("", "3", "all"):
        return "all"
    if answer in ("1", "compute"):
        return "compute"
    if answer in ("2", "stats"):
        return "stats"

    print(f"  Unrecognised selection {answer!r} — defaulting to 'all'.")
    return "all"


# ─────────────────────────────────────────────────────────────────────────────
# Argument parser
# ─────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ace-neuro",
        description="ACE-NeuroTools — single-command pipeline launcher.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline from the project directory
  cd C:\\path\\to\\project
  ace-neuro

  # Explicit config path (from any directory)
  ace-neuro --config C:\\path\\to\\lab_config.json

  # Stats only, skip path-confirmation prompt
  ace-neuro --mode stats --yes

  # Quick single-subject test
  ace-neuro --mode stats --line-nums 97 --verbose

First-time setup:
  python -m aceneurotools.init --project-path C:\\path\\to\\project
""",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        help=(
            "Path to lab_config.json.  "
            "Defaults to lab_config.json in the current working directory."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["compute", "stats", "all"],
        default=None,
        metavar="MODE",
        help=(
            "compute, stats, or all.  "
            "Overrides run.mode in lab_config.json.  "
            "Default: value from lab_config.json, or 'all' if not set."
        ),
    )
    parser.add_argument(
        "--line-nums",
        nargs="+",
        type=int,
        metavar="N",
        help="Override which subjects to process.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Disable all GUIs and use the matplotlib Agg backend.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-subject progress.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the path-confirmation prompt.",
    )
    return parser


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``ace-neuro`` command."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # ── Print banner ──────────────────────────────────────────────────────────
    print(_banner())

    # ── Locate lab_config.json ────────────────────────────────────────────────
    config_path = Path(args.config) if args.config else Path.cwd() / "lab_config.json"

    if not config_path.exists():
        print(
            f"\n  ERROR: lab_config.json not found at {config_path}\n"
            "\n"
            "  Generate template files with:\n"
            f"    python -m aceneurotools.init --project-path {Path.cwd()}\n"
            "\n"
            "  Or specify the config location explicitly:\n"
            "    ace-neuro --config /path/to/lab_config.json\n"
        )
        return 1

    # ── Load lab config ───────────────────────────────────────────────────────
    from aceneurotools.multimodal.lab_config import LabConfig
    from aceneurotools.shared.exceptions import ConfigurationError

    try:
        lab_config = LabConfig.from_json(config_path)
    except ConfigurationError as exc:
        print(f"\n  ERROR loading lab_config.json:\n\n  {exc}\n")
        return 1

    # ── Auto-load stats_config.json if present ────────────────────────────────
    from aceneurotools.multimodal.stats_config import StatsConfig

    stats_config: StatsConfig | None = None
    stats_config_path = config_path.parent / "stats_config.json"
    if stats_config_path.exists():
        try:
            stats_config = StatsConfig.from_json(stats_config_path)
        except Exception as exc:
            print(f"\n  WARNING: Could not load stats_config.json: {exc}")
            print("  Using built-in algorithm defaults.\n")

    # ── Resolve effective run settings (CLI overrides lab_config) ─────────────
    effective_headless: bool = args.headless or (
        lab_config.run.headless if lab_config.run else False
    )
    effective_verbose: bool = args.verbose or (
        lab_config.run.verbose if lab_config.run else False
    )
    effective_line_nums: list[int] | None = args.line_nums or (
        lab_config.run.line_nums if lab_config.run else None
    )

    if effective_headless:
        from aceneurotools.shared.plotting import set_backend
        set_backend(headless=True)

    # ── Path confirmation (skip when headless or --yes) ───────────────────────
    if not args.yes and not effective_headless:
        if not _confirm_paths(lab_config):
            print(
                "\n  Edit the 'paths' section in lab_config.json and re-run "
                "ace-neuro.\n"
            )
            return 0

    # ── Mode selection ────────────────────────────────────────────────────────
    mode: str | None = args.mode
    if mode is None:
        if effective_headless:
            # In headless mode we cannot prompt; fall back to config or 'all'.
            mode = (lab_config.run.mode if lab_config.run else None) or "all"
        else:
            mode = _select_mode(lab_config)
    if mode is None:
        return 0  # user interrupted

    print(_divider(f"Running  [{mode} mode]"))
    print()

    # ── Resolve paths ─────────────────────────────────────────────────────────
    paths = lab_config.paths
    project_path = (
        Path(paths.project_path)
        if paths and paths.project_path
        else config_path.parent
    )
    data_path = (
        Path(paths.data_path)
        if paths and paths.data_path
        else None
    )
    output_dir = (
        Path(paths.output_dir)
        if paths and paths.output_dir
        else project_path / "stats_results"
    )
    calcium_signal_dir = (
        Path(paths.calcium_signal_dir)
        if paths and paths.calcium_signal_dir
        else None
    )

    # ── compute mode ──────────────────────────────────────────────────────────
    if mode in ("compute", "all"):
        if calcium_signal_dir is None:
            print(
                "  ERROR: paths.calcium_signal_dir is not set in lab_config.json.\n"
                "  This path is required for compute mode — it is where the\n"
                "  meanFluorescence_<line_num>.npz files will be saved.\n"
                "  Add it to the 'paths' section and re-run.\n"
            )
            return 1

        from aceneurotools.pipelines.compute import ComputePipeline

        compute = ComputePipeline()
        compute.run(
            project_path=project_path,
            data_path=data_path,
            lab_config=lab_config,
            calcium_signal_dir=calcium_signal_dir,
            line_nums=effective_line_nums,
            headless=effective_headless,
            verbose=effective_verbose,
        )

    # ── stats mode ────────────────────────────────────────────────────────────
    if mode in ("stats", "all"):
        from aceneurotools.pipelines.stats import StatsPipeline

        analyses = (lab_config.run.analyses if lab_config.run else None) or None

        pipeline = StatsPipeline()
        try:
            pipeline.run(
                project_path=project_path,
                data_path=data_path,
                output_dir=output_dir,
                calcium_signal_dir=calcium_signal_dir,
                analyses=analyses,
                line_nums=effective_line_nums,
                lab_config=lab_config,
                stats_config=stats_config,
                headless=effective_headless,
                verbose=effective_verbose,
            )
        except KeyboardInterrupt:
            print("\n  Interrupted.")
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
