# Getting Started with ACE-NeuroTools

Welcome to the Experiment Analysis pipeline! This guide will help you set up your environment, organize your data, and run your first analysis.

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

## 3a. Passing parameters into the pipelines (read this)

Every pipeline is driven by **keyword arguments** to `run()`. There are three ways those kwargs get set; they stack in this order (later steps override earlier ones):

| Source | What it sets | When to use |
|--------|----------------|-------------|
| **1. Defaults in code** | Built-in defaults inside `EphysPipeline.run`, `MiniscopePipeline.run`, `MultimodalPipeline.run` | Starting point; see [API — Pipelines](api/pipelines.md) or `help(EphysPipeline.run)` in Python. |
| **`analysis_parameters.csv`** | Per–line-number overrides for the same kwarg names (via `load_analysis_params`) | Reproducible, shareable settings per experiment row. Column names match kwargs where possible (see `aceneurotools.config.config_utils.parse_analysis_params`). |
| **Your call** | Explicit arguments to `run(...)` or a dict you merge yourself | Final say: pass any kwarg the pipeline accepts. |

**Always required (for real data):**

- `line_num` — row in `experiments.csv` / `analysis_parameters.csv`
- `project_path` — directory containing those CSVs
- `data_path` — raw data root (strongly recommended; if omitted, the library may fall back to a path under the repo)

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
    run_CNMFE=True,
    headless=True,
)
```

**Python — merge CSV row, then override**

```python
from aceneurotools.config.config_utils import load_analysis_params
from aceneurotools.pipelines.ephys import EphysPipeline

project = Path("/path/to/project")
params = load_analysis_params(96, project_path=project)
params.update(
    project_path=project,
    data_path=Path("/path/to/raw_data"),
    headless=True,
    filter_type="butter",
    filter_range=[0.5, 4.0],
)
EphysPipeline().run(**params)
```

`load_analysis_params` returns only keys present in your CSV; empty cells are skipped so pipeline defaults still apply.

**Command line — only a few flags; the rest comes from defaults + CSV**

The `python -m aceneurotools.pipelines.*` entry points accept **`--line-num`**, **`--project-path`**, optional **`--data-path`**, and usually **`--headless`**. They build a `run_params` dict (defaults), then **`run_params.update(load_analysis_params(...))`**, then apply CLI path/headless overrides. You **cannot** set arbitrary kwargs (e.g. `filter_range`) from the CLI unless you add flags or use the Python API / CSV.

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

Paths are **`project_path`** and **`data_path`** — there are no hidden environment variables or `.env` files. See **§3a** for how paths combine with other parameters.

### Option 1: Command line (scripts and HPC)

Only path-related flags plus `headless`; other behavior comes from **defaults + `analysis_parameters.csv`** (see §3a).

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
)
```

> **Note:** If `data_path` is omitted, it may default to a path under the repository; always pass it explicitly for real experiments.

---

## 5. Running Your First Pipeline

### Miniscope Analysis
Executes preprocessing, motion correction, source extraction (CNMF-E), and post-processing.
```bash
python -m aceneurotools.pipelines.miniscope --line-num 96 --project-path /path/to/project
```

### Ephys Analysis
Loads ephys channels, filters signals, and generates spectrograms.
```bash
python -m aceneurotools.pipelines.ephys --line-num 96 --project-path /path/to/project
```

### Multimodal (Synchronized) Analysis
Aligns miniscope and ephys data based on TTL pulses and performs synchronized analysis.
```bash
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /path/to/project
```

---

## 6. Resources and Documentation
- **Docs home**: [index.md](index.md) (includes tutorial links).
- **Examples**: [examples.md](examples.md).
- **Box integration**: See the [Data Management Guide](guides/data_management.md#optional-box-cloud-integration) for setup instructions.
