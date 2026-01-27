# Miniscope Module Documentation

This directory contains the logic for the calcium imaging pipeline.

## Core Components

### `MiniscopeAPI` (`miniscope_api.py`)
This is the main entry point for the workflow. It orchestrates the entire pipeline from data loading to post-processing.
*   **Usage:**
    ```python
    api = MiniscopeAPI()
    api.run(line_num=..., filenames=..., ...)
    ```
*   **Key Responsibilities:**
    *   Initializes the `MiniscopeDataManager`.
    *   Runs the preprocessing via `MiniscopePreprocessor`.
    *   Runs the processing via `MiniscopeProcessor`.
    *   Runs the post-processing via `MiniscopePostprocessor`.

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

### `MiniscopePreprocessor` (`miniscope_preprocessor.py`)
Handles the preparation of the raw movie data before the heavy computational steps.
*   **Key Methods:**
    *   `preprocess_calcium_movie`: Orchestrates cropping, detrending, and dF/F calculation.
    *   `crop_movie`: Interactive or coordinate-based cropping of the movie.
    *   `detrend_movie`: Removes trends (e.g., photobleaching) from the movie.
    *   `compute_df_over_f`: Calculates the delta F over F signal.

### `MiniscopeProcessor` (`miniscope_processor.py`)
This class executes the heavy computational steps using the CaImAn library.
*   **Key Methods:**
    *   `process_calcium_movie`: Orchestrates motion correction, parameter preparation, and CNMF-E execution.
    *   `motion_correction_manager`: Handles rigid or non-rigid motion correction and saves memory-mapped files.
    *   `CNMFE_parameter_handler`: Interactive step for tuning CNMF-E parameters (Summary Images).
    *   `_save_processed_data`: Saves the CNMF-E estimates and parameters to disk.

### `MiniscopePostprocessor` (`miniscope_postprocessor.py`)
Handles analysis and visualization after the sources have been extracted.
*   **Key Methods:**
    *   `postprocess_calcium_movie`: Orchestrates component evaluation, event detection, and spectral analysis.
    *   `evaluate_components`: Filters components based on quality metrics.
    *   `find_calcium_events_with_derivatives`: Detects calcium events using derivatives.
    *   `compute_miniscope_spectrogram`: Computes and plots the spectrogram of the calcium data.

## Utilities & Helper Modules

*   **`multiple_session_utils.py`**: Contains logic for registering and tracking the same neurons across multiple imaging sessions.
*   **`head_direction_utils.py`**: Utilities for processing and visualizing head orientation data (e.g., converting quaternions to Euler angles).
*   **`movie_io.py`**: Handles saving and loading of movie files and memory maps.
*   **`projections.py`**: Defines the `Projections` data class used to store summary images (Mean, Max, STD, etc.).
*   **`gui_utils.py`**: Contains the Tkinter and Matplotlib GUI logic for interactive cropping and component selection.

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