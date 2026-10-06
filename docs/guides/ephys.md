# Ephys Pipeline

The ephys pipeline loads a selected EEG/LFP channel through the registered data
manager for the recording format. Shipped managers cover Neuralynx, RHS2116,
and ONIX data. Artifact removal, filtering, phase computation, and plotting are
optional. The [experiment GUI](experiment_gui.md) runs a reviewed single-channel
analysis and saves an explicit output inventory.

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
    channel_name="PFCLFPvsCBEEG",
    filter_type="butter",
    filter_range=[0.5, 4],
    compute_phases=True,
    headless=True,
)

channel = api.ephys_data_manager.get_channel("PFCLFPvsCBEEG")
signal = channel.signal
filtered_signal = channel.signal_filtered
phases = channel.phases
```

The direct Python API uses its arguments and signature defaults; it does not
automatically apply the pipeline-level settings from `analysis_parameters.csv`.
The module CLI merges supported CSV settings into its CLI defaults. In the API,
filtering, phases, and plots are off by default. The CLI enables channel and
spectrogram plots unless `--headless` suppresses them. See the
[pipeline reference](../api/pipelines.md) for parameter loading.

## Pipeline Steps

1. **Channel Loading**: Reads Neuralynx `.ncs` files and organizes by channel name
2. **Artifact Removal**: Optional removal of electrical artifacts
3. **Filtering**: When `filter_type` is set, bandpass-filter the requested channel
   with the selected filter family and `filter_range` cutoffs
4. **Phase Analysis**: When `compute_phases=True`, compute the Hilbert phase of
   `channel.signal`
5. **Visualization**: Optional channel, spectrogram, and phase plots; disabled in
   headless mode

The high-level loader stores filtered data in `channel.signal_filtered` while
retaining `channel.signal`. Phase computation uses `channel.signal`, so enabling
filtering does not make those phases describe the filtered frequency band. If you
need band-specific phases, use the lower-level manager with deliberate signal
replacement before computing phases. This differs from miniscope `inline`,
which controls replacement of the temporal movie projection.

## Key Parameters in `analysis_parameters.csv`

| Parameter | Description | Example |
|-----------|-------------|---------|
| `channel_name` | Neuralynx channel to analyze | `PFCLFPvsCBEEG` |
| `filter_type` | Filter family; blank/None skips filtering | `butter` |
| `filter_range` | Filter frequency range [low, high] | `[0.5, 4]` |
| `compute_phases` | Compute Hilbert phase from `channel.signal` | `True` |
| `zero time (s)` | Reference time for alignment | `0` |
| `baseline period (min)` | Baseline duration | `10` |

## Data Organization

Raw data paths are specified in `experiments.csv` under the `ephys directory`
column; the selected manager determines the required file layout.

Direct API calls leave channels and events in memory for the caller to consume.
The GUI worker additionally saves `ephys.npz`, `ephys-events.json`,
`diagnostics.json`, and `output-inventory.json` in its isolated run folder. The
inventory identifies available filtered signals and phases, with reasons for
missing outputs. These worker exports are separate from the core pipeline API.
