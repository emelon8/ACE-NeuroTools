# Multimodal alignment

Use this workflow when a miniscope video and an electrical recording came from the same session. It runs both analyses and places their time stamps on a comparable time line. Neuralynx/UCLA recordings use recorded synchronization pulses (TTL pulses); ONIX recordings can use their shared hardware clock. Calcium-event phase analysis is available when the required events and phase signals have been computed.

## Quick Start

### Prerequisites

1. Ensure `experiments.csv` has a row with the same `line number` for both recording paths. The raw recordings must be from one synchronized session.
2. Give `--data-path` the root containing the paths in that row. `analysis_parameters.csv` is optional for module commands, but an existing file must include the requested ID.
3. Confirm the ephys channel name and that the chosen recording format supplies timestamps or sync pulses. The default channel name is only an example.

### Command Line

```bash
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/project --data-path /my/raw_data

# Run in headless mode
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/project --data-path /my/raw_data --headless
```

### Python API

```python
from aceneurotools.pipelines.multimodal import MultimodalPipeline

pipeline = MultimodalPipeline()
pipeline.run(
    line_num=97,
    project_path="/my/project",
    data_path="/my/raw_data",
    channel_name="CBvsPCEEG",  # replace with a channel in your recording
    save_estimates=True,
    headless=True,
)
```

The Python call uses its method defaults plus these arguments. It does not merge `analysis_parameters.csv` settings automatically. Use `ca_events=True` when you need calcium-event phase results and have valid event and phase arrays.

## Pipeline Steps

1. **Load ephys**: Read the selected channel. Artifact removal, filtering, and plots run only when their options are enabled.
2. **Process miniscope video**: Preprocess and run CNMF-E with current multimodal defaults. Motion correction is enabled by default; cropping needs usable coordinates or an interactive GUI.
3. **Align times**: Use recorded sync pulses or compatible hardware-clock timing to match frames with ephys samples. Low-confidence alignment periods are recorded on the Python result object.
4. **Analyze calcium events when requested**: If event and phase data are available, map events onto the ephys time line and build phase histograms.

## Key Parameters

| Option | Direct Python `run(...)` default | Module command default | Effect |
| --- | --- | --- | --- |
| `filter_type` | `None` | `None` | Ephys filtering is skipped until a family such as `butter` is set. |
| `apply_motion_correction` | `True` | `True` | Corrects movement in miniscope video. |
| `run_CNMFE` | `True` | `True` | Attempts cell extraction. |
| `save_estimates` | `True` | `False` | Controls saving `estimates.hdf5`; the module command does not save it by default. |
| `fix_TTL_gaps` | `False` | `True` | Interpolates missing sync pulses when enabled. |
| `ca_events` | `False` | `True` | Requests calcium-event mapping; phase results still require suitable input arrays. |
| `only_experiment_events` | `True` | `False` | Limits sync events to the experiment window when enabled. |

`MultimodalPipeline.run(...)` exposes a selected set of ephys and miniscope options. It does not accept every argument of the two underlying pipelines. See the [multimodal API reference](../api/multimodal.md) for the accepted parameters. The CLI merges only recognized CSV options into its own defaults.

## Data Requirements

The selected `experiments.csv` row must contain both:

- `calcium imaging directory`: Path to miniscope recordings
- `ephys directory`: Path to ephys recordings

Both directories should contain data from the same synchronized recording session.
