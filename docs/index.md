# ACE-NeuroTools: Analysis of Calcium Imaging and Ephys

**ACE-NeuroTools** (Analysis of Calcium Imaging and Ephys) is an integrated, object-oriented Python library designed for the systems neuroscience community. It provides high-level pipelines for processing simultaneous 1-photon calcium imaging (Miniscope) and multi-channel electrophysiology (EEG/LFP) data.

For a **class-diagram overview** of core managers and processors, see the Mermaid diagram in the [README on GitHub](https://github.com/emelon8/experiment_analysis/blob/main/README.md#system-architecture).

---

<div class="grid cards" markdown>

-   __Unified Search__
    
    Full integrated search functionality across all pipelines, guides, and API references.

-   __Multimodal Alignment__
    
    Seamlessly align miniscope movies with ephys timestamps using TTL pulses for cross-modal analysis.

-   __CNMF-E Integrated__
    
    Native wrappers around [CaImAn](https://github.com/flatironinstitute/CaImAn) for optimized source extraction in micro-endoscopic data.

-   __HPC Ready__
    
    Headless mode for batch processing, with a [Slurm submission example](examples.md#2-supercomputer-slurm-workflow).

</div>

---

## Experiment GUI

From a checkout with the scientific environment installed:

```bash
./launch-gui --project /path/to/project
```

Open the folder containing `experiments.csv` and `analysis_parameters.csv`, edit
settings, review a run, and inspect results. **Results → Output inventory** lists
events, component IDs, signals, and diagnostics with export status. **Neurons →
Finish review** can save curated estimates and rerun calcium-event detection;
earlier run outputs remain unchanged. See the [experiment GUI guide](guides/experiment_gui.md).

## Step-by-step tutorials

These notebooks explain **`project_path`** (folder with **`experiments.csv`** and **`analysis_parameters.csv`**) vs **`data_path`** (raw recordings), then walk each pipeline stage by stage:

- [Miniscope](notebooks/miniscope_pipeline_tutorial.ipynb)
- [Ephys](notebooks/ephys_pipeline_tutorial.ipynb)
- [Multimodal alignment](notebooks/multimodal_alignment_tutorial.ipynb)
---

## Installation

Install ACE-NeuroTools and its core dependencies in your environment:

```bash
# Clone and install in editable mode
git clone https://github.com/emelon8/experiment_analysis.git
cd experiment_analysis
# Install scientific dependencies first using linux_environment.yml (see Getting Started)
pip install -e "."
```

---

## Tests and sample data

- **`tests/data/sample_recording/`** — Committed fixtures for factory tests and the optional slow Miniscope CNMF-E end-to-end test.
- To regenerate fixtures from a local `sample data/` tree, use `scripts/create_test_data.py` (see the [README](https://github.com/emelon8/experiment_analysis/blob/main/README.md#development-and-testing) Development and testing section).

---

## API Overview

ACE-NeuroTools provides a clear, modular API optimized for both interactive use and automated scripts.

```python
from aceneurotools.pipelines.multimodal import MultimodalPipeline

# Initialize and run a synchronized analysis
api = MultimodalPipeline()
api.run(
    line_num=97,
    project_path="/path/to/project",
    data_path="/path/to/raw_data",
    headless=True  # Run without GUIs for batch processing
)
```

**Parameters:** use named arguments to `run(...)` for clarity. Direct Python calls
use method defaults and explicit arguments; loading a CSV row into run arguments
requires `load_analysis_params`. Module CLIs merge CLI defaults, supported CSV
settings, and CLI overrides. Miniscope CNMF-E extraction defaults to **off** in
`MiniscopePipeline.run()` and **on** in its module CLI and GUI CNMF-E mode. See
[Getting started](getting_started.md#3a-passing-parameters-into-the-pipelines) for
precedence and examples.

Headless mode respects the configured `inline` filtering behavior. A filtered final
temporal projection can coexist with phases/spectra computed before filtering.
See the [Miniscope guide](guides/miniscope.md) for signal semantics.

---

## Core Features

*   **Miniscope**: Preprocessing, Motion Correction, CNMF-E, and Post-processing GUI.
*   **Ephys**: Neuralynx/ONIX import, artifact removal, bandpass filtering, and spectral analysis.
*   **Alignment**: TTL-based synchronization of dual-stream datasets.
*   **Data Management**: CSV-driven experiment cohorts and automated Box cloud storage downloads.
*   **Development Tools**: Type annotations, Google-style docstrings, and automated testing.

---

<p align="center">
  [Getting Started](getting_started.md){ .md-button .md-button--primary }
  [Tutorials: Miniscope](notebooks/miniscope_pipeline_tutorial.ipynb){ .md-button }
  [API Reference](api/index.md){ .md-button }
</p>
