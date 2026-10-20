# Calcium Imaging Pipeline

The calcium imaging pipeline performs calcium imaging analysis using CaImAn, including preprocessing (cropping, detrending, DF/F), motion correction, CNMF-E source extraction, and postprocessing (component evaluation, event detection, phase analysis).

## Quick Start

### Prerequisites

1. Ensure your project directory has:
   - `experiments.csv` with experiment metadata
   - `analysis_parameters.csv` with CaImAn and pipeline parameters

### Command Line

```bash
# Run with explicit project path
python -m aceneurotools.pipelines.calcium_imaging --line-num 96 --project-path /my/project

# Run with explicit project and data paths
python -m aceneurotools.pipelines.calcium_imaging --line-num 96 --project-path /my/project --data-path /my/raw_data

# Run in headless mode (no GUI)
python -m aceneurotools.pipelines.calcium_imaging --line-num 96 --project-path /my/project --headless
```

### Python API

```python
from aceneurotools.pipelines.calcium_imaging import CalciumImagingPipeline

api = CalciumImagingPipeline()
api.run(
    line_num=96,
    project_path="/my/project",
    data_path="/my/raw_data",
    headless=True
)
```

## Pipeline Steps

### 1. Preprocessing (`CalciumImagingPreprocessor`)
- **Cropping**: Interactive GUI or automatic (headless) using `crop_coords` from `analysis_parameters.csv`
- **Detrending**: Linear or median-based photobleaching correction
- **DF/F**: Delta F over F or sqrt(F) normalization

### 2. Processing (`CalciumImagingProcessor`)
- **Motion Correction**: Rigid or piecewise-rigid via CaImAn
- **CNMF-E**: Constrained non-negative matrix factorization for source extraction
- **Parameter Tuning**: Interactive plots for `gSig`, `min_corr`, `min_pnr`, etc.

### 3. Postprocessing (`CalciumImagingPostprocessor`)
- **Component Evaluation**: Interactive GUI to accept/reject detected neurons
- **Event Detection**: Calcium transient identification
- **Phase Analysis**: Hilbert transform phase computation
- **Spectrograms**: Multi-taper spectral analysis

## Headless Mode

When `headless=True`:
- Crop GUI is bypassed; coordinates from `analysis_parameters.csv` are used directly
- Component evaluation GUI is skipped
- Motion correction inspection is disabled
- All matplotlib plots are suppressed (uses `Agg` backend)
- Detrend comparison plots are suppressed

> **Note**: For headless cropping, ensure your `analysis_parameters.csv` has `crop_coords` coordinates (e.g., `"(67, 503, 555, 61)"`). If missing, the crop step is skipped with a warning. You can also pass coordinates directly via `crop_coords=(x0, y0, x1, y1)` in the Python API.

## Key Parameters in `analysis_parameters.csv`

| Parameter | Description | Example |
|-----------|-------------|---------|
| `crop_coords` | Crop coordinates (x0, y0, x1, y1) | `"(67, 503, 555, 61)"` |
| `gSig` | Gaussian kernel half-size | `(3, 3)` |
| `min_corr` | Minimum correlation threshold | `0.85` |
| `min_pnr` | Minimum peak-to-noise ratio | `10` |
| `rf` | Half-size of patch | `25` |
| `stride` | Overlap between patches | `10` |
| `decay_time` | Transient decay time (s) | `0.4` |

## Data Organization

Raw data is found via `experiments.csv` paths. Processed outputs are saved to `saved_movies/` within each experiment's calcium imaging directory.
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
