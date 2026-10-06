# Examples & Workflows

Choose a GUI workflow for reviewed runs, a module CLI for batch execution, or the Python API for explicit control.

**Passing parameters:** direct Python calls use method defaults and arguments; module CLIs merge their own defaults with supported CSV settings. To apply CSV run settings in Python, load and merge them explicitly. Read [parameter precedence](getting_started.md#3a-passing-parameters-into-the-pipelines) before copying snippets below.

## 1. Explicit Paths API
**Script**: `examples/explicit_paths_demo.py`

This script contains commented starter calls for the three individual pipelines. Set its project/data paths and uncomment the calls you need. The example below explicitly enables CNMF-E; the method defaults to `run_CNMFE=False`.

```python
from aceneurotools.pipelines.miniscope import MiniscopePipeline

# Run with explicit project and data paths
api = MiniscopePipeline()
api.run(
    line_num=96,
    project_path="/path/to/project",
    data_path="/path/to/raw_data",
    filenames=["0.avi"],
    crop=False,  # Full frame; use crop=True with reviewed coordinates for a crop
    run_CNMFE=True,
    inline=False,
    headless=True,
)
```

## 2. Supercomputer (Slurm) Workflow
Save the following as your own `submit_job.slurm`, adapting paths and resources
to your cluster. The repository does not include that file. Activate the scientific
environment before submitting, or add your cluster's environment setup to the job.

```bash
#!/usr/bin/env bash
#SBATCH --job-name=ace-miniscope
#SBATCH --cpus-per-task=6
#SBATCH --mem=150G
#SBATCH --time=24:00:00
#SBATCH --output=ace-%j.log
set -euo pipefail

cd /path/to/experiment_analysis
python -m aceneurotools.pipelines.miniscope \
  --line-num 96 \
  --project-path /path/to/project \
  --data-path /path/to/raw_data \
  --headless
```

```bash
sbatch submit_job.slurm
```

Memory/time needs depend on movie size and settings; the values above are examples.
Save crop coordinates in the parameter CSV before a headless cropped run. The
Miniscope CLI defaults to extraction enabled and `inline=True`. Filtering still
runs in headless mode, and `inline=True` replaces the final temporal projection
with filtered data. To retain the older headless behavior, save `inline=False` in
the experiment's CSV settings or use a Python call with that argument. Events use
component traces `C`; phases and spectra precede projection filtering.

## 3. Data Integration Workflows

### Batch Processing
Use experiment identifiers from the CSV's `line number` column, rather than file
row positions. This shell example applies each experiment's supported CSV settings:

```bash
for line_num in 96 97; do
  python -m aceneurotools.pipelines.miniscope \
    --line-num "$line_num" \
    --project-path /path/to/project \
    --data-path /path/to/raw_data \
    --headless || break
done
```

Direct CLI runs use the pipeline's normal recording output paths. GUI runs instead
stage inputs and group their outputs under unique `.ace-runs` folders.

### Cloud Integration
The pipeline can automatically pull missing data from Box if configured. See the [Data Management Guide](guides/data_management.md#optional-box-cloud-integration) for setup instructions.

## 4. Interactive Tutorials

Notebooks emphasize **`project_path`** (CSVs) vs **`data_path`** (raw data) before running pipelines. They render on the docs site via **mkdocs-jupyter** ([Miniscope](https://aceneurotools.readthedocs.io/en/latest/notebooks/miniscope_pipeline_tutorial/), [Ephys](https://aceneurotools.readthedocs.io/en/latest/notebooks/ephys_pipeline_tutorial/), [Multimodal](https://aceneurotools.readthedocs.io/en/latest/notebooks/multimodal_alignment_tutorial/)).

| Notebook | In-repo after `scripts/sync_notebooks_for_docs.sh` |
|----------|-----------------------------------------------------|
| Miniscope | [notebooks/miniscope_pipeline_tutorial.ipynb](notebooks/miniscope_pipeline_tutorial.ipynb) |
| Ephys | [notebooks/ephys_pipeline_tutorial.ipynb](notebooks/ephys_pipeline_tutorial.ipynb) |
| Multimodal | [notebooks/multimodal_alignment_tutorial.ipynb](notebooks/multimodal_alignment_tutorial.ipynb) |

> [!TIP]
> **Docstrings:** use `help(MiniscopePipeline)` or the [API Reference](api/index.md).

## 5. Review extraction and recompute curated events

```bash
./launch-gui --project /path/to/project
```

1. Select the experiment and **Set up CNMF-E**. Review input movies, crop, extraction,
   saving, and run settings, then **Review & run**.
2. On completion, inspect **Results → Output inventory**. It reports exported event
   dictionaries, component IDs, signals, footprints, and available diagnostics, or
   explains why an output is unavailable.
3. Choose **Review extracted neurons**, record keep/reject decisions, then open
   **Finish review**. Check the derivative and event height threshold.
4. Choose **Save curated copies & detect events** to write curated estimates and
   new events for kept neurons. `calcium-events.json` records detector settings and
   the mapping from curated rows to original component IDs. Uncheck detection to
   save curated copies alone.

The extraction run performs event detection before embedded neuron review. Curated
export does not change those earlier results; the explicit detection action creates
a new event result in the curation folder. Ephys and multimodal analysis require
separate runs. See the [experiment GUI guide](guides/experiment_gui.md) for exact
filenames, event index conventions, and preserved provenance.
