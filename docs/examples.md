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

## 2. Headless execution

Pass `--headless` to disable interactive GUIs for unattended local, batch, or HPC execution:

```bash
python -m aceneurotools.pipelines.miniscope \
  --line-num 96 \
  --project-path /path/to/project \
  --data-path /path/to/raw_data \
  --headless
```

ACE-NeuroTools does not include a Slurm submission file. For Slurm or another scheduler, place the headless command in a site-specific job script and choose resources appropriate for your data and cluster.

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
