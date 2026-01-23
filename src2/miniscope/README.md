# Miniscope Module Documentation

This directory contains the logic for the calcium imaging pipeline.

## Core Components

### `MiniscopeDataManager` (`miniscope_data_manager.py`)
This class acts as the central state container.
*   **Initialization:** Requires `line_num` (from `experiments.csv`) and a list of `filenames` (e.g., `['0.avi']`).
*   **Key Attributes:**
    *   `self.movie`: A `caiman.base.movies.movie` object. This is a subclass of a numpy array with shape `(frames, height, width)`.
    *   `self.time_stamps`: A numpy array of timestamps (seconds) derived from the Miniscope CSV logs.
    *   `self.CNMFE_obj`: The `caiman.source_extraction.cnmf.CNMF` object. This is only populated after the processing step.
        *   `CNMFE_obj.estimates.A`: Sparse matrix of spatial footprints (neurons).
        *   `CNMFE_obj.estimates.C`: Temporal traces (calcium activity).
        *   `CNMFE_obj.estimates.S`: Deconvolved spiking activity.
    *   `self.opts_caiman`: A `CNMFParams` object containing configuration for the algorithm.

### `MiniscopeProcessor` (`miniscope_processor.py`)
This class executes the heavy computational steps.
*   **Method: `motion_correction_manager`**:
    *   Uses `caiman.motion_correction.MotionCorrect`.
    *   Saves a memory-mapped file (`.mmap`) to disk to handle large video files efficiently.
*   **Method: `CNMFE_parameter_handler`**:
    *   Interactive Step: Calculates Summary Images (Correlation and Peak-to-Noise Ratio).
    *   **Developer Note:** This method forces an interactive backend (`Qt5Agg`) to display plots.

## Data Types & Files

*   **Input:** `.avi` files (raw video) and accompanying `.csv` timestamp files from the Miniscope software.
*   **Intermediate:** `.mmap` files (created by CaImAn for memory efficiency).
*   **Output:** `estimates.hdf5`
    *   This is a serialized `CNMF` object.
    *   **Loading in Python:**
        ```python
        from caiman.source_extraction.cnmf.cnmf import load_CNMF
        cnmfe = load_CNMF('path/to/estimates.hdf5')
        ```
