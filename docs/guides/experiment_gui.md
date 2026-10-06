# Experiment GUI

The local experiment application opens projects defined by `experiments.csv` and
`analysis_parameters.csv`. Use it to edit settings, crop movies, run supported
analyses, review extracted neurons, and inspect exported results.

## Launch and open a project

From the repository root, use the environment you already use for ACE-NeuroTools:

```bash
./launch-gui --project /path/to/project
```

The launcher finds an existing CaImAn environment and opens
`http://127.0.0.1:8780/`. On a configured Linux desktop, **ACE Experiments** in the
application menu opens the same application. `./launch-gui --check` checks the
environment; `--no-browser` starts the server without opening a browser. The
launcher keeps the server running when the browser closes.
If the server is already running, the launcher reuses it; use **Open project**
inside the application to switch to a different project's CSVs.

For a terminal-managed server that stops with Ctrl+C, activate your analysis
environment and run:

```bash
python scripts/run_gui.py --project /path/to/project
```

This command uses `http://127.0.0.1:8765/` by default. Omit `--project` to choose a
project in the application. Open either its folder or its `experiments.csv` file.

## Prepare an experiment

1. Select an experiment row and check the subject, date, and recording locations
   in **Overview**.
2. Open **Data & settings** to edit experiment details and analysis settings.
   Section saves write the selected experiment row. A missing settings row can
   be created with **Add settings for this experiment**.
3. Ensure the selected recording exists locally. For Box recordings, connect
   through **Box settings**, then use **Choose recording files**. Review files,
   destination, and download size before **Confirm & download**. Selecting a
   subset restricts subsequent previews and runs to those confirmed files.
4. For calcium recordings, open **Crop → Load recording preview**. Draw a crop
   or enter pixel bounds, then **Save crop**. The preview samples the recording;
   it does not rewrite raw movies. Set **Apply crop = No** in Run settings to
   process the full frame.

CSV saves preserve other rows and unknown fields and back up the previous file
under `<project>/.ace-gui-backups`. Save pending edits before reviewing a run.
The toolbar **Save** applies edits across the changed experiment sections.
Use **Reload project** after editing CSVs outside the application.

## Review and run analysis

The Analysis menu supports these workflows:

| Analysis | Main result |
| --- | --- |
| Mean fluorescence | Mean-fluorescence NPZ |
| Crop & preprocess movie | Processed movie and projection/timing arrays |
| Calcium imaging / CNMF-E | Estimates, component signals and footprints, events, projections, and available diagnostics |
| Electrophysiology | Signal, timing, filtered signal, phases, and events when available |

For extraction, choose **Set up CNMF-E** in Overview, or select calcium imaging
in Analysis. In **Run settings**, enable **Extract neurons with CNMF-E** and
**Save CNMF-E estimates**. Scientific detection and motion parameters remain in
**Data & settings**. Save changes, then choose **Review & run**.

Review the input files, copy size, output paths, and every effective parameter.
The **From** column distinguishes saved CSV values from inherited defaults and
GUI overrides. Check **I have reviewed this experiment and its parameters**,
then choose **Start analysis**. Missing inputs, invalid crops, unsaved changes,
and stale reviews block execution.

Each run freezes the CSVs and parameters and copies inputs into a unique folder
under `<project>/.ace-runs/<run-id>/`. Outputs from subsequent runs remain
separate. The copy needs disk space in addition to processing outputs. One heavy
GUI analysis runs at a time; progress and logs appear in **Results**.

**Stop this run** terminates its worker and retains inputs, logs, and partial
outputs. Keep the GUI server running during analysis. Saved runs remain visible
after restarting; an old worker the restarted server cannot control is marked
**Untracked** until an outcome is available.

## Review neurons and recompute calcium events

The extraction run performs its configured postprocessing before embedded neuron
review. There is no automatic review checkpoint that pauses and resumes that run.
Use the curated event export to obtain events from the neurons you keep:

1. After successful extraction, choose **Results → Review extracted neurons**.
   Alternatively, open **Neurons**, choose a CaImAn estimates HDF5, and select
   **Load estimates**.
2. Inspect each footprint and raw `C` trace. Choose **Keep & next** or
   **Reject & next**; K/R and the arrow keys also navigate. **Next undecided**
   finds remaining decisions. **Undo last decision** applies in the current
   browser session.
3. Choose **Finish review**. Resolve every undecided neuron, inspect the counts,
   and choose the output folder and curated estimates filename.
4. Leave **Detect calcium events from curated estimates** checked, review the
   derivative and event-height threshold, and choose **Save curated copies &
   detect events**. Unchecking detection saves only the curated copies.

Decisions save automatically under
`<project>/.ace-neuron-reviews/<source-key>/review.json`. Reopen the same unchanged
estimates to resume. Changing the frame rate changes the time axis and export
metadata; it does not resample traces.

