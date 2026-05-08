# Ephys Pipeline

The ephys pipeline processes Neuralynx electrophysiology recordings, including channel loading, artifact removal, filtering, spectral analysis, and phase computation.

## Quick Start

### Prerequisites

1. Ensure your project directory has:
   - `experiments.csv` with experiment metadata
   - `analysis_parameters.csv` with pipeline parameters

### Command Line

```bash
# Run with explicit project path
python -m aceneurotools.pipelines.ephys --line-num 96 --project-path /my/project

# Run with explicit project and data paths
python -m aceneurotools.pipelines.ephys --line-num 96 --project-path /my/project --data-path /my/raw_data

# Run in headless mode
python -m aceneurotools.pipelines.ephys --line-num 96 --project-path /my/project --headless
```

### Python API

```python
from aceneurotools.pipelines.ephys import EphysPipeline

api = EphysPipeline()
api.run(
    line_num=96, 
    project_path="/my/project",
    data_path="/my/raw_data",
    channel_name='PFCLFPvsCBEEG'
)
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