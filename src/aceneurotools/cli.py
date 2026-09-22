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
    from aceneurotools.config.lab_config import LabConfig

# ─────────────────────────────────────────────────────────────────────────────
# Terminal layout constants
# ─────────────────────────────────────────────────────────────────────────────

_W = 80  # banner / divider width


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

    Stats is a modular opt-in component: the default selection (option 1)
    runs only the compute pipeline, and a follow-up prompt after compute
    finishes asks whether to run statistical analyses.
    """
    if lab_config.run and lab_config.run.mode:
        return lab_config.run.mode

    print(_divider("Select Pipeline Mode"))
    print()
    print("  1.  compute          —  Generate calcium signal files from raw videos  [default]")
    print("  2.  compute + stats  —  Then run statistical analyses on those files")
    print("  3.  stats only       —  Run stats on existing calcium signal files")
    print()
    print("  (You can also skip this menu by setting run.mode in lab_config.json.)")
    print()

    try:
        answer = input("  Selection [1]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  Interrupted.")
        return None

    if answer in ("", "1", "compute"):
        return "compute"
    if answer in ("2", "all", "compute + stats", "compute+stats"):
        return "all"
    if answer in ("3", "stats", "stats only"):
        return "stats"

    print(f"  Unrecognised selection {answer!r} — defaulting to 'compute'.")
    return "compute"


# ─────────────────────────────────────────────────────────────────────────────
# First-time setup wizard + data-path tutorial
# ─────────────────────────────────────────────────────────────────────────────

def _tutorial(project_path: Path) -> None:
    """Walk the user through every data path they need to fill in.

    Covers the four ``paths`` keys in lab_config.json plus the per-subject
    ``ephys directory`` and ``calcium imaging directory`` columns in
    experiments.csv. Each section gives: what it is, why it's needed, an
    example value, and the common pitfalls.
    """
    from rich.console import Console
    from rich.text import Text

    console = Console()

    def _section(label: str) -> None:
        console.print()
        console.print(Text(label, style="bold cyan"))

    def _field(name: str, lines: list[str]) -> None:
        title = Text()
        title.append("  ", style="default")
        title.append(name, style="bold green")
        console.print(title)
        for line in lines:
            console.print(f"      {line}")

    _section("Guided tutorial: data paths")
    console.print(
        "  ACE-NeuroTools needs to know where your data lives.  There are "
        "four directories"
    )
    console.print(
        "  in lab_config.json (project-wide) and two columns in "
        "experiments.csv (per-subject)."
    )

    # ── lab_config.json paths ────────────────────────────────────────────────
    _section("lab_config.json  →  paths")

    _field("project_path", [
        "What:   The directory that contains lab_config.json and experiments.csv.",
        "Why:    All other lab_config paths are resolved relative to this if",
        "        left as null.  It is also the default output location.",
        f"Example: {project_path}",
        "Gotcha: Use forward slashes on Windows (C:/Users/...) — JSON treats",
        "        backslashes as escape characters.",
    ])

    _field("data_path", [
        "What:   Base directory containing the raw experimental data — both",
        "        the Neuralynx .ncs files and the Miniscope recordings.",
        "Why:    Per-subject 'ephys directory' and 'calcium imaging directory'",
        "        entries in experiments.csv are resolved relative to this.",
        "        Set to null to resolve them relative to project_path instead.",
        "Example: /Volumes/lab-nas/raw_recordings",
        "Gotcha: Must be readable from wherever you run ace-neuro.  On an HPC",
        "        cluster, that means the shared filesystem path, not your laptop.",
    ])

    _field("output_dir", [
        "What:   Where statistical results (CSVs, figures, run_log.json) go.",
        "Why:    Each pipeline run writes one subdirectory per analysis here.",
        "Example: /path/to/project/stats_results",
        "Gotcha: Created automatically if it does not exist.  Set to null to",
        "        default to <project_path>/stats_results.",
    ])

    _field("calcium_signal_dir", [
        "What:   Where meanFluorescence_<line_num>.npz files are stored.",
        "Why:    Mode 'compute' WRITES these files; mode 'stats' READS them.",
        "        If you only ever run mode 'all', this is the bridge between",
        "        the two halves of the pipeline.",
        "Example: /path/to/project/calcium_signals",
        "Gotcha: Set to null to default to <project_path>/calcium_signals.",
        "        Stats mode will error if the .npz file for a subject is missing.",
    ])

    # ── experiments.csv per-subject paths ────────────────────────────────────
    _section("experiments.csv  →  per-subject paths")

    _field("ephys directory", [
        "What:   Path to the Neuralynx folder for ONE subject.  Contains the",
        "        per-channel .ncs files (e.g. CBvsPCEEG.ncs) and the Events.nev.",
        "Why:    Drives every ephys load: filtering, TTL-event sync, coherence.",
        "Example: ExampleRat/2024-01-01_12-00-00",
        "Gotcha: Relative path — resolved against data_path (or project_path",
        "        if data_path is null).  Match the exact case of the folder name.",
    ])

    _field("calcium imaging directory", [
        "What:   Path to the Miniscope recording folder for ONE subject.",
        "        Contains the .avi movies and timeStamps.csv (UCLA V3) or .raw",
        "        timestamp files (ONIX V4).",
        "Why:    Drives calcium loading, preprocessing, and TTL alignment.",
        "Example: ExampleRat/2024_01_01/12_00_00",
        "Gotcha: Same as ephys directory — relative to data_path/project_path.",
        "        For ONIX recordings, point at the directory containing the",
        "        timestamp .raw files, not the .avi files themselves.",
    ])

    # ── Pipeline structure (compute vs stats) ────────────────────────────────
    _section("Pipeline structure: compute vs stats")
    console.print(
        "  ACE-NeuroTools has two halves and they run independently:"
    )
    console.print()
    console.print("    [bold green]compute[/bold green]  →  reads raw .avi / .ncs, "
                  "writes meanFluorescence_<N>.npz")
    console.print("    [bold green]stats[/bold green]    →  reads those .npz files, "
                  "produces coherence / scatter results + figures")
    console.print()
    console.print(
        "  Stats is a [bold]modular opt-in[/bold] — running ace-neuro defaults to "
        "compute only."
    )
    console.print(
        "  When compute finishes you'll be asked whether to run stats on "
        "the results."
    )
    console.print(
        "  You can also choose 'compute + stats' in the menu, or set run.mode = 'all' "
    )
    console.print("  in lab_config.json to skip the prompt.")

    # ── Sanity check + next step ─────────────────────────────────────────────
    _section("Quick mental check")
    console.print("  Open lab_config.json and confirm:")
    console.print("    1. paths.project_path points at the folder containing this file")
    console.print("    2. paths.data_path either points at your raw-data root, or is null")
    console.print("    3. Every subject in conditions has an entry in time_windows")
    console.print("    4. Every subject is also a row in experiments.csv")
    console.print()
    console.print(Text("Tutorial complete.", style="bold green"))


def _setup_wizard() -> int:
    """Interactive first-time setup. Generates templates and prints next steps.

    Returns the shell exit code (0 = success, non-zero = abort).
    """
    from rich.console import Console
    from rich.text import Text

    from aceneurotools.init import main as init_main

    console = Console()

    def _step(num: int, title: str) -> None:
        console.print()
        console.print(Text(f"Step {num} — {title}", style="bold cyan"))

    # ── Step 1: choose project path ──────────────────────────────────────────
    _step(1, "Choose a project directory")
    cwd = Path.cwd()
    console.print(f"  Where would you like the configuration files to live?")
    console.print(f"  Press Enter to use the current directory: [dim]{cwd}[/dim]")
    try:
        answer = input("  Project path: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  Setup cancelled.")
        return 1

    project_path = Path(answer).expanduser().resolve() if answer else cwd

    # ── Step 2: handle existing files ────────────────────────────────────────
    _step(2, "Generate template files")
    existing = [
        f for f in ("lab_config.json", "stats_config.json", "experiments_template.csv")
        if (project_path / f).exists()
    ]
    force = False
    if existing:
        console.print(f"  The following file(s) already exist in {project_path}:")
        for f in existing:
            console.print(f"    [yellow]• {f}[/yellow]")
        try:
            ans = input("  Overwrite? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  Setup cancelled.")
            return 1
        if ans not in ("y", "yes"):
            console.print("  Keeping existing files. Skipping template generation.")
        else:
            force = True

    if not existing or force:
        import contextlib
        import io

        argv = ["--project-path", str(project_path)]
        if force:
            argv.append("--force")
        # init_main also prints its own next-steps guide that overlaps with
        # ours — capture its stdout and re-emit only the per-file Created lines.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = init_main(argv)
        if rc != 0:
            console.print(
                Text("  Template generation failed; aborting.", style="bold red")
            )
            console.print(buf.getvalue())
            return rc
        for line in buf.getvalue().splitlines():
            stripped = line.lstrip()
            if stripped.startswith("Created:"):
                console.print(f"  ✓ {stripped[len('Created:'):].strip()}")

    # ── Step 3: offer the in-depth path tutorial ─────────────────────────────
    _step(3, "Optional: guided tutorial")
    console.print(
        "  Would you like a guided tour of every data path you need to fill in?"
    )
    console.print("  (4 lab_config keys + 2 experiments.csv columns, with examples)")
    try:
        ans = input("  Show tutorial? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = "n"

    if ans in ("", "y", "yes"):
        _tutorial(project_path)
    else:
        console.print()
        console.print(Text("Setup complete.", style="bold green"))
        console.print("  Edit lab_config.json + experiments.csv, then run:")
        if project_path == cwd:
            console.print(Text("      ace-neuro", style="bold cyan"))
        else:
            console.print(
                Text(
                    f"      ace-neuro --config {project_path}/lab_config.json",
                    style="bold cyan",
                )
            )
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# `ace-neuro history` — experiment version control surface
# ─────────────────────────────────────────────────────────────────────────────

_HISTORY_USAGE = (
    "usage: ace-neuro history [--dir PATH | --experiment N "
    "[--project-path P] [--data-path D]]\n"
    "                         <command> [command options]\n"
    "commands: init record status log show diff restore comment comments "
    "recover push verify\n"
    "(run `ace-neuro history <command> --help` for a command's options)"
)


def _resolve_experiment_dir(
    line_num: int,
    project_path: str | None,
    data_path: str | None,
) -> Path | None:
    """Resolve an experiment's directory from its experiments.csv row.

    Provisional until Comenius decision D06 (data layout): the experiment's
    calcium-imaging directory is treated as its home. Prints an actionable
    error and returns None when the row or column is missing.
    """
    from aceneurotools.shared.experiment_data_manager import ExperimentDataManager

    manager = ExperimentDataManager(
        line_num,
        project_path=project_path or Path.cwd(),
        data_path=data_path,
        auto_import_analysis_params=False,
    )
    if manager.metadata is None:
        print(f"error: no experiments.csv row for line {line_num}", file=sys.stderr)
        return None
    directory = manager.get_miniscope_directory()
    if directory is None:
        print(
            f"error: line {line_num} has no 'calcium imaging directory' in "
            "experiments.csv; pass --dir instead",
            file=sys.stderr,
        )
        return None
    return Path(directory)


def _run_history(args: argparse.Namespace) -> int:
    """Delegate `ace-neuro history ...` verbatim to the EVC CLI.

    No logic lives in this layer (plan §Phase 5): the EVC CLI is itself a
    thin shell over ``ExperimentVersionControl`` — the same porcelain the
    GUI will call (ADR 0001).
    """
    from aceneurotools.evc.__main__ import main as evc_main

    rest = list(args.rest)
    if rest and rest[0] == "--":
        rest = rest[1:]
    if not rest:
        print(_HISTORY_USAGE, file=sys.stderr)
        return 2
    if args.experiment is not None:
        directory = _resolve_experiment_dir(
            args.experiment, args.project_path, args.data_path
        )
        if directory is None:
            return 1
    else:
        directory = Path(args.dir) if args.dir else Path.cwd()
    return evc_main(["--dir", str(directory), *rest])


# ─────────────────────────────────────────────────────────────────────────────
# Experiment version control (opt-in)
# ─────────────────────────────────────────────────────────────────────────────

def _history_recorder(
    lab_config: LabConfig,
    project_path: Path,
    pipeline: str,
    line_nums: list[int] | None,
):
    """Build a RunRecorder for one pipeline run, or None (the off switch).

    History participation is opt-in per experiment until D07/D08 are accepted
    (docs/design/evc-implementation-plan.md §Phase 3): a recorder is built only
    when ``run.history`` is enabled in lab_config.json AND the project
    directory is EVC-tracked (has ``.evc/``). With None, every pipeline is
    byte-identical to a build without EVC.
    """
    if not (lab_config.run and lab_config.run.history):
        return None
    if not (project_path / ".evc").is_dir():
        return None
    from aceneurotools.evc.hooks import RunRecorder

    return RunRecorder(
        project_path,
        pipeline=pipeline,
        line=line_nums if line_nums else lab_config.all_line_nums(),
    )


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
    parser.add_argument(
        "--setup",
        action="store_true",
        help=(
            "Run the interactive first-time setup wizard.  "
            "Generates template configuration files and walks you through "
            "the fields you need to fill in before running the pipeline."
        ),
    )

    # Subcommands (optional; plain `ace-neuro` keeps running the pipelines).
    sub = parser.add_subparsers(dest="subcommand", metavar="")
    history = sub.add_parser(
        "history",
        help=(
            "Experiment version control: record/inspect/restore experiment "
            "revisions (status, log, show, diff, restore, comment, recover, "
            "push, verify)."
        ),
        description=(
            "Thin gateway to experiment version control — every command is "
            "delegated verbatim to `python -m aceneurotools.evc` and the "
            "shared porcelain backend. Place --dir/--experiment BEFORE the "
            "history command."
        ),
    )
    history.add_argument(
        "--dir",
        default=None,
        metavar="PATH",
        help="Experiment directory to operate on (default: current directory).",
    )
    history.add_argument(
        "--experiment",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Resolve the experiment directory from experiments.csv line N "
            "(its calcium-imaging directory; provisional until D06)."
        ),
    )
    history.add_argument(
        "--project-path",
        default=None,
        metavar="PATH",
        help="Directory containing experiments.csv (with --experiment; default: cwd).",
    )
    history.add_argument(
        "--data-path",
        default=None,
        metavar="PATH",
        help="Base directory for raw data (with --experiment).",
    )
    history.add_argument(
        "rest",
        nargs=argparse.REMAINDER,
        metavar="command",
        help=(
            "History command and its options: init, record, status, log, "
            "show, diff, restore, comment, comments, recover, push, verify."
        ),
    )
    return parser


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``ace-neuro`` command."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # ── Subcommands (headless-safe: no banner, no config loading) ────────────
    if getattr(args, "subcommand", None) == "history":
        return _run_history(args)

    # ── Print banner ──────────────────────────────────────────────────────────
    from aceneurotools.shared.banner import welcome
    welcome()

    # ── Locate lab_config.json ────────────────────────────────────────────────
    config_path = Path(args.config) if args.config else Path.cwd() / "lab_config.json"

    # ── First-time setup wizard ───────────────────────────────────────────────
    # Run the wizard if the user asked for it explicitly, OR if no config was
    # found in the cwd (auto first-run experience). When --config was given
    # explicitly and points at a missing file, handle it below as an error
    # without launching the wizard or creating files somewhere unexpected.
    if args.setup or (not config_path.exists() and not args.config):
        return _setup_wizard()

    if not config_path.exists():
        # An explicit config path is a contract with scripts and schedulers.
        # Returning success here would report a run that never started as complete.
        print(
            f"ERROR: --config file does not exist: {config_path}\n"
            "Check the path, run `ace-neuro --setup`, or generate templates with:\n"
            f"  python -m aceneurotools.init --project-path {config_path.parent}",
            file=sys.stderr,
        )
        return 1

    # ── Load lab config ───────────────────────────────────────────────────────
    from aceneurotools.config.lab_config import LabConfig
    from aceneurotools.shared.exceptions import ConfigurationError

    try:
        lab_config = LabConfig.from_json(config_path)
    except ConfigurationError as exc:
        print(f"\n  ERROR loading lab_config.json:\n\n  {exc}\n")
        return 1

    # ── Auto-load stats_config.json if present ────────────────────────────────
    from aceneurotools.config.stats_config import StatsConfig

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
            # In headless mode we cannot prompt; fall back to config, or
            # default to compute-only (stats remains an explicit opt-in).
            mode = (lab_config.run.mode if lab_config.run else None) or "compute"
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
            recorder=_history_recorder(
                lab_config, project_path, "compute", effective_line_nums
            ),
        )

    # ── Optional post-compute stats opt-in ───────────────────────────────────
    # Stats is modular: when a user chose 'compute' alone (interactively or by
    # config), we ask whether they want to run statistical analyses now on the
    # freshly-produced .npz files. Promotes 'compute' to 'all' on yes; otherwise
    # the run ends here. Skip the prompt for headless / --yes / explicit modes.
    if (
        mode == "compute"
        and not effective_headless
        and not args.yes
    ):
        print()
        print(_divider("Compute complete"))
        print()
        print("  Statistical analyses (coherence / scatter correlations) are")
        print("  available as a modular next step.  They run on the calcium")
        print("  signal files just produced and require no extra raw data.")
        print()
        try:
            ans = input("  Run statistical analyses now? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n  Skipping stats.")
            return 0
        if ans in ("y", "yes"):
            mode = "all"  # fall through into the stats block below
        else:
            print("\n  Done.  Re-run with --mode stats or --mode all to run stats later.")
            return 0

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
                recorder=_history_recorder(
                    lab_config, project_path, "stats", effective_line_nums
                ),
            )
        except KeyboardInterrupt:
            print("\n  Interrupted.")
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
