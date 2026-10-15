# Pipelines API

This section details the high-level entry points for running the analysis workflows.

Each class exposes `run(...)`. Pass keyword arguments matching its signature.
`line_num` identifies the CSV's `line number` value, not a physical row offset.
Provide `project_path` explicitly, and `data_path` when recording paths need a
separate base directory.

## Parameters and defaults

Direct Python calls use the signature's defaults and explicit arguments.
Data managers still read recording metadata and CaImAn settings from the project,
but this does not merge every pipeline run flag into a direct `run()` call.
CLI modules merge CLI defaults with recognized nonblank CSV settings, then apply
explicit CLI flags and headless policy. See [Getting started](../getting_started.md)
for commands and environment setup.

To merge shared parameter CSV values into a Python call, filter them to the
chosen signature before applying your overrides:

```python
from pathlib import Path
from aceneurotools.pipelines.miniscope import MiniscopePipeline
from aceneurotools.shared.cli_utils import run_allowed_keys
from aceneurotools.config.config_utils import load_analysis_params

project = Path("/my/project")
pipeline = MiniscopePipeline()
csv_params = load_analysis_params(96, project_path=project)
allowed = run_allowed_keys(pipeline.run)
params = {key: value for key, value in csv_params.items() if key in allowed}
params.update(
    line_num=96,
    project_path=project,
    data_path=Path("/my/raw_data"),
    run_CNMFE=True,
    save_estimates=True,
    inline=False,
    headless=True,
)
pipeline.run(**params)
```

The core CSV mapper uses aliases `filter_data` → `filter_miniscope_data`,
`spectrogram` → `compute_miniscope_spectrogram`, and `method` → `df_over_f_method`.
It does not load every accepted argument, including multimodal synchronization
flags and `miniscope_filenames`; pass those explicitly in Python. The GUI run
review additionally accepts supported run-argument column names and shows each
effective value and its source.

Set scientific choices explicitly when comparing entry points:

| Setting | Direct miniscope API | Miniscope CLI / GUI | Multimodal API / CLI |
| --- | --- | --- | --- |
| `run_CNMFE` default | `False` | `True` | `True` |
| `inline` default | `False` | `True` | `False` |

Headless mode disables interactive windows while preserving the requested
`inline` setting. When filtering is enabled, `inline=True` replaces the final
temporal projection with filtered data; `False` retains the unfiltered
projection. Earlier headless calls always forced `False`; specify `False`
explicitly to retain that behavior. The miniscope postprocessor computes phases
and spectra before filtering and detects events from component traces `C`.

## Results and exports

`run()` on miniscope, ephys, and multimodal pipelines returns `None`; inspect the
pipeline's results and data managers after completion. Miniscope exposes
`preprocessing_result`, `processing_result`, and `postprocessing_result`.
For structured stage configuration, use `MiniscopePipeline.run_with_configs`
with `PreprocessConfig`, `ProcessConfig`, and `PostprocessConfig` from
`aceneurotools.miniscope.pipeline_results`.

Saved estimates, movies, and parameters are distinct from in-memory computed
results. Direct API/CLI calls do not automatically export every array or event
dictionary. The experiment GUI's supported runs add an explicit
[output inventory](../guides/experiment_gui.md#output-inventory), including
events, component IDs/traces, sparse footprints, raw/filtered signals, timing,
and available diagnostics with missing-output reasons.

GUI neuron curation writes separate estimates. Its optional event recomputation
reloads the curated HDF5 and writes new events for kept neurons. It does not
update earlier outputs or resume a full multimodal run. See the
[GUI guide](../guides/experiment_gui.md#review-neurons-and-recompute-calcium-events)
and [multimodal guide](../guides/multimodal.md#curated-estimates-and-saved-results)
for the supported boundaries and derivative-index convention.

## Miniscope Pipeline
::: aceneurotools.pipelines.miniscope.MiniscopePipeline

## Ephys Pipeline
::: aceneurotools.pipelines.ephys.EphysPipeline

## Multimodal Pipeline
::: aceneurotools.pipelines.multimodal.MultimodalPipeline
