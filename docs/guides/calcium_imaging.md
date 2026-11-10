# Calcium imaging analysis

This pipeline reads supported UCLA/ONIX miniscope recordings and can crop,
normalize, correct motion, extract cell signals with CaImAn CNMF-E, and compute
postprocessing results. Which steps run depends on the settings.
For a click-by-click path, use the [experiment workbench](../gui.md).

## Quick start

Prepare `experiments.csv`, the complete recording, and recording-specific settings as
shown in [Getting started](../getting_started.md). `analysis_parameters.csv` is
optional for modality commands but is needed to store overrides.

```sh
python -m aceneurotools.pipelines.calcium_imaging --line-num 96 --project-path /my/project --data-path /my/raw_data --headless
```

Replace the paths and experiment ID. The command enables extraction and saves
estimates by default, selects `0.avi`, and does not enable motion correction by
default. Set `filenames=[]` in saved settings to process all supported movies.
Headless mode skips interactive cell selection; inspect the saved estimates
using [Neurons](../gui.md#review-neurons-and-save-accepted-cells).

Direct Python calls have different defaults. Request extraction explicitly:

```python
from aceneurotools.pipelines.calcium_imaging import CalciumImagingPipeline

CalciumImagingPipeline().run(
    line_num=96,
    project_path="/my/project",
    data_path="/my/raw_data",
    filenames=[],
    crop=False,
    run_CNMFE=True,
    save_estimates=True,
    headless=True,
)
```

This example uses the full frame. It does not enable motion correction or
fluorescence normalization. Choose those options to suit your acquisition.
Direct `run()` defaults to no extraction and does not automatically merge CSV
run switches; see [parameter precedence](../getting_started.md#3-passing-parameters-into-the-pipelines).

## Crop coordinates and settings

`crop_coords=(left, bottom, right, top)` uses original image pixels and a
bottom-left origin. For example, `(10, 20, 110, 120)` selects a 100 by 100 area
only if it fits the recording. Prefer drawing and saving it in the GUI.
The old `(67, 503, 555, 61)` example reversed its vertical bounds and is not a
valid GUI crop.

In headless command-line runs, missing coordinates cause a warning and skipped
cropping. Cancelling the desktop crop dialog skips cropping for that operation
and preserves the caller’s saved coordinate inputs. The browser GUI blocks an
invalid/missing crop until it is saved or disabled.

| Setting | Meaning |
| --- | --- |
| `run_CNMFE` | Extract cell signals |
| `apply_motion_correction` | Correct movement before extraction |
| `save_estimates` | Save estimates for later review |
| `save_CNMFE_params` | Save resolved CaImAn settings |
| `gSig`, `rf`, `stride`, `min_corr`, `min_pnr`, `decay_time` | Recording-specific cell scale, patches, thresholds and indicator decay in the analysis metadata |
| `find_calcium_events`, `derivative_for_estimates`, `event_height` | Event detection choices |

Use the [API](../api/calcium_imaging.md) for full details. GUI separate-window
plots and component-selection dialogs are disabled; use embedded Crop/Neurons.

## Outputs and interpretation

Successful saved extraction normally creates `saved_movies/estimates.hdf5` within
the calcium recording directory. CaImAn settings are `opts_caiman.json` when
saving is enabled. GUI runs place that recording copy under
`<project>/.ace-runs/<run-id>/recording/` and also export signals, footprints,
events and available diagnostics; consult [Results](../gui.md#find-and-reopen-results).
Those GUI exports are not automatically written by direct pipeline calls.

When motion correction runs (`apply_motion_correction`), the per-frame shifts
are also saved to `saved_movies/motion_correction_shifts.npz`, so the
correction can be inspected later without running it again. Saving the file does
not change any analysis result. Read it with
`aceneurotools.calcium_imaging.motion_correction_record.load_motion_correction_shifts`,
which returns a dictionary of arrays:

| Key | Contents | Present |
| --- | --- | --- |
| `shifts_rig` | Rigid shift per frame, float32, shape `(frames, 2)`. Column 0 is the row (vertical) axis, column 1 the column (horizontal) axis. Values are the correction CaImAn computed, the negative of the movement. For rigid runs this is the correction applied to the movie; for `pw_rigid` runs it comes from the rigid pass CaImAn uses to build the template, and the movie is corrected with the piecewise shifts. | Always, after motion correction |
| `x_shifts_els`, `y_shifts_els` | Piecewise shift per frame and patch, float32, shape `(frames, patches)`. Following CaImAn's naming, `x_shifts_els` is the **row** (vertical) axis and `y_shifts_els` the column (horizontal) axis; same sign as `shifts_rig`. Patches are ordered row by row over the patch grid. | `pw_rigid` runs |
| `total_template_rig`, `total_template_els` | Rigid and piecewise templates, float32 | Rigid always; piecewise for `pw_rigid` runs |
| `strides`, `overlaps`, `max_shifts`, `upsample_factor_grid`, `shifts_opencv` | Motion settings that locate each patch. With `shifts_opencv` false, CaImAn reports piecewise shifts on a grid refined by `upsample_factor_grid` | Always |
| `border_to_0` | CaImAn's largest shift rounded up, in pixels. It is not necessarily what was zeroed: before CNMF-E the pipeline zeroes `border_pix` pixels (saved in `opts_caiman.json`), which is this value unless `border_nan` is `'copy'` (CaImAn's default), in which case no border is zeroed | Always |
| `pw_rigid` | Whether piecewise-rigid correction was requested | Always |
| `frame_rate` | Frame rate in Hz | When the recording's frame rate is known |
| `source_movie` | Path of the movie the shifts were computed from | Always |
| `saved_at` | Time the file was written, UTC, ISO 8601 | Always |
| `skipped_attributes` | Names of values that could not be stored as numbers and were left out | Only when something was skipped |

`source_movie` names the input movie, not the run: every run with the same
preprocessing reads the same movie path. A later run without motion correction,
or one whose save fails, leaves an earlier file in place, so compare `saved_at`
with the time of the run, or use the path the run reports in
`ProcessingResult.motion_correction_shifts_filepath`, which is `None` when that
run did not write the file. The file is written to a temporary file, flushed to
disk and then renamed, so a save that fails with an error never leaves a partial
file; a run killed outright during the save can leave a hidden
`.motion_correction_shifts.npz.*.tmp` file in `saved_movies/`, which is safe to
delete. If the file cannot be written for any reason, the run prints a warning
and continues.

The core pipeline computes projection phases and spectra before filtering;
those describe the unfiltered projection even if `inline=True` replaces the
final projection with its filtered version. `inline=False` retains the original
projection and keeps filtered data separately. Headless mode respects `inline`.
Events are detected from component traces, not from the final movie projection.
Curating cells does not automatically replace earlier results.

## Naming and acquisition formats


Shared analysis uses `CalciumImagingPipeline`, `CalciumImagingDataManager`,
`CalciumImagingPreprocessor`, `CalciumImagingProcessor`,
`CalciumImagingPostprocessor`, and `FilterCalciumImagingData` under
`aceneurotools.calcium_imaging` (the pipeline lives in
`aceneurotools.pipelines.calcium_imaging`). The phase, filtering and spectrogram
options are `compute_calcium_imaging_phase`, `filter_calcium_imaging_data`, and
`compute_calcium_imaging_spectrogram`. Phase results use `calcium_imaging_phases`.
The multimodal pipeline uses `calcium_imaging_filenames` and exposes its shared
pipeline as `calcium_imaging_pipeline`.

The previous `Miniscope…` classes, module paths, option keywords and public
attributes remain compatibility aliases. Existing CSV column names and the
legacy CLI command (`python -m aceneurotools.pipelines.miniscope`) still work.
CSV settings also accept the new option names; if both spellings are present,
the new spelling takes precedence. Python calls that supply both spellings of
the same option raise `TypeError`. The GUI's persisted run kinds, output keys and
existing metadata directory columns retain their historical identifiers.

UCLA and ONIX readers remain in `aceneurotools.miniscope`; their hardware names,
timestamp synchronization and acquisition directory layouts are unchanged.
The shared data-manager base retains the historical protected adapter hooks
`_get_miniscope_metadata` and `_get_miniscope_events` for reader compatibility.

This is a naming change. It does not add a 2-photon acquisition reader, validate
a 2-photon dataset, or select different CaImAn/CNMF-E parameters. Use parameters
and a compatible reader appropriate to the acquisition; processing defaults
are unchanged.
