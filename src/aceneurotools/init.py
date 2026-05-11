"""
ACE-NeuroTools project initialiser.

Generates annotated template configuration files so a new lab can get started
without writing JSON from scratch.

Usage::

    python -m aceneurotools.init --project-path /path/to/your/project

Three files are created in ``--project-path``:

* ``lab_config.json`` — fill in your channel names, conditions, and per-subject
  time windows.  Your lab's actual study design goes here.
* ``stats_config.json`` — algorithm parameters (filter cutoffs, bootstrap
  iterations, plot settings).  The defaults reproduce the original analysis;
  most labs will leave this file unchanged.
* ``experiments_template.csv`` — the exact column headers that
  ``experiments.csv`` must contain.  Use this as the starting point for your
  subject spreadsheet.

The generated ``lab_config.json`` is pre-filled with the bundled example study
(4 drug conditions, 24 subjects) so every field has a concrete working value.
Replace the example values with your own study data before running analyses.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# ------------------------------------------------------------------ #
# Template content definitions                                         #
# ------------------------------------------------------------------ #

def _lab_config_template() -> dict:
    """Return the annotated lab_config template as a Python dict."""
    return {
        "_description": (
            "ACE-NeuroTools lab configuration.  "
            "Replace ALL example values below with your study-specific data.  "
            "Fields beginning with '_' are documentation only and are ignored "
            "by the analysis pipeline."
        ),
        "_notes": {
            "primary_channel": (
                "The ephys channel name exactly as stored in your Neuralynx "
                "recording files (the .ncs filename without the extension).  "
                "Example: if your channel file is 'CBvsPCEEG.ncs', enter "
                "'CBvsPCEEG'.  This is used for EEG-calcium analyses and as "
                "the TTL-sync driver for EEG-EEG analyses."
            ),
            "secondary_channel": (
                "Optional.  Only required for the coherence_ephys_ephys "
                "analysis (two-channel EEG coherence).  Set to null (JSON) or "
                "remove this field if you are not running that analysis."
            ),
            "freq_range": (
                "Bandpass filter range [lowcut_Hz, highcut_Hz].  "
                "The example [0.5, 4.0] targets the delta band.  "
                "Change to match the frequency band relevant to your study."
            ),
            "conditions": (
                "Your experimental conditions.  Keys are free-form labels — "
                "use any string that describes the condition "
                "('propofol', 'saline control', '5 mg/kg ketamine', etc.).  "
                "Each condition requires:\n"
                "  subjects  — list of line numbers from experiments.csv\n"
                "  is_drug   — true if the condition involves drug/treatment "
                "administration; false for baseline or control conditions "
                "(controls whether drug-infusion events are expected in the "
                "recording)."
            ),
            "time_windows": (
                "Per-subject control and treatment analysis windows in "
                "MINUTES.  Keys are subject line numbers written as strings "
                "(JSON requirement).  Format:\n"
                "  \"<line_num>\": [[ctrl_start, ctrl_end], "
                "[treat_start, treat_end]]\n"
                "Every subject listed in 'conditions' must have an entry here."
            ),
            "paths": (
                "File system paths for this project.  Edit ALL values to "
                "match your machine before running ace-neuro.\n"
                "  project_path       — directory containing experiments.csv "
                "(usually the same folder as this file)\n"
                "  data_path          — base directory for raw experimental "
                "data; on Windows use forward slashes or null to resolve "
                "paths relative to project_path\n"
                "  output_dir         — where results CSVs and figures are "
                "saved; created automatically if absent\n"
                "  calcium_signal_dir — where meanFluorescence_<N>.npz files "
                "are written by compute mode and read by stats mode"
            ),
            "run": (
                "Pipeline execution settings.\n"
                "  mode       — 'compute' generates calcium signal files from "
                "raw videos; 'stats' runs statistical analyses; 'all' runs "
                "both in sequence (default)\n"
                "  analyses   — list of analysis keys; null shows an "
                "interactive menu.  Valid keys: coherence_ephys_calcium, "
                "coherence_ephys_ephys, scatter_correlation\n"
                "  line_nums  — subjects to process; null uses all subjects "
                "listed in 'conditions'\n"
                "  headless   — true disables all GUIs (required for "
                "automated/HPC runs)\n"
                "  verbose    — true prints per-subject progress messages"
            ),
        },
        "primary_channel": "CBvsPCEEG",
        "secondary_channel": "PFCEEGvsCBEEG",
        "freq_range": [0.5, 4.0],
        "conditions": {
            "dexmedetomidine: 0.00045": {
                "subjects": [46, 47, 64, 88, 97, 101],
                "is_drug": True,
            },
            "dexmedetomidine: 0.0003": {
                "subjects": [40, 41, 48, 87, 93, 94],
                "is_drug": True,
            },
            "propofol": {
                "subjects": [36, 43, 44, 86, 99, 103],
                "is_drug": True,
            },
            "ketamine": {
                "subjects": [39, 42, 45, 85, 96, 112],
                "is_drug": True,
            },
        },
        "time_windows": {
            # dexmedetomidine 0.00045
            "46":  [[1,    20],    [28.24, 75]],
            "47":  [[1,    20],    [28.24, 75]],
            "64":  [[4,    17],    [28.24, 75]],
            "88":  [[1,     8],    [28.24, 83.24]],
            "97":  [[1,    13],    [28.24, 83.24]],
            "101": [[1,    25],    [37,    90]],
            # dexmedetomidine 0.0003
            "40":  [[8,    20],    [55,    75]],
            "41":  [[10,   19],    [60,    68]],
            "48":  [[1,    20],    [25,    35]],
            "87":  [[5,    13],    [73,    85]],
            "93":  [[18,   28],    [75,    95]],
            "94":  [[1,    20],    [75,    90]],
            # propofol
            "36":  [[1,    11],    [55,    67]],
            "43":  [[15,   20],    [40,    60]],
            "44":  [[0,    21],    [40,    65]],
            "86":  [[5,    16],    [33,    65]],
            "99":  [[0,    19],    [33,    45]],
            "103": [[1,    17],    [38,    65]],
            # ketamine
            "39":  [[10,   20],    [38,    50]],
            "42":  [[1,    20],    [40,    51]],
            "45":  [[1,    15],    [40,    60]],
            "85":  [[14,   24],    [30,    50]],
            "96":  [[1,    12],    [38,    55]],
            "112": [[1,    10],    [40,    60]],
        },
        "paths": {
            "project_path": "/path/to/your/project",
            "data_path": None,
            "output_dir": None,
            "calcium_signal_dir": None,
        },
        "run": {
            "mode": "all",
            "analyses": ["coherence_ephys_calcium"],
            "line_nums": None,
            "headless": False,
            "verbose": True,
        },
    }


def _stats_config_template() -> dict:
    """Return the annotated stats_config template as a Python dict."""
    return {
        "_description": (
            "ACE-NeuroTools algorithm parameters.  "
            "The defaults reproduce the settings used in the original "
            "analysis scripts.  Most labs will not need to change this file.  "
            "Fields beginning with '_' are documentation only."
        ),
        "_notes": {
            "lowcut / highcut": (
                "Butterworth bandpass cutoffs in Hz.  Overridden at runtime "
                "by freq_range in lab_config.json or --freq-range on the CLI."
            ),
            "filter_order": "Butterworth filter order.  2 gives smooth phase response.",
            "edge_trim_seconds": (
                "Seconds trimmed from each end of a filtered segment to "
                "remove Butterworth transients.  Only applied by the scatter "
                "correlation analysis; coherence analysis ignores this."
            ),
            "normalization_method": (
                "'zscore' or 'none'.  The original coherence script uses "
                "'none'; scatter correlation uses 'zscore'."
            ),
            "coherence_nperseg_seconds": (
                "Welch segment length in seconds.  null uses scipy's default "
                "(256 samples), matching the legacy analysis scripts."
            ),
            "spectrogram_verbose": (
                "The original compute_power() passes verbose=True to "
                "multitaper_spectrogram.  This implementation passes "
                "verbose=False to suppress output.  This does not affect "
                "computed values."
            ),
        },
        "lowcut": 0.5,
        "highcut": 4.0,
        "filter_order": 2,
        "edge_trim_seconds": 5.0,
        "normalization_method": "none",
        "global_normalization": True,
        "correct_autocorrelation": True,
        "confidence_level": 0.95,
        "max_acf_lags": 100,
        "bootstrap_iterations": 10000,
        "paired_test": "wilcoxon",
        "min_subjects_for_stats": 3,
        "coherence_nperseg_seconds": None,
        "coherogram_window_length": 5.0,
        "coherogram_window_step": 2.5,
        "coherogram_nrolling": 8,
        "spectrogram_window_length": 60.0,
        "spectrogram_window_step": 3.0,
        "spectrogram_time_bandwidth": 2.0,
        "spectrogram_freq_lims": [0.0, 20.0],
        "plot_formats": ["svg"],
        "color_dpi": 300,
        "headless": True,
    }


# Required columns for the stats pipeline (in display order).
# Format: (column_name, example_value_row1, example_value_row2, note)
_CSV_COLUMNS: list[tuple[str, str, str, str]] = [
    (
        "line number",
        "1",
        "2",
        "REQUIRED — unique integer identifier for each experiment row.  "
        "Must match the line numbers used in lab_config.json time_windows.",
    ),
    (
        "id",
        "rat_001",
        "rat_002",
        "Animal/subject identifier string.",
    ),
    (
        "date (YYMMDD)",
        "230415",
        "230416",
        "Recording date in YYMMDD format (e.g. 230415 = 15 April 2023).",
    ),
    (
        "rat weight (kg)",
        "0.35",
        "0.38",
        "Subject weight in kilograms at time of recording.",
    ),
    (
        "ephys directory",
        "/data/raw/experiment_001/ephys",
        "/data/raw/experiment_002/ephys",
        "REQUIRED — absolute path to the folder containing Neuralynx .ncs files.",
    ),
    (
        "calcium imaging directory",
        "/data/raw/experiment_001/miniscope",
        "/data/raw/experiment_002/miniscope",
        "REQUIRED — absolute path to the folder containing miniscope data.",
    ),
    (
        "LFP and EEG CSCs",
        "CBvsPCEEG;PFCEEGvsCBEEG",
        "CBvsPCEEG;PFCEEGvsCBEEG",
        "REQUIRED — semicolon-separated list of available channel names "
        "(the .ncs filenames without extension).",
    ),
    (
        "method_deconvolution",
        "oasis",
        "oasis",
        "CNMF-E deconvolution method.  Usually 'oasis'.",
    ),
    (
        "method_init",
        "greedy_roi",
        "greedy_roi",
        "CNMF-E initialisation method.  Usually 'greedy_roi'.",
    ),
    (
        "border_nan",
        "copy",
        "copy",
        "CNMF-E border handling.  Usually 'copy'.",
    ),
]


# ------------------------------------------------------------------ #
# File writers                                                         #
# ------------------------------------------------------------------ #

def _write_lab_config(path: Path) -> None:
    """Write the annotated lab_config.json template to *path*."""
    data = _lab_config_template()
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)


def _write_stats_config(path: Path) -> None:
    """Write the annotated stats_config.json template to *path*."""
    data = _stats_config_template()
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)


def _write_experiments_template(path: Path) -> None:
    """Write the experiments_template.csv with required headers and two example rows."""
    headers = [col[0] for col in _CSV_COLUMNS]
    row1 = [col[1] for col in _CSV_COLUMNS]
    row2 = [col[2] for col in _CSV_COLUMNS]

    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        writer.writerow(row1)
        writer.writerow(row2)


def _column_notes_text() -> str:
    """Return a human-readable description of each CSV column."""
    lines = ["Column reference for experiments_template.csv", "=" * 50]
    for name, _ex1, _ex2, note in _CSV_COLUMNS:
        lines.append(f"\n{name}")
        lines.append(f"  {note}")
    return "\n".join(lines)


# ------------------------------------------------------------------ #
# Main entry point                                                     #
# ------------------------------------------------------------------ #

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m aceneurotools.init",
        description=(
            "Generate ACE-NeuroTools configuration templates for a new project.  "
            "Creates lab_config.json, stats_config.json, and "
            "experiments_template.csv in the specified directory."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
After running this command:
  1. Open lab_config.json and fill in the 'paths' section for your machine.
  2. Replace the example conditions, subjects, and time_windows with your
     study design.
  3. Ensure your experiments.csv uses the column headers shown in
     experiments_template.csv (or rename your existing columns to match).
  4. Run the full pipeline with a single command:
       ace-neuro --config <dir>/lab_config.json
     Or run individual steps:
       ace-neuro --config <dir>/lab_config.json --mode compute
       ace-neuro --config <dir>/lab_config.json --mode stats
""",
    )
    parser.add_argument(
        "--project-path",
        required=True,
        metavar="PATH",
        help="Directory where the template files will be written.  "
             "Created if it does not exist.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files without prompting.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m aceneurotools.init``."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    project_path = Path(args.project_path).resolve()
    project_path.mkdir(parents=True, exist_ok=True)

    targets = {
        "lab_config.json": (project_path / "lab_config.json", _write_lab_config),
        "stats_config.json": (project_path / "stats_config.json", _write_stats_config),
        "experiments_template.csv": (
            project_path / "experiments_template.csv",
            _write_experiments_template,
        ),
    }

    # Check for existing files before writing any of them.
    existing = [name for name, (path, _) in targets.items() if path.exists()]
    if existing and not args.force:
        print(
            f"The following file(s) already exist in {project_path}:\n"
            + "".join(f"  {name}\n" for name in existing)
            + "Use --force to overwrite them."
        )
        return 1

    # Write all three files.
    for name, (path, writer) in targets.items():
        writer(path)
        print(f"  Created: {path}")

    # Print the next-steps guide.
    print(
        f"\nACE-NeuroTools project initialised at: {project_path}\n"
        "\nNext steps:\n"
        "  1. Open lab_config.json and replace the example values:\n"
        "       • primary_channel  — your ephys channel name (.ncs filename)\n"
        "       • conditions       — your experimental conditions and subject lists\n"
        "       • time_windows     — per-subject control/treatment windows (minutes)\n"
        "\n"
        "  2. Build your experiments.csv using experiments_template.csv as a guide.\n"
        "     The column names must match exactly.  Required columns:\n"
        "       • 'line number'                  (subject identifier)\n"
        "       • 'ephys directory'              (path to .ncs files)\n"
        "       • 'calcium imaging directory'    (path to miniscope data)\n"
        "       • 'LFP and EEG CSCs'             (semicolon-separated channel names)\n"
        "\n"
        "  3. Run the analysis pipeline:\n"
        f"       python -m aceneurotools.pipelines.stats \\\n"
        f"           --project-path {project_path} \\\n"
        f"           --lab-config {project_path / 'lab_config.json'} \\\n"
        "           --analyses coherence_ephys_calcium scatter_correlation\n"
        "\n"
        "  4. Check <output-dir>/run_log.json after each run to see which\n"
        "     subjects completed successfully and why any were skipped.\n"
    )

    # Print column notes as an additional reference.
    print(_column_notes_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
