# Use the experiment workbench

ACE opens in your browser and runs on your own computer. Use it to edit
experiment details, choose a movie area, run an analysis, review neurons, and
find the saved results. Start with [installation](gui_installation.md). For a
first session, use the [first-run walkthrough](lab_walkthrough.md).

## Prepare a project

ACE opens an existing project; the GUI does not create the initial experiment
list. If you already have a compatible project, make a separate working copy
and continue to [Open ACE and a project](#open-ace-and-a-project).

1. Create a writable folder for your project, separate from the ACE source
   folder. Keep the original recordings in their acquisition folder structure.
2. In your downloaded `ACE-NeuroTools` source folder, open
   `src/aceneurotools/shared/metadata_templates` in your file manager. Copy
   `experiments_template.csv` and `analysis_parameters_template.csv` into the
   project folder. Rename the copies to `experiments.csv` and
   `analysis_parameters.csv`.
3. Open the copies in a spreadsheet editor. Preserve the column headers and
   replace the example experiment with your recording's details. Give each
   experiment a unique integer in `line number`, enter its subject and recording
   date, and set its calcium or electrical recording folder. Use the same
   `line number` in the settings file. Remove unused example rows from both files.
4. Replace example paths and channel names with real values. Leave Box folder IDs
   blank for local recordings. Keep metadata, timestamps, and movie segments in
   the layout produced by your acquisition system; a movie alone may be insufficient.
   See [calcium recording formats](guides/calcium_imaging.md#naming-and-acquisition-formats)
   and [electrical recordings](guides/ephys.md) for supported inputs.
5. Review the settings for your recording, especially frame rate, calcium indicator
   decay, cell size, motion correction, and any electrical channels or filters.
   Template values are examples, not validated settings for every recording.
6. Save each file as **comma-separated CSV in UTF-8**, keeping the `.csv`
   extension. Close the spreadsheet editor before editing the files in ACE.

You can also create starter files using the command in
[Getting started](getting_started.md#1-prepare-project-files-and-recordings).
The generated `lab_config.json` and `stats_config.json` belong to the separate
compute/statistics launcher; neither is required to open a CSV project in the GUI.
The settings CSV is optional, but supplying it makes your chosen analysis
settings explicit. If it is absent, use **Add settings for this experiment**
after opening the project and review inherited defaults before running analysis.

## Open ACE and a project

1. Activate the environment created during installation and run `ace-gui`.
2. Keep the application terminal open. If your browser does not open, copy the
   complete launch address printed in that terminal. It includes a private token;
   typing only `http://127.0.0.1:8765/` will not reconnect an unauthenticated tab.
3. Choose **Open project** and select the folder containing `experiments.csv`.
   You can also select the file itself. If a system picker is unavailable, use
   the folder browser in ACE and choose **Open this project**.
4. Select the experiment and check its subject, date, and recording locations
   in **Overview**. The experiment number is its ID, not its spreadsheet row.

The optional `analysis_parameters.csv` stores analysis settings for those same
experiment IDs. If you do not already have a project,
[prepare one from the templates](#prepare-a-project). No ready-to-run
demonstration recording is bundled.

## Check recording locations

Download Box recordings outside ACE before continuing. **Choose recording files**
checks files already on your computer; this version has no Box connection or
download service. Box folder links open the Box website.

In **Data & settings → Experiment details**, choose the local calcium or ephys
recording folder and save. For relative folder names, use **Choose data base
folder** in the Details sidebar to select their shared parent folder. For example,
`Rat01/session1` under a data base folder of `D:/recordings` resolves to
`D:/recordings/Rat01/session1`. Reselect the base folder after restarting ACE;
that choice is held in the current browser session. Absolute recording folders
saved in experiment details do not need a base folder.

Keep the recording's original metadata, timestamp files, and movie segments
together. A single movie copied without its companion files may not be usable.

## Edit and save details or settings

1. Open **Data & settings** and choose **Experiment details** or **Analysis settings**.
2. Edit the desired field. **Find a field** searches labels and values.
3. Choose **Save experiment details** or **Save analysis settings**. Each saves
   only that section; save both separately if you changed both.
4. If settings are missing, choose **Add settings for this experiment**, fill in
   values appropriate to your recording, and save. Blank settings can inherit defaults;
   a blank field does not establish that the default suits your recording.

**Discard changes** removes the current section's unsaved edits. ACE warns before
leaving unsaved work. **Reload project** rereads the files after an edit in another
application; resolve or discard your drafts first. Avoid simultaneous edits in
ACE and a spreadsheet editor. A conflicting save is rejected rather than silently
overwriting a newer file.

Saves preserve other rows and unknown fields and keep previous files under
`.ace-gui-backups` in the project. The backup location appears in **File details**.
These backups are separate from the **History** screen, which is not connected.

## Preview and crop a movie

1. Save pending details and settings, then open **Crop → Load recording preview**.
2. Drag outside the selection to draw a box, inside it to move, or a corner to
   resize. You can also enter **Left**, **Bottom**, **Right**, and **Top** bounds.
3. Use **Image**, **Zoom**, **Black**, and **White** to inspect the preview.
   **Full frame** selects everything; **Restore saved crop** undoes preview edits.
4. Choose **Save crop**. The box must fit inside the image with positive width
   and height. Coordinates use original pixels with a bottom-left origin.

The preview samples frames; it is not a summary of every frame. Saving the crop
stores settings and leaves the original movie unchanged. To create a processed
movie, choose **Review movie export**, or select **Crop and preprocess movie**
from the Analysis menu. To process the full frame, set **Apply crop = No** in
**Run settings**.

## Review and run an analysis

Choose the analysis from the menu beside **Review & run**:

| Analysis | What it produces |
| --- | --- |
| Mean fluorescence | Average image brightness over time |
| Crop and preprocess movie | A processed movie and image/timing summaries |
| Calcium imaging (preprocessing and CNMF-E) | Extracted cell signals, cell footprints, events, and available diagnostics |
| Electrophysiology | Electrical signals and timing, plus requested filtering and phases |
| Calcium imaging + electrophysiology alignment | Both recording analyses and synchronized timing, with event comparisons when requested |

CNMF-E is the method used to separate cell signals from a calcium movie. Cropping
alone does not find neurons. For neuron extraction, choose **Set up CNMF-E** in
Overview, set **Extract neurons with CNMF-E = Yes** and **Save CNMF-E estimates =
Yes**, and choose **Save run settings**. Check **Movie filenames**: the calcium
analysis default is `["0.avi"]`; enter `[]` to use all supported movies. Use a short supported recording and settings appropriate to its acquisition
system and calcium indicator. Motion and cell-detection
parameters also appear in **Data & settings**.

1. Save changes, then choose **Review & run**.
2. Check the experiment, input filenames, copy size, output locations, and every
   effective setting. **From** explains whether a value comes from the saved
   spreadsheet, a default, or the GUI's suppression of separate windows.
3. Tick **I have reviewed this experiment and its parameters**, then choose
   **Start analysis**. Missing inputs, unsaved edits, or an invalid crop must be
   resolved first. After changing inputs or settings, review the run again.
4. Follow the state and log in **Results**. Keep the computer awake and the
   application terminal running. Closing only the browser tab does not stop it.

Each run copies inputs into its own folder under `<project>/.ace-runs/<run-id>/`.
Allow disk space for that copy and processing outputs. Repeating an analysis
creates another folder and preserves earlier results. One heavy run executes
at a time. **Stop this run** stops its worker and retains logs and partial files;
these do not count as a completed analysis. A failed stop keeps the run active.
After a server restart, an old worker may be marked **Untracked** rather than
assumed to have completed.

For combined recordings, set both recording folders and review both input lists.
Calcium data is copied under `recording/` and electrical data under
`recording-ephys/`. Verify the synchronization information before interpreting aligned results.

## Find and reopen results

In **Results**, select a run and expand **Output inventory**. It names exported
files and explains unavailable or disabled outputs. **Open output folder** opens
the originals in your file manager; individual file links download browser copies.
Some exports are data archives rather than files that a movie player or
spreadsheet can display. Ask the analyst to inspect those arrays.

| Location within a run | Contents when the corresponding step succeeds |
| --- | --- |
| `run.log`, CSV snapshots, `effective-parameters.json` | Log and settings used for that run |
| `recording/saved_movies/` | Processed movies, saved estimates and CaImAn settings when enabled |
| `calcium_signals/meanFluorescence_<ID>.npz` | Mean fluorescence |
| `preprocessing.npz` | Preprocessing image/timing summaries |
| `postprocessing.npz`, `components.npz` | Available cell signals and footprints |
| `calcium-events.json` | Calcium events and component IDs |
| `ephys.npz`, `ephys-events.json` | Electrical signals, timing and events |
| `alignment.npz` | Combined-recording alignment results |
| `output-inventory.json`, `diagnostics.json` | Output listing and explanations |

Saved runs remain on disk after closing ACE. Reopen ACE using its shortcut or
`ace-gui`, use the new printed launch address, reopen the same project, and
choose **Results**. This is saved-run access, not revision history. The run record
is not a complete record of software versions, random seeds, or input/output
content hashes. The output inventory is written for successful GUI runs; a failed
run can have partial files without an inventory. Direct Python/command-line runs
do not automatically create these GUI exports.

## Review neurons and save accepted cells

1. After successful extraction, choose **Results → Review extracted neurons**.
   Alternatively, open **Neurons**, choose an estimates HDF5 file, and choose
   **Load estimates**.
2. Inspect the cell footprint (its highlighted image area) and activity trace.
   Apply your neuron acceptance criteria consistently; choose **Keep & next** or **Reject & next**.
   K/R and arrow keys also navigate. **Next undecided** finds unfinished decisions.
3. Decisions save automatically. Reopen the same unchanged estimates file to
   resume. **Undo last decision** works within the current browser session.
4. Choose **Finish review**, resolve every undecided cell, and check the totals.
   Choose the **Curation output folder** and **Curated estimates filename**.
5. To calculate calcium events from the kept cells, leave **Detect calcium events
   from curated estimates** checked. Choose a derivative and event height appropriate to your signals, then choose **Save curated copies & detect events**.
6. When saving finishes, choose **Open curation folder** and confirm the exports.

Each export creates a separate folder, by default under `<project>/.ace-curations`.
It contains decisions, curated HDF5 estimates, `C_curated.npz`, and, if requested,
`calcium-events.json`. If all cells are rejected, only the decisions are exported.
The source estimates stay intact. Decisions are stored separately under
`.ace-neuron-reviews` in the project.

Saving curated copies alone does not update calcium events. Curated event export
also does not replace earlier run outputs or recompute electrical or aligned
results. A new combined-recording run uses its recordings and saved run settings,
not the curated estimates. Changing the review frame rate changes displayed time
and export metadata; it does not resample the signals.

For analysts: events use the detector's array coordinates. Zeroth derivative
indexes `C`, first indexes `np.diff(C, n=1)`, and second indexes `np.diff(C, n=2)`;
no frame offset is added. `neuron_ids` maps exported rows to original zero-based
component IDs; displayed neuron numbers start at 1.

## If something goes wrong

| Problem | Next step |
| --- | --- |
| Browser asks you to reopen ACE | Use the complete launch address from the running terminal, including its token. A restart creates a new address. |
| Address is already in use | Open a new terminal in the ACE environment and run `ace-gui --port 8766`; use its printed address. |
| Recording missing | Download it first, then select its local folder or the correct data base folder. Save and retry. |
| Preview will not load | Save pending edits and check that the recording has its metadata, timestamps, and readable movies. Include the exact error when [reporting a problem](gui_installation.md#report-an-installation-problem). |
| Settings changed elsewhere | Keep a copy of any draft you need, reload the project, and apply your edits to the current version. |
| Run failed | Select it in Results and include the error, `run.log`, experiment ID, and chosen analysis in your problem report. |
| Neurons list is empty | Check that extraction succeeded and estimates saving was enabled; a cropped movie alone contains no extracted cells. |

Box setup, cluster job-script generation, and experiment revision history are not
connected in this installed GUI. Some controls are retained from the earlier
pilot; follow this guide for the supported workflow.
