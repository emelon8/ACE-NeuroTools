# Ephys Pipeline

The ephys pipeline processes Neuralynx electrophysiology recordings, including channel loading, artifact removal, filtering, spectral analysis, and phase computation.

## Quick Start

### Prerequisites

1. Ensure your project directory has `experiments.csv` with an ephys directory and a matching `line number` value. `analysis_parameters.csv` is optional for the runtime and can supply per-experiment settings.
2. Point `--data-path` at the root containing the recording paths listed in `experiments.csv`.

### Command Line

```bash
python -m aceneurotools.pipelines.ephys --line-num 96 --project-path /my/project --data-path /my/raw_data

# Run in headless mode
python -m aceneurotools.pipelines.ephys --line-num 96 --project-path /my/project --data-path /my/raw_data --headless
```

### Python API

```python
from aceneurotools.pipelines.ephys import EphysPipeline

api = EphysPipeline()
api.run(
    line_num=96,
    project_path="/my/project",
    data_path="/my/raw_data",
    channel_name="PFCLFPvsCBEEG",  # replace with a channel in your recording
    filter_type="butter",
    filter_range=[0.5, 4.0],  # frequencies in Hz
    plot_spectrogram=True,
)
```

This call filters one channel with a bandpass filter and plots its spectrogram. Python calls do not automatically use values from `analysis_parameters.csv`. The module command plots a channel and spectrogram by default in interactive mode; filtering and phase computation remain optional.

## Pipeline Steps

1. **Channel Loading**: Reads Neuralynx `.ncs` files and organizes by channel name
2. **Artifact Removal**: Optional removal of electrical artifacts
3. **Filtering**: Optional bandpass filtering when `filter_type` is set to a filter family such as `butter` or `fir`
4. **Spectrogram**: Optional multi-taper spectral analysis when plotting is enabled
5. **Phase Analysis**: Optional Hilbert transform phase computation when `compute_phases=True`
6. **Visualization**: Optional channel and spectrogram plots; the module CLI enables them in interactive mode

## Key Parameters in `analysis_parameters.csv`

| Parameter | Description | Example |
|-----------|-------------|---------|
| `channel_name` | Neuralynx channel to analyze | `PFCLFPvsCBEEG` |
| `filter_type` | Filter family (`butter` or `fir`); omit to skip filtering | `butter` |
| `filter_range` | Bandpass frequency cutoffs [low Hz, high Hz] | `[0.5, 4.0]` |
| `zero time (s)` | Reference time for alignment | `0` |
| `baseline period (min)` | Baseline duration | `10` |

## Data Organization

Raw data paths are specified in `experiments.csv` under the `ephys directory` column. The pipeline reads `.ncs` files from these directories.
