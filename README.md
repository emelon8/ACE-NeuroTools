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

```mermaid
classDiagram
    class ExperimentDataManager {
        +int line_num
        +dict metadata
        +dict analysis_params
        +import_metadata()
        +import_analysis_parameters()
    }

    class MiniscopeDataManager {
        +list time_stamps
        +list frame_numbers
        +movie movie
        +dict miniscope_events
        +MiniscopeProcessor processor
        +load_attributes()
    }

    class EphysDataManager {
        +dict channels
        +Block ephys_block
        +import_ephys_block()
        +process_ephys_block_to_channels()
        +filter_ephys()
    }

    class Channel {
        +str name
        +np.array signal
        +float sampling_rate
        +np.array time_vector
        +dict events
        +np.array signal_filtered
        +np.array phases
    }

    class MiniscopeProcessor {
        +MiniscopeDataManager data_manager
        +process_calcium_movie()
        +motion_correction_manager()
        +CNMFE_parameter_handler()
    }

    class BlockProcessor {
        +Block ephys_block
        +process_raw_ephys()
        +remove_artifacts()
    }

    ExperimentDataManager <|-- MiniscopeDataManager : Inherits
    ExperimentDataManager <|-- EphysDataManager : Inherits
    EphysDataManager --> BlockProcessor : Uses
    BlockProcessor ..> Channel : Creates
    EphysDataManager *-- Channel : Contains
    MiniscopeProcessor --> MiniscopeDataManager : Processes
```

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

### Project Setup

Each research project has its own directory containing experiment configuration files. See this [example project](https://github.com/reedpen/example-project) for a template.

1. **Create a project directory** with:
   - `experiments.csv` — Experiment metadata (paths, IDs, etc.)
   - `analysis_parameters.csv` — Pipeline parameters per experiment
   - `run_analysis.py` — Optional batch processing script

2. **Configure your `.env` file** (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to point to your project:
   ```
   PROJECT_REPO=/path/to/your/project
   BASE_FILE_PATH=/path/to/raw/data  # Optional, defaults to PROJECT_REPO/data/downloaded_data
   ```

3. **Cloud storage** (optional): For automated downloading from Box, configure `src2/shared/box_credentials.py` (see `src2/shared/BLANK_box_credentials.py`).

## Usage

The project uses modular pipeline scripts as the primary entry points. Each pipeline loads parameters from your project's `analysis_parameters.csv` based on the experiment's line number.

### 1. Miniscope Analysis
**Script:** `src2/miniscope/miniscope_pipeline.py`

```bash
# Run analysis for experiment line 96
python -m src2.miniscope.miniscope_pipeline --line-num 96

# Run in headless mode (e.g., for HPC/Slurm jobs)
python -m src2.miniscope.miniscope_pipeline --line-num 96 --headless
```

### 2. Electrophysiology Analysis
**Script:** `src2/ephys/ephys_pipeline.py`

```bash
python -m src2.ephys.ephys_pipeline --line-num 96
```

### 3. Multimodal Analysis
**Script:** `src2/multimodal/multimodal_pipeline.py`

```bash
python -m src2.multimodal.multimodal_pipeline --line-num 97
```

For detailed documentation, see the module-specific READMEs in `src2/miniscope/README.md`, `src2/ephys/README.md`, and `src2/multimodal/README.md`.

## License

This project is licensed under the GNU General Public License v2.0 (or later) - see the LICENSE file for details.
