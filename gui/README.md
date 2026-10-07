# Experiment application

A local GUI for browsing projects, editing experiment CSVs, setting up Box,
cropping recordings, reviewing neurons, and running existing analyses. It uses
`CSVWorker`, `update_csv_cell`, and `append_row_csv` from the existing tool. All GUI
orchestration lives outside `src` and calls the existing scientific methods.
Headless runs respect `inline`, and curated exports can recompute events from
saved estimates.
There are no sample-data workspaces or frontend build dependencies.

For a task-oriented walkthrough, see the [Experiment GUI user guide](../docs/guides/experiment_gui.md).
This README also documents storage, Box downloads, validation, and desktop integration.

## Launch

On this computer, search for **ACE Experiments** in the application menu. The
shortcut opens the GUI using the existing CaImAn environment, without activating
Conda or opening Python files. From this checkout, the equivalent command is:

```bash
./launch-gui
```

The launcher opens `http://127.0.0.1:8780/`, with the repository's `data` project
when present. Opening it again reuses the running application. Use
`./launch-gui --project /path/to/project` for another initial project,
`--no-browser` to leave browser opening to you, or `--check` to verify the environment.
It checks `ACE_GUI_PYTHON`, existing `caiman` Conda environments, and the current
Python interpreter; it never installs packages. On another Linux computer, install
the application-menu shortcut with `python3 scripts/install_gui_shortcut.py`.
Reinstall the shortcut if you move this checkout. Startup errors appear in the
terminal or a desktop notification when available; logs are in
`~/.cache/aceneurotools/gui.log` (or `$XDG_CACHE_HOME/aceneurotools/gui.log`).
The launcher leaves the local server running after the browser closes. For a server
that stops with Ctrl+C, use the original command below.

Activate the Python environment you already use for ACE-NeuroTools. From the
repository root:

```bash
python scripts/run_gui.py --project /path/to/project
```

The browser opens at `http://127.0.0.1:8765/`. Omit `--project` to choose a project
in the application. A full path to `experiments.csv` also works. `--no-browser`
leaves browser opening to you; `--port 8780` uses another port. Stop with Ctrl+C.
The GUI needs the existing scientific Python environment, not an empty system Python.

`--project data` opens the repository's actual CSVs. Historical paths and Box IDs are shown as stored; the application
checks local recording availability before runs. Box authentication is optional;
Missing Box-linked recordings are downloaded before cropping or run review.
An existing folder ID selects the recording automatically; global account setup
is required only when there is no usable shared connection.

## Browse and edit

1. Choose **Open project**. A system folder picker opens on the local desktop.
   Other **Choose file/folder** buttons also use system dialogs, including recording
   locations, the shared Box download folder, events files, estimates, and curation
   destinations. **Choose movies** selects multiple local AVI files without typing
   a Python list. Box folder selection remains in the connected Box browser.
   Cancel leaves the current value unchanged. If no desktop dialog is available,
   the embedded browser remains available. It shows folders, CSV files, breadcrumbs,
   Home, and Computer. Open a folder containing `experiments.csv`, then choose
   **Open this project**, or click its `experiments.csv` file. Typing a path is optional.
2. Each opened project appears as an expandable folder containing experiment rows.
   Click anywhere on a row, or focus it and press Enter. Rows identify the subject,
   experiment number, recording date, recording types, and availability of settings.
3. Opening an experiment shows its **Overview**, with actual metadata and recording
   locations. **Data & settings → Experiment details** provides labeled subject, date, recording, treatment,
   channel, and notes fields. Dates use a calendar; recording folders have a chooser;
   Box IDs are filled from the CSV, with links and a **Choose Box folder** browser. **Analysis settings** groups timing, cropping, neuron detection,
   motion correction, and other fields. Advanced groups expand when clicked.
4. **Find a field** searches labels, original column names, and current values.
   Unknown lab columns remain editable under **Other fields**. Original keys and
   interpreted reader output are available in **File details**.
5. Choose **Save experiment details** or **Save analysis settings**. Each button saves
   only that section's selected experiment row to its original CSV. Other sections'
   pending changes stay in memory. The application warns before leaving with unsaved
   changes; **Discard changes** discards only the current section's draft.

