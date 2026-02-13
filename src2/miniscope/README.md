# Miniscope Pipeline

The miniscope pipeline performs calcium imaging analysis using CaImAn, including preprocessing (cropping, detrending, DF/F), motion correction, CNMF-E source extraction, and postprocessing (component evaluation, event detection, phase analysis).

## Quick Start

### Prerequisites

1. Set up your project's `.env` file (see root [README](../../README.md)):
   ```
   PROJECT_REPO=/path/to/your/project
   ```

2. Ensure your project has:
   - `experiments.csv` with experiment metadata
   - `analysis_parameters.csv` with CaImAn and pipeline parameters

### Command Line

```bash
# Run using analysis_parameters.csv from PROJECT_REPO (set in .env)
python -m src2.miniscope.miniscope_pipeline --line-num 96

# Run in headless mode (no GUI) for batch processing
python -m src2.miniscope.miniscope_pipeline --line-num 96 --headless
```

### Python API

```python
from src2.miniscope.miniscope_pipeline import MiniscopePipeline
from src2.shared.config_utils import load_analysis_params

params = load_analysis_params(96)
api = MiniscopePipeline()
api.run(line_num=96, headless=True, **params)
```

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