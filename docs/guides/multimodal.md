# Multimodal Pipeline

The multimodal pipeline combines ephys and calcium imaging analysis for synchronized electrophysiology and miniscope recordings. It handles timestamp alignment between Neuralynx and Miniscope systems, and performs phase-based calcium event analysis.

## Quick Start

### Prerequisites

1. Ensure your project directory has:
   - `experiments.csv` with both ephys and miniscope paths
   - `analysis_parameters.csv` with parameters for both modalities

### Command Line

```bash
# Run with explicit project path
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/project --data-path /my/raw_data

# Run with explicit project and data paths
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/project --data-path /my/raw_data

# Run in headless mode
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/project --data-path /my/raw_data --headless
```

### Python API

```python
from aceneurotools.pipelines.multimodal import MultimodalPipeline

api = MultimodalPipeline()
api.run(
    line_num=97, 
    project_path="/my/project",
    data_path="/my/raw_data",
    headless=True
)
```

## Pipeline Steps

1. **Ephys Processing**: Loads the requested channel and applies requested processing.
2. **Miniscope Processing**: Runs the full miniscope pipeline (preprocessing, CNMF-E, postprocessing)
3. **Timestamp Synchronization**: Aligns Neuralynx and Miniscope timestamps using TTL events
4. **TTL Event Detection**: Identifies and optionally cleans TTL synchronization events
5. **Phase-Based Event Analysis**: Computes requested calcium event phases relative to available oscillation phases.
6. **Phase Histograms**: Generates circular histograms of calcium event phase distributions

## Key Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `delete_TTLs` | Remove problematic TTL events | `True` |
| `fix_TTL_gaps` | Correct gaps in TTL timing | `True` |
| `only_experiment_events` | Restrict to experimental time window | `False` |
| `all_TTL_events` | Use all detected TTL events | `True` |
| `ca_events` | Analyze calcium events | `True` |
| `time_range` | Time window to analyze (seconds) | `None` |

The combined pipeline accepts a selected subset of ephys and calcium options;
check its [run signature](../api/pipelines.md) before forwarding settings.
The table above gives shared command-line defaults, which the GUI also inherits.
Direct Python defaults differ: `fix_TTL_gaps=False`, `only_experiment_events=True`,
`ca_events=False`, and `save_estimates=True`. The shared command defaults instead
set `save_estimates=False`; enable estimates saving explicitly for later review.
Filtering is off unless `filter_type` is supplied, and event-phase analysis is
conditional on the requested events/phases. The steps below describe capabilities,
not a promise that every output is computed for every run.

## Data Requirements

The `experiments.csv` must contain both:
- `calcium imaging directory`: Path to miniscope recordings
- `ephys directory`: Path to Neuralynx recordings

Both directories should contain data from the same synchronized recording session.


## TTL synchronization and gap detection

TTL pulses are synchronization markers used to map movie frames to electrical
recording times. Verify that the recordings belong to the same session, their
frame rate is correct, and the pulse mapping matches the acquisition. The reader
may instead use the shared ONIX hardware clock. Inspect aligned frame times and
`low_confidence_periods` before accepting results. Gap-repair settings change
alignment behavior and require acquisition-specific review; they do not prove
that missing synchronization data has been recovered correctly.

For GUI runs, review both input lists and the enabled alignment/event options.
Results stay in separate `.ace-runs` folders. See [the workbench guide](../gui.md).
