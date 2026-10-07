# Multimodal Pipeline

The multimodal pipeline combines ephys and calcium imaging analysis for synchronized electrophysiology and miniscope recordings. It handles timestamp alignment between Neuralynx and Miniscope systems, and performs phase-based calcium event analysis.

This pipeline is available through the Python API and CLI. The
[experiment GUI](experiment_gui.md) runs miniscope and ephys separately; it does
not provide a multimodal run or automatic continuation from curated estimates.

## Quick Start

### Prerequisites

1. Ensure your project directory has:
   - `experiments.csv` with both ephys and miniscope paths
   - `analysis_parameters.csv` with parameters for both modalities

Select an existing `line number` experiment identifier with `--line-num`; it is
not the physical CSV row number. Both modalities need valid timing metadata
from the same recording session.

### Command Line

```bash
# Run with explicit project path
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/project

# Run with explicit project and data paths
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/project --data-path /my/raw_data

# Run in headless mode
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/project --headless
```

### Python API

```python
from aceneurotools.pipelines.multimodal import MultimodalPipeline

api = MultimodalPipeline()
api.run(
    line_num=97,
    project_path="/my/project",
    data_path="/my/raw_data",
    miniscope_filenames=["0.avi"],
    run_CNMFE=True,
    find_calcium_events=True,
    compute_miniscope_phase=True,
    ca_events=True,
    fix_TTL_gaps=True,
    only_experiment_events=False,
    inline=False,
    headless=True,
)

aligned_calcium_times = api.t_ca_im
event_phases = api.ca_events_phases_ephys
```

These explicit flags opt into calcium-event alignment and gap correction, which
are disabled by default in direct Python calls. The CLI has different defaults
for several synchronization options, as shown below. Direct `run()` calls use
their signature defaults and supplied kwargs rather than automatically merging
every run flag from `analysis_parameters.csv`.

## Pipeline Steps

1. **Ephys Processing**: Runs the full ephys pipeline (channel loading, filtering, phase analysis)
2. **Miniscope Processing**: Runs the full miniscope pipeline (preprocessing, CNMF-E, postprocessing)
3. **Timestamp Synchronization**: Aligns Neuralynx and Miniscope timestamps using TTL events
4. **TTL Mapping**: Maps aligned frame/event times to ephys indices
5. **Phase-Based Event Analysis**: Computes calcium event phases relative to ephys oscillations
6. **Phase Histograms**: Generates circular histograms when calcium-event phases are available

## TTL Synchronization and Gap Detection

Synchronization uses Neuralynx TTL events and miniscope timing metadata.
`delete_TTLs` controls cleanup, `fix_TTL_gaps` enables correction of timing gaps,
and `only_experiment_events` restricts the synchronization events used. Review
the aligned `t_ca_im` and `low_confidence_periods` returned on the pipeline
before interpreting event-phase relationships.

`all_TTL_events` controls mapping all synchronized TTL/frame events to ephys
indices. `ca_events=True` additionally maps detected calcium-event indices and
computes their ephys and miniscope phases. Keep `find_calcium_events` and
`compute_miniscope_phase` enabled when requesting those event-phase products.

Calcium event indices preserve the detector's coordinates: peaks in `C` for
`zeroth` or in `np.diff(C, n=1 or 2)` for derivatives. No derivative frame
offset is added. Account for this convention when assessing alignment.

## Headless Runs and Filtering

`headless=True` suppresses ephys plotting, motion-correction inspection,
parameter plots, and the pipeline's component-selection dialog. It preserves
`inline`, which defaults to `False` for both multimodal API and CLI calls.
When miniscope filtering is enabled, `inline=True` replaces the final temporal
projection with the filtered signal; `False` retains the unfiltered projection
and keeps filtered data separately.

The miniscope postprocessor computes its phases and spectra before filtering,
and detects calcium events from component traces `C`. An inline replacement
does not change these products already computed earlier in the run.

## Key Parameters

| Parameter | Description | Python API default | CLI default |
| --- | --- | --- | --- |
| `delete_TTLs` | Remove problematic TTL events | `True` | `True` |
| `fix_TTL_gaps` | Correct gaps in TTL timing | `False` | `True` |
| `only_experiment_events` | Restrict synchronization to experimental events | `True` | `False` |
| `all_TTL_events` | Map all synchronized TTL events | `True` | `True` |
| `ca_events` | Map calcium events and compute event phases | `False` | `True` |
| `inline` | Replace final miniscope projection with filtered data | `False` | `False` |
| `time_range` | Accepted argument; currently not used by `run()` | `None` | `None` |

Use the [API signature](../api/pipelines.md#multimodal-pipeline) for supported
ephys and miniscope arguments; movie names use `miniscope_filenames`. The current
core CSV mapper does not load the multimodal synchronization flags or
`miniscope_filenames`. The CLI offers project, data, experiment, and headless
flags, so custom synchronization choices require explicit Python arguments.

## Data Requirements

The `experiments.csv` must contain both:

- `calcium imaging directory`: Path to miniscope recordings
- `ephys directory`: Path to Neuralynx recordings

Both directories should contain data from the same synchronized recording session.

## Curated Estimates and Saved Results

The complete multimodal run extracts neurons and performs its configured
postprocessing before synchronization. The embedded GUI can subsequently save
curated estimates and recompute calcium events, but that export does not update
existing multimodal phases, indices, or histograms. `MultimodalPipeline.run()`
has no curated-estimates input or resume checkpoint. A fresh full run will
extract neurons again; it will not automatically consume the curated HDF5.

For analysis from curated estimates, the new curated event file and its
`neuron_ids` mapping must be supplied deliberately to a separate downstream
analysis. The GUI currently provides that event export, not a full synchronized
rerun. Preserve the selected threshold, derivative-index convention, and
original component IDs when carrying results between stages.

`run()` stores synchronized times, low-confidence periods, mapped ephys event
indices, event phases, and histogram arrays on the pipeline object. It does not
automatically export all of them as a results archive. The explicit
`output-inventory.json` contract in the GUI applies to its four supported
individual workflows, not this multimodal API/CLI.
