# ACE-NeuroTools: Analysis of Calcium Imaging and Electrophysiology

ACE-NeuroTools helps a lab analyze two kinds of brain recordings. A **miniscope** is a small camera that records activity in cells; **electrophysiology** records electrical signals from named channels. When both were collected in one session, the tool can align their time stamps so the results can be compared.

Start with your raw recording files and an `experiments.csv` spreadsheet that says where each recording lives. A miniscope run can save processed movies and, when cell extraction is enabled, an `estimates.hdf5` result. An ephys run can filter signals or display plots. [Getting started](getting_started.md) walks through the first run and how to check its output.

See the [plain-language terms](glossary.md) page when a recording or processing term is unfamiliar.

The [system architecture diagram in the GitHub README](https://github.com/emelon8/experiment_analysis/blob/main/README.md#system-architecture) is for readers extending the Python code.

---

<div class="grid cards" markdown>

-   __Miniscope processing__

    Clean miniscope video, correct movement when requested, and use CNMF-E to identify cell signals. CNMF-E is the cell-extraction method provided by [CaImAn](https://github.com/flatironinstitute/CaImAn).

-   __Electrophysiology processing__

    Read Neuralynx and RHS2116/ONIX electrical recordings. You can remove artifacts, filter signals, or plot their frequency content.

-   __Multimodal alignment__

    Compare recordings on one time line using recorded sync pulses (TTL pulses) or the shared ONIX hardware clock.

-   __Batch-friendly execution__

    Use `--headless` to run without pop-up windows on a shared computer or in a batch job.

</div>

---

## Installation

Create the supported CaImAn environment, then install ACE-NeuroTools in editable mode:

```bash
git clone https://github.com/emelon8/experiment_analysis.git
cd experiment_analysis
micromamba create -n aceneurotools -f conda-lock.yml  # Linux or Windows
micromamba activate aceneurotools
pip install --no-deps -e .
```

See [Getting started](getting_started.md) for prerequisites, data layout, configuration, and your first pipeline run.

---

## Step-by-step tutorials

The tutorials distinguish `project_path`, which contains `experiments.csv` and optional parameter files, from `data_path`, which contains raw recordings. Each notebook then walks through one pipeline:

- [Miniscope processing](notebooks/miniscope_pipeline_tutorial.ipynb)
- [Ephys processing](notebooks/ephys_pipeline_tutorial.ipynb)
- [Multimodal alignment](notebooks/multimodal_alignment_tutorial.ipynb)

---

## For developers: Python API

The miniscope, ephys, and multimodal pipelines expose a `run(...)` method for programmatic use:

```python
from aceneurotools.pipelines.multimodal import MultimodalPipeline

pipeline = MultimodalPipeline()
pipeline.run(
    line_num=97,
    project_path="/path/to/project",
    data_path="/path/to/raw_data",
    headless=True,
)
```

Pass options as keyword arguments for clarity. For direct Python use, supply them yourself or explicitly load values with `load_analysis_params(...)`.

The pipeline CLI entry points combine their defaults, optional values from `analysis_parameters.csv`, and common CLI arguments.

See [Pass pipeline parameters](getting_started.md#5-pass-pipeline-parameters) for precedence and examples.

---

## Supporting features

- **Data management:** CSV-driven experiment metadata with optional Box downloads when folder IDs, the Box extra, and credentials are configured.
- **Documentation search:** search the published guides, tutorials, and generated API reference from any documentation page.
- **Project infrastructure:** a typed-package marker, type annotations across much of the public API, pytest coverage, and automated CI checks.

---

<div align="center" markdown>
  [Getting started](getting_started.md){ .md-button .md-button--primary }
  [Miniscope tutorial](notebooks/miniscope_pipeline_tutorial.ipynb){ .md-button }
  [API reference](api/index.md){ .md-button }
</div>
