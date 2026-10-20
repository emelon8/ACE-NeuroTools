# Electrophysiology analysis

The ephys pipeline imports supported Neuralynx or RHS2116/ONIX recordings and
selects a named electrical channel. Artifact removal, filtering and phases are
optional. See the [GUI guide](../gui.md#review-and-run-an-analysis) for browser use.

## Quick start

Prepare `experiments.csv` and the complete recording as described in
[Getting started](../getting_started.md). Set the real `channel_name` in saved
analysis settings before using this command; the example channel default may
not exist in your recording.

```sh
python -m aceneurotools.pipelines.ephys --line-num 96 --project-path /my/project --data-path /my/raw_data --headless
```

`analysis_parameters.csv` is optional for this command; absent settings use
command defaults. Filtering and phase calculation are off by default. The command
normally requests channel/spectrogram plots, but headless mode suppresses them.

A Python example with explicit filtering:

```python
from aceneurotools.pipelines.ephys import EphysPipeline

pipeline = EphysPipeline()
pipeline.run(
    line_num=96,
    project_path="/my/project",
    data_path="/my/raw_data",
    channel_name="YOUR_CHANNEL",
    filter_type="butter",
    filter_range=[0.5, 4.0],
    compute_phases=True,
    headless=True,
)
channel = pipeline.ephys_data_manager.get_channel("YOUR_CHANNEL")
```

Replace `YOUR_CHANNEL` with the actual recording channel, and choose the
frequency range appropriate to the scientific question. Direct Python calls
use explicit arguments and method defaults, not an automatic CSV override merge.

## Settings

| Parameter | Meaning | Example |
| --- | --- | --- |
| `channel_name` | Actual channel name | `PFCLFPvsCBEEG` only if present |
| `filter_type` | Filter family; `None` skips filtering | `butter` or `fir` |
| `filter_range` | Bandpass cutoffs in Hz | `[0.5, 4.0]` |
| `compute_phases` | Calculate signal phase | `True` |
| `remove_artifacts` | Enable supported artifact removal | `False` by default |

`bandpass`, `lowpass`, and `highpass` are not valid ephys `filter_type` values.
The pipeline's filter uses a bandpass; lower-level filter APIs have separate
band-type controls. Direct Python `run()` also leaves plotting off unless enabled.

## Recording locations and results

The `ephys directory` in `experiments.csv` is resolved under `data_path`, or used
directly when absolute. Keep channel, event, and timing files together in their
acquisition layout. The requested channel must match what the reader imports.
GUI runs export `ephys.npz` and `ephys-events.json` in a separate run folder,
with optional arrays identified in the [output inventory](../gui.md#find-and-reopen-results).
Direct Python `run()` returns `None`. Retrieve the selected channel from
`pipeline.ephys_data_manager` after the run, as shown above. Direct calls do not
automatically write the GUI's exported inventory and archives.
