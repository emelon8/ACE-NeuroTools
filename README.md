# Experiment-Analysis

**A comprehensive, open-source data analysis pipeline for systems neuroscience.**

This software facilitates the processing, analysis, and visualization of simultaneous calcium imaging (Miniscope) and electrophysiology (EEG/LFP) data. It provides a modular and extensible framework for handling complex multimodal datasets, as described in **[Paper Title/Citation Placeholder]**.

## Key Features

*   **Miniscope Processing:** End-to-end pipeline for 1-photon calcium imaging data, incorporating:
    *   Preprocessing: Cropping, detrending, and $\Delta F/F$ normalization.
    *   Motion Correction: Rigid and non-rigid registration.
    *   Source Extraction: Implementation of Constrained Nonnegative Matrix Factorization for micro-Endoscopic data (CNMF-E).
    *   Event Detection: Robust inference of calcium events from temporal traces.
*   **Electrophysiology Analysis:** Tools for importing and cleaning Neuralynx data, including artifact removal, filtering, phase computation, and spectral analysis.
*   **Multimodal Integration:** Seamless alignment of independent Miniscope and Ephys timestamps, enabling cross-modal analysis such as phase-locking of calcium events to channel-specific oscillations.
*   **Data Management:** Integrated utilities for managing large experiment cohorts and automated cloud storage (Box) interaction.

## System Architecture

The project is built on a robust object-oriented framework designed for scalability and reproducibility:

### Core Data Classes
*   **`ExperimentDataManager`**: Base class for managing experiment metadata and analysis parameters.
*   **`MiniscopeDataManager`**: Specialized handler for calcium imaging data, managing video streams, timestamps, and CNMF-E results.
*   **`EphysDataManager`**: Specialized handler for electrophysiology data, managing raw Block imports and channel signal processing.

### Processing Classes
*   **`MiniscopeProcessor`**: Orchestrates the calcium imaging workflow, wrapping `CaImAn` functionality with optimized defaults and parallel processing management.
*   **`BlockProcessor`**: Handles signal conditioning and artifact removal for electrophysiological data.

## Getting Started

### Prerequisites
*   **Python 3.10+**
*   **Miniforge3/Mamba** (Recommended for managing conflicting dependencies like `liblapack` and `CaImAn`)

### Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/emelon8/experiment_analysis.git
    cd experiment_analysis
    ```

2.  **Create Environment:**

    **macOS:**
    ```bash
    mamba env create -f environment.yml
    ```

    **Windows:**
    ```bash
    mamba env create -f windows.yml
    ```

    **Linux:**
    ```bash
    mamba env create -f linux_environment.yml
    ```

    > **Note:** If you encounter dependency conflicts (e.g., with `liblapack`), we strongly recommend using `mamba` instead of `conda` for the environment creation step.

    Activate the environment:
    ```bash
    conda activate caiman
    ```

3.  **Install the Package:**
    ```bash
    pip install -e .
    ```

### Data Setup

Experimental metadata is managed via `data/experiments.csv`. File paths in this CSV can be relative or absolute.
For automated downloading from Box, configure `src2/shared/box_credentials.py` (see `src2/shared/BLANK_box_credentials.py`).

## Usage

The project uses modular API scripts as the primary entry points. These can be run from the command line with YAML configuration files for reproducibility.

### 1. Miniscope Analysis
**Script:** `src2/miniscope/miniscope_pipeline.py`

```bash
# Run with configuration file (Recommended)
python src2/miniscope/miniscope_pipeline.py --config src2/miniscope/miniscope_config.yaml

# Run in headless mode (e.g., for HPC/Slurm jobs)
python src2/miniscope/miniscope_pipeline.py --config src2/miniscope/miniscope_config.yaml --headless
```

### 2. Electrophysiology Analysis
**Script:** `src2/ephys/ephys_pipeline.py`

```bash
python src2/ephys/ephys_pipeline.py --config experiment_template.yaml
```

### 3. Multimodal Analysis
**Script:** `src2/multimodal/multimodal_pipeline.py`

```bash
python src2/multimodal/multimodal_pipeline.py --config experiment_template.yaml
```

For detailed documentation on output files (e.g., `estimates.hdf5`) and analysis interpretation, please refer to the module-specific utility guides in `src2/miniscope/README.md` and `src2/ephys/README.md`.

## License

This project is licensed under the GNU General Public License v2.0 (or later) - see the LICENSE file for details.
