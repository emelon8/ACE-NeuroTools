# Miniscope Pipeline

The miniscope pipeline performs calcium imaging analysis using CaImAn, including preprocessing (cropping, detrending, DF/F), motion correction, CNMF-E source extraction, and postprocessing (component evaluation, event detection, phase analysis).

For the local application's crop, run-review, neuron-curation, and export workflow,
see the [Experiment GUI guide](experiment_gui.md).

## Quick Start

### Prerequisites

1. Ensure your project directory has:
   - `experiments.csv` with experiment metadata
   - `analysis_parameters.csv` with CaImAn and pipeline parameters

`line_num` selects the experiment's `line number` identifier, not its physical
line in the CSV. The examples use experiment 96; substitute an existing ID in
your project.

### Command Line

```bash
# Run with explicit project path
python -m aceneurotools.pipelines.miniscope --line-num 96 --project-path /my/project

# Run with explicit project and data paths
python -m aceneurotools.pipelines.miniscope --line-num 96 --project-path /my/project --data-path /my/raw_data

# Run in headless mode (no GUI)
python -m aceneurotools.pipelines.miniscope --line-num 96 --project-path /my/project --headless
```

### Python API

```python
from aceneurotools.pipelines.miniscope import MiniscopePipeline

api = MiniscopePipeline()
api.run(
    line_num=96,
    project_path="/my/project",
    data_path="/my/raw_data",
    filenames=["0.avi"],
    run_CNMFE=True,
    save_estimates=True,
    inline=False,
    headless=True,
)

# run() stores results on the pipeline; it does not return an output archive.
events = api.postprocessing_result.ca_events_idx
estimates = api.processing_result.CNMFE_obj.estimates
```

The Python API and CLI use different defaults. In particular, direct `run()`
defaults to `run_CNMFE=False` and `inline=False`; the miniscope CLI and GUI
inherit `run_CNMFE=True` and `inline=True`. Set these choices explicitly when
comparing workflows. The CLI merges its defaults with supported saved CSV
parameters. Calling `run()` directly does not automatically merge all run flags
from the parameter CSV; see [Pipelines API](../api/pipelines.md).

## Pipeline Steps

### 1. Preprocessing (`MiniscopePreprocessor`)

- **Cropping**: Interactive GUI or automatic (headless) using `crop_coords` from `analysis_parameters.csv`
- **Detrending**: Linear or median-based photobleaching correction
- **DF/F**: Delta F over F or sqrt(F) normalization

### 2. Processing (`MiniscopeProcessor`)

- **Motion Correction**: Rigid or piecewise-rigid via CaImAn
- **CNMF-E**: Constrained non-negative matrix factorization for source extraction
- **Parameter Tuning**: Interactive plots for `gSig`, `min_corr`, `min_pnr`, etc.

### 3. Postprocessing (`MiniscopePostprocessor`)

- **Component Evaluation**: Interactive GUI to accept/reject detected neurons
- **Event Detection**: Calcium transient identification
- **Phase Analysis**: Hilbert transform phase computation
- **Spectrograms**: Multi-taper spectral analysis

## Headless Mode

When `headless=True`:

- Crop GUI is bypassed; coordinates from `analysis_parameters.csv` are used directly
- Component evaluation GUI is skipped
- Motion correction inspection is disabled
- Matplotlib uses the `Agg` backend, so plots do not open windows
- Detrend comparison plots are suppressed
- `inline` keeps its configured value; headless mode does not disable filtering

For headless cropping, save valid `crop_coords` in `analysis_parameters.csv`,
or pass `crop_coords=(x0, y0, x1, y1)` explicitly. These are original-image pixel
bounds using the crop tool's bottom-left origin. The GUI crop tool validates
them against the recording. If coordinates are unavailable, the headless crop
step is skipped with a warning.

### Filtering semantics

With `filter_miniscope_data=True`, filtering runs in both interactive and
headless modes. `inline=True` replaces `projections.time` with the filtered
signal; `inline=False` leaves it unfiltered while retaining
`filter_object.filtered_data` separately. With filtering disabled, `inline`
does not replace the projection.

Earlier headless runs forced `inline=False`. Headless runs that now specify or
inherit `True` therefore produce a different final temporal projection. Set
`False` explicitly to retain the earlier behavior.

The postprocessor detects events from component traces `C`, then computes
spectra and phases from the movie's temporal projection **before filtering**.
Changing `inline` affects the final projection and subsequent consumers, not
those already-computed event, phase, or spectral products.

## Curated neurons and event detection

Interactive pipeline component selection occurs before event detection when
`remove_components_with_gui=True`. Headless execution disables that dialog.
The experiment GUI's embedded **Neurons** review happens after extraction and
its configured postprocessing have completed; it does not pause/resume the run.

In **Neurons → Finish review**, **Save curated copies** creates new estimates
without recomputing results. With **Detect calcium events from curated
estimates** enabled, **Save curated copies & detect events** reloads the saved
kept-neuron estimates and writes new `calcium-events.json` in the curation
folder. Review the derivative and threshold; they initially reflect current
experiment settings, which can differ from the original run. Existing results
remain separate. This export does not rerun phases, spectra, ephys, or
multimodal alignment.

Event indices are zero-based peaks in `C` for `zeroth`, `np.diff(C, n=1)` for
`first`, or `np.diff(C, n=2)` for `second`. The detector adds no derivative frame
offset. The curated event dictionary uses curated row indices; `neuron_ids`
maps them to the reviewed source's original component IDs.

## Key Parameters in `analysis_parameters.csv`

| Parameter | Description | Example |
|-----------|-------------|---------|
| `crop_coords` | Saved crop-tool pixel bounds (x0, y0, x1, y1) | `"(10, 10, 200, 150)"` |
| `gSig` | Gaussian kernel half-size | `(3, 3)` |
| `min_corr` | Minimum correlation threshold | `0.85` |
| `min_pnr` | Minimum peak-to-noise ratio | `10` |
| `rf` | Half-size of patch | `25` |
| `stride` | Overlap between patches | `10` |
| `decay_time` | Transient decay time (s) | `0.4` |
| `run_CNMFE` | Enable source extraction | `True` |
| `find_calcium_events` | Detect peaks in component traces | `True` |
| `derivative_for_estimates` | Event-detection derivative | `first` |
| `event_height` | Peak-height threshold | `5` |
| `inline` | Replace final temporal projection with filtered data | `False` |

The core CSV mapper uses `filter_data` for `filter_miniscope_data`,
`spectrogram` for `compute_miniscope_spectrogram`, and `method` for
`df_over_f_method`. The GUI also accepts the corresponding run-argument names.
Check effective settings before starting a run.

## Data Organization

Raw data is found via `experiments.csv` paths. Direct API/CLI runs save configured
movies, estimates, and CaImAn parameters to `saved_movies/` within the calcium
recording directory. Their postprocessing results are also available on the
pipeline's structured stage results and data manager; not every computed result
is automatically written to disk.

GUI runs instead copy inputs and save outputs under
`<project>/.ace-runs/<run-id>/`. A completed run's `output-inventory.json`
identifies exported events, component IDs/traces, sparse footprints,
unfiltered/filtered projections, timing, spectra/phases, and available
diagnostics, including reasons for unavailable outputs. See the
[GUI output guide](experiment_gui.md#output-inventory) for file names,
loading examples, and signal provenance. Curated exports use a separate unique
folder under the selected curation destination.
