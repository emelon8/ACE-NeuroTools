# Examples and workflows

These examples show common ways to run ACE-NeuroTools from Python, batch jobs, and interactive notebooks.

Python calls use `run(...)` defaults plus the arguments you pass. Module CLIs use separate defaults, recognized CSV overrides, and common CLI values.

See [Pass pipeline parameters](getting_started.md#5-pass-pipeline-parameters) before adapting these snippets.

## 1. Explicit-path Python API

The [explicit-path example on GitHub](https://github.com/emelon8/ACE-NeuroTools/blob/main/examples/explicit_paths_demo.py) contains templates for all three modality pipelines.

Set `project_path` and `data_path` explicitly to avoid fallback path resolution:

```python
from aceneurotools.pipelines.miniscope import MiniscopePipeline

pipeline = MiniscopePipeline()
pipeline.run(
    line_num=96,
    project_path="/path/to/project",
    data_path="/path/to/raw_data",
    crop=False,
    run_CNMFE=True,
    save_estimates=True,
    headless=True,
)
```

This Python call runs source extraction on the full movie and saves estimates when it succeeds. The example script leaves its pipeline calls commented out. Set its placeholder paths and uncomment only the calls you want to run.

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


## 3. Batch processing

Each modality CLI invocation processes one `line number` identifier from `experiments.csv`. A shell loop can run several identifiers sequentially:

```bash
for line_num in 96 97 101; do
  python -m aceneurotools.pipelines.ephys \
    --line-num "$line_num" \
    --project-path /path/to/project \
    --data-path /path/to/raw_data \
    --headless
done
```

The separate `ace-neuro` launcher also accepts multiple identifiers with `--line-nums` for configured compute and statistics workflows.

## 4. Optional Box integration

When local data is missing, configured Box integration can download it if the metadata row contains the relevant folder ID and the optional Box SDK and credentials are available.

See [Optional Box cloud integration](guides/data_management.md#optional-box-cloud-integration) for setup instructions.

## 5. Interactive tutorials

The notebooks explain `project_path` for CSV configuration and `data_path` for raw recordings before running a pipeline.

Canonical sources live in the top-level `notebooks/` directory. Read the Docs synchronizes them before building; for local builds, first run `scripts/sync_notebooks_for_docs.sh`.

- [Miniscope processing](notebooks/miniscope_pipeline_tutorial.ipynb)
- [Electrophysiology processing](notebooks/ephys_pipeline_tutorial.ipynb)
- [Multimodal alignment](notebooks/multimodal_alignment_tutorial.ipynb)

!!! tip
    Use `help(MiniscopePipeline.run)` or browse the [pipeline API reference](api/pipelines.md) for accepted parameters.

## 6. Review extraction and recompute curated events

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