Each export creates a new child folder under the selected destination, which
defaults to `<project>/.ace-curations`. It contains `decisions.json`, curated
HDF5 estimates, and `C_curated.npz` with `C`, `neuron_ids`, `fr`, and footprints.
Footprints use `A_dense` unless that would exceed 128 MB; larger footprints use
the sparse CSC keys `A_data`, `A_indices`, `A_indptr`, and `A_shape`. If all
neurons are rejected, only the decision record is exported.

Detection reloads the saved curated HDF5 and computes events for kept neurons.
`calcium-events.json` records the detector settings, frame rate, trace length,
source and curated-file signatures, review revision, and original component IDs.
Its `ca_events_idx` dictionary uses zero-based curated row keys; `neuron_ids`
maps those rows back to zero-based IDs in the reviewed source file. UI neuron
numbers start at 1.

Event indices preserve the existing detector's coordinates: `zeroth` uses `C`,
`first` uses `np.diff(C, n=1)`, and `second` uses `np.diff(C, n=2)`. No frame
offset is added for derivatives. Check this convention before timestamp alignment.

The derivative and threshold initially come from the experiment's current run
settings, which can differ from the original extraction settings. Re-exporting
allows another threshold without rerunning extraction. An export or detection
failure retains the original estimates and saved decisions and installs no
partial curation folder.

Saving curated estimates alone does not update computed results. Curated event
export creates a new event file; earlier run products remain tied to their
original estimates. Ephys, movie projections, phases, spectra, and multimodal
products are not recomputed by this action. The GUI has no full multimodal
continuation from curated estimates; see the [multimodal guide](multimodal.md).

## Output inventory

In **Results**, select a run and expand **Output inventory**. Each entry names
its exported file and NPZ key, or explains why the result was not computed or is
unavailable. Older runs may have files without an inventory. An inventory is
written when a new run completes successfully; a failed run can contain partial
files without one.

| Miniscope file | Contents |
| --- | --- |
| `output-inventory.json` | Output names, status, files/keys, array shapes and types, and effective parameters |
| `calcium-events.json` | Event dictionary, component IDs, frame rate, detector parameters, and index convention |
| `postprocessing.npz` | Available component traces `C`, `S`, `F_dff`, `YrA`, `b`, `f`; IDs; final, unfiltered, and filtered temporal projections; spatial projections; timing; spectra and phases |
| `components.npz` | Sparse spatial footprints in CSC form |
| `diagnostics.npz` | Available component quality metrics, automatic accepted/rejected indices, and fitted component parameters |
| `diagnostics.json` | Settings, neuron count, filtering behavior, phase/spectral input semantics, and unavailable outputs |

Estimates and CaImAn settings normally reside in
`recording/saved_movies/estimates.hdf5` and `opts_caiman.json` when their save
options are enabled. The reviewed estimates filename is respected. The run
folder also retains `run.log`, CSV snapshots, and `effective-parameters.json`.
**Open output folder** opens the originals; file links download browser copies.

NPZ exports contain numeric arrays and can be loaded without pickle:

```python
import json
from pathlib import Path
import numpy as np
from scipy.sparse import csc_matrix

run = Path("/path/to/project/.ace-runs/your-run-id")
with np.load(run / "postprocessing.npz", allow_pickle=False) as signals:
    traces = signals["C"]
    neuron_ids = signals["neuron_ids"]
events = json.loads((run / "calcium-events.json").read_text())
with np.load(run / "components.npz", allow_pickle=False) as spatial:
    footprints = csc_matrix(
        (spatial["A_data"], spatial["A_indices"], spatial["A_indptr"]),
        shape=tuple(spatial["A_shape"]),
    )
```

Check the inventory before loading optional files/keys. Interactive
correlation/PNR plots are not computed by GUI runs, and the core pipeline does
not retain motion-correction shifts. Missing diagnostics are reported instead
of filled with substitute values. Ephys runs export `ephys.npz` and
`ephys-events.json`; preprocessing runs export `preprocessing.npz` and their
processed movie. This explicit inventory is a GUI export contract; direct
pipeline API/CLI runs do not automatically write it.

## Filtering and headless behavior

GUI workers run with `headless=True` to suppress separate analysis windows.
Headless mode respects `inline`:

| Setting | Final temporal projection |
| --- | --- |
| Filtering enabled, `inline=True` | Filtered signal |
| Filtering enabled, `inline=False` | Unfiltered signal; filtered data is retained separately |
| Filtering disabled | Unfiltered signal |

The GUI inherits the miniscope CLI default `inline=True`; direct Python API
calls default to `False`. Set it explicitly when comparing runs. Earlier
headless behavior forced `False`; choosing `False` explicitly retains that
behavior.

The core postprocessor detects calcium events from component traces `C` and
computes movie-projection phases and spectra before filtering. Consequently,
those phase/spectral results describe the unfiltered projection even when the
final projection is filtered. Exports preserve both signal versions and
`diagnostics.json` records whether replacement occurred.
