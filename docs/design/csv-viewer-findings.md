# Experiment GUI: source findings

Observed during project loading and CSV editing, October 3, 2026; integration
status updated October 6. The initial CSV slice made no changes to `src`.
Further source fixes require explicit user approval; approved event-detector and
headless-policy changes are recorded below. The bundled files at the initial
audit loaded 118 experiments and 114 parameter records;
all 118 metadata records can be inspected by the existing reader.

The bundled CSVs also have five metadata rows with no settings record (`114`,
`115`, `116`, `117`, and `Example`) and one settings row whose `line number` is
descriptive text rather than a matching experiment. These are displayed as file
content issues; the viewer preserves them and reports the unmatched records.

## Missing parameter row does not use the documented fallback

[`ExperimentDataManager.import_analysis_parameters`](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/shared/experiment_data_manager.py#L118)
documents an empty settings dictionary when an experiment number is absent.
However, its call to
[`CSVWorker.csv_row_to_dict`](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/shared/csv_worker.py#L41)
raises `ValueError` for an absent number. The manager only checks for a `None`
return, so that exception bypasses the fallback.

Reproduction: load a metadata record whose `line number` does not occur in an
otherwise valid `analysis_parameters.csv`. Calling `import_analysis_parameters`
raises instead of assigning `{}`. The bundled CSVs have unmatched experiment
numbers, so a future GUI run adapter must account for this before enabling runs.
The viewer shows missing settings explicitly and does not invoke this manager.

## Zero-padded experiment numbers cannot match the existing reader

Reproduction with a small fixture:

```csv
line number,id
001,R1
```

`CSVWorker.csv_row_to_dict(path, "001")` raises “not found”: pandas infers the
column as an integer, and string conversion yields `"1"` rather than `"001"`.
This is covered by the GUI test. The viewer retains the raw `001` identity and
shows the reader error alongside the intact record. The bundled project did
not encounter this error.

## Boundary decisions

The existing reader loads one selected experiment and converts its types. The
GUI adds whole-table enumeration/validation, labeled editors, and a local browser
adapter, then reuses that reader for the optional interpreted view. Raw fields are kept
as text so exact IDs, `NA`, dates, blanks, and additional columns remain visible.

Settings are matched by exact `line number`. Missing files/rows are distinct from
invalid files. The GUI never silently repairs a malformed file or substitutes
defaults. Explicit saves reuse `update_csv_cell` and `append_row_csv` on a temporary
CSV, validate it, back up the original, and atomically replace the selected file.
Unknown columns and other records are retained. Box links are constructed only
from numeric folder IDs, without claiming authentication or recording availability.
At the October 3 checkpoint, execution remained outside scope. The October 5
wrapper integration is described below and in the GUI guide.

## The parameter template example has a missing cell

[`analysis_parameters_template.csv`](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/shared/metadata_templates/analysis_parameters_template.csv)
has 53 headers and 52 fields in its example row. Loading that example through the
existing strict CSV reader raises a malformed-CSV error. This was encountered in
the new missing-file tests; the template was not changed.

For a missing settings file, the GUI reads only the template header and appends
the user's explicitly saved row with blank unspecified values. This reuses the
schema without importing its broken example or inventing defaults.

## October 5 wrapper integration findings

No source files were changed for the October 5 Box/cropping/run wrapper. The following source
behaviors were inspected while integrating public functions and are recorded for
later source work:

- `shared/config_utils.parse_analysis_params` omits the `crop` flag and some direct
  run flags. Its legacy `crop` coordinates are also not mapped to `crop_coords`.
  The wrapper resolves accepted run arguments at its boundary, preserves the legacy
  cell, and saves new crop tuples in canonical `crop_coords`.
- `MiniscopeDataManager.create` depends on an explicitly populated subclass registry.
  `miniscope/__init__.py` intentionally does not eagerly import the readers, and the
  direct pipeline module alone leaves the registry empty in this environment. The
  worker explicitly imports the existing UCLA/ONIX reader modules before calling
  the factory; it does not modify the factory or install replacements.
- `MiniscopePipeline.run` writes `data_manager.coords` back to `crop_coords` after
  preprocessing. The preprocessor stores a coordinate dictionary; the CSV helper
  stringifies it. `get_coords_dict_from_analysis_params` expects positional values
  and indexes with `0..3`, so that dictionary is not reusable as a crop tuple.
  Worker writeback is confined to its run-local execution CSV. Frozen input CSVs
  and the researcher's canonical tuple remain intact.
- `MovieIO.save_movie` and processor estimate saving use fixed output names in
  `saved_movies`. This can replace earlier results in direct reruns. The wrapper
  gives each run private recording copies and outputs, without changing script behavior.
- `ComputePipeline.run` catches subject exceptions and returns only successful
  subjects. An unhandled adapter relying on process exit alone could show false
  success. The wrapper verifies the returned experiment entry.
- The Box downloader's `make_auth` does not make a live account request before
  saying connected. `verify_path` accepts any nonempty directory as complete;
  `download_file` reads one listing page and ignores recursive failure return values.
  GUI setup verifies real account/folder calls. The recording wrapper gathers all
  listing pages, stages and verifies transfers, and invokes the unchanged downloader
  with a validated flat file listing. Download failures remain visible.

These are integration findings, not changes to the core scientific code. Additional
source failures remain visible in run logs with Failed status; they are not silently
repaired by the GUI.


## Suggested source changes (not implemented)

The user requested these suggestions while keeping `src` untouched. They remain
proposals requiring their own explicit approval, separate from the approved
October 6 changes below.
For `shared/file_downloader.py`, the smallest useful changes would be:

1. Iterate every `get_folder_items` page, including nested folders. A recording with
   more than one page currently loses files silently.
2. Propagate recursive download failures and preserve a safe failure result/message.
   A parent download can currently report success after a child fails. The special
   Miniscope branch also assumes every child is a file instead of recursing into folders.
3. Replace the nonempty-directory readiness test and existence-only file skip with
   expected-file/size checks, stage file writes, and publish completed files atomically.
   Interrupted downloads can otherwise be accepted as complete on retry.

The wrapper implements guards at its own boundary and reuses the source transfer
function. These proposed core changes would benefit command-line users too, but
require separate explicit permission and regression tests before implementation.

The GUI's connection-saving issue was in wrapper defaults and lifecycle: remembering
was opt-in, startup did not reuse saved credentials, and opening an experiment's
wizard showed account fields again. Defaults, restart reuse, and separate account/
recording-folder flows are now covered by regression tests.


The download wrapper now requires a server-issued file review and explicit
confirmation before transferring bytes. Selections persist separately from download
completeness, and crop previews/private run copies are restricted to the confirmed
paths. A cooperative cancellation flag is checked during streaming and verification;
existing source transfer code remains unchanged.

A further source improvement worth evaluating is timestamp/event alignment for
movie subsets: `UCLADataManager._get_timestamps` reads the entire timestamp file,
while movie selection can load only some files. Timing-dependent workflows should
explicitly map selected frame ranges to their timestamps/events. This was inspected
and recorded, not changed in `src`; mean-fluorescence fixture tests verify only the
selected frame values, not full-recording timing or synchronization.


## CaImAn export filename compatibility (October 5)

The installed CaImAn `load_CNMF` accepts `.h5` and `.hdf5`, while `CNMF.save`
requires a `.hdf5` filename. The GUI stages exports using `estimates.hdf5`, then
renames only that new copy to the chosen filename. Tests reload named `.h5`,
`.HDF5`, and `.hdf5` outputs and compare the unchanged source bytes. This is a
wrapper workaround; no CaImAn or ACE `src` change was made.

Run review also rejects a CNMF-E estimates filename without the required lowercase
`.hdf5` extension before a long extraction starts. Curation exports can use `.h5`
or `.HDF5` because their new staged file can safely be renamed after saving.

## October 6 event, output, and headless integration

The original worker collected numeric arrays and skipped dictionary-shaped
calcium event indices. The worker now uses an explicit export contract in
[`gui/run_outputs.py`](https://github.com/emelon8/experiment_analysis/blob/main/gui/run_outputs.py): `output-inventory.json` lists
exported products with file/key/shape information or a `not_computed` reason.
Events use `calcium-events.json`; component IDs, component traces, original and
filtered temporal projections use `postprocessing.npz`; sparse footprints use
`components.npz`; available quality arrays use `diagnostics.npz`.
`diagnostics.json` records effective settings, projection replacement, stage-input
semantics, and unavailable diagnostics. Correlation/PNR plot diagnostics and
motion-correction shifts are explicitly unavailable rather than silently omitted.

Review still follows the initial headless run. Saving curated copies alone does
not update earlier events. The explicit **Save curated copies & detect events**
action reloads saved curated estimates and calls the existing derivative
detector, now static, with reviewed derivative/threshold settings. Its JSON export
includes original zero-based IDs, the curated-row mapping, and provenance.
Automatic pre-event checkpointing and multimodal continuation remain future work.

Approved source changes removed the forced `inline=False` assignments in
[`shared/cli_utils.py`](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/shared/cli_utils.py) and
[`pipelines/miniscope.py`](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/miniscope.py).
Headless policy still suppresses GUI inspections and respects the scientific
`inline` setting: `True` replaces the final temporal projection with filtered data;
`False` keeps the original projection. Miniscope CLI defaults to `True`, direct
pipeline API defaults to `False`. Explicit `inline=False` preserves previous
headless behavior. Phases/spectra remain before filtering and events use `C`;
their inputs and scientific calculations are unchanged.
