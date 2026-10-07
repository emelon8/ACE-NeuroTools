# Getting started with ACE-NeuroTools

This guide starts with one recording, a spreadsheet row that points to it, and a command that analyzes it. The examples use a UCLA V3 miniscope video; change the paths and experiment ID to match your own files. Miniscope analysis can take minutes to hours and create large intermediate movies, depending on recording length and processing choices.

## 1. Prerequisites

- A terminal: the application where you paste the commands below. On Windows, use the terminal configured by micromamba.
- [Git](https://git-scm.com/install/) to copy the repository to your computer. `git clone` in step 2 does that copying.
- [micromamba](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html) to create the analysis environment. Check `git --version` and `micromamba --version` in a new terminal before continuing.

CaImAn, the neuroscience package used for cell extraction, is installed by the environment file; you do not need to install it separately.

## 2. Install ACE-NeuroTools

Paste these commands in your terminal. `pip install --no-deps -e .` registers this local checkout so its commands work while you edit the project:

```bash
git clone https://github.com/emelon8/ACE-NeuroTools.git
cd ACE-NeuroTools
micromamba create -n aceneurotools -f conda-lock.yml  # Linux or Windows
micromamba activate aceneurotools
pip install --no-deps -e .
```

Do not run `pip install caiman`: that name on PyPI belongs to unrelated software. The neuroscience CaImAn package is supplied by conda-forge.

The committed lock covers Linux and Windows. On macOS, create from `environment.yml` instead; that platform has not yet been locked or QA-tested.

On macOS, replace the `micromamba create ... conda-lock.yml` line above with `micromamba create -f environment.yml`. Keep the activation and `pip install` lines. If activation says your shell is not configured, finish the shell setup in the [micromamba installation guide](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html), then reopen the terminal.

## 3. Create project configuration

Generate starter configuration and a metadata template in a separate project directory:

```bash
python -m aceneurotools.init --project-path /path/to/project
```

Copy the generated `experiments_template.csv` to `experiments.csv` in the same folder. A file manager or spreadsheet editor can do the copy. Replace the sample rows with your recording information before running anything. The initializer also creates `lab_config.json` and `stats_config.json` for the separate `ace-neuro` compute/statistics launcher; edit their example values before using that launcher.

Each project must contain `experiments.csv`. The `line number` column is an experiment ID, not a spreadsheet row position. `analysis_parameters.csv` is optional for the modality commands. If you create it, use matching IDs.

For a UCLA V3 miniscope recording under `/path/to/raw_data/Rat01/session1`, set these cells in one row of `experiments.csv`:

| Column | Example value | Meaning |
| --- | --- | --- |
| `line number` | `96` | The ID used with `--line-num 96` |
| `calcium imaging directory` | `Rat01/session1` | Folder under the raw-data root containing the recording |
| `Box Calcium Folder ID` | blank | Leave blank when the files are already on your computer |

Keep the template's other columns. Replace these example values with a real recording and its ID. For ephys, also fill `ephys directory` and use an actual channel name from the recording.

See [Data management](guides/data_management.md) for the metadata columns and template locations.

### Open the experiment GUI

From the repository root:

```bash
./launch-gui --check
./launch-gui --project /path/to/project
```

The launcher finds an existing scientific Python environment and opens
`http://127.0.0.1:8780/`. With no `--project`, it opens the checkout's `data` project
when present. The launcher can reuse a running server; use **Open project** to
switch projects in that server. It never installs dependencies. If environment
discovery fails, activate your CaImAn environment and run
`python scripts/run_gui.py --project /path/to/project` (default port 8765).

Choose an experiment, review **Data & settings** and **Run settings**, save changes,
then choose **Review & run**. CNMF-E setup identifies the movie, crop, and estimates
output before execution. Each run preserves its reviewed inputs under
`<project>/.ace-runs/<run-id>/`. See the [experiment GUI guide](guides/experiment_gui.md)
for Box setup, run review, and results.


## 4. Organize raw data

`project_path` is the directory containing `experiments.csv` and configuration. `data_path` is the root under which relative raw-data paths are resolved.

For the example row above, the folders can look like this:

```text
/path/to/project/
└── experiments.csv
/path/to/raw_data/
└── Rat01/
    └── session1/
        ├── metaData.json
        ├── timeStamps.csv
        └── Miniscope/
            └── 0.avi
```

The UCLA V3 manager needs its video, metadata, and timestamp file for a useful run. Confirm the named files exist before running the command. Keep enough free space under the recording folder for derived movies and results.

Supported inputs include:

- **Miniscope data:** UCLA V3 videos with metadata and timestamp files, or UCLA V4/ONIX start-time, clock, and raw files.
- **Electrophysiology data:** Neuralynx NEV and NCS files, or RHS2116/ONIX start-time and raw files.

Relative values in the `ephys directory` and `calcium imaging directory` columns are resolved under `data_path`. Absolute paths remain absolute.

Pass both paths explicitly for real data. If omitted, defaults derive from `ACE_NEUROTOOLS_DATA` when set, or from the current working directory; ACE-NeuroTools does not load `.env` files.

## 5. Pass pipeline parameters

The commands in step 6 are the simplest entry point. They accept `--line-num` for the experiment ID, `--project-path` for the CSV folder, `--data-path` for raw files, and optional `--headless` to run without pop-up windows.

| Parameter file state | What a module command does |
| --- | --- |
| No `analysis_parameters.csv` | Uses its built-in processing defaults. |
| File exists with a row matching the chosen ID | Uses recognized nonempty values from that row over its defaults. |
| File exists but has no matching ID | Stops with an error; add the row or remove the optional file. |

The direct Python API has different defaults and does not automatically merge CSV options. See [For Python users](#8-for-python-users) after the first-run steps.

Miniscope CLI and GUI extraction default to `run_CNMFE=True` and `inline=True`.
Direct miniscope Python calls default to `False` for both. Headless mode preserves
`inline`; when enabled, it replaces the final temporal projection with filtered
data. Events use component traces `C`, and phases/spectra are computed before
projection filtering. See the [pipeline reference](api/pipelines.md).

## 6. Run a pipeline

These commands pass both project and raw-data paths explicitly. Adjust processing options in `analysis_parameters.csv`, or use the Python API for full control.

Replace every `/path/to/...` value with an actual folder on your machine. Use one command for the kind of recording in your selected CSV row.

### Miniscope analysis

The module CLI preprocesses miniscope data and runs CNMF-E with its CLI defaults. Motion correction runs only when enabled in the CSV or Python API.

```bash
python -m aceneurotools.pipelines.miniscope \
  --line-num 96 \
  --project-path /path/to/project \
  --data-path /path/to/raw_data
```

### Electrophysiology analysis

The module CLI loads the selected ephys channel and, in interactive mode, plots its signal and spectrogram. Configure filtering through the CSV or Python API.

```bash
python -m aceneurotools.pipelines.ephys \
  --line-num 96 \
  --project-path /path/to/project \
  --data-path /path/to/raw_data
```

### Multimodal analysis

The module CLI runs both modality pipelines, then aligns Neuralynx/UCLA recordings with TTLs or ONIX recordings with their shared hardware clock.

```bash
python -m aceneurotools.pipelines.multimodal \
  --line-num 97 \
  --project-path /path/to/project \
  --data-path /path/to/raw_data
```

Add `--headless` to any command to disable interactive GUIs for batch or HPC execution.

### Check the result

After a miniscope run with CNMF-E and saving enabled, look under the recording's `saved_movies/` folder for `estimates.hdf5`. If that file is absent, check whether saving was enabled and read the command's error output. The ephys module command opens signal and spectrogram windows in interactive mode; `--headless` disables those plots. A multimodal run keeps its alignment results in Python attributes but does not export a report file automatically. The [output map](guides/data_management.md#where-results-appear) lists other generated files and their locations.

### Review neurons and inspect outputs

GUI extraction runs their configured postprocessing before embedded neuron review.
After extraction, open **Neurons**, record keep/reject decisions, and choose
**Finish review**. **Save curated copies & detect events** loads the saved curated
estimates and detects events for kept neurons with the derivative and threshold
shown there. It writes a new `calcium-events.json` with component ID mapping and
provenance. Saving curated copies alone does not recompute events; ephys and
multimodal results require separate runs. Original estimates and earlier outputs
are preserved.

**Results → Output inventory** lists events, component IDs, traces, footprints,
raw/filtered signals, and available diagnostics, with filenames/array keys or
missing-output reasons. These explicit inventories are a GUI worker export feature;
a direct Python call exposes result objects and data managers, and pipeline disk
outputs depend on its saving settings.

Headless mode respects `inline`: if Miniscope filtering runs, `inline=True`
replaces the final temporal projection with filtered data; `inline=False` retains
the unfiltered projection. Earlier headless runs forced `inline=False`; set it
explicitly to retain that behavior. Event detection uses component traces `C`;
phases and spectra are computed before projection filtering. Review both signal
versions and their diagnostics when interpreting outputs. See the
[Miniscope guide](guides/miniscope.md) and [GUI guide](guides/experiment_gui.md).


## 7. Follow the tutorials

Each tutorial requires both `experiments.csv` and `analysis_parameters.csv` under `project_path`, even though the latter is optional for the runtime itself.

- [Miniscope processing](notebooks/miniscope_pipeline_tutorial.ipynb)
- [Ephys processing](notebooks/ephys_pipeline_tutorial.ipynb)
- [Multimodal alignment](notebooks/multimodal_alignment_tutorial.ipynb)

## 8. For Python users

Python `run(...)` calls use the arguments you pass and the selected method's defaults. They do not automatically merge pipeline options from `analysis_parameters.csv`. Miniscope components can still read lower-level CaImAn fields from that CSV when it exists.

```python
from pathlib import Path

from aceneurotools.pipelines.miniscope import MiniscopePipeline

pipeline = MiniscopePipeline()
pipeline.run(
    line_num=96,
    project_path=Path("/path/to/project"),
    data_path=Path("/path/to/raw_data"),
    filenames=["0.avi"],
    crop=False,
    run_CNMFE=True,
    save_estimates=True,
    headless=True,
)
```

To use per-experiment CSV options in a Python call, load them explicitly and keep only options accepted by that pipeline:

```python
from pathlib import Path

from aceneurotools.pipelines.ephys import EphysPipeline
from aceneurotools.shared.cli_utils import run_allowed_keys
from aceneurotools.config.config_utils import load_analysis_params

line_num = 96
project = Path("/path/to/project")
params = load_analysis_params(line_num, project_path=project)
allowed = run_allowed_keys(EphysPipeline.run)
params = {key: value for key, value in params.items() if key in allowed}
params.update(filter_type="butter", filter_range=[0.5, 4.0])

EphysPipeline().run(
    line_num=line_num,
    project_path=project,
    data_path=Path("/path/to/raw_data"),
    headless=True,
    **params,
)
```

`load_analysis_params` needs an existing CSV with the requested ID. See the [pipeline API reference](api/pipelines.md) for accepted arguments, or run `help(MiniscopePipeline.run)` in Python with the equivalent class for ephys or multimodal analysis.

## 9. Further resources

- [Documentation home](index.md)
- [Examples](examples.md)
- [Optional Box integration](guides/data_management.md#optional-box-cloud-integration)
