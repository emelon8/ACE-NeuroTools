# Miniscope Pipeline

The miniscope pipeline performs calcium imaging analysis using CaImAn, including preprocessing (cropping, detrending, DF/F), motion correction, CNMF-E source extraction, and postprocessing (component evaluation, event detection, phase analysis).

## Quick Start

### Prerequisites

1. Ensure your project directory has `experiments.csv` with a `line number` value matching the one you will run. `analysis_parameters.csv` is optional for the runtime, but recommended when you need per-experiment CaImAn settings or crop coordinates.
2. Point `--data-path` at the root containing the recording paths listed in `experiments.csv`.

### Command Line

```bash
# Replace 96 with an experiment ID from the line number column
python -m aceneurotools.pipelines.miniscope --line-num 96 --project-path /my/project --data-path /my/raw_data

# Run in headless mode (no GUI)
python -m aceneurotools.pipelines.miniscope --line-num 96 --project-path /my/project --data-path /my/raw_data --headless
```

The module command runs CNMF-E by default. Motion correction is optional; enable it through recognized CSV settings or the Python API.

### Python API

```python
from aceneurotools.pipelines.miniscope import MiniscopePipeline

pipeline = MiniscopePipeline()
pipeline.run(
    line_num=96,
    project_path="/my/project",
    data_path="/my/raw_data",
    crop=False,  # analyze the full movie; add crop coordinates if needed
    run_CNMFE=True,
    save_estimates=True,
    headless=True,
)
```

Direct Python calls do not merge `analysis_parameters.csv` into `run(...)`. The Python defaults leave CNMF-E and motion correction off. The example explicitly enables CNMF-E and skips cropping. Add `apply_motion_correction=True` if your recording needs it; set `crop=True` with valid `crop_coords=(x0, y0, x1, y1)` to analyze only part of the movie.

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
