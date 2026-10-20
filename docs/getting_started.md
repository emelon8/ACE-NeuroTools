# Command-line getting started

For the browser application, start with [Install and open ACE](gui_installation.md)
and [Use the experiment workbench](gui.md). This page is for analysts running
commands or Python scripts. Install the source in the full conda environment
using the [maintainer instructions](gui_installation.md#for-maintainers-install-the-current-source).

## 1. Prepare project files and recordings

Ask the lab for a prepared project and short recording first. To create starter
files yourself, run in the activated analysis environment:

```sh
python -m aceneurotools.init --project-path /path/to/project
```

Replace `/path/to/project` with your configuration folder. Copy the generated
`experiments_template.csv` to `experiments.csv` and replace its example row with
your own recording. The generated `lab_config.json` and `stats_config.json` are
for the separate `ace-neuro` compute/statistics launcher; their example study
values must be replaced before using that launcher.

`experiments.csv` is required. `analysis_parameters.csv` is optional for the
modality commands; absent files or rows leave the command-line defaults in effect.
Copy the [analysis template](https://github.com/emelon8/ACE-NeuroTools/blob/main/src/aceneurotools/shared/metadata_templates/analysis_parameters_template.csv)
if you need saved overrides. It must use the same `line number` IDs.
`load_analysis_params()` itself raises for a missing file; the modality commands
catch that missing-file error and use defaults. Direct Python calls require you
to merge those overrides explicitly.

For a UCLA V3 recording with movies in `/path/to/raw_data/Rat01/session1/Miniscope`,
metadata and timestamps in the original acquisition layout, set:

| Column in experiments.csv | Example |
| --- | --- |
| `line number` | `96` |
| `id` | `Rat01` |
| `date (YYMMDD)` | `240101` |
| `calcium imaging directory` | `Rat01/session1` |

Keep the template's remaining headers. Leave Box folder IDs blank for local-only
work. For ephys, supply `ephys directory`, `events filename`, and actual channel
names appropriate to your recording. The example ID `96` means the value in the
`line number` column, not physical spreadsheet row 96. Raw-data paths are resolved
under `data_path`; absolute recording paths are used directly.

## 2. Run one recording

Replace paths and ID below with your actual values. A full extraction can take
minutes to hours and create large intermediate files.

```sh
python -m aceneurotools.pipelines.calcium_imaging --line-num 96 --project-path /path/to/project --data-path /path/to/raw_data --headless
```

The calcium command enables CNMF-E extraction and estimates saving by default,
but selects only `0.avi` unless your saved `filenames` setting changes it. Set
`filenames` to `[]` to use all supported movie files. Review cropping, frame rate,
cell-detection, filtering, and motion settings for your recording. Headless mode
suppresses interactive review; it does not validate biological results.
If cropping is enabled without coordinates, the command-line pipeline warns and
skips cropping. The browser GUI instead requires a valid crop or **Apply crop = No**.

After successful extraction and saving, look for
`<calcium recording>/saved_movies/estimates.hdf5`. Its filename can be changed by
`save_CNMFE_estimates_filename`. Use the [GUI neuron review](gui.md#review-neurons-and-save-accepted-cells)
to inspect estimates. Direct pipeline runs write near the recording; GUI runs
copy recordings and keep outputs under the project's `.ace-runs` folders.

Other modality commands use the same explicit paths:

```sh
python -m aceneurotools.pipelines.ephys --line-num 96 --project-path /path/to/project --data-path /path/to/raw_data --headless
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /path/to/project --data-path /path/to/raw_data --headless
```

These examples need actual electrical channels and, for combined recordings,
verified synchronization information. See the [ephys](guides/ephys.md) and
[alignment](guides/multimodal.md) guides before running them.

## 3. Passing parameters into the pipelines

| Entry point | Effective settings |
| --- | --- |
| Modality command | Shared command defaults, then recognized nonblank CSV values, then explicit path/headless flags |
| Browser GUI | Shared command defaults and saved CSV values, with separate-window actions disabled; the review shows each source |
| Python `run(...)` | Explicit arguments and method defaults; it does not automatically merge CSV run switches |

The data managers can still read acquisition/algorithm metadata from the CSVs.
That does not make CSV run switches override explicit Python arguments. Python
and command defaults differ: direct calcium `run()` defaults to `run_CNMFE=False`
and `inline=False`, while the calcium command uses `True` for both.

A direct extraction example makes the requested steps explicit:

```python
from aceneurotools.pipelines.calcium_imaging import CalciumImagingPipeline

CalciumImagingPipeline().run(
    line_num=96,
    project_path="/path/to/project",
    data_path="/path/to/raw_data",
    filenames=[],
    crop=False,
    run_CNMFE=True,
    save_estimates=True,
    headless=True,
)
```

To merge saved parameters, filter to the selected method's accepted arguments;
a shared settings row can contain options for more than one pipeline:

```python
from pathlib import Path
from aceneurotools.shared.config_utils import load_analysis_params
from aceneurotools.shared.cli_utils import run_allowed_keys
from aceneurotools.pipelines.ephys import EphysPipeline

project = Path("/path/to/project")
allowed = run_allowed_keys(EphysPipeline.run)
params = {k: v for k, v in load_analysis_params(96, project_path=project).items() if k in allowed}
params.update(
    line_num=96,
    project_path=project,
    data_path=Path("/path/to/raw_data"),
    channel_name="YOUR_CHANNEL",
    filter_type="butter",
    filter_range=[0.5, 4.0],
    headless=True,
)
EphysPipeline().run(**params)
```

Replace `YOUR_CHANNEL` with an actual channel name. The module commands expose
only a few flags, not every run argument. Use saved settings or Python for other
options. See the [pipeline API](api/pipelines.md) for accepted arguments and the
[examples](examples.md) for notebooks.