Each project has a **Default parameters from** selector. Choose an experiment with
saved analysis settings; the choice is stored in `.ace-gui-project.json` in that
project folder. Its current analysis settings provide the project's defaults. In
**Analysis settings**, choose an open project under **Populate analysis settings
from**, apply its default experiment's values, review them, then save. The copy
includes matching analysis columns and skips the source experiment number, subject,
date, and recording locations. **New experiment** creates an experiment number,
subject, and date and can copy settings from any open project's default experiment.
Open the new experiment to fill its remaining details.

The experiment number remains fixed so the CSV join stays intact. Duplicate subject,
location, and date columns in the settings file are separate fields under **Recording
details in settings**; they are not automatically synchronized with metadata.

## Missing settings and errors

- Missing settings are marked on the individual rows and listed as clickable subject
  names and experiment numbers above the project. **Missing settings only** filters
  the project lists to affected experiments.
- For a missing settings row, **Add settings for this experiment** prepares a draft;
  saving appends that row. If the file is absent, its columns come from the existing
  parameter template. The project's chosen default can be applied explicitly.
  Blank fields remain blank until populated. A malformed settings file must be
  repaired before writing settings; metadata can still be edited without replacing
  that file.
- Errors persist and name the affected file or field. Validation checks edited
  numbers, dates, boolean choices, numeric Box IDs, and known list/tuple shapes.
  Unchanged legacy values and missing-value markers are preserved.
- Opening a malformed project does not remove previously opened projects. Orphan
  settings records are identified in a disclosure within their project.
- Use **Reload project** after edits made in another application. Unsaved changes
  require a discard confirmation before reload. The GUI checks file hashes and client
  revisions before saving; a stale edit is rejected while the draft remains visible.

## Save behavior

Writes use the existing CSV helpers on a temporary file. The staged CSV is validated
before the original is replaced with `os.replace`. Each save touches one CSV file,
retains column order, unknown fields and other records, and keeps a byte-for-byte copy
of the previous file in `.ace-gui-backups` within the project. The backup location is
shown in **File details** after saving. CSV quoting and record line endings may be
normalized by the existing writers. UTF-8 BOM is preserved. Editing through a CSV
symbolic link is blocked; open the original folder instead.

The in-process server lock serializes GUI writes, and hashes are checked immediately
before replacement. External applications do not share that lock, so simultaneous
writes from those applications should be avoided. Opened project locations are held for the server session. CSVs remain the project
format; run records and optional Box user settings are separate additive files.

The server binds to `127.0.0.1`, rejects foreign hosts/origins, and serves only its
own assets and project endpoints. CSV text is inserted as text, never as HTML.
Scientific version control, statistics workflows,
and environment installation are not connected yet. The History section says so
explicitly. Embedded neuron curation and the five supported run modes are documented below. See [source findings](../docs/design/csv-viewer-findings.md) for
backend issues recorded without source fixes.

## Supercomputer job scripts

Select an experiment and analysis, save any pending settings, then choose **Output
script** beside **Review & run**. Enter the recording folder and output base folder
on the cluster, CPU count, memory in GB, and time limit. Slurm account and partition
are optional. Use `python` from an activated ACE environment or enter its absolute
interpreter path. These are cluster locations; local recording availability and
Box authentication are not required to generate scripts.
Multimodal jobs also require the ephys recording folder on the cluster. Both
recordings are copied into separate folders in the exported run.

