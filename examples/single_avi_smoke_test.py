#!/usr/bin/env python3
"""Single-AVI smoke test for the miniscope pipeline.

Goal: on a fresh machine, prove end-to-end that
  1. ``box_credentials.py`` authenticates with Box,
  2. one ``.avi`` file can be downloaded for a given experiment row,
  3. CNMF-E runs and writes ``estimates.hdf5`` to disk, and
  4. the component-selection GUI opens so you can accept/reject neurons.

Usage:
    1. Make sure you have copied ``src/aceneurotools/shared/BLANK_box_credentials.py``
       to ``src/aceneurotools/shared/box_credentials.py`` and filled in your Box
       client_id / client_secret / user_id (or dev_token).
    2. Edit the four constants under ``--- EDIT THESE ---`` below.
    3. Activate the environment (``micromamba activate aceneurotools``) and run:

           python examples/single_avi_smoke_test.py

The script is deliberately verbose: every stage prints what it is about to do
and what it found, so a failure points at one specific step rather than a
generic stack trace deep inside CaImAn.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import NoReturn

# --- EDIT THESE -------------------------------------------------------------
# Directory containing experiments.csv and analysis_parameters.csv:
PROJECT_PATH = Path("/path/to/your/project")

# Root of your raw data (Box will mirror folders under here):
DATA_PATH = Path("/path/to/your/raw_data")

# Row in experiments.csv / analysis_parameters.csv to test against. The row
# must have non-empty "Box Calcium Folder ID" and "calcium imaging directory".
LINE_NUM = 96

# Single movie filename to download and process. UCLA miniscope videos are
# typically split into 0.avi, 1.avi, ... — start with 0.avi for a smoke test.
AVI_FILENAME = "0.avi"
# ---------------------------------------------------------------------------


def _fail(stage: str, msg: str, hint: str = "") -> NoReturn:
    """Print a labelled error and exit non-zero."""
    print(f"\n[smoke-test] FAILED at: {stage}", file=sys.stderr)
    print(f"[smoke-test] reason: {msg}", file=sys.stderr)
    if hint:
        print(f"[smoke-test] hint:   {hint}", file=sys.stderr)
    sys.exit(1)


def step_0_check_paths() -> None:
    """Verify project / data layout and that box_credentials.py is filled in."""
    print("[smoke-test] Step 0/3: checking paths and credentials...")

    if not PROJECT_PATH.is_dir():
        _fail(
            "path check",
            f"PROJECT_PATH does not exist: {PROJECT_PATH}",
            "Edit PROJECT_PATH at the top of this script.",
        )
    for csv_name in ("experiments.csv", "analysis_parameters.csv"):
        csv_path = PROJECT_PATH / csv_name
        if not csv_path.is_file():
            _fail(
                "path check",
                f"Missing {csv_name} at {csv_path}",
                "PROJECT_PATH must contain both experiments.csv and analysis_parameters.csv.",
            )

    if not DATA_PATH.exists():
        DATA_PATH.mkdir(parents=True, exist_ok=True)
        print(f"[smoke-test] created DATA_PATH: {DATA_PATH}")
    elif not DATA_PATH.is_dir():
        _fail(
            "path check",
            f"DATA_PATH exists but is not a directory: {DATA_PATH}",
            "Point DATA_PATH at a writable directory that will hold raw recordings.",
        )

    try:
        from aceneurotools.shared import box_credentials  # noqa: F401
    except ModuleNotFoundError:
        _fail(
            "box_credentials import",
            "src/aceneurotools/shared/box_credentials.py was not found.",
            "Copy BLANK_box_credentials.py to box_credentials.py and fill in your Box info.",
        )
    except Exception as e:
        _fail(
            "box_credentials import",
            f"box_credentials.py imported but raised: {e!r}",
            "Open the file and confirm client_id / client_secret / user_id / dev_token are correct.",
        )

    print("[smoke-test]   project_path :", PROJECT_PATH)
    print("[smoke-test]   data_path    :", DATA_PATH)
    print("[smoke-test]   line_num     :", LINE_NUM)
    print("[smoke-test]   avi          :", AVI_FILENAME)


def step_1_download_avi() -> Path:
    """Pull the single AVI from Box (if not already on disk) and return its path."""
    print("\n[smoke-test] Step 1/3: downloading AVI from Box (skipped if already present)...")
    import pandas as pd

    from aceneurotools.shared.file_downloader import verify_file_by_line

    experiments_csv = PROJECT_PATH / "experiments.csv"
    try:
        row = pd.read_csv(experiments_csv, index_col="line number").loc[str(LINE_NUM)]
    except KeyError:
        _fail(
            "experiments.csv lookup",
            f"line_num {LINE_NUM} not found in {experiments_csv}.",
            "Use a row that exists in your experiments.csv, or add this experiment row.",
        )
    except Exception as e:
        _fail(
            "experiments.csv lookup",
            f"could not read {experiments_csv}: {e!r}",
            "Make sure experiments.csv has a 'line number' column and is well-formed CSV.",
        )

    miniscope_dir = row.get("calcium imaging directory")
    box_id = row.get("Box Calcium Folder ID")
    if pd.isnull(miniscope_dir) or pd.isnull(box_id):
        _fail(
            "experiments.csv lookup",
            f"row {LINE_NUM} is missing 'calcium imaging directory' or 'Box Calcium Folder ID'.",
            "Fill those columns for this row before re-running.",
        )

    expected_avi = DATA_PATH / miniscope_dir / "Miniscope" / AVI_FILENAME
    print(f"[smoke-test]   target file  : {expected_avi}")

    try:
        ok = verify_file_by_line(
            line_num=LINE_NUM,
            csv_path=experiments_csv,
            do_type="miniscope",
            avi_list=[AVI_FILENAME],
            base_file_path=str(DATA_PATH),
        )
    except Exception as e:
        traceback.print_exc()
        _fail(
            "Box download",
            f"verify_file_by_line raised: {e!r}",
            "Most often this is a Box auth error — re-check box_credentials.py and that your "
            "enterprise has approved the custom app (CCG grant).",
        )

    if not expected_avi.is_file():
        _fail(
            "Box download",
            f"{AVI_FILENAME} did not land at {expected_avi} (verify_file_by_line returned {ok!r}).",
            "Confirm the Box folder ID actually contains this AVI, and that your Box token "
            "has read access. If you are using a dev_token, remember they expire after 1 hour.",
        )

    print(f"[smoke-test]   downloaded   : {expected_avi.stat().st_size / 1e6:.1f} MB")
    return expected_avi


def step_2_run_pipeline() -> None:
    """Run the miniscope pipeline: CNMF-E -> estimates.hdf5 -> component GUI."""
    print("\n[smoke-test] Step 2/3: running MiniscopePipeline (CNMF-E + GUI)...")

    try:
        from aceneurotools.pipelines.miniscope import MiniscopePipeline
    except Exception as e:
        traceback.print_exc()
        _fail(
            "pipeline import",
            f"could not import MiniscopePipeline: {e!r}",
            "This is usually a CaImAn / Tk / FreeSimpleGUI install problem. "
            "Re-create the environment from environment.yml.",
        )

    api = MiniscopePipeline()
    try:
        api.run(
            line_num=LINE_NUM,
            project_path=PROJECT_PATH,
            data_path=DATA_PATH,
            filenames=[AVI_FILENAME],
            # Preprocessing: trust crop_coords from analysis_parameters.csv if
            # present; otherwise the GUI will pop up so she can draw a box.
            crop=True,
            detrend_method="median",
            df_over_f=False,
            # Processing: this is the bit that actually writes estimates.hdf5.
            parallel=False,
            apply_motion_correction=False,
            inspect_motion_correction=False,
            plot_params=False,
            run_CNMFE=True,
            save_estimates=True,
            save_CNMFE_estimates_filename="estimates.hdf5",
            save_CNMFE_params=False,
            # Postprocessing: open the GUI so she can click neurons to reject.
            # The downstream phase / filter / spectrogram steps add failure
            # modes that don't matter for a one-AVI smoke test, so disable them.
            remove_components_with_gui=True,
            find_calcium_events=False,
            compute_miniscope_phase=False,
            filter_miniscope_data=False,
            compute_miniscope_spectrogram=False,
            headless=False,
        )
    except Exception as e:
        traceback.print_exc()
        _fail(
            "pipeline run",
            f"MiniscopePipeline.run raised: {e!r}",
            "Check the traceback above; common culprits are missing crop_coords / gSig / "
            "min_corr / min_pnr in analysis_parameters.csv, or FreeSimpleGUI being unavailable.",
        )


def step_3_report_estimates() -> None:
    """Locate the estimates.hdf5 that the pipeline should have just written."""
    print("\n[smoke-test] Step 3/3: locating estimates.hdf5...")
    import pandas as pd

    experiments_csv = PROJECT_PATH / "experiments.csv"
    miniscope_dir = pd.read_csv(experiments_csv, index_col="line number").loc[
        str(LINE_NUM), "calcium imaging directory"
    ]
    base = DATA_PATH / miniscope_dir / "saved_movies"

    hits = list(base.rglob("estimates.hdf5")) if base.exists() else []
    if not hits:
        print(
            f"[smoke-test]   no estimates.hdf5 under {base} — CNMF-E may not have run, "
            "or it was saved elsewhere. Search your data tree to confirm.",
            file=sys.stderr,
        )
        return

    for h in hits:
        print(f"[smoke-test]   wrote: {h}  ({h.stat().st_size / 1e6:.1f} MB)")


def main() -> None:
    print("[smoke-test] starting single-AVI miniscope smoke test")
    step_0_check_paths()
    step_1_download_avi()
    step_2_run_pipeline()
    step_3_report_estimates()
    print("\n[smoke-test] done.")


if __name__ == "__main__":
    main()
