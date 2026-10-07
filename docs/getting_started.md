# Getting Started with ACE-NeuroTools

Set up the scientific environment, create a CSV project, then choose the experiment GUI, a pipeline CLI, or the Python API.

---

## 1. Prerequisites

* **Python 3.10+** (Recommended: 3.10.19)
* **Conda/Mamba** (For managing dependencies)
* **CaImAn** (Core dependency for miniscope analysis)

---

## 2. Installation

Clone the repository and install the package in editable mode:

```bash
git clone https://github.com/emelon8/experiment_analysis.git
cd experiment_analysis

# Recommended: Use the provided environment file
conda env create -f linux_environment.yml
conda activate caiman

# Install the package
pip install -e .
```

---

## 3. Data Organization

The pipeline relies on a structured project directory. Each project should contain:

### A. Project Repository (`project_path`)
This directory holds your configuration files:
- `experiments.csv`: Master list of every experiment/recording session.
- `analysis_parameters.csv`: Parameter overrides (cropping, filtering, etc.) for specific experiments.

### B. Shared Data Storage (`data_path`)
This is where your raw experimental data lives:
- **Miniscope Data**: `.avi` files, `metaData.json`, or ONIX-style `.csv/.raw` files.
- **Ephys Data**: `.ncs` files or ONIX-style binary data.

Path fields inside `experiments.csv` (for example **ephys directory** and **calcium imaging directory**) are resolved **relative to `data_path`**, not inside `project_path`.

---

### C. Start a new CSV project

Copy the bundled templates into a new project folder:

```bash
mkdir -p /path/to/project
cp src/aceneurotools/shared/metadata_templates/experiments_template.csv /path/to/project/experiments.csv
cp src/aceneurotools/shared/metadata_templates/analysis_parameters_template.csv /path/to/project/analysis_parameters.csv
```

Replace the example rows with your recordings and scientific settings. Each CSV
uses `line number` to identify the same experiment; it is an identifier, not a
physical file line. Keep required headers, match identifiers across both files,
and set recording paths relative to your raw-data root (or use absolute paths).
See [Data management](guides/data_management.md) for column and path details.

The separate `python -m aceneurotools.init --project-path /path/to/project`
command prepares `lab_config.json`, `stats_config.json`, and a smaller
`experiments_template.csv` for the compute/statistics workflow. It does **not**
create `analysis_parameters.csv` or a finished experiment project. Use the bundled
CSV templates above for the GUI and individual analysis pipelines.

### D. Open the experiment GUI

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

## 3a. Passing parameters into the pipelines

Use named arguments to `run()` so each setting is visible. The individual pipeline
CLIs and direct Python calls assemble those arguments differently:

| Entry point | Run setting precedence |
|-------------|------------------------|
| **Module CLI** (`python -m aceneurotools.pipelines.*`) | CLI's default dictionary → supported nonempty CSV values → explicit CLI paths/headless flag → headless GUI suppression. |
| **Direct Python** (`Pipeline().run(...)`) | Method defaults → arguments you supply. Call `load_analysis_params` and merge the returned values yourself to apply CSV run settings. |
| **Experiment GUI** | Supported run defaults and saved CSV values, shown as effective arguments in **Review & run**; interactive pipeline dialogs are disabled for the worker. |

Managers still load experiment metadata and scientific analysis parameters from the
project CSVs. For Miniscope, CaImAn settings and fallback crop coordinates are read
there even in a direct API call. This does not automatically apply every CSV column
to `run()` arguments. `load_analysis_params` recognizes a specific set of names;
for example `filter_data` maps to `filter_miniscope_data`, `spectrogram` maps to
`compute_miniscope_spectrogram`, and `method` maps to `df_over_f_method`.

Defaults can also differ between entry points:

| Miniscope setting | Direct `MiniscopePipeline.run()` | Miniscope module CLI / GUI CNMF-E mode |
|-------------------|--------------------------------|-------------------------------------|
| `run_CNMFE` | `False` | `True` |
| `inline` | `False` | `True` |
| `detrend_method` | `"median"` | `None` |
| `parallel` / `n_processes` | `False` / `12` | `True` / `6` |
| `save_CNMFE_params` | `False` | `True` |

Set these explicitly or save the desired CSV values when comparing runs. In
particular, a bare Python Miniscope call does **not** request CNMF-E extraction.

**Supply these for reproducible analyses:**

- `line_num` — experiment identifier in the CSVs' `line number` column
- `project_path` — directory containing those CSVs
- `data_path` — raw data root; supply it explicitly to avoid current-directory or environment-based path fallbacks

**Python — pass kwargs directly**

```python
from pathlib import Path
from aceneurotools.pipelines.miniscope import MiniscopePipeline

api = MiniscopePipeline()
api.run(
    line_num=96,
    project_path=Path("/path/to/project"),
    data_path=Path("/path/to/raw_data"),
    filenames=["0.avi"],
    crop=False,  # Use the full frame; otherwise supply or save crop coordinates
    run_CNMFE=True,
    inline=False,  # Keep the unfiltered final temporal projection
    headless=True,
)
```

