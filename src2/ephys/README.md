# Ephys Pipeline

The ephys pipeline processes Neuralynx electrophysiology recordings, including channel loading, artifact removal, filtering, spectral analysis, and phase computation.

## Quick Start

### Prerequisites

1. Set up your project's `.env` file (see root [README](../../README.md)):
   ```
   PROJECT_REPO=/path/to/your/project
   ```

2. Ensure your project has:
   - `experiments.csv` with experiment metadata
   - `analysis_parameters.csv` with pipeline parameters

### Command Line

```bash
# Run using analysis_parameters.csv from PROJECT_REPO (set in .env)
python -m src2.ephys.ephys_pipeline --line-num 96

# Run in headless mode
python -m src2.ephys.ephys_pipeline --line-num 96 --headless
```

### Python API

```python
from src2.ephys.ephys_pipeline import EphysPipeline
from src2.shared.config_utils import load_analysis_params

params = load_analysis_params(96)
api = EphysPipeline()
api.run(line_num=96, **params)
```

## Pipeline Steps

1. **Channel Loading**: Reads Neuralynx `.ncs` files and organizes by channel name
2. **Artifact Removal**: Optional removal of electrical artifacts
3. **Filtering**: Bandpass, lowpass, or highpass filtering with configurable parameters
4. **Spectrogram**: Multi-taper spectral analysis with sliding windows
5. **Phase Analysis**: Hilbert transform phase computation for specified frequency bands
6. **Visualization**: Channel traces and spectrogram plotting

## Key Parameters in `analysis_parameters.csv`

| Parameter | Description | Example |
|-----------|-------------|---------|
| `channel_name` | Neuralynx channel to analyze | `PFCLFPvsCBEEG` |
| `filter_type` | Filter type (`bandpass`, `lowpass`, `highpass`) | `bandpass` |
| `filter_range` | Filter frequency range [low, high] | `[0.5, 4]` |
| `zero time (s)` | Reference time for alignment | `0` |
| `baseline period (min)` | Baseline duration | `10` |

## Data Organization

Raw data paths are specified in `experiments.csv` under the `ephys directory` column. The pipeline reads `.ncs` files from these directories.