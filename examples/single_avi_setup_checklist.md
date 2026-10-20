# Legacy single-AVI smoke test: maintainer reference

For nontechnical lab testing, use the [lab walkthrough](../docs/lab_walkthrough.md)
and [installed GUI guide](../docs/gui.md). This older script is a separate,
interactive source-checkout test of Box access and one UCLA-style AVI. It is
not a complete-recording analysis or the installed browser workflow.

**This script currently needs repair before use.** Its CSV lookups infer numeric
experiment IDs, then search for string IDs, so ordinary template-derived projects
can fail before download. Both lookups in `step_1_download_avi()` and
`step_3_report_estimates()` need consistent ID handling. The steps below describe
the intended legacy setup, not a verified working test. Use the GUI lab walkthrough
for acceptance testing until the script is repaired.

## 1. Prepare the environment

Follow [source installation](../docs/gui_installation.md#for-maintainers-install-the-current-source)
using `environment.yml` and the `aceneurotools` environment. The old
`linux_environment.yml` and `windows.yml` setup commands do not apply.

```sh
conda activate aceneurotools
python -c "import caiman, aceneurotools; print('imports OK')"
```

An import check alone does not validate a full scientific run. If installation
fails, preserve the error and repair that environment before continuing; do not
remove another environment named `caiman`.

## 2. Prepare Box access, if needed

Ask the lab administrator for an authorized Box application and access to the
recording. Copy `src/aceneurotools/shared/BLANK_box_credentials.py` to
`src/aceneurotools/shared/box_credentials.py` and fill in the CCG client ID,
client secret and user ID fields. Keep the file private; it is ignored by Git.
See [optional command-line Box integration](../docs/guides/data_management.md#optional-box-cloud-integration).

The template's `dev_token` variable is not used by its configured CCG `auth`.
Do not follow the former instruction to uncomment a numbered downloader line.
This checklist uses the template's CCG path only. For browser testing, download
recordings separately; the installed GUI does not use this credentials file.

## 3. Prepare project files

Use a separate practice project containing `experiments.csv` and
`analysis_parameters.csv`, with matching experiment IDs in `line number`.
This particular script requires both files even though modality commands can
run with defaults when the settings file is missing.

Supply the real recording's Box folder ID and `calcium imaging directory`.
Keep metadata and timestamps in the original acquisition layout. Get the
crop, cell scale, detection thresholds and indicator decay from the lab; the
template values are examples, not validated settings for every UCLA recording.
Do not assume historical rows in the repository refer to data you can access.

## 4. Intended script procedure (after repair)

Edit the four constants in [single_avi_smoke_test.py](single_avi_smoke_test.py):
`PROJECT_PATH` is the project folder, `DATA_PATH` is the raw-data root,
`LINE_NUM` is the experiment ID, and `AVI_FILENAME` is the selected movie.
For Windows paths use forward slashes or raw Python strings.

From the repository root in the activated environment:

```sh
python examples/single_avi_smoke_test.py
```

The script checks paths/credentials, downloads or finds the AVI, runs extraction,
and locates saved estimates. Its separate component-selection window uses
FreeSimpleGUI, not PySimpleGUI. If that import fails, repair the declared
`FreeSimpleGUI` dependency in the analysis environment; do not install an old
PySimpleGUI build. Report the exact `[smoke-test] FAILED at:` stage and error.

One-AVI results describe only that selected movie. For a complete recording,
use the [calcium guide](../docs/guides/calcium_imaging.md) and explicitly set
`filenames=[]` or list all intended movie segments. The default modality command
selects `0.avi`; changing commands alone does not select the whole session.
