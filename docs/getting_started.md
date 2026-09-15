# Getting started with ACE-NeuroTools

This guide shows how to install ACE-NeuroTools, organize project metadata and raw data, and run your first pipeline.

## 1. Prerequisites

- **micromamba or mamba**
- **CaImAn from conda-forge**, installed by the environment file

## 2. Install ACE-NeuroTools

Clone the repository, create its supported environment, and install the checkout in editable mode:

```bash
git clone https://github.com/emelon8/experiment_analysis.git
cd experiment_analysis
micromamba create -n aceneurotools -f conda-lock.yml  # Linux or Windows
micromamba activate aceneurotools
pip install --no-deps -e .
```

Do not run `pip install caiman`: that name on PyPI belongs to unrelated software. The neuroscience CaImAn package is supplied by conda-forge.

The committed lock covers Linux and Windows. On macOS, create from `environment.yml` instead; that platform has not yet been locked or QA-tested.

## 3. Create project configuration

Generate starter configuration and a metadata template in a separate project directory:

```bash
python -m aceneurotools.init --project-path /path/to/project
```

Copy `experiments_template.csv` to `experiments.csv`. The initializer also creates `lab_config.json` and `stats_config.json`; edit their example values before using the `ace-neuro` launcher.

Each project must contain `experiments.csv`, keyed by its `line number` column. An optional `analysis_parameters.csv` can supply per-experiment processing settings.

See [Data management](guides/data_management.md) for the metadata columns and template locations.

## 4. Organize raw data

`project_path` is the directory containing `experiments.csv` and configuration. `data_path` is the root under which relative raw-data paths are resolved.

Supported inputs include:

- **Miniscope data:** UCLA V3 videos with metadata and timestamp files, or UCLA V4/ONIX start-time, clock, and raw files.
- **Electrophysiology data:** Neuralynx NEV and NCS files, or RHS2116/ONIX start-time and raw files.

Relative values in the `ephys directory` and `calcium imaging directory` columns are resolved under `data_path`. Absolute paths remain absolute.

Pass both paths explicitly for real data. If omitted, defaults derive from `ACE_NEUROTOOLS_DATA` when set, or from the current working directory; ACE-NeuroTools does not load `.env` files.

## 5. Pass pipeline parameters

The miniscope, ephys, and multimodal APIs accept positional-or-keyword parameters through `run(...)`. Keyword arguments are recommended for clarity.

### Python API

Omitted values use the defaults in the selected `run(...)` signature. CSV values are not merged automatically.

```python
from pathlib import Path

from aceneurotools.pipelines.miniscope import MiniscopePipeline

pipeline = MiniscopePipeline()
pipeline.run(
    line_num=96,
    project_path=Path("/path/to/project"),
    data_path=Path("/path/to/raw_data"),
    filenames=["0.avi"],
    run_CNMFE=True,
    headless=True,
)
```

To use per-experiment CSV settings, load them explicitly and keep only options accepted by the target pipeline:

```python
from pathlib import Path

from aceneurotools.pipelines.ephys import EphysPipeline
from aceneurotools.shared.cli_utils import run_allowed_keys
from aceneurotools.shared.config_utils import load_analysis_params

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

`load_analysis_params` converts recognized, nonempty columns into a combined pipeline-options dictionary. Low-level CaImAn fields in the same CSV are read later by miniscope components.

### Pipeline module CLIs

The `ephys`, `miniscope`, and `multimodal` module entry points accept `--line-num`, `--project-path`, optional `--data-path`, and `--headless`.

They start with CLI-specific defaults, overlay CSV keys accepted by that pipeline, then apply the common CLI values. The CLI defaults can differ from the Python method defaults.

Use Python or `analysis_parameters.csv` for analysis options without dedicated flags. If the CSV exists, it must contain the requested `line_num`.

### Parameter reference

- Run `help(MiniscopePipeline.run)` in Python, using the equivalent class for ephys or multimodal analysis.
- See the [pipeline API reference](api/pipelines.md).

## 6. Run a pipeline

These commands pass both project and raw-data paths explicitly. Adjust processing options in `analysis_parameters.csv`, or use the Python API for full control.

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

## 7. Follow the tutorials

Each tutorial requires both `experiments.csv` and `analysis_parameters.csv` under `project_path`, even though the latter is optional for the runtime itself.

- [Miniscope processing](notebooks/miniscope_pipeline_tutorial.ipynb)
- [Ephys processing](notebooks/ephys_pipeline_tutorial.ipynb)
- [Multimodal alignment](notebooks/multimodal_alignment_tutorial.ipynb)

## 8. Further resources

- [Documentation home](index.md)
- [Examples](examples.md)
- [Optional Box integration](guides/data_management.md#optional-box-cloud-integration)