**Python — merge CSV row, then override**

```python
from pathlib import Path

from aceneurotools.config.config_utils import load_analysis_params
from aceneurotools.pipelines.ephys import EphysPipeline

project = Path("/path/to/project")
params = load_analysis_params(96, project_path=project)
params.update(
    line_num=96,
    project_path=project,
    data_path=Path("/path/to/raw_data"),
    headless=True,
    filter_type="butter",
    filter_range=[0.5, 4.0],
)
# A shared CSV row can contain Miniscope-only keys; pass only Ephys arguments.
from aceneurotools.shared.cli_utils import run_allowed_keys

allowed = run_allowed_keys(EphysPipeline.run)
EphysPipeline().run(**{key: value for key, value in params.items() if key in allowed})
```

`load_analysis_params` returns recognized nonempty settings; it does not return `line_num` or paths. Empty cells leave the chosen entry point's defaults in effect.

**Command line — only a few flags; the rest comes from defaults + CSV**

The Miniscope, Ephys, and Multimodal module entry points require **`--line-num`** and **`--project-path`**, and accept optional **`--data-path`** and **`--headless`**. They merge supported CSV settings into a default dictionary and apply the command-line paths and headless flag. Other run arguments (for example `filter_range` or `inline`) must be set through supported CSV columns or the Python API.

**Where to see every parameter**

- Docstrings: `help(MiniscopePipeline.run)` (same pattern for ephys and multimodal).
- [API Reference — Pipelines](api/pipelines.md).

---

## 3b. Tutorials (Jupyter + documentation site)

Step-by-step notebooks stress-test this layout: they **assert both CSVs exist** under `project_path` before any pipeline runs.

| Topic | In the docs site | Notebook source in repo |
|-------|------------------|-------------------------|
| Miniscope | [Tutorial](https://aceneurotools.readthedocs.io/en/latest/notebooks/miniscope_pipeline_tutorial/) | `notebooks/miniscope_pipeline_tutorial.ipynb` |
| Ephys | [Tutorial](https://aceneurotools.readthedocs.io/en/latest/notebooks/ephys_pipeline_tutorial/) | `notebooks/ephys_pipeline_tutorial.ipynb` |
| Multimodal | [Tutorial](https://aceneurotools.readthedocs.io/en/latest/notebooks/multimodal_alignment_tutorial/) | `notebooks/multimodal_alignment_tutorial.ipynb` |

---

## 4. Configuring paths (still explicit)

For the individual pipelines, pass **`project_path`** and **`data_path`** explicitly. The separate `ace-neuro` compute/statistics command reads an explicit `lab_config.json` (or looks for it in the current directory). See **§3a** for run parameter precedence.

### Option 1: Command line (scripts and HPC)

The individual pipeline CLIs accept experiment identity, path, and headless flags; other behavior comes from defaults and supported CSV settings (see §3a).

```bash
python -m aceneurotools.pipelines.miniscope \
  --line-num 96 \
  --project-path /path/to/your/project \
  --data-path /path/to/your/raw_data \
  --headless
```

### Option 2: Programmatic API (notebooks and scripts)

Pass **all** kwargs to `run()` — see §3a for the full pattern.

```python
from aceneurotools.pipelines.miniscope import MiniscopePipeline

api = MiniscopePipeline()
api.run(
    line_num=96,
    project_path="/path/to/project",
    data_path="/path/to/data",
    crop=False,
    run_CNMFE=True,
    inline=False,
    headless=True,
)
```

> **Note:** If `data_path` is omitted, it may default to a path under the repository; always pass it explicitly for real experiments.

---

## 5. Running Your First Pipeline

### Miniscope Analysis
Runs preprocessing, optional motion correction, CNMF-E extraction, and postprocessing according to the merged settings.
```bash
python -m aceneurotools.pipelines.miniscope --line-num 96 --project-path /path/to/project --data-path /path/to/raw_data
```

### Ephys Analysis
Loads ephys channels, filters signals, and generates spectrograms.
```bash
python -m aceneurotools.pipelines.ephys --line-num 96 --project-path /path/to/project --data-path /path/to/raw_data
```

### Multimodal (Synchronized) Analysis
Aligns miniscope and ephys data based on TTL pulses and performs synchronized analysis.
```bash
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /path/to/project --data-path /path/to/raw_data
```

---

## 6. Review neurons and inspect outputs

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

## 7. Resources and Documentation
- **Docs home**: [index.md](index.md) (includes tutorial links).
- **Examples**: [examples.md](examples.md).
- **Box integration**: See the [Data Management Guide](guides/data_management.md#optional-box-cloud-integration) for setup instructions.