**Generate scripts** previews the Slurm file and effective settings. **Download job
ZIP** includes `run_job.py`, `submit.slurm`, `job.json`, the selected experiment's
CSV rows, and the existing GUI analysis worker and its helper modules. No running
GUI is required on the cluster. Copy and extract the ZIP there, activate the same
ACE-NeuroTools analysis environment, and run `sbatch submit.slurm` from the extracted
folder. Add site-specific module loads to the Slurm file if required. Direct
execution with `python run_job.py` also works. The Slurm flags follow the
[official sbatch reference](https://slurm.schedmd.com/sbatch.html).

The job reuses the local run worker and output exports. It copies inputs into a
fresh folder under the chosen output base; allow disk space for that copy and
results. Original recordings and results remain intact. CNMF-E worker processes
match `SLURM_CPUS_PER_TASK` (or the configured CPUs for direct execution). Crop and
neuron review windows stay disabled. A confirmed local Box file selection is
included when its receipt is available; otherwise the cluster folder's supported
recording files are used, with the saved movie filename selection applied by the
pipeline. Recordings and Box credentials are not bundled. Job logs identify the
output folder. Bring estimates back to the GUI's Neurons workflow for review.

The resource fields are requests, not estimates of the memory or time needed for
the recording. Real cluster execution still requires appropriate files, an installed
analysis environment, and valid account/partition limits.

## Validation

### Analysis parity

Run the strict differential suite in the existing CaImAn environment:

```bash
PYTHONPATH=.:src python -m pytest tests/test_gui_parity.py tests/test_gui_run_outputs.py
```

The tests use temporary lossless movies and synthetic RHS2116 recordings. They
exercise real GUI HTTP settings/save/review/run endpoints, the existing CLI entry
points, direct Python calls, structured miniscope configs, and extracted cluster
job bundles.
Scientific pipelines are not mocked. The CLI parameter checks observe its public
`run()` boundary; output checks allow the CLI to finish the actual analysis.
The comparisons use the same effective scientific settings in each entry point;
direct Python calls have different defaults and therefore receive explicit options.

| Workflow | Compared results |
| --- | --- |
| Mean fluorescence | Cropped and full-frame signals against Python, native compute CLI, GUI, exported Python, and the Slurm shell script |
| Preprocessing | Decoded saved movie pixels, projections, frame numbers, frame rate, and timestamps, with and without DF/F normalization |
| Electrophysiology | Raw/filtered signals, sampling rate, timing, and phases against Python, CLI, GUI, and exported jobs |
| CNMF-E | Actual neuron traces and spatial footprints, events, filters, phases, spectra, saved HDF5 estimates, and deconvolution diagnostics across Python, structured configs, CLI, GUI, and exported jobs, with one and two workers |
| Saved settings | Defaults, CSV overrides, missing-value markers, legacy crop coordinates, canonical flags, aliases, and headless policy against the actual CLI |

The CNMF-E fixture must extract at least two neurons and produce calcium events;
empty outputs cannot pass. Deterministic fluorescence, preprocessing, and ephys
outputs must match exactly. CNMF-E floating-point comparisons use `rtol=1e-5` and
`atol=1e-6`; event indices must match exactly. GUI runs must retain the original CSVs
and raw movie. All archives are read without pickle.

These tests protect parity for the covered workflows and settings. Multimodal
parameter matching, two-recording staging, exports, and worker execution have
separate checks in `tests/test_gui_multimodal.py`. Standalone preprocessing has
no separate module CLI.
The tests do not establish parity for every possible dataset, motion-correction
configuration, or cluster installation. The Slurm shell script runs locally; a real
scheduler submission is not exercised. The suite is included in the existing CI
`tests/` discovery, without skips or expected-failure exemptions.

```bash
PYTHONPATH=.:src python -m pytest tests/test_gui_job_scripts.py tests/test_gui_csv_projects.py tests/test_gui_server.py tests/test_gui_box_setup.py tests/test_gui_analysis.py tests/test_gui_recordings.py tests/test_gui_neurons.py tests/test_gui_launcher.py tests/test_gui_native_dialogs.py tests/test_csv_worker.py
```

Tests cover raw values, stable-number joins, missing/malformed files, selected-row
writes, backups, unknown fields, exact Box IDs, BOM, write failure, new settings,
validation, stale saves, HTTP endpoints, and the unchanged reader.

Browser checks against temporary CSVs covered project grouping, whole-row selection,
calendar editing, folder navigation/picking, Box IDs, notes, real saves, validation,
backups, missing-settings creation, unsaved-change protection, and narrow screens.
The bundled CSVs were only inspected during verification, never edited.


## Global Box setup and recording downloads

Choose **Box settings** in the header. Connect once with the lab app's Client ID,
masked Client secret, and Box user/enterprise ID, then choose a local download folder.
**Check connection** verifies the account with a real `get_user_me` request. The
walkthrough links to Box's Developer Console and explains app authorization and
managed-user permissions. Lab administrator authorization and folder sharing happen
in Box. A temporary developer token is also supported for session-only access.

Lab credentials are remembered **by default** and reused across every experiment,
project, browser refresh, and server restart. Uncheck Remember for session-only access.
Global setup does not ask for a recording folder. Opening settings while connected
shows the account and download location; credential fields appear only for initial
setup or an explicit **Change account**. Saving a new download location persists it.
**Disconnect this session** leaves saved settings but disables automatic reuse during
that server session until explicitly reconnected. **Forget saved connection** removes
the saved settings after confirmation.

Saved lab settings live in `$XDG_CONFIG_HOME/aceneurotools/gui/box.json` (default
`~/.config/aceneurotools/gui/box.json`) with file permissions `0600`, outside projects
and CSV backups. This is a private plaintext settings file, not a system credential
vault. Developer tokens are never saved. Secrets are not returned in API responses,
stored in browser localStorage, or included in URLs, logs, run manifests, or CSVs.
SDK errors are converted to safe messages about access, credentials, or connectivity.

Each recording uses its own `Box Calcium Folder ID` or `Box ephys folder ID` from
`experiments.csv`. Existing values populate the editor automatically. **Choose Box
folder** browses that saved ID using the shared connection; **Use this folder** saves
the selection to that experiment, with the normal CSV backup/revision checks. Missing
IDs require choosing a recording folder, not repeating account credentials. A Box ID
alone does not authenticate an account; an inaccessible folder produces a clear
permission error rather than asking for new secrets for every experiment.

**Choose recording files** opens a download review with filenames, sizes, verified
local copies, the full recording size, free disk space, and the destination. Select
individual files, search by name/folder, or use **One movie + metadata** for a small
test. That helper prefers a calcium/Miniscope folder and selects its smallest movie
plus known metadata/timestamp files in the same folder or its parents. Every checkbox
remains editable. The live total shows selected size and bytes still to download;
confirmation is disabled when the selection exceeds free space.

**Confirm & download** is required before any recording bytes transfer. Merely
opening an experiment, listing Box files, or loading a crop preview cannot initiate
a download without this review. If files are missing, **Load recording preview**
and **Review & run** open the same selection/confirmation step. Already verified
selected local files can be used without another transfer. The review checks CSV
versions and expires after 30 minutes, preventing an outdated selection from starting.

**Cancel download** interrupts the current streamed file, removes staged data, and
leaves original files/results intact. A blocked network read may take up to the
configured read timeout (20 seconds) to return before cancellation completes. The
button is disabled during the final installation of verified files. Cancellation
discards newly staged files, including files completed during that cancelled request;
retrying the selection downloads those again. Previously installed files are retained.

An absolute CSV recording directory remains the download destination. A relative directory is appended to the global download
folder (e.g. `sessions/rat03` → `<download folder>/sessions/rat03`). An explicitly
selected **data base folder** takes priority. Existing local recordings under the CSV
project remain usable without moving them. Existing local data can also be used
without any Box setup. Windows paths on Linux require choosing the local equivalent.

The wrapper checks every Box listing page and nested folder, verifies sizes and SHA-1
hashes when provided, and skips verified local files. New or repaired files download
into a temporary staging folder on the destination filesystem. No new files are
installed until all requested transfers verify. Replaced partial/changed files are
retained under `<recording>/.ace-box-backups/<download id>/`; unrelated files and old
analysis results are retained. A `.ace-box.json` receipt allows reuse without another
network listing. It remembers the selected paths independently of the full Box
listing, so a one-file test is never silently expanded into a full download. Both crop
previews and private run copies use only that selection, even if other movies already
exist locally. Changing the selection invalidates an old run review. To add files or
switch back to the whole recording, use **Choose recording files** and confirm again.
Subset outputs are test results, not complete-recording analyses; timing/event workflows
still need appropriate supporting files and valid source timestamp mapping. Missing
selected files require reviewing a new download rather than silently repairing them.
Refreshing during a download leaves the server's download running; loading again
reattaches to it. Failed or interrupted transfers can be retried.

Downloads reuse the unchanged core `download_file` byte-transfer function through
an adapter that supplies complete, validated listings. The GUI uses the same optional
`box-sdk-gen` dependency but does not create `src/.../box_credentials.py` or change
legacy script credentials. Network requests have bounded timeouts/retries. Missing
SDK or connection errors do not disable CSV editing or local recording use.

## Embedded cropping

Select an experiment, choose **Crop**, and **Load recording preview**. Relative
recording paths use the configured download/data base folder; absolute paths remain absolute. Choose a different base folder or edit the
recording location through the file browser if a historical path is unavailable.
Missing Box-linked AVI recordings require selecting files and confirming their
download before previewing. The confirmed selection is reused for later previews/runs.

The wrapper samples at most 8 movies and 16 frames per movie, lowering frame counts
for large images. It uses the existing `compute_projections` implementation for
max/min/mean/median/std/range images. The preview states its sampled frame/file counts;
it is not presented as a full-recording projection. Image dimensions must agree.

Drag outside the selection to draw, drag inside to move, or drag a corner to resize.
Numeric **Left, Bottom, Right, Top** fields provide precise and keyboard-accessible
bounds. Projection, zoom, black/white levels, **Full frame**, and **Restore saved crop**
affect the preview without changing raw files. Coordinates use the original pixels
and the core pipeline's bottom-left origin; resizing the browser never changes them.

**Save crop** validates positive dimensions and image bounds, then writes a tuple to
`crop_coords` in the selected experiment's `analysis_parameters.csv` row. Older
projects gain that canonical column explicitly while retaining every other row and
column, including their legacy `crop` value. A missing settings row is added as part
of this deliberate save. The prior file is backed up. Stale files or changed recording
inputs require a fresh preview. Other pending settings must be saved/discarded first.
Raw movies are never cropped in place. To produce an actual cropped AVI, choose **Review movie export** in Crop, or select
**Crop & preprocess movie** from Analysis, review its settings, and start it.

## Review neurons

Open an experiment and choose **Neurons**. The newest estimates HDF5 is preselected
from that experiment's local recording folder, its `saved_movies` folder, and
completed CNMF-E runs, ordered by file modification time. Curation archives are
not searched recursively. Choose **Load estimates**, select another entry, or use
**Choose file** to browse to an existing CaImAn estimates
file. Refreshing does not replace an explicit file choice or an active review.
**Load estimates** opens real spatial footprints and temporal `C` arrays;
no sample candidates are generated. **Review neuron extraction** opens the normal
parameter review for a new CNMF-E run. Extraction must save an estimates file
before it can be curated here.

The review matches the supplied `curate_neurons-3.py` workflow:

| Script feature | Embedded control |
| --- | --- |
| Load estimates; optional frame-rate override | File browser/run outputs and **Frame rate (Hz)** |
| Sum of footprints and selected footprint | Two image views, normalized as in the script |
| Location marker | Selected footprint's maximum pixel, matching the script's calculation |
| Raw `C` fluorescence trace centred on its maximum | Trace with time in seconds; **Trace window (s)** defaults to 30 |
| Keep/reject and advance | **Keep & next**, **Reject & next**, K/R |
| Previous/next | Buttons and left/right arrow keys |
| Done with explicit undecided handling | **Finish review**, D or Enter; choose keep/reject remaining or continue |
| Curated HDF5 and NPZ | **Save curated copies** after reviewing the decision counts and output folder |

Additional controls include a numbered decision list, jump to neuron, **Next
undecided**, **Mark undecided**, **Undo last decision**, full trace, peak centring,
and an overview you can click to move the window. Change the window duration for
zoom and choose **Centre on peak** or **Show window** to apply it. Frame-rate changes
change the time axis and exported frame-rate metadata; they do not resample `C`.
Keyboard shortcuts stay inactive while editing a field. Enter activates a focused
button normally. Keep/reject also have text labels, so color is not the only cue.

Neuron numbers shown in the UI start at 1; **Original component ID** and exported
`neuron_ids` use the source file's zero-based indices. Footprints use the script's
Fortran-order reshape. The location is a peak pixel, not a computed centre of mass.
Raw `C` values are not relabeled as normalized fluorescence or event rates. Long
traces use min/max envelopes for browser display to retain narrow peaks; exports
keep the full arrays.

Decisions and the current neuron save automatically in
`<project>/.ace-neuron-reviews/<source-key>/review.json`. Choose the same estimates
file after reopening the GUI to resume. A changed source file gets a separate
review; stale tabs and changed files are blocked. Undo applies to individual
decisions in the current browser session; persisted choices can always be changed
by revisiting a neuron. At most three estimates sets remain loaded in server memory.
This loads the estimates, not the raw movie, but large estimates still need RAM.

Exports create a unique child folder under the chosen output location (default
`<project>/.ace-curations`). Each contains `decisions.json` with source information,
all choices, frame rate, and original kept IDs. When at least one neuron is kept,
it also contains the named estimates HDF5 and `C_curated.npz`, produced by the
existing CaImAn load/select/save methods. NPZ keys match the script: `C`,
`A_dense`, `neuron_ids`, and `fr`. If dense footprints would exceed 128 MB, the NPZ
uses sparse CSC keys `A_data`, `A_indices`, `A_indptr`, `A_shape` instead of
`A_dense`; the completion message explains this. If all neurons are rejected,
only the decision record is exported. Original estimates and earlier curations
are retained. **Curated estimates filename** defaults to the source name with
`_curated.hdf5`; it accepts a filename, not a path. Choose the parent output folder
with the system picker, then **Save curated copies**. Every save creates a new
child folder, even when you select the original folder and filename, so the original
CNMF-E `estimates.hdf5` is never replaced. **Open curation folder** opens the saved
files in the system file manager. An export failure leaves saved decisions intact.

**Detect calcium events from curated estimates** is enabled in Finish review.
Review the derivative and event height threshold, then choose **Save curated
copies & detect events**. These controls start from the experiment's current Run
settings, which may differ from those of the original extraction run. Uncheck
detection to save only curated copies. A repeat export can use a different
threshold without rerunning extraction or replacing earlier results.

Detection loads the saved curated HDF5 and uses the pipeline's existing derivative
detector for kept neurons only. `calcium-events.json` contains `ca_events_idx`
keyed by zero-based curated row index, with `neuron_ids` mapping rows to original
component IDs. It records the reviewed frame rate, trace length, parameters, review
revision, original source signature, and saved curated estimates signature/path.
Indices follow the existing detector: zeroth derivative indexes raw `C`; first
and second derivatives index `np.diff(C, n=1)` and `np.diff(C, n=2)`, without adding
a frame offset. Use this convention when aligning events to other recordings.
All-rejected exports contain only the decision record. A detection failure
installs no partial export; the original estimates and review journal are retained.

Completed run outputs remain tied to their original estimates. This action writes
new calcium events in the curation folder; ephys, movie projection analyses, and
multimodal products require a new run. The full extraction pipeline still
runs its configured postprocessing before embedded review; this export provides
the explicit event recomputation path from curated estimates.
No Git/EVC history support is implied by the review journals or curation folders.
See [meeting follow-ups](../docs/design/neuron-review-and-meeting-followups.md).

## Review and run

To run CNMF-E:

1. Open the experiment and choose **Set up CNMF-E** on Overview (or select
   **Calcium imaging / CNMF-E** in the Analysis menu, then **Run settings**).
2. Ensure **Extract neurons with CNMF-E** and **Save CNMF-E estimates** are **Yes**.
   Review motion/detection parameters in **Data & settings**. Choose/save a crop
   in **Crop**, or set **Apply crop = No** for the full frame. Save any changes.
3. Choose **Review & run**. The review shows the exact planned run folder, estimates
   path, saved parameter path, input files, and effective settings. Extraction or
   estimates saving turned off is clearly identified. Confirm before starting.
4. Follow progress in **Results**. **Open output folder** opens that run in the
   system file manager. After successful extraction, **Review extracted neurons**
   loads its estimates directly into Neurons.

All run artifacts remain grouped under `<project>/.ace-runs/<run-id>/`.
CNMF-E estimates normally land at `recording/saved_movies/estimates.hdf5` within
that folder; the configured estimates filename is respected. Saved CaImAn
parameters are `recording/saved_movies/opts_caiman.json` when enabled. Run logs,
CSV snapshots and `effective-parameters.json` remain with those results.
Choosing a download/data folder changes where raw recordings are found, not the
run output root. Curated estimates use their separate curation destination above.
File links in Results export a copy through the browser; **Open output folder**
opens the originals without creating another copy.

On Linux, native dialogs reuse installed Zenity or KDialog. Tk dialogs are a
fallback on supported desktops with Tk already installed. No packages are installed
automatically. Detached launches can recover the current user's Wayland display.
With no desktop available, use the embedded browser. Folder opening uses the
system file manager (`xdg-open` on Linux).

The Analysis menu connects five existing workflows:

| GUI mode | Existing code called | Preserved results |
| --- | --- | --- |
| Mean fluorescence | `ComputePipeline.run` | `calcium_signals/meanFluorescence_<number>.npz` |
| Crop & preprocess movie | `MiniscopeDataManager.create` + `MiniscopePreprocessor.preprocess_calcium_movie` | `recording/saved_movies/preprocessed*.avi` |
| Calcium imaging / CNMF-E | `MiniscopePipeline.run` | Cropped/preprocessed movies, configured estimates/params, events with IDs, component traces/footprints, raw/filtered projections, spectra, phases, available quality metrics |
| Electrophysiology | `EphysPipeline.run` | `ephys.npz` with signal, time, sampling rate, filtered signal/phases when requested, plus event JSON |
| Calcium + electrophysiology alignment | `MultimodalPipeline.run` | Both sub-pipeline results, aligned times, TTL mappings, event phases, and phase histograms when requested |

Every new completed run writes `output-inventory.json` and `diagnostics.json`.
**Results → Output inventory** lists each result's status and its exact file/key,
or explains why it is unavailable or disabled. Older runs have no inventory;
their existing output files remain accessible. Serialization errors fail the run
instead of silently dropping a computed value.

| Miniscope export | Contents |
| --- | --- |
| `calcium-events.json` | Ragged `ca_events_idx` dictionary, zero-based component IDs, frame rate, detector settings, and index convention; includes empty event lists |
| `postprocessing.npz` | Component IDs and available `C`, `S`, `F_dff`, `YrA`, `b`, `f`; temporal projection as left by the pipeline; unfiltered and filtered temporal projections; spatial projection images; frame rate, timestamps/frame numbers, spectra/axes, and phases |
| `components.npz` | Sparse CSC footprints as `A_data`, `A_indices`, `A_indptr`, `A_shape` |
| `diagnostics.npz` | Available `SNR_comp`, `r_values`, `cnn_preds`, automatic accepted/rejected indices, neuron noise and fitted `g`, `bl`, `c1` values |
| `diagnostics.json` | Run settings, neuron count, requested inline mode and observed projection replacement, phase/spectral input semantics, and unavailable outputs |

NPZ files use numeric arrays and load with `allow_pickle=False`. `neuron_ids`
maps `C` rows and event dictionary keys to extraction component IDs; automatic
accepted/rejected indices are saved separately. The GUI does not invent missing
quality scores or compute the interactive correlation/PNR diagnostics. The core
pipeline does not retain motion-correction shifts; the inventory identifies that
limitation. Preprocess runs additionally export projection/timing arrays to
`preprocessing.npz`; ephys inventories cover signal, filtered signal, phases,
sampling rate, timing, and events.

The core postprocessor computes phases and spectra before filtering. Its final
temporal projection may therefore be filtered while those products describe the
unfiltered signal. Exports retain both signal versions and record that ordering.
Headless mode respects the configured `inline` setting while suppressing GUI
steps. `inline=True` replaces the final temporal projection with filtered data;
`inline=False` retains the unfiltered projection. The GUI inherits the miniscope
CLI default of `inline=True`; the Python API default is `False`. Filtering must
be enabled for replacement to occur. `diagnostics.json` records
whether replacement actually occurred. This changes earlier headless behavior,
which always forced `inline=False`: batch runs that specify or inherit
`inline=True` now return a filtered final projection. Set `inline=False`
explicitly to retain the earlier behavior. Calcium-event detection and the
phases/spectra computed before filtering keep their existing input semantics.

**Run settings** exposes the applicable run arguments, and **Save run settings**
writes edited values to the real parameter CSV (adding supported missing columns).
Scientific CaImAn detection/motion parameters stay in **Data & settings**. Blank/None
run settings inherit the existing CLI defaults; the review identifies inherited
values versus saved CSV values. Headless policy uses the existing helper. Separate
windows and the pipeline's original neuron-selection dialog are disabled. Review
saved estimates in the embedded **Neurons** section after extraction. Finish review
can recompute calcium events from curated estimates into a separate curation
folder, using the settings shown there. Multimodal products require a new run.
Cropping is controlled explicitly: save
a crop or set **Apply crop = No** to process the full frame.

**Review & run** shows the project, subject, experiment number, date, local recording,
analysis type, copy size, output location, every effective run argument, and all saved
CSV metadata/settings. It reports missing recordings, invalid crops, missing filenames,
and other blockers. Starting requires checking the review confirmation; unsaved
settings, stale CSV revisions, changed inputs, or expired reviews prevent execution.
Supported legacy identity must be an integer without leading zeros. Records with
other identities remain editable.

Each run gets a unique `<project>/.ace-runs/<UTC time>-<id>/` folder. The run freezes
both CSV files and reviewed effective parameters, copies supported raw recording
files into its own `recording/` directory, and invokes the existing API in a separate
process using the same Python environment as the GUI. Execution CSVs remap only the
selected recording to that private copy. Fixed pipeline output names consequently
stay inside that run; reruns never replace earlier outputs or change original raw
files/CSVs. Copying is deliberate and can require substantial disk space; the review
shows the copy size and blocks insufficient input-copy space. Extra processing output
space is workload-dependent. Raw input sizes/mtimes are checked before and after copy.

For compute, the adapter checks the returned subject map: the core's caught/skipped
errors cannot be reported as success. Other pipeline exceptions produce Failed and a
nonzero exit status. **Results** lists runs, output downloads, exact run parameters,
and a bounded live log. **Stop this run** terminates that worker's process group and
retains inputs/logs/partial results. One heavy GUI job runs at a time. Other experiment
settings can be edited while it works without altering the captured inputs.

Completed/failed runs persist on disk and survive page/server restarts. A server
restart cannot take control of a still-active old worker; such a run is marked
Untracked until its outcome is available, never assumed successful. Keep the GUI
server running during analysis. Files are retained until deliberately removed outside
the GUI. `.ace-runs` and CSV backups are Git-ignored, not deleted.

## Scope of verification

Automated tests run real mean-fluorescence and cropping/preprocessing code on small
lossless temporary AVI recordings, verify numeric crop orientation and output dimensions,
rerun preservation, immutable original files, failure reporting, and stale-review guards.
Box SDK factories are constructed against the installed SDK, with mocked account/folder/download
requests for credentials, permissions, pagination, persistence, and redaction tests.
Real AVI bytes transferred through the unchanged downloader feed into real crop and
compute code. Tests cover global reuse after restart, relative/absolute/explicit paths,
partial repair, nested folders, failed staging, and preservation of old results.
Further tests cover confirmation before any byte transfer, a selected file fitting
on disk when the full 50 GB listing does not, cancellation during a streamed file,
staging cleanup, remembered subsets, and a real subset compute run that excludes
other movies already present locally.
Browser checks cover crop dragging and real CSV saves, mandatory review, a real cropped
movie run, results after refresh, guided Box recovery, global saving, automatic download/crop continuation, saved folder
selection without credentials, refresh reuse, and narrow layouts.

The refreshed app successfully reconnected to the researcher's previously saved
Box account using a live account verification request. Live recording-folder
downloads and full CNMF-E/ephys analysis on researcher data remain unverified;
transfer tests use mocked Box responses with real recording bytes. Verification
fixtures are outside the repository and are not product demo workspaces.
